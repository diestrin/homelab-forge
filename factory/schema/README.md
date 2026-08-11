# Factory task schema

JSON Schema: [`task.schema.json`](./task.schema.json) (ADR-004 / ADR-009).

Tasks live as YAML under [`../tasks/`](../tasks/). **Git is the source of truth**;
GitHub Projects is a kanban mirror (see [`../PROJECTS.md`](../PROJECTS.md)).

## State machine

```text
planning → proposed → claimed → in_progress → review → done
    \          \              \              \→ failed
     \→ failed  \→ failed      \→ failed
```

| Status | Meaning |
| --- | --- |
| `planning` | Orchestrator opened a plan PR; **not** claimable. Slack thread feedback iterates the plan until explicit approval |
| `proposed` | Plan approved (or authored claimable); free for workers to claim |
| `claimed` | A worker reserved it (lease); not yet executing |
| `in_progress` | Sandbox/worktree up; Cursor SDK or hook implementing |
| `review` | Artifacts ready (PR, logs); human/reviewer gate |
| `done` | Merged / acceptance met; board column Done |
| `failed` | Budget exceeded, hook/SDK error, or operator abort |

Illegal skips (e.g. `proposed` → `done`, or worker claim of `planning`) are rejected by
`forge factory validate` / worker transitions. Approve with
`./forge factory approve TASK-NNN` (`planning` → `proposed`).

## Required fields

`id`, `title`, `goal`, `acceptance_criteria`, `sandbox_profile`, `repo_path`, `status`, `risk_level`

Optional: `assignee_agent`, `artifacts[]`, `github_project_item_id`, `budget_minutes` (default 30),
`branch`, `worker_hook`, `notes`, timestamps.
