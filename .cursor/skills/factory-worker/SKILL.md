---
name: factory-worker
description: Claim and implement a homelab-forge factory task interactively. Use when asked to work on, claim, implement, or finish a TASK-NNN from factory/tasks/, or to attach to a branch a worker prepared. The systemd worker daemon handles hook-scripted tasks; this skill covers Cursor-driven implementation.
---

# Factory worker

Read and follow `factory/worker/PLAYBOOK.md` — it is the source of truth
(lifecycle, Vault AppRole login, artifact conventions, daemon env).

## Hard rules

1. Work inside an `agent-cell` sandbox by default (`./forge factory claim`,
   `factory/worker/run-task.sh`). Concurrent tasks are allowed with separate
   worktrees (`FORGE_WORKER_CONCURRENCY`, ADR-011); never run two jobs on the
   same task at once, and never mount the host Docker socket, `$HOME`, or
   sibling project trees.
2. Secrets come from Vault AppRole `forge-agent`
   (`factory/scripts/vault-agent-login.sh`); GitHub identity is a minted App
   installation token (`factory/scripts/github-app-token.sh`). Never write tokens to
   the repo or task YAML.
3. `kubectl diff` only for artifacts — never `kubectl apply` Argo-managed apps.
4. Write artifacts under `/media/diestrin/data/forge/factory/artifacts/`, set
   `status: review` with the PR link, and stop. Never merge autonomously.
