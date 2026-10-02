# ADR-016: Self-hosted Obico for 3D printer monitoring

- Status: Accepted
- Date: 2026-10-02 (proposed 2026-10-01)
- Related: ADR-003 (k3s / Traefik / Let's Encrypt), ADR-005 (host-watch),
  ADR-007 (Vault), ADR-008 (GitOps), ADR-014 / ADR-015 (app patterns),
  GitHub #72 (epic) / #73 / #74 / #75 / #77

## Context

The operator wants to watch their 3D printers from home and from anywhere else,
with AI failure detection, using a self-hosted [Obico](https://www.obico.io)
server rather than Obico Cloud.

How Obico works, from upstream `obico-server` (`release` branch, commit
`49c0bc70`, July 2026):

| Component | What it is |
| --- | --- |
| `web` | Django on Daphne (ASGI) on `:3334`. UI, REST API, and the websockets the printers and browsers use |
| `tasks` | Celery worker plus beat. Notifications, timelapse encoding (ffmpeg) |
| `ml-api` | Gunicorn on `:3333`. Failure detection model (Darknet/ONNX), CPU or NVIDIA |
| `redis` | Celery broker, Channels layer, cache. No persistence needed |
| Database | `DATABASE_URL`. SQLite by default; PostgreSQL supported |
| Media | Snapshots, timelapses, G-code on the local filesystem (or GCS). No S3 backend |

Printers do not accept connections from the server. An agent on each printer's
host (`moonraker-obico` for Klipper, `octoprint-obico` for OctoPrint) opens an
**outbound** websocket to the server URL and posts webcam snapshots over HTTPS.
A printer anywhere on the internet only needs to reach that URL.

Upstream now publishes, from the same repo:

- a Helm chart as a signed OCI artifact, `oci://ghcr.io/thespaghettidetective/charts/obico`
  (latest `2026.7.11`), whose images are pinned to the build commit
- images `ghcr.io/thespaghettidetective/obico-web` and `obico-ml-api-cpu` (tags
  `2026.7.11`, `sha-49c0bc70`)

Facts that shape the design:

1. **Seeded superuser.** Migration `app/migrations/0002_seed_data_2247.py` creates
   `root@example.com` with the documented password `supersecret`. The server must
   not be reachable from the internet until that account is rotated.
2. **SQLite is evaluation-only** per the chart README. Web and Celery write the
   same file and hit `database is locked` under load.
3. **Webcam streaming.** Basic streaming is the snapshot feed, relayed by the
   server. Premium streaming is WebRTC: the server relays only signalling
   (`/ws/janus/<printer>/`) and the video flows peer-to-peer between the browser
   and Janus on the printer host. The frontend uses Google STUN, and adds TURN
   only from the built-in `SYNDICATES` table, which self-hosted settings leave
   unset and do not expose as an env var.
4. **Printer UI tunnel** (Mainsail/Fluidd/OctoPrint through Obico) needs either
   one public port per printer (`OCTOPRINT_TUNNEL_PORT_RANGE`) or random
   subdomains under `*.tunnels.<site domain>` (wildcard DNS and a wildcard cert).
5. **Notifications** include an Apprise plugin, so ntfy works without code changes.
6. Upstream license is AGPL-3.0.

Forge constraints: public repo with no secrets, GitOps only, no new host
listeners or UFW holes, data on the data disk, no paid services.

## Decision

1. **Packaging: upstream Helm chart through Argo CD.** Argo CD Application
   `obico` pins chart `2026.7.11`, with values in
   `k8s/apps/obico/helm/values.yaml`, the same multi-source pattern as
   `monitoring`. A second source syncs `k8s/apps/obico/` (kustomize) for the
   forge-specific pieces: namespace, quota, NetworkPolicies, ExternalSecrets,
   Ingress. The chart's own Ingress and Secret are disabled. If the chart gets
   in the way, vendor it with `helm template` into plain manifests (media-style).
2. **Namespace `obico`**, label `forge.homelab/plane: apps`, its own
   ResourceQuota and LimitRange. The LimitRange defaults are required: the
   chart's `collectstatic` and `migrate` init containers set no resources, so
   give the default limit at least 512Mi.
3. **Database: a dedicated `obico` database and role on the existing
   `forge-postgres`** (`forge-system`). ESO templates `DATABASE_URL` into Secret
   `obico-db`, consumed through `database.existingSecret`. One Postgres to back
   up. The obico data set is small because media stays on disk.
4. **Media and data: chart PVCs on `local-path`**, which already lives on the
   data disk (`/media/diestrin/data/forge/k3s/local-path`). Media 50Gi
   (`local-path` does not enforce the size), data 1Gi (Celery beat schedule only).
5. **One hostname everywhere: `obico.localpower.diegobarahona.com`.** Public DNS
   points it at the WAN address (HTTP-01 via Traefik, ADR-003). Printers, the
   browser and the mobile app all use this one URL. Obico stores a single Django
   Site domain and embeds it in timelapse and notification links, so a second
   `.lan.` name (as Garage uses) would break links. For now, home devices reach
   the name through the router's hairpin NAT, the same way they reach the
   forge's other public names. #74 checks that path from a printer host. If
   it is unreliable, home printers lose status, controls and alerts. Resolving
   the same name to the forge host on the LAN is follow-up #77.
6. **Admin is never public.** A second Ingress on `/admin` routes through a
   Traefik `ipAllowList` Middleware that admits nothing (`127.0.0.1/32`), so the
   edge returns 403. Admin work goes through `kubectl port-forward`. As a second
   layer, set `ADMIN_IP_WHITELIST='["127.0.0.1"]'`. Sign-up stays off
   (`ACCOUNT_ALLOW_SIGN_UP=False`); the admin creates accounts. Obico gives
   each printer exactly one owner (`Printer.user`), so one shared **household**
   account owns all printers and both people log in to it. The personal
   superuser owns no printers.
7. **Secrets in Vault `secret/forge/obico`** (`django_secret_key`, `db_password`,
   later SMTP or Telegram tokens), synced with ExternalSecrets into
   `obico-secrets` (chart `obico.existingSecret`) and `obico-db`. Never use the
   chart's generated key: Argo renders with `helm template`, which regenerates it
   on every sync.
8. **ML on CPU** (`obico-ml-api-cpu`) on the i7-10710U. There is no NVIDIA GPU,
   and the Intel iGPU is unused by upstream and already serves Jellyfin.
9. **Notifications through Apprise → ntfy.** Each user enters an Apprise
   `ntfys://` URL in the Obico UI, so the topic lives in the database, not git.
   Email is deferred.
10. **Tunnel off** for now: `OCTOPRINT_TUNNEL_PORT_RANGE="0-0"`, as in upstream
    compose. Print control (pause, cancel, temperatures) works through the Obico
    UI without the tunnel.
11. **No TURN server.** The table below is the accepted remote-viewing behaviour.

    | Feature | On the LAN | Away from home |
    | --- | --- | --- |
    | Status, controls, AI alerts | Yes | Yes |
    | Snapshot feed (Basic streaming) | Yes | Yes, through Traefik |
    | Live video (Premium, WebRTC) | Yes | Best effort; fails behind symmetric NAT (common on mobile data) |
    | Printer UI tunnel | Off | Off |

    The LAN column assumes home devices can reach the public name (decision 5).

12. **NetworkPolicy:** default-deny; DNS; same-namespace; Traefik (`kube-system`)
    → `web:3334` only; `web` and `tasks` egress to `forge-postgres:5432` and
    TCP 443 (ntfy and other notifiers); `ml-api` gets DNS only (model is baked
    in). `forge-postgres`'s policy gains an ingress rule from namespace `obico`.
13. **Monitoring:** add `obico` to the A4–A7 alert selectors in
    `k8s/platform/metrics/rules/forge-alerts.yaml`.

Values sketch (renders and passes `kubeconform -strict` against the chart at
`49c0bc70`):

```yaml
obico:
  siteUsesHttps: true
  csrfTrustedOrigins:
    - https://obico.localpower.diegobarahona.com
  existingSecret: obico-secrets
  extraEnv:
    ACCOUNT_ALLOW_SIGN_UP: "False"
    ADMIN_IP_WHITELIST: '["127.0.0.1"]'
    OCTOPRINT_TUNNEL_PORT_RANGE: "0-0"
    TZ: America/Costa_Rica
database:
  existingSecret: obico-db
  existingSecretKey: DATABASE_URL
ingress:
  enabled: false
persistence:
  media:
    size: 50Gi
```

## Rollout

Tracked in #72: steps 1–3 are #73, #74 and #75, and step 0 is the operator
checklist on #73. Steps 1 and 2 are separate PRs so that the public Ingress
cannot merge before the seeded admin is gone.

### 0. Operator prep (no PR)

- Public DNS: `obico.localpower.diegobarahona.com` → the same DDNS target as the
  other forge names. Home devices reach it through the router's hairpin NAT
  for now; a LAN DNS override for the same name is #77.
- Vault (after unseal). The DB password is hex so it is URL-safe in `DATABASE_URL`:

  ```bash
  vault kv put secret/forge/obico \
    django_secret_key="$(openssl rand -base64 48)" \
    db_password="$(openssl rand -hex 24)"
  ```

- Create the role and database in `forge-postgres`, reading the password from
  Vault (the runbook will carry the exact `psql` command).

### 1. PR A: cluster-internal deploy (risk: medium)

- `k8s/apps/obico/`: kustomization, namespace, quota and LimitRange,
  NetworkPolicies (no Traefik ingress rule yet), ExternalSecrets, `helm/values.yaml`,
  README.
- `k8s/overlays/root/applications.yaml`: Application `obico` with two sources:
  the chart, and this repo as both the `$values` ref and the `k8s/apps/obico`
  path. Argo CD v3.5 pulls a public OCI chart from a `repoURL` without
  `oci://` and needs no repository Secret.
- `k8s/platform/postgres/networkpolicy.yaml`: allow from namespace `obico`.
- CI: `helm template` the pinned chart with our values, pipe to kubeconform,
  and `cosign verify` the chart signature.
- Alerts A4–A7 include `obico`. New `docs/runbooks/obico.md`; rows in
  `restore.md`; `k8s/README.md`; CHANGELOG.

Done when: Argo `obico` is Synced/Healthy; `web`, `ml-api` and `redis` are Ready.
Then, over `kubectl -n obico port-forward svc/obico-web 3334`:

- log in as `root@example.com`, create a personal superuser, and delete or
  deactivate the seeded account
- set the Django Site domain to `obico.localpower.diegobarahona.com` (no scheme)
- confirm the admin loads through port-forward with the IP whitelist on

### 2. PR B: public endpoint (risk: high, public Ingress)

- `k8s/apps/obico/ingress.yaml`: TLS Ingress for `/`, plus the `/admin` deny
  Ingress and Middleware.
- NetworkPolicy: allow `kube-system` → `web:3334`.
- The PR description carries a checkbox confirming step 1's admin rotation.

Done when: the certificate is Ready; `/admin/` returns 403 from the LAN and from
mobile data; login works from mobile data; a websocket session stays up behind
Traefik.

### 3. Printers and notifications (no PR, runbook updates only)

- Create the household account in Django admin (over port-forward).
- On each printer host, install `moonraker-obico` with server
  `https://obico.localpower.diegobarahona.com`, then link it to the household
  account with the 6-digit code.
- Add an Apprise ntfy URL in Obico notification settings and send a test.
- In the Obico mobile app, tap the wrench on the login screen and set the
  server URL.
- Check: a print triggers detections (`ml-api` logs); the snapshot feed works
  over mobile data. Record whether live video works on mobile data in the
  runbook.

### Later (separate issues, each re-reviewed)

- **Printer UI tunnel** in subdomain mode: wildcard DNS
  `*.tunnels.obico.localpower.diegobarahona.com`, a DNS-01 `ClusterIssuer` (DNS
  API token in Vault), and a Traefik `HostRegexp` route. Port mode is rejected:
  it needs one public port per printer.
- **TURN** for remote live video, only if step 3 shows it is needed. Requires
  patching upstream settings (AGPL: publish the patch) and a public UDP listener
  for coturn, which means a UFW change, a router forward, and host-watch
  allowlists. Its own ADR.
- Email (SMTP in Vault); scheduled `pg_dump` plus a media backup to Garage;
  media retention.

## Consequences

- No new host listener, UFW rule or router forward. Traefik keeps 80/443 and
  printer agents connect outbound, so host-watch allowlists do not change.
- Footprint about 0.9 CPU / 2.3 GiB requested, 4.2 CPU / 5.5 GiB limits. Quota:
  `requests.cpu: 2`, `requests.memory: 4Gi`, `limits.cpu: 8`,
  `limits.memory: 10Gi`, `pods: 10`, which leaves room for the ml-api and
  redis surge pods during a rolling update.
- Single node. If the NUC is down, prints keep running but nobody watches them
  and AI auto-pause cannot fire.
- `obico` now depends on `forge-postgres` (512Mi limit, manual backups). Revisit
  its limits if connections or memory climb.
- `local-path` PVs use `reclaimPolicy: Delete`. The chart marks its PVCs
  `helm.sh/resource-policy: keep` (Argo CD: `Delete=false`), and the `obico`
  Namespace carries `Delete=false,Prune=false`, because deleting the Namespace
  would delete the PVCs too. Deleting the app leaves the media. Deleting a PVC
  or the Namespace by hand still deletes it.
- The chart is young (`0.2.x` line, July 2026). Pinning plus CI rendering
  catches breakage at bump time. Dependabot covers Actions only, so bumps are
  manual.
- Upstream's LLM ("JusPrin") settings stay unset, so nothing reaches OpenAI.

## Alternatives considered

- **Obico Cloud.** Paid tiers for live video and AI hours, and not self-hosted.
- **docker compose on the host.** Bypasses GitOps and binds a host port.
- **Hand-written manifests.** Would re-derive the chart's fixes (non-root user,
  `collectstatic` into an `emptyDir`, beat schedule path, ffmpeg OOM limits).
  Kept as the fallback.
- **SQLite.** Upstream's chart calls it evaluation-only.
- **Dedicated Postgres in `obico`.** Better isolation, but a second database to
  run and back up on one NUC.
- **Separate LAN hostname (Garage style).** Obico has one Site domain; links
  would break.
- **Tailscale or Cloudflare Tunnel.** A non-goal in `PLAN.md`; the direct
  Traefik path already exists.

## Operator answers (2026-10-02)

| Question | Answer |
| --- | --- |
| Printer software | Klipper/Moonraker on every printer, so `moonraker-obico` only |
| Printer locations | All at home |
| Users | Two people, sharing one household account (decision 6) |
| Live video away from home | Best effort is acceptable; no TURN |
| LAN resolution | Home devices reach the forge's public URLs through the router's hairpin NAT. A same-name LAN DNS override is deferred to #77 |
