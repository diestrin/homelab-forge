# Orchestrator playbook

The orchestrator turns operator intent into tasks on the control plane. Surfaces:

- **Cursor chat** (interactive) — this playbook in a Cursor session
- **Slack Socket Mode** (ADR-009/ADR-011) — `factory/orchestrator/slack_intake.py`
  is a **thin intake client**: it POSTs slash commands and thread replies to
  `POST /api/v1/slack/intake` and never runs the Cursor SDK, git, or `gh`.
  Plan jobs are executed by the worker daemon (`run_plan_job.py`), and all
  agent progress/failure replies to Slack come from the control plane notify
  queue.

It **creates/revises plans**; it does not mutate production or merge to `main`
(ADR-004 / ADR-008).

## Hard rules

1. Write structured tasks under `factory/tasks/TASK-NNN-*.yaml` (schema in
   [`../schema/`](../schema/)).
2. New Slack-originated tasks start as **`planning`** (not claimable). Open a plan
   PR; iterate via the Slack thread; only after explicit approve → `proposed`.
3. Never silent-prod-deploy: no `kubectl apply` to Argo-managed apps; no force-push;
   no disabling UFW/host-watch.
4. Prefer **git** as source of truth; sync the board with
   `./forge factory sync` after creating/updating tasks.
5. Capture conversation decisions in `notes:` or a short ADR when they outlive the task.

## Intent → profile / risk

| User intent | `sandbox_profile` | `risk_level` | Notes |
| --- | --- | --- | --- |
| Docs / README / comments only | `agent-cell` | `low` | Default worker path |
| App code, no public ingress | `agent-cell` or `devcontainer` | `low`/`medium` | |
| New dependency / system packages | `incus` if installed else `devcontainer` | `medium` | |
| Long-running service / Ingress | `k8s-workload` for dry-runs; manifests land via PR | `high` | Deploy only after merge → Argo |
| Touch SSH/UFW/Vault unseal | *(human only)* | `high` | Keep `planning`; do **not** approve into worker queue without care |
| Secrets / tokens | never commit; document Vault path in `notes` | `high` | Worker fetches via AppRole |

## Task authoring checklist

- [ ] `id` next free `TASK-NNN` (`./forge factory` / `task_lib next-id`); filename `TASK-NNN-slug.yaml`
- [ ] Clear `goal` + measurable `acceptance_criteria`
- [ ] `repo_path` (usually `.` for this repo)
- [ ] Slack path: `status: planning` until approve; interactive Cursor may use `proposed` when the operator is ready for workers immediately
- [ ] `budget_minutes` set (default 30)
- [ ] `worker_hook` only for scripted/demo tasks; omit so Cursor SDK worker implements
- [ ] `branch: factory/task-NNN-…`
- [ ] Run `./forge factory validate` then `./forge factory sync`

## Slack flow (ADR-009 / ADR-011)

```text
/forge plan → intake API → planning task (branch pinned) → plan job → plan PR
            → thread feedback → plan-update job (same PR, same branch)
            → approve → proposed → implement job → same PR
            → watch-checks job polls CI → fix runs until green (no merge)
```

- Approve in-thread with `approve` / `lgtm` / `/forge approve`, or
  `./forge factory approve TASK-NNN`.
- The branch is pinned in Postgres at intake; planner YAML must never rewrite
  it, and `gh pr create` runs only when no pinned/open PR exists (TASK-011).
- Thread replies **after** approve are stored on the task and acknowledged —
  they never start a new plan-PR cycle or a host planner run.

## Prompt skeleton (Cursor chat)

```text
You are the homelab-forge orchestrator. Given my request:
1. Clarify acceptance criteria if ambiguous.
2. Choose sandbox_profile + risk_level from the playbook table.
3. Add factory/tasks/TASK-NNN-*.yaml (planning if Slack-bound; else proposed when I want workers now).
4. Do not implement the change yourself unless I ask; leave it for a worker.
5. Remind me that merge to main → Argo CD is the only steady-state deploy path.
```

## After workers finish

Point the human at [`../review/CHECKLIST.md`](../review/CHECKLIST.md). Orchestrator
may summarize the PR but must not merge without explicit human approval.
