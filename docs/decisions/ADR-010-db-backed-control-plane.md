# ADR-010: DB-backed factory control plane

## Status

Accepted (2026-08-12) — supersedes **runtime coordination** aspects of ADR-004 and ADR-009.
Git remains code/config SoT and GitOps deploy path (ADR-008). ADR-004/009 orchestrator and
worker **contracts** (state machine, review gate, Slack plan gate) are preserved.

## Context

ADR-004 made git-backed YAML under `factory/tasks/` the task store. ADR-009 added Slack
Socket Mode intake and Cursor SDK workers. In production this races when operators switch
branches or worktrees: workers scan YAML on disk, re-implement tasks, and open redundant PRs.
The forge-site dashboard (TASK-007) mirrored task YAML via ConfigMap — stale as soon as
runtime state diverged from the synced git snapshot.

We need a **runtime source of truth** for tasks, orchestrator/Slack messages, and job dispatch
that is independent of whichever branch is checked out on the host.

## Decision

1. **Postgres on k3s** (`k8s/platform/postgres/`) is the runtime SoT for:
   - factory tasks (full task record + status machine)
   - task messages (orchestrator, Slack, system, worker)
   - Slack thread bindings
   - pg-boss job queue (`plan`, `implement`, `notify`, `sync-projects`, control actions)

2. **Git** remains SoT for:
   - application code, k8s manifests, ADRs, runbooks
   - optional **export/mirror** of task YAML (`factory/tasks/*.yaml`) for audit/portfolio — not authoritative at runtime

3. **forge-site Next.js backend** exposes:
   - HTTP API (`/api/v1/…`) with bearer token auth (Vault → ExternalSecret)
   - in-process MCP tools via `apps/forge-site/scripts/mcp-server.ts` (documented sidecar pattern)
   - live dashboard reading Postgres, not filesystem YAML

4. **Workers and orchestrator** are thin clients of the API:
   - claim/dequeue via `POST /api/v1/jobs/claim`, not `./forge factory claim` scanning disk
   - status transitions and messages via API
   - host systemd units unchanged in shape; env adds `FORGE_CONTROL_PLANE_URL` + `FORGE_API_TOKEN`

5. **Slack (ADR-009)** retains Socket Mode (no Ingress). **Slash commands only** (`/forge …`) for
   new work; ordinary channel messages are ignored. Thread feedback and approve flow persist;
   orchestrator replies are stored in Postgres and visible on the task detail page.

6. **Secrets:** Postgres credentials and API token in Vault (`secret/forge/postgres`,
   `secret/forge/control-plane`); ExternalSecrets into cluster — never in git.

## State machine (unchanged from ADR-004/009)

| Status | Claimable by worker |
| --- | --- |
| `planning` | no — awaiting Slack/CLI approve |
| `proposed` | yes — `implement` job enqueued on approve |
| `claimed` / `in_progress` / `review` / `done` / `failed` | per ADR-004 transitions |

Approve: `planning` → `proposed` + enqueue `implement` job (API `POST …/actions {action: approve}`).

## Migration from `factory/tasks/*.yaml`

1. Deploy Postgres + migrate forge-site (Argo sync after merge).
2. Run `./forge factory migrate-yaml` once (reads YAML, upserts into Postgres via API).
3. Point worker/orchestrator env at control plane URL + API token.
4. Disable YAML-only claim path: workers **must not** treat checked-out YAML as authoritative.
5. Optional: `./forge factory export-yaml` to refresh git mirror for portfolio/audit.
6. Remove forge-site ConfigMap task mount (dashboard reads DB).

Operator cutover:

```bash
# After merge + Argo healthy:
systemctl --user stop forge-factory-worker.service forge-factory-orchestrator.service
# Add to host env (from Vault, mode 600):
#   FORGE_CONTROL_PLANE_URL=https://localpower.diegobarahona.com
#   FORGE_API_TOKEN=…
systemctl --user start forge-factory-orchestrator.service forge-factory-worker.service
```

## Consequences

- Single runtime view for dashboard, MCP, Slack, and workers — no branch-switch races.
- Postgres + pg-boss adds cluster dependency; backup/restore documented in runbook.
- GitHub Projects sync remains a mirror; API/DB wins over board or YAML on conflict.
- CI builds forge-site without Postgres (graceful empty state); integration tests optional later.

## Supersedes

- ADR-004 § Task store ("Source of truth: Git-backed YAML") for **runtime coordination**.
- ADR-009 filesystem task writes as primary path — replaced by API persistence; plan PR flow retained.
