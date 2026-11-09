# GBrain runbook (ADR-017)

## First-time setup

1. Merge the PR; CI publishes `ghcr.io/diestrin/homelab-forge/gbrain:main`
   (make the package public or add pull credentials if the first pull fails).
2. Seed the owner token in Vault (never commit it):

   ```bash
   vault kv put secret/forge/gbrain \
     admin_token="$(openssl rand -hex 32)" \
     postgres_password="$(openssl rand -hex 24)"
   ```

3. Argo CD syncs Application `gbrain`. Check:

   ```bash
   kubectl -n gbrain get pods,certificate
   curl -fsS https://gbrain.localpower.diegobarahona.com/health
   ```

## Connect clients

Owner login link. gbrain requires the token in a private (0600) regular file, so the
command writes a temp file in the pod and removes it afterwards:

```bash
kubectl -n gbrain exec deploy/gbrain -- bash -c \
  'umask 077; f=$(mktemp); printf %s "$GBRAIN_ADMIN_BOOTSTRAP_TOKEN" > "$f"; gbrain mcp admin login-link --url "$GBRAIN_PUBLIC_URL/mcp" --admin-token-file "$f"; rm -f "$f"'
```

Claude Code:

```bash
claude mcp add --transport http --scope user gbrain https://gbrain.localpower.diegobarahona.com/mcp
```

Then register the OAuth client / grant per upstream `docs/mcp/ADMIN.md`.

## Backup and teardown

Brain data lives in Postgres at `/media/diestrin/data/forge/gbrain-pg`; include it in backups
(or `kubectl -n gbrain exec deploy/gbrain-postgres -- pg_dump -U gbrain gbrain > gbrain.sql`).
The Namespace is never pruned by Argo; delete manually only after backing up.
