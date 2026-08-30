# Worker playbook

Workers claim **jobs** (plan, implement, watch-checks) from the control plane
queue and run up to `FORGE_WORKER_CONCURRENCY` of them in parallel — separate
worktrees per task; same-task jobs serialize on a lock (ADR-011 supersedes the
old "one task at a time" rule). Secrets come from Vault AppRole `forge-agent`
(ADR-007). Cluster deploys happen only after merge via Argo CD (ADR-008).
Implementation runtime is **Cursor SDK** by default (ADR-009); scripted
`worker_hook` remains for demos.

## Lifecycle

1. **Claim** — `POST /api/v1/jobs/claim` with `kinds: [plan, implement, watch-checks]`
   (daemon). Tasks in `planning` are **not** implement-claimable (Slack plan gate);
   plan jobs serve them instead.
2. **Cell / worktree** — provision worktree (`factory/worker/run-task.sh`, plan
   jobs via `factory/orchestrator/run_plan_job.py`) on the **DB-pinned branch**
   (`tasks.branch`). Never rename or re-slug the branch (TASK-011).
3. **Secrets** — AppRole login; mint GitHub App **installation token** from
   `secret/forge/agents/github`; load Cursor API key from
   `secret/forge/agents/cursor` (`factory/scripts/fetch-cursor-key.sh`).
4. **Implement** — if `worker_hook` set, run it (optionally in `agent-cell`);
   else run `factory/worker/cursor_implement.py` (Cursor SDK `Agent.create` +
   streamed transcript into the control plane `agent_runs` record). Prompts
   carry the runtime card (role, sandbox, no TTY, no host sudo/apt, ADR-002).
   If no SDK key and `FORGE_SKIP_CURSOR_SDK=1`, leave branch ready for attach
   (legacy).
5. **Lint** — before every push, `factory/scripts/lint-local.sh` (the CI checks
   that need no GitHub secrets: markdownlint-cli2, factory schema, shellcheck,
   actionlint, kubeconform). SDK runs fix findings in the same conversation.
6. **Verify / hand off** — push to the pinned branch; **reuse** the pinned PR
   (artifact `kind: pr` / open PR on the branch) — `gh pr create` only when
   none exists. Artifacts under `/media/diestrin/data/forge/factory/artifacts/`.
   Set `status: review` with the PR link; never merge autonomously.
7. **CI watch** — after push the worker enqueues a `watch-checks` job; the watch
   polls GitHub checks and enqueues fix runs on the same branch/PR until green,
   retries exhausted, or timeout. Slack hears only terminal states (via the
   control plane notify queue — workers never post to Slack directly; failures
   go through `POST /api/v1/tasks/{id}/notify`).
8. **Cleanup** — remove cell; budget watchdog auto-fails and cleans up.

## Artifact conventions

| Kind | Where |
| --- | --- |
| `pr` | URL on artifact + `*-pr.txt` — **pinned**: one PR per task |
| `log` | `/media/diestrin/data/forge/factory/artifacts/logs/TASK-NNN.log` |
| `kubectl_diff` | dry-run diff only — **never apply** |
| `note` | freeform markdown for attach/await states |

SDK conversation transcripts are **not** file artifacts — they live in the
`agent_runs` table (redacted) and render on the dashboard task page.

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
| `FORGE_WORKER_CONCURRENCY` | `2` | parallel job slots (plan/implement/watch) |
| `FORGE_SKIP_VAULT` | `0` | set `1` to skip AppRole |
| `FORGE_SKIP_CURSOR_SDK` | `0` | set `1` to force attach-only when no hook |
| `FORGE_CURSOR_MODEL` | `composer-2.5` | Cursor SDK model id |
| `FORGE_LINT_FIX_ATTEMPTS` | `2` | in-run lint fix follow-ups |
| `FORGE_CI_FIX_ATTEMPTS` | `2` | CI-red fix runs per PR |
| `FORGE_CI_POLL_SECONDS` | `60` | checks poll interval |
| `FORGE_CI_WATCH_TIMEOUT_MINUTES` | `45` | watch budget per job |
| `VAULT_ADDR` | `http://127.0.0.1:8200` | requires port-forward / local access |
| `FORGE_APPROLE_ENV` | `…/approle-forge-agent.env` | role_id + secret_id |

Host venv should include `cursor-sdk` (see `factory/orchestrator/requirements.txt`);
`markdownlint-cli2` must be installed for the lint gate (`npm i -g markdownlint-cli2`).

## Isolation rules

- No host Docker socket in agent-cells.
- No bind-mount of `$HOME` or sibling project trees.
- Cursor SDK runs **on the host** with `cwd` = task worktree (local runtime).
- If the task branch is already checked out (operator Cursor clone), the worker
  uses a detached worktree and pushes with `HEAD:refs/heads/<branch>`. The
  orchestrator must not `git checkout` plan branches in the operator clone.
- Do not `kubectl apply` Argo-managed apps; `kubectl diff` only for artifacts.
- Time budget from `budget_minutes` → auto `failed` + cleanup.
