# GBrain runbook (ADR-017)

## First-time setup

1. Merge the PR; CI publishes `ghcr.io/diestrin/homelab-forge/gbrain:main`
   (make the package public or add pull credentials if the first pull fails).
2. Seed the owner token in Vault (never commit it):

   ```bash
   vault kv put secret/forge/gbrain admin_token="$(openssl rand -hex 32)"
   ```

3. Argo CD syncs Application `gbrain`. Check:

   ```bash
   kubectl -n gbrain get pods,certificate
   curl -fsS https://gbrain.localpower.diegobarahona.com/health
   ```

## Connect clients

Owner login link (token read from the cluster secret, not printed to logs):

```bash
kubectl -n gbrain exec deploy/gbrain -- sh -c \
  'gbrain mcp admin login-link --url "$GBRAIN_PUBLIC_URL/mcp" --admin-token-file /dev/stdin <<<"$GBRAIN_ADMIN_BOOTSTRAP_TOKEN"'
```

Claude Code:

```bash
claude mcp add --transport http --scope user gbrain https://gbrain.localpower.diegobarahona.com/mcp
```

Then register the OAuth client / grant per upstream `docs/mcp/ADMIN.md`.

## Backup and teardown

Brain data lives in `/media/diestrin/data/forge/gbrain`; include it in backups.
The Namespace is never pruned by Argo; delete manually only after copying that directory.
