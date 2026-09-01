#!/usr/bin/env python3
"""Run a Cursor SDK local agent to implement a factory task (ADR-009 / TASK-011).

Streams a redacted conversation transcript to the control plane agent_runs
record, injects the runtime card, and fixes local lint findings in the same
run before handing back to run-task.sh for commit/push/PR.

Expects env:
  CURSOR_API_KEY   — from Vault secret/forge/agents/cursor
  FORGE_TASK_REPO  — worktree path (cwd for local agent)
  FORGE_TASK_ID, FORGE_TASK_TITLE, FORGE_TASK_GOAL, FORGE_TASK_AC, FORGE_TASK_BRANCH
  FORGE_TASK_PROFILE           — sandbox profile for the runtime card
  FORGE_TASK_FIX_CONTEXT       — optional CI failure summary (fix run)
  FORGE_JOB_ID / FORGE_WORKER_ID — observability metadata

Exit codes: 0 ok, 1 startup/config failure, 2 run failed mid-flight,
3 blocked (agent reported FORGE_BLOCKED), 4 lint failures remain.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sdk_session import SdkSession, SdkStartupError, log, runtime_card  # noqa: E402


def build_prompt(branch: str, profile: str) -> str:
    task_id = os.environ.get("FORGE_TASK_ID", "TASK-???")
    title = os.environ.get("FORGE_TASK_TITLE", "")
    goal = os.environ.get("FORGE_TASK_GOAL", "")
    ac = os.environ.get("FORGE_TASK_AC", "")
    fix_context = os.environ.get("FORGE_TASK_FIX_CONTEXT", "").strip()

    if fix_context:
        return f"""{runtime_card("implement", profile, branch)}
You are the homelab-forge factory worker FIXING CI failures on {task_id} ({title}).

The PR for this task has failing GitHub checks. Fix them on this branch —
do not start over, do not open a new PR, do not change unrelated code.

Failing checks (redacted summary):
---
{fix_context}
---

Hard rules:
- Follow AGENTS.md, PLAN.md, and ADRs. Public repo: no secrets in git.
- Do not kubectl apply Argo-managed apps; do not merge to main; do not force-push.
- When done, leave a clean git working tree with commits on this branch.
"""

    return f"""{runtime_card("implement", profile, branch)}
You are the homelab-forge factory worker implementing {task_id}.

Title: {title}

Goal:
{goal}

Acceptance criteria:
{ac}

Working branch: {branch}
Repo cwd is already the task worktree. Implement the change fully.

Hard rules:
- Follow AGENTS.md, PLAN.md, and ADRs. Public repo: no secrets in git.
- Do not kubectl apply Argo-managed apps; do not merge to main; do not force-push.
- Do not disable UFW/host-watch. Steady-state deploys are merge → Argo CD (ADR-008).
- Prefer reversible, documented changes. Update playbooks/runbooks when contracts change.
- When done, leave a clean git working tree with commits on this branch.
"""


def main() -> int:
    task_id = os.environ.get("FORGE_TASK_ID", "TASK-???")
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        log(task_id, "cursor_implement: CURSOR_API_KEY missing")
        return 1

    cwd = os.environ.get("FORGE_TASK_REPO") or os.getcwd()
    if not Path(cwd).is_dir():
        log(task_id, f"cursor_implement: bad cwd {cwd}")
        return 1

    model = os.environ.get("FORGE_CURSOR_MODEL", "composer-2.5")
    branch = os.environ.get("FORGE_TASK_BRANCH", "")
    profile = os.environ.get("FORGE_TASK_PROFILE", "agent-cell")
    worker_id = os.environ.get("FORGE_WORKER_ID")
    job_id = os.environ.get("FORGE_JOB_ID")
    kind = "fix" if os.environ.get("FORGE_TASK_FIX_CONTEXT", "").strip() else "implement"
    prompt = build_prompt(branch, profile)

    try:
        with SdkSession(
            task_id,
            kind,
            cwd,
            api_key,
            model,
            worker_id=worker_id,
            branch=branch,
            job_id=job_id,
        ) as session:
            status = session.send(prompt)
            blocked = session.blocked_reason()
            if blocked:
                session.finish("error", error=f"agent blocked: {blocked}")
                log(task_id, f"cursor_implement: blocked: {blocked}")
                return 3
            if status == "error":
                log(task_id, "cursor_implement: run failed mid-flight")
                return 2
            # Lint gate before push: same checks CI runs; fixed in the same run.
            attempts = int(os.environ.get("FORGE_LINT_FIX_ATTEMPTS", "2"))
            if not session.ensure_lint_clean(cwd, attempts=attempts):
                log(task_id, "cursor_implement: lint failures remain after fix attempts")
                return 4
            if session.last_text:
                print(session.last_text)
    except SdkStartupError as err:
        log(task_id, f"cursor_implement: startup failed: {err}")
        return 1
    except Exception as err:  # noqa: BLE001 — surface any SDK blow-up
        log(task_id, f"cursor_implement: error: {err}")
        return 1

    log(task_id, "cursor_implement: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
