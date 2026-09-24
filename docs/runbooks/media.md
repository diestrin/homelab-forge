# Media platform (Phase 1 MVP)

Movies and TV on the forge: **Jellyfin** for playback, **Jellyseerr** for
requests, **Prowlarr / Radarr / Sonarr / qBittorrent** for acquisition.
Decisions: [ADR-014](../decisions/ADR-014-media-platform.md). Epic: GitHub #60.

Steady-state deploy is merge to `main` → Argo CD Application `media` (ADR-008).
Do not `kubectl apply` these manifests.

## URLs and access

| Service | How to reach it |
| --- | --- |
| Jellyfin (public) | `https://media.localpower.diegobarahona.com` |
| Jellyseerr | `kubectl -n media port-forward svc/jellyseerr 5055:5055` → `http://127.0.0.1:5055` |
| Radarr | `kubectl -n media port-forward svc/radarr 7878:7878` |
| Sonarr | `kubectl -n media port-forward svc/sonarr 8989:8989` |
| Prowlarr | `kubectl -n media port-forward svc/prowlarr 9696:9696` |
| qBittorrent | `kubectl -n media port-forward svc/qbittorrent 8080:8080` |

Arr UIs are ClusterIP on purpose. Do not add Ingress for them without a new
high-risk review.

DNS: `media.localpower.diegobarahona.com` uses the same wildcard (or explicit
record) as `grafana.localpower.diegobarahona.com` and PR previews. If the cert
stays pending, add the record before blaming Traefik.

## Storage

Host path (data disk, same filesystem for hardlinks):

```text
/media/diestrin/data/forge/media/
  config/{jellyfin,radarr,sonarr,prowlarr,qbittorrent,jellyseerr}/
  data/
    media/{movies,tv}/
    torrents/{incomplete,movies,tv}/
```

Inside every media pod that needs library + downloads, that tree is `/data`.
Radarr root folder: `/data/media/movies`. Sonarr: `/data/media/tv`.
qBittorrent default save path: `/data/torrents` with categories `movies` and
`tv`. No remote path mappings — every arr sees the same paths.

MVP disk: hundreds of GB free on the data volume is enough. Expansion is a
later epic item, not a blocker.

## Vault

Path `secret/forge/media` (KV v2; ESO key `forge/media`):

| Field | Use |
| --- | --- |
| `qbittorrent_webui_password` | qBittorrent WebUI (`admin` / this password) |
| `radarr_api_key` | `RADARR__AUTH__APIKEY` (≥ 20 chars) |
| `sonarr_api_key` | `SONARR__AUTH__APIKEY` |
| `prowlarr_api_key` | `PROWLARR__AUTH__APIKEY` |
| `jellyfin_api_key` | Created in Jellyfin after the wizard; store here for Jellyseerr |

Create or rotate (never commit values):

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN="$(cat /media/diestrin/data/secrets/vault/root.token)"
vault kv put secret/forge/media \
  qbittorrent_webui_password='…' \
  radarr_api_key='…' \
  sonarr_api_key='…' \
  prowlarr_api_key='…'
```

The ExternalSecret `media-secrets` does not read `jellyfin_api_key`, so the
wizard can finish before that field exists.

## First-run (operator)

1. Confirm Application `media` is `Synced` / `Healthy` and all six pods are
   `Running`: `kubectl -n media get pods,ingress,certificate`.
2. Open Jellyfin, complete the wizard (local admin, libraries pointing at
   `/data/media/movies` and `/data/media/tv`). Under **Dashboard → Playback**,
   set hardware acceleration to **Intel QuickSync (QSV)**. Under
   **Dashboard → Networking**, confirm the public HTTPS URL is
   `https://media.localpower.diegobarahona.com`.
3. **Dashboard → API Keys** — create a key, then
   `vault kv patch secret/forge/media jellyfin_api_key='…'`.
4. qBittorrent (port-forward): log in `admin` + Vault password. Default save
   path `/data/torrents`. Categories: `movies` → `/data/torrents/movies`,
   `tv` → `/data/torrents/tv`. Global share limits are operator taste; set
   something finite. Do not port-forward the torrent port on the router.
5. Prowlarr: add indexers, then **Settings → Apps** → add Radarr and Sonarr
   (`http://radarr:7878`, `http://sonarr:8989`) using the Vault API keys.
   Sync.
6. Radarr / Sonarr: root folders as above. Download client qBittorrent at
   `http://qbittorrent:8080` with the Vault password, category `movies` /
   `tv`. Enable completed-download handling so imports hardlink (not copy).
7. Jellyseerr: Jellyfin URL `http://jellyfin:8096` (internal) and the API
   key from Vault. Add Radarr/Sonarr with their internal URLs and API keys.
   Sign-in is Jellyfin users.

## Streaming clients

- **Phone / PC (away from home):** Jellyfin Android/iOS/web against the
  public HTTPS URL. Create per-person Jellyfin users (no shared admin).
- **Chromecast (Cast button):** the Chromecast must reach that HTTPS URL
  (same WAN path as the phone). LAN and remote both go through Traefik.
- **Chromecast with Google TV / Android TV / most smart TVs:** install the
  native Jellyfin app instead of Cast. Point it at the public URL (or the
  LAN Service IP only if you accept a split-horizon later).
- **QSV check:** play a title that needs a transcode (for example a high-bitrate
  file to a phone). Jellyfin Dashboard → **Playback** / **Active devices**
  should show **QSV**, not `VideoToolbox`/`vaapi` software fallback
  (`libx264`). `ls -l /dev/dri` inside the pod must show `card0` and
  `renderD128`. Host groups on this Ubuntu 24.04 node: `video` = 44,
  `render` = 993 (`getent group video render` after a reinstall).

## host-watch and firewall

No new host bind. Traefik still owns 80/443; qBittorrent stays on the pod
network with outbound-only peering. Do **not** `ufw allow` a torrent port.

host-watch is a **user** systemd timer (`NoNewPrivileges=true`). Unprivileged
`ss -tpn` cannot name other users' sockets, so `row["process"]` is empty for
k3s-SNAT'd torrent peers and `[peers].ignore_process_substrings` does **not**
match. Leave that list empty here; do not run host-watch as root to make it
work. Findings are de-duplicated in state, so each new peer IP warns once.
Expect that noise after qBittorrent starts; it is not a new host listener.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Arr pods `CreateContainerConfigError` | Vault `secret/forge/media` missing fields; ESO `media-secrets` |
| Jellyfin cert `False` | DNS for `media.localpower.diegobarahona.com`; HTTP-01 on 80 |
| Duplicate disk use after import | Paths differ across pods; must all be `/data` on one hostPath |
| Software transcode | `/dev/dri` mount, supplemental groups 44/993, QSV enabled in Dashboard |
| Indexer works in Prowlarr but not Radarr | Prowlarr app sync; NetworkPolicy egress 80/443 |
| Stuck downloads | qBittorrent categories vs Radarr/Sonarr category names; completed-download handling |
| Chromecast fails | Client and Chromecast using the public HTTPS URL; cert valid |

## Related

- [gitops.md](./gitops.md) — merge → Argo.
- [vault.md](./vault.md) — unseal, ESO.
- [operations.md](./operations.md) — cold start.
- [network-exposure.md](./network-exposure.md) — WAN 80/443.
