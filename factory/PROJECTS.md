# GitHub Projects mirror

**Board:** [homelab-forge factory](https://github.com/users/diestrin/projects/1)  
**Owner / number:** `diestrin` / `1`  
**Project id:** `PVT_kwHOAA3gD84Bfo-B`  
**Status field id:** `PVTSSF_lAHOAA3gD84Bfo-BzhZ6dSI`

Linked to repo `diestrin/homelab-forge`. Visibility: **public**.

## Column ↔ task status

| Git status | Projects Status option | Option id |
| --- | --- | --- |
| `planning` | Planning | `9d0b2c46` |
| `proposed` | Proposed | `a5a9735c` |
| `claimed` | Claimed | `654955ca` |
| `in_progress` | In Progress | `acd648e9` |
| `review` | Review | `2ec5fd72` |
| `done` | Done | `f4ef9446` |
| `failed` | Failed | `8ccee8f2` |

Option ids were refreshed when the **Planning** column was added (ADR-009). If sync
fails with `no column id`, re-list options and update this table +
`factory/scripts/sync-projects.sh`.

## Sync convention

- **Git wins.** Task YAML under `factory/tasks/` is authoritative.
- Mirror with `./forge factory sync` (wrapper around `factory/scripts/sync-projects.sh`).
- Sync creates draft items when `github_project_item_id` is null, writes the id back
  into the YAML, and updates Status to match git.
- If the board drifts, re-run sync; do **not** edit task status only on the board.

Manual v1 is fine: editing YAML + sync is the supported path. The worker daemon
also best-effort syncs after each run. The Slack orchestrator syncs after plan
create/update and after approve (`planning` → `proposed`).
