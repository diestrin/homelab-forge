# GitHub Projects mirror

**Board:** [homelab-forge factory](https://github.com/users/diestrin/projects/1)  
**Owner / number:** `diestrin` / `1`  
**Project id:** `PVT_kwHOAA3gD84Bfo-B`  
**Status field id:** `PVTSSF_lAHOAA3gD84Bfo-BzhZ6dSI`

Linked to repo `diestrin/homelab-forge`. Visibility: **public**.

## Column ↔ task status

| Git status | Projects Status option | Option id |
| --- | --- | --- |
| `proposed` | Proposed | `f75ad846` |
| `claimed` | Claimed | `ce587ea2` |
| `in_progress` | In Progress | `47fc9ee4` |
| `review` | Review | `db289240` |
| `done` | Done | `98236657` |
| `failed` | Failed | `7e7241b8` |

## Sync convention

- **Git wins.** Task YAML under `factory/tasks/` is authoritative.
- Mirror with `./forge factory sync` (wrapper around `factory/scripts/sync-projects.sh`).
- Sync creates draft items when `github_project_item_id` is null, writes the id back
  into the YAML, and updates Status to match git.
- If the board drifts, re-run sync; do **not** edit task status only on the board.

Manual v1 is fine: editing YAML + sync is the supported path. The worker daemon
also best-effort syncs after each run.
