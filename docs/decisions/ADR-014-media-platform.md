# ADR-014: Self-hosted media platform (Jellyfin + arr stack)

- Status: Accepted
- Date: 2026-09-16
- Related: ADR-003 (k3s / Traefik / Let's Encrypt), ADR-007 (Vault), ADR-008
  (GitOps), GitHub #60 / #61 / #62

## Context

The forge should host a family media library (movies, TV, later photos, music,
and books) with no paid third-party services. Constraints from the operator:

- Self-host everything that can be self-hosted; no subscriptions.
- MVP is movies and TV: a catalog, automated acquisition from p2p sources,
  and playback on Chromecast, smart TVs, phones, and PCs — on LAN and away
  from home.
- Customizing the consumption UI is interesting later, not an MVP blocker.
- p2p egress from the home IP is acceptable; no inbound peer port / UFW hole.
- Existing data disk is enough for the MVP; dedicated expansion comes later.

## Decision

1. **Playback server: Jellyfin.** Fully free (including hardware transcoding and
   remote streaming), local auth, no cloud account. Plex is rejected because
   remote streaming of own media is paywalled. Emby is rejected because
   hardware transcoding is paywalled. Jellyfin's API also keeps a custom
   frontend (Pelagica, JellyNext, Aurora, or a `jellyfin-web` fork) as a later
   phase without replacing the server.
2. **Acquisition: Prowlarr + Radarr + Sonarr + qBittorrent + Jellyseerr.**
   Standard arr-stack. Jellyseerr is the family request catalog and uses
   Jellyfin accounts. qBittorrent egress is direct from the home IP (no VPN
   sidecar). No inbound BitTorrent port on the host firewall.
3. **GitOps on k3s.** Manifests live under `k8s/apps/media/`. Merge to `main`
   → Argo CD Application `media` syncs (ADR-008). No `kubectl apply` of the
   app. Public Ingress is Jellyfin only
   (`media.localpower.diegobarahona.com`). Arr UIs stay ClusterIP.
4. **Storage.** One hostPath tree on the data disk so downloads and the library
   share a filesystem (atomic hardlink imports). Layout is TRaSH-style
   `/data/media/{movies,tv}` + `/data/torrents/{movies,tv}`.
5. **Transcode.** Pass `/dev/dri` into Jellyfin and use Intel Quick Sync on the
   i7-10710U (H.264/HEVC). No AV1 decode on this iGPU.
6. **Secrets.** qBittorrent WebUI password and Servarr API keys live in Vault
   `secret/forge/media` and are injected with ExternalSecrets (ADR-007).
   Jellyfin's own API key is created at first-run (wizard) and copied into
   Vault afterwards for Jellyseerr.

## Consequences

- Remote streaming uses the existing Traefik + Let's Encrypt path (ADR-003).
  Chromecast casting needs that HTTPS URL reachable by the cast device; Google
  TV / Android TV devices should prefer the native Jellyfin app over Cast.
- p2p from the home IP is visible to the ISP. VPN egress would require a paid
  provider (free tiers disallow p2p) and was declined.
- host-watch should see no new host listeners (80/443 stay on Traefik). SNAT'd
  torrent peers may surface as k3s remote-peer warnings; the media runbook
  covers live allowlist tuning.
- Later phases (custom frontend, Immich, Navidrome, Kavita, Audiobookshelf,
  storage expansion) are out of this ADR's deploy scope and stay on epic #60.

## Alternatives considered

- **Plex / Emby.** Rejected on cost and cloud-account requirements.
- **gluetun VPN sidecar.** Rejected: conflicts with the no-paid-services rule.
- **Usenet.** Deferred; needs a paid indexer. p2p is the MVP path.
- **hostNetwork qBittorrent + inbound peer port.** Faster swarming, but opens
  a host listener and an UFW hole. Declined for MVP.
