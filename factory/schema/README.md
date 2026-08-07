# Factory task schema

JSON Schema: [`task.schema.json`](./task.schema.json) (ADR-004).

Tasks live as YAML under [`../tasks/`](../tasks/). **Git is the source of truth**;
GitHub Projects is a kanban mirror (see [`../PROJECTS.md`](../PROJECTS.md)).

## State machine

```text
proposed → claimed → in_progress → review → done
                 \              \→ failed
                  \→ failed
```

| Status | Meaning |
| --- | --- |
| `proposed` | Orchestrator wrote the task; free for workers to claim |
| `claimed` | A worker reserved it (lease); not yet executing |
| `in_progress` | Sandbox up; implement / tests running |
| `review` | Artifacts ready (PR, logs); human/reviewer gate |
| `done` | Merged / acceptance met; board column Done |
| `failed` | Budget exceeded, hook error, or operator abort |

Illegal skips (e.g. `proposed` → `done`) are rejected by `forge factory validate` / worker transitions.

## Required fields

`id`, `title`, `goal`, `acceptance_criteria`, `sandbox_profile`, `repo_path`, `status`, `risk_level`

Optional: `assignee_agent`, `artifacts[]`, `github_project_item_id`, `budget_minutes` (default 30),
`branch`, `worker_hook`, `notes`, timestamps.
