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
record) as `grafana.localpower.diegobarahona.com` and PR previews. A Traefik
**DEFAULT CERT** (browser “invalid SSL”) means the Let’s Encrypt HTTP-01
challenge has not finished — see Troubleshooting.

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

## Setup guide (first run)

Do these in order. Arr UIs stay on port-forwards (separate terminals). Open
Vault once and leave it running:

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN="$(cat /media/diestrin/data/secrets/vault/root.token)"
```

Read a field with `vault kv get -field=<name> secret/forge/media` (never paste
values into git).

### 0. Health

```bash
kubectl -n forge-system get application media   # Synced / Healthy
kubectl -n media get pods,certificate           # 6/6 Running; jellyfin-tls Ready
curl -fsSI https://media.localpower.diegobarahona.com | head -5
```

If the certificate subject is `CN = TRAEFIK DEFAULT CERT`, wait or see
Troubleshooting. Reload the browser after it becomes Let’s Encrypt.

### 1. Jellyfin wizard (you are on Libraries)

Still in `https://media.localpower.diegobarahona.com/web/#/wizard/library`:

1. **Add media library → Movies.** Folder **`/data/media/movies`**. Leave
   English (or your metadata language). Next.
2. **Add media library → Shows.** Folder **`/data/media/tv`**. Do not add
   music/photos/books in this MVP.
3. Finish metadata language if asked.
4. **Remote Access:** keep remote access enabled. Turn **off** automatic port
   mapping (UPnP). The public URL is already Traefik + Let’s Encrypt.
5. Finish the wizard and sign in as the admin you created.

Then in the dashboard (gear):

6. **Playback → Transcoding** (or **Playback**): hardware acceleration
   **Intel QuickSync (QSV)**. Enable hardware encoding if shown.
7. **Networking:** published server URL
   `https://media.localpower.diegobarahona.com` (also set via
   `JELLYFIN_PublishedServerUrl`).
8. **API Keys:** create one named `jellyseerr`. Copy it, then:

   ```bash
   vault kv patch secret/forge/media jellyfin_api_key='paste-here'
   ```

9. **Users:** one Jellyfin user per person. Do not share the admin account
   with family clients.

### 2. qBittorrent

```bash
kubectl -n media port-forward svc/qbittorrent 8080:8080
```

Open `http://127.0.0.1:8080`. User `admin`. Password:

```bash
vault kv get -field=qbittorrent_webui_password secret/forge/media
```

**Tools → Options → Downloads:**

- Default save path: `/data/torrents`
- Keep incomplete torrents in: `/data/torrents/incomplete`
- **Categories:** `movies` → save path `/data/torrents/movies`; `tv` →
  `/data/torrents/tv`

**Connection:** do not change the listen port to a host/UFW mapping. Outbound
peering is enough.

**BitTorrent:** set a finite share ratio (for example pause at ratio 2) so
the disk does not seed forever.

### 3. Prowlarr

```bash
kubectl -n media port-forward svc/prowlarr 9696:9696
```

`http://127.0.0.1:9696`. First-run auth: pick forms auth and an admin
password. API key is already injected (`prowlarr_api_key` in Vault) —
**Settings → General** should show it.

1. **Indexers:** add your torrent indexers (whatever you already have access
   to). Test each one.
2. **Settings → Apps → Add:**
   - Radarr: `http://radarr:7878`, API key
     `vault kv get -field=radarr_api_key secret/forge/media`
   - Sonarr: `http://sonarr:8989`, API key
     `vault kv get -field=sonarr_api_key secret/forge/media`
3. Sync / save so the indexers appear inside Radarr and Sonarr.

### 4. Radarr (movies)

```bash
kubectl -n media port-forward svc/radarr 7878:7878
```

`http://127.0.0.1:7878`. Authentication: set an admin login on first visit if
prompted. Confirm **Settings → General** API key matches Vault
`radarr_api_key`.

1. **Settings → Media Management:** add root folder `/data/media/movies`.
   Enable **Use Hardlinks instead of Copy**.
2. **Settings → Download Clients → qBittorrent:** host `qbittorrent`, port
   `8080`, user `admin`, Vault qBittorrent password. Category `movies`.
3. **Settings → Quality:** start with a 1080p profile; you can tighten later.
4. Optional: add one movie by name and hit Search to prove the indexer +
   download client path. It should land in `/data/media/movies` without a
   second copy under `/data/torrents` (hardlink).

### 5. Sonarr (TV)

```bash
kubectl -n media port-forward svc/sonarr 8989:8989
```

Same pattern as Radarr: root folder `/data/media/tv`, hardlinks on, download
client qBittorrent with category `tv`. API key = Vault `sonarr_api_key`.

### 6. Jellyseerr (family requests)

```bash
kubectl -n media port-forward svc/jellyseerr 5055:5055
```

`http://127.0.0.1:5055`.

1. Jellyfin URL **`http://jellyfin:8096`** (cluster DNS, not the public
   hostname). API key = Vault `jellyfin_api_key`.
2. Sign in with your Jellyfin admin (or a dedicated request-admin user).
3. Add **Radarr:** `http://radarr:7878` + `radarr_api_key`. Default root
   folder `/data/media/movies`, 1080p quality profile.
4. Add **Sonarr:** `http://sonarr:8989` + `sonarr_api_key`. Root
   `/data/media/tv`.
5. Request one title and watch it flow: Jellyseerr → Radarr/Sonarr →
   qBittorrent → library folder → Jellyfin.

Family members request from Jellyseerr after they have Jellyfin logins.
Leave Jellyseerr off public Ingress for now.

### 7. Playback smoke test

On a phone or PC, add the server
`https://media.localpower.diegobarahona.com`. Play something that needs a
transcode; Dashboard should show **QSV**. Chromecast: Cast from the Android
app, or install Jellyfin on Google TV / Android TV and use that app instead
of Cast.

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
| Traefik DEFAULT CERT / invalid SSL | Let’s Encrypt still pending. `kubectl -n media get challenge,certificate`. HTTP-01 **502** means Traefik cannot reach the ACME solver (NetworkPolicy `allow-acme-http01-from-ingress`) |
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
