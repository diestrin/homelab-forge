---
name: factory-orchestrator
description: Turn a user request into a homelab-forge factory task. Use when the user asks for new work, a feature, a fix, or a change that should become a task for a worker agent, or mentions creating/proposing a factory task, the task board, or GitHub Projects sync.
---

# Factory orchestrator

Read and follow `factory/orchestrator/PLAYBOOK.md` — it is the source of truth
(task authoring checklist, intent → `sandbox_profile`/`risk_level` table, prompt skeleton).

## Hard rules

1. Output is a task file `factory/tasks/TASK-NNN-<slug>.yaml` matching
   `factory/schema/task.schema.json`, with `status: proposed`. Do not implement the
   change yourself unless the user explicitly asks.
2. Never silent-prod-deploy: no `kubectl apply` to Argo-managed apps, no force-push,
   no disabling UFW/host-watch. Steady-state deploys are merge to `main` → Argo CD (ADR-008).
3. Validate and mirror after writing:

```bash
./forge factory validate
./forge factory sync
```

Capture conversation-derived decisions in the task `notes:` field, or as a short ADR
under `docs/decisions/` when they outlive the task.
