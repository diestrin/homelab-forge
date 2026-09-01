# Agent handoff

You are working in **homelab-forge**, a portfolio-grade home software forge running
on Ubuntu + Nix + k3s.

## Context for agents

1. Read [`PLAN.md`](./PLAN.md) for vision and architecture.
2. Read [`docs/current-state.md`](./docs/current-state.md) for current host state.
3. Respect ADRs in [`docs/decisions/`](./docs/decisions/).
4. **Task management:** GitHub Issues with `task` label (see `.cursor/skills/homelab-task/`).

## Key architecture decisions

- **Agent platform:** Cursor My Machines (ADR-012, since 2026-09-01)
  - Request changes via Cursor Slack, mobile app, or cursor.com/agents
  - Worker runs locally on localpower host
  - Environment defined in `.cursor/environment.json`
  
- **GitOps:** Merge to `main` → Argo CD syncs `k8s/` (ADR-008)
  - Never `kubectl apply` to Argo-managed apps
  - All cluster changes via PR → review → merge
  
- **Secrets:** HashiCorp Vault on k3s (ADR-007)
  - No secrets in git (repo is **public**)
  - Vault accessed via local MCP server on worker
  
- **Host IDS:** `security/host-watch/` monitors processes (ADR-005)
  - Update allowlists when adding new services
  - Never disable UFW to "fix" networking

## Defaults

- Prefer reversible, documented changes.
- Never disable the firewall to unblock networking.
- Repo is **public** — no secrets, no personal data in git.
- Cluster steady-state deploys go through Argo CD from `main` (ADR-008).
- For new work, create GitHub Issue with `task` label first (see `.cursor/skills/homelab-task/`).

## Superseded (historical reference)

- **ADR-009/010/011:** Custom factory pipeline (Slack Socket Mode → Postgres control
  plane → worker daemon) retired 2026-09-01 in favor of Cursor My Machines (ADR-012).
- Factory task YAML under `factory/tasks/` is legacy; use GitHub Issues.
