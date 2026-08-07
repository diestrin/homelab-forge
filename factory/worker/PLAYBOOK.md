# Worker playbook

Workers execute **one task at a time** inside sandboxes (ADR-002 L4 `agent-cell` by
default). Secrets come from Vault AppRole `forge-agent` (ADR-007). Cluster deploys
happen only after merge via Argo CD (ADR-008).

## Lifecycle

1. **Claim** — `status: proposed → claimed` (`./forge factory claim` or daemon).
2. **Cell** — provision agent-cell / worktree (`factory/worker/run-task.sh`).
3. **Secrets** — AppRole login; read `secret/forge/agents/*` (e.g. `github` token).
4. **Implement** — run `worker_hook` if set; else leave branch ready for attach.
5. **Verify** — tests / acceptance notes; write artifacts under
   `/media/diestrin/data/forge/factory/artifacts/`.
6. **Hand off** — `status: review` + PR link; never merge autonomously.
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
| `VAULT_ADDR` | `http://127.0.0.1:8200` | requires port-forward / local access |
| `FORGE_APPROLE_ENV` | `…/approle-forge-agent.env` | role_id + secret_id |

## Isolation rules

- No host Docker socket in agent-cells.
- No bind-mount of `$HOME` or sibling project trees.
- Do not `kubectl apply` Argo-managed apps; `kubectl diff` only for artifacts.
- Time budget from `budget_minutes` → auto `failed` + cleanup.
