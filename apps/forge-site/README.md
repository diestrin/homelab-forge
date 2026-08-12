# forge-site

Next.js public front page for homelab-forge: landing at `/` and a read-only factory
task dashboard at `/dashboard`.

## Local development

```bash
cd apps/forge-site
npm install
npm run dev
```

Task YAML is read from `../../factory/tasks/` by default. Override with
`FORGE_TASKS_DIR`.

## Container build

Build from the **repository root** so the standalone Next.js output can be copied
into a minimal runtime image:

```bash
docker build -f apps/forge-site/Dockerfile -t forge-site:local .
```

In Kubernetes, task YAML is mounted from a ConfigMap at `/data/factory/tasks`
(see `k8s/apps/forge-site/`). After adding tasks under `factory/tasks/`, run
`k8s/apps/forge-site/sync-tasks.sh` and update `kustomization.yaml` if needed.

## Deploy path

Merge to `main` → GitHub Actions publishes `ghcr.io/diestrin/homelab-forge/forge-site`
→ Argo CD Application `forge-site` syncs `k8s/apps/forge-site/`. Do not `kubectl apply`
Argo-managed apps directly (ADR-008).
