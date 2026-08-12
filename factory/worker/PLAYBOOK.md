# Worker playbook

Workers execute **one task at a time**. Secrets come from Vault AppRole
`forge-agent` (ADR-007). Cluster deploys happen only after merge via Argo CD
(ADR-008). Implementation runtime is **Cursor SDK** by default (ADR-009);
scripted `worker_hook` remains for demos.

## Lifecycle

1. **Claim** — `status: proposed → claimed` (`./forge factory claim` or daemon).
   Tasks in `planning` are **not** claimable (Slack plan gate).
2. **Cell / worktree** — provision worktree (`factory/worker/run-task.sh`).
3. **Secrets** — AppRole login; mint GitHub App **installation token** from
   `secret/forge/agents/github`; load Cursor API key from
   `secret/forge/agents/cursor` (`factory/scripts/fetch-cursor-key.sh`).
4. **Implement** — if `worker_hook` set, run it (optionally in `agent-cell`);
   else run `factory/worker/cursor_implement.py` (Cursor SDK local agent against
   the worktree). If no SDK key and `FORGE_SKIP_CURSOR_SDK=1`, leave branch ready
   for attach (legacy).
5. **Verify** — tests / acceptance notes; write artifacts under
   `/media/diestrin/data/forge/factory/artifacts/`.
6. **Hand off** — push to the existing plan branch/PR when present; set
   `status: review` with the PR link; never merge autonomously. Slack orchestrator
   may notify the thread.
7. **Cleanup** — remove cell; budget watchdog auto-fails and cleans up.

## Artifact conventions

| Kind | Where |
| --- | --- |
| `pr` | URL on artifact + `*-pr.txt` |
| `log` | `/media/diestrin/data/forge/factory/artifacts/logs/TASK-NNN.log` |
| `kubectl_diff` | dry-run diff only — **never apply** |
| `note` | freeform markdown for attach/await states |

## Daemon (1B)

```bash
# foreground once
./forge factory worker --once

# loop
./forge factory worker

# user systemd
systemctl --user enable --now forge-factory-worker.service
# unit file: factory/systemd/forge-factory-worker.service
# install: mkdir -p ~/.config/systemd/user && cp factory/systemd/forge-factory-worker.service ~/.config/systemd/user/
```

Env:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FORGE_WORKER_ID` | `worker-<host>` | assignee stamp |
| `FORGE_WORKER_POLL_SECONDS` | `30` | idle poll |
| `FORGE_SKIP_VAULT` | `0` | set `1` to skip AppRole |
| `FORGE_SKIP_CURSOR_SDK` | `0` | set `1` to force attach-only when no hook |
| `FORGE_CURSOR_MODEL` | `composer-2.5` | Cursor SDK model id |
| `VAULT_ADDR` | `http://127.0.0.1:8200` | requires port-forward / local access |
| `FORGE_APPROLE_ENV` | `…/approle-forge-agent.env` | role_id + secret_id |

Host venv should include `cursor-sdk` (see `factory/orchestrator/requirements.txt`).

## Isolation rules

- No host Docker socket in agent-cells.
- No bind-mount of `$HOME` or sibling project trees.
- Cursor SDK runs **on the host** with `cwd` = task worktree (local runtime).
- If the task branch is already checked out (operator Cursor clone), the worker
  uses a detached worktree and pushes with `HEAD:refs/heads/<branch>`. The
  orchestrator must not `git checkout` plan branches in the operator clone.
- Do not `kubectl apply` Argo-managed apps; `kubectl diff` only for artifacts.
- Time budget from `budget_minutes` → auto `failed` + cleanup.
