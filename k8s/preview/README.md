# Forge-site PR preview manifests (non-Argo)

Ephemeral preview stacks for pull requests. Applied by
`.github/workflows/forge-site-preview.yml` via the in-cluster runner — **not**
synced by Argo CD.

## Model

| Item | Value |
| --- | --- |
| Namespace | `forge-preview-<pr-number>` |
| Hostname | `pr-<n>.localpower.diegobarahona.com` |
| Image tag | `ghcr.io/diestrin/homelab-forge/forge-site:pr-<n>-<sha>` |
| Labels | `forge.homelab/preview: "true"` on namespace (Postgres NetworkPolicy) |

Templates live in `templates/` with `$PREVIEW_*` placeholders. Render with:

```bash
export PREVIEW_PR_NUMBER=42
export PREVIEW_IMAGE=ghcr.io/diestrin/homelab-forge/forge-site:pr-42-deadbeef
export PREVIEW_HOST=pr-42.localpower.diegobarahona.com
./render.sh | kubectl apply -f -
```

Cleanup: `kubectl delete namespace forge-preview-<pr-number>` (workflow handles this).

See [`docs/runbooks/forge-site-preview.md`](../../docs/runbooks/forge-site-preview.md).
