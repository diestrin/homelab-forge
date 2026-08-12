#!/usr/bin/env python3
"""Run a Cursor SDK local agent to implement a factory task (ADR-009).

Expects env:
  CURSOR_API_KEY   — from Vault secret/forge/agents/cursor
  FORGE_TASK_REPO  — worktree path (cwd for local agent)
  FORGE_TASK_ID, FORGE_TASK_TITLE, FORGE_TASK_GOAL, FORGE_TASK_AC, FORGE_TASK_BRANCH

Exit codes: 0 ok, 1 startup/config failure, 2 run failed mid-flight.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def build_prompt() -> str:
    task_id = os.environ.get("FORGE_TASK_ID", "TASK-???")
    title = os.environ.get("FORGE_TASK_TITLE", "")
    goal = os.environ.get("FORGE_TASK_GOAL", "")
    ac = os.environ.get("FORGE_TASK_AC", "")
    branch = os.environ.get("FORGE_TASK_BRANCH", "")
    return f"""You are the homelab-forge factory worker implementing {task_id}.

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
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        print("cursor_implement: CURSOR_API_KEY missing", file=sys.stderr)
        return 1

    cwd = os.environ.get("FORGE_TASK_REPO") or os.getcwd()
    if not Path(cwd).is_dir():
        print(f"cursor_implement: bad cwd {cwd}", file=sys.stderr)
        return 1

    model = os.environ.get("FORGE_CURSOR_MODEL", "composer-2.5")
    prompt = build_prompt()

    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions, CursorAgentError
    except ImportError:
        print(
            "cursor_implement: cursor-sdk not installed "
            "(pip install -r factory/orchestrator/requirements.txt)",
            file=sys.stderr,
        )
        return 1

    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=cwd),
            ),
        )
    except CursorAgentError as err:
        print(
            f"cursor_implement: startup failed: {err} "
            f"retryable={getattr(err, 'is_retryable', None)}",
            file=sys.stderr,
        )
        return 1
    except Exception as err:  # noqa: BLE001 — surface any SDK blow-up
        print(f"cursor_implement: error: {err}", file=sys.stderr)
        return 1

    status = getattr(result, "status", None)
    if status == "error":
        print(f"cursor_implement: run failed id={getattr(result, 'id', '?')}", file=sys.stderr)
        return 2

    text = getattr(result, "result", None) or getattr(result, "text", None) or ""
    if text:
        print(text)
    print(f"cursor_implement: ok status={status}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
