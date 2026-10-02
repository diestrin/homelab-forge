# Obico printer monitoring

Self-hosted Obico for the home Klipper printers (ADR-016). It runs the upstream
Helm chart through Argo CD, keeps its database on `forge-postgres`, and stores
media on `local-path` PVCs on the data disk.

| Who | URL |
| --- | --- |
| Printers, browsers, mobile app | `https://obico.localpower.diegobarahona.com` (from #74) |
| Operator (admin, bootstrap) | `kubectl -n obico port-forward svc/obico-web 3334` → `http://localhost:3334` |
| Pods in the cluster | `http://obico-web.obico.svc:3334` |

Until #74 merges there is no Ingress. Obico is reachable only through
port-forward.

## Before merge

Do these before the Argo CD app first syncs, or the web pod waits on missing
secrets and its `migrate` init container fails.

1. Vault (after unseal; see [vault.md](./vault.md) for `VAULT_ADDR`). The DB
   password is hex so it stays valid inside `DATABASE_URL`. Do not paste the
   values into git, issues, or chat logs.

   ```bash
   vault kv put secret/forge/obico \
     django_secret_key="$(openssl rand -base64 48)" \
     db_password="$(openssl rand -hex 24)"
   ```

   `django_secret_key` signs sessions and tokens. Changing it later logs
   everyone out.

2. Role and database on `forge-postgres`. The password goes in on stdin, not
   on a command line:

   ```bash
   OBICO_DB_PASSWORD="$(vault kv get -field=db_password secret/forge/obico)"
   kubectl -n forge-system exec -i deploy/forge-postgres -- \
     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<SQL
   CREATE ROLE obico LOGIN PASSWORD '${OBICO_DB_PASSWORD}';
   CREATE DATABASE obico OWNER obico;
   SQL
   unset OBICO_DB_PASSWORD
   ```

3. Public DNS: `obico.localpower.diegobarahona.com` → the same DDNS target as
   the other forge names. Only #74 needs it, but adding it now gives it time to
   propagate.

## Deploy

Merge to `main`. Argo CD Application `obico` renders chart `obico` from
`ghcr.io/thespaghettidetective/charts` with
[`k8s/apps/obico/helm/values.yaml`](../../k8s/apps/obico/helm/values.yaml) and
syncs [`k8s/apps/obico/`](../../k8s/apps/obico/). Do not `kubectl apply` it.

```bash
kubectl -n forge-system get application obico
kubectl -n obico get externalsecret,pods,pvc
kubectl -n obico exec deploy/obico-web -c server -- \
  python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:3334/hc/').status)"
kubectl -n obico exec deploy/obico-ml-api -- \
  python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:3333/hc/').status)"
kubectl -n obico get ingress   # empty until #74
```

Expect `obico-web` (containers `server` and `tasks`), `obico-ml-api` and
`obico-redis` Ready, both ExternalSecrets `SecretSynced`, both PVCs Bound, and
`200` from each `/hc/` check. The readiness probes use the same endpoints.

## Bootstrap (once, before #74)

Upstream migration `0002` creates the superuser `root@example.com` with the
published password `supersecret`. Replace it before anything is public. Use
`manage.py`, which avoids logging in with the default account at all.

1. Create your own superuser. It prompts for an email and a password:

   ```bash
   kubectl -n obico exec -it deploy/obico-web -c server -- python manage.py createsuperuser
   ```

2. Delete the seeded account. Rename the seeded `localhost:3334` Site to the
   public name: Obico builds notification and timelapse links from it, and
   requests on any other host (port-forward included) fall back to the first
   Site.

   ```bash
   kubectl -n obico exec -i deploy/obico-web -c server -- python manage.py shell <<'PY'
   from django.contrib.sites.models import Site
   from app.models import User

   User.objects.filter(email='root@example.com').delete()

   site = Site.objects.get(domain='localhost:3334')
   site.domain = site.name = 'obico.localpower.diegobarahona.com'
   site.save()

   print('superusers:', list(User.objects.filter(is_superuser=True).values_list('email', flat=True)))
   print('sites:', list(Site.objects.values_list('domain', flat=True)))
   PY
   ```

   Expect only your email under `superusers` and exactly one site. If another
   site (such as `example.com`) is listed, delete it.

3. Restart the web pod so it drops cached Site lookups:

   ```bash
   kubectl -n obico rollout restart deploy/obico-web
   kubectl -n obico rollout status deploy/obico-web
   ```

4. Check the admin over port-forward:

   ```bash
   kubectl -n obico port-forward svc/obico-web 3334
   ```

   Open `http://localhost:3334/admin/` and log in with the new superuser. A 403
   means `ADMIN_IP_WHITELIST` does not see port-forward traffic as
   `127.0.0.1`. In that case, remove it from `helm/values.yaml`; the Traefik
   block in #74 is the primary control.

Tick the bootstrap boxes on #73. #74 must not merge before they are done.

## Upgrades

1. Pick a CalVer from the chart's package page
   (`ghcr.io/thespaghettidetective/charts/obico`).
2. In one PR, bump the Application `targetRevision`, `OBICO_CHART_VERSION` in
   `.github/workflows/ci.yml`, and both image tags in `helm/values.yaml`. CI
   verifies the chart signature and renders it with our values.
3. Compare chart resource changes against `k8s/apps/obico/quota.yaml`.
4. Take a database dump first (below). The `migrate` init container applies
   migrations on every web pod start.

## Data and backups

| What | Where |
| --- | --- |
| Database | `obico` on `forge-postgres` |
| Media (snapshots, timelapses, G-code) | PVC `obico/obico-media` under `/media/diestrin/data/forge/k3s/local-path/` |
| Celery beat schedule | PVC `obico/obico-data` (disposable) |

The chart marks both PVCs `helm.sh/resource-policy: keep`. Argo CD treats that
as `Delete=false`, so deleting the Application leaves them in place.

Database dump:

```bash
kubectl -n forge-system exec deploy/forge-postgres -- \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d obico -Fc' > "obico-$(date +%F).dump"
```

## Firewall and host-watch

No new host listener, UFW rule or router forward. Traefik keeps 80/443, and
printer agents connect outbound to the public URL. host-watch allowlists do not
change.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Pods `CreateContainerConfigError` | Vault `secret/forge/obico` fields; `kubectl -n obico get externalsecret` |
| `migrate` init: `password authentication failed` or `database "obico" does not exist` | Role and database from "Before merge"; `db_password` must match the role password |
| `migrate` init hangs on connect | NetworkPolicies: `obico/allow-web-egress-postgres` and the obico rule in `forge-system/forge-postgres` |
| Argo `obico` cannot fetch the chart | `repoURL` must have no `oci://`; GHCR must allow anonymous pulls (otherwise add a repository Secret with `enableOCI: "true"`) |
| Pod rejected with `exceeded quota` | Chart resources changed on upgrade; resize `quota.yaml` |
| 500 on every page after the Site rename | More than one Site, or cached lookups: list Sites, then restart `obico-web` |
| Admin 403 over port-forward | `ADMIN_IP_WHITELIST`; see Bootstrap step 4 |
| Timelapses never appear | `tasks` container OOM during ffmpeg; the chart limit is 2Gi |

## Related

- [ADR-016](../decisions/ADR-016-obico-printer-monitoring.md) — design and rollout.
- [gitops.md](./gitops.md) — merge → Argo.
- [vault.md](./vault.md) — unseal, ESO.
- Issues: #72 (epic), #73 (this deploy), #74 (public endpoint), #75 (printers), #77 (LAN DNS).
