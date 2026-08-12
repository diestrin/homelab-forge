# forge-site

Next.js public front page for homelab-forge: landing at `/`, live factory dashboard at
`/dashboard`, and task detail at `/dashboard/[id]`. Hosts the **factory control plane API**
(ADR-010): Postgres + pg-boss, HTTP `/api/v1/*`, and MCP tools.

## Local development

```bash
cd apps/forge-site
npm install
export DATABASE_URL=postgresql://forge:forge@127.0.0.1:5432/forge
export FORGE_API_TOKEN=dev-token
export FORGE_RUN_MIGRATIONS=true
npm run dev
```

Without `DATABASE_URL`, the dashboard renders empty state (CI/build-safe).

## API

OpenAPI spec: [`docs/openapi.yaml`](./docs/openapi.yaml) — served at `/api/v1/openapi`.

Bearer auth (`FORGE_API_TOKEN`) required for mutations and job claim.

## MCP server (stdio sidecar)

Documented pattern for Cursor and other MCP clients:

```bash
cd apps/forge-site
export FORGE_CONTROL_PLANE_URL=http://127.0.0.1:3000
export FORGE_API_TOKEN=…
npm run mcp
```

Configure in Cursor MCP settings pointing at the above command.

## Container build

Build from the **repository root**:

```bash
docker build -f apps/forge-site/Dockerfile -t forge-site:local .
```

Runtime expects `DATABASE_URL` and `FORGE_API_TOKEN` from Kubernetes ExternalSecret
(Vault paths `secret/forge/postgres`, `secret/forge/control-plane`).

## Deploy path

Merge to `main` → GitHub Actions publishes `ghcr.io/diestrin/homelab-forge/forge-site`
→ Argo CD syncs `k8s/apps/forge-site/` and platform Postgres under `k8s/platform/postgres/`.
Do not `kubectl apply` Argo-managed apps (ADR-008).
