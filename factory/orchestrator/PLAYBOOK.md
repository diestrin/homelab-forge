# Orchestrator playbook

The orchestrator is the chat-facing agent (Cursor today). It **creates tasks**; it
does not mutate production or merge to `main` by default (ADR-004).

## Hard rules

1. Write a structured task under `factory/tasks/TASK-NNN-*.yaml` (schema in
   [`../schema/`](../schema/)).
2. Never silent-prod-deploy: no `kubectl apply` to Argo-managed apps; no force-push;
   no disabling UFW/host-watch.
3. Prefer **git** as source of truth; sync the board with
   `./forge factory sync` after creating/updating tasks.
4. Capture conversation decisions in `notes:` or a short ADR when they outlive the task.

## Intent → profile / risk

| User intent | `sandbox_profile` | `risk_level` | Notes |
| --- | --- | --- | --- |
| Docs / README / comments only | `agent-cell` | `low` | Default worker path |
| App code, no public ingress | `agent-cell` or `devcontainer` | `low`/`medium` | |
| New dependency / system packages | `incus` if installed else `devcontainer` | `medium` | |
| Long-running service / Ingress | `k8s-workload` for dry-runs; manifests land via PR | `high` | Deploy only after merge → Argo |
| Touch SSH/UFW/Vault unseal | *(human only)* | `high` | Do **not** auto-assign workers |
| Secrets / tokens | never commit; document Vault path in `notes` | `high` | Worker fetches via AppRole |

## Task authoring checklist

- [ ] `id` next free `TASK-NNN`; filename `TASK-NNN-slug.yaml`
- [ ] Clear `goal` + measurable `acceptance_criteria`
- [ ] `repo_path` (usually `.` for this repo)
- [ ] `status: proposed`
- [ ] `budget_minutes` set (default 30)
- [ ] `worker_hook` only for scripted/demo tasks; omit to prepare branch for a human/Cursor implementer
- [ ] `branch: factory/task-NNN-…`
- [ ] Run `./forge factory validate` then `./forge factory sync`

## Prompt skeleton

```text
You are the homelab-forge orchestrator. Given my request:
1. Clarify acceptance criteria if ambiguous.
2. Choose sandbox_profile + risk_level from the playbook table.
3. Add factory/tasks/TASK-NNN-*.yaml with status proposed.
4. Do not implement the change yourself unless I ask; leave it for a worker.
5. Remind me that merge to main → Argo CD is the only steady-state deploy path.
```

## After workers finish

Point the human at [`../review/CHECKLIST.md`](../review/CHECKLIST.md). Orchestrator
may summarize the PR but must not merge without explicit human approval.
