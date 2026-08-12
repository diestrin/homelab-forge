# TASK-007 plan — Forge site (Next.js landing + task dashboard, v1)

## What

Phase 1 of a multi-phase Forge web project: a **Next.js** app (frontend + API routes)
that **replaces** the current `forge-demo-hello` nginx ConfigMap demo as the public
front page on
[localpower.diegobarahona.com](https://localpower.diegobarahona.com).

- **`/`** — landing page explaining the Forge OSS project, its components, and how the
  factory pipeline works (orchestrator → plan PR → worker → review → merge).
- **`/dashboard`** — read-only board of factory tasks parsed from `factory/tasks/*.yaml`
  (id, title, status, assignee when set).

Keep both pages intentionally simple; polish and extra features come in later phases /
Slack thread iteration.

## Why

The static hello ConfigMap was a bootstrap demo. A real Next.js site gives visitors a
coherent story about Forge and lets operators see live task state from git — the same
source of truth the factory already uses — without opening GitHub.

## How

1. **Plan gate:** task stays `planning` until the operator approves in the Slack thread
   (`approve` / `lgtm` / `/forge approve`) and `./forge factory approve TASK-007`
   moves status to `proposed`.
2. **App:** add a Next.js project in-repo (worker picks layout, e.g. under `apps/`) with
   Dockerfile or equivalent container build; API route(s) read and parse task YAML from
   the mounted/checked-out `factory/tasks/` tree.
3. **K8s:** new or updated manifests under `k8s/apps/` (likely replacing
   `k8s/apps/forge-demo-hello`) — Deployment, Service, Ingress on the existing host/TLS
   pattern; point Argo Application source at the new app path.
4. **PR:** worker opens/updates the implementation PR on branch
   `factory/task-007-let-s-plan-to-build-a-multi-phase-projec`; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md).
5. **Deploy:** **human merge to `main` only.** Argo CD syncs the demo Application — this
   is the **sole steady-state deploy path** (ADR-008). No worker `kubectl apply` to
   Argo-managed apps. Worker may use `k8s-workload` sandbox for dry-runs only.

## Risks

- **High** — new dependency (Node/Next.js), container image, and public Ingress replace
  an existing Argo-managed demo. Rollback is git revert + Argo sync.
- Dashboard reads task YAML at runtime/build — schema drift or parse errors need graceful
  handling in v1 (empty state or error message, not a crash loop).
- Do **not** auto-approve this task into the worker queue without operator review; prod
  exposure changes require explicit human approval.

## Out of scope (v1)

- Authentication, write/edit actions on tasks, Slack Socket Mode UI, or replacing the
  orchestrator intake flow
- SSH, UFW, Vault unseal, disabling host-watch, force-push, or silent prod deploy
- Real-time push updates (polling or static build-time snapshot is fine for v1)
- Scripted `worker_hook` (Cursor SDK worker implements per task YAML)

## Multi-phase / iteration

Slack thread feedback refines this plan before approval. After v1 ships, follow-on
phases (richer dashboard, styling, filters, live sync) land as thread-approved plan
updates or new `TASK-NNN` entries — not scope creep in this task unless the operator
re-approves expanded acceptance criteria.
