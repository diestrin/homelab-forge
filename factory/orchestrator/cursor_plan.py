#!/usr/bin/env python3
"""Cursor SDK helper for Slack orchestrator plan create/update (ADR-009).

Modes:
  create  — draft task YAML + short plan markdown from a Slack prompt
  update  — revise existing task YAML + plan given thread feedback

Writes files under --out-dir. Does not push or open PRs (caller does).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


CREATE_PROMPT = """You are the homelab-forge factory orchestrator (ADR-004 / ADR-009).

Given the operator Slack request below, produce TWO files in the working directory:
1) factory/tasks/{task_id}-{slug}.yaml — a valid factory task with:
   - id: {task_id}
   - status: planning  (NOT proposed — workers must not claim yet)
   - clear goal + measurable acceptance_criteria
   - sandbox_profile + risk_level from the orchestrator playbook table
   - repo_path: .
   - budget_minutes (default 30, raise if needed)
   - branch: factory/{task_id_lower}-{slug}
   - worker_hook: null
   - notes: capture Slack-derived decisions; mention Slack thread will iterate the plan
2) factory/plans/{task_id}.md — a short plan for the PR body (what/why/how, risks, out of scope).

Hard rules:
- Do not implement the feature itself.
- Do not put secrets, tokens, real Slack user IDs, or private ntfy topics in files.
- High-risk host intents (SSH/UFW/Vault unseal/disable host-watch/force-push/kubectl apply
  to Argo apps) must keep risk_level: high and notes saying human-only / do not auto-approve.
- Follow factory/orchestrator/PLAYBOOK.md intent → profile/risk table.
- Remind in the plan that merge to main → Argo CD is the only steady-state deploy path.

Operator request:
---
{request}
---
"""

UPDATE_PROMPT = """You are the homelab-forge factory orchestrator updating an existing plan.

Task id: {task_id}
Revise factory/tasks/{task_file} and factory/plans/{task_id}.md according to the
operator feedback below. Keep status: planning. Do not implement the feature.
No secrets in files.

Feedback:
---
{feedback}
---
"""


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "request").strip("-")


def run_sdk(prompt: str, cwd: str, api_key: str, model: str) -> int:
    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions, CursorAgentError
    except ImportError:
        print("cursor_plan: cursor-sdk not installed", file=sys.stderr)
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
        print(f"cursor_plan: startup failed: {err}", file=sys.stderr)
        return 1
    status = getattr(result, "status", None)
    if status == "error":
        print(f"cursor_plan: run failed id={getattr(result, 'id', '?')}", file=sys.stderr)
        return 2
    return 0


def write_fallback_create(
    repo: Path, task_id: str, request: str, slug: str
) -> Path:
    """Deterministic stub when SDK unavailable — still produces schema-valid planning task."""
    tasks = repo / "factory" / "tasks"
    plans = repo / "factory" / "plans"
    tasks.mkdir(parents=True, exist_ok=True)
    plans.mkdir(parents=True, exist_ok=True)
    branch = f"factory/{task_id.lower()}-{slug}"
    path = tasks / f"{task_id}-{slug}.yaml"
    # Quote multiline fields safely
    goal = request.strip().replace("'", "''")
    path.write_text(
        f"""id: {task_id}
title: '{goal[:72]}'
goal: |
  {goal}
acceptance_criteria:
- Plan refined via Slack thread and approved before worker claim
- Implementation lands on the plan PR after Cursor SDK worker run
- No secrets in git; merge remains human-gated (ADR-008)
sandbox_profile: agent-cell
repo_path: .
status: planning
assignee_agent: null
artifacts: []
risk_level: medium
budget_minutes: 60
branch: {branch}
worker_hook: null
notes: |
  Created by Slack orchestrator fallback (Cursor SDK unavailable).
  Operator should refine via Slack thread before approve.
claimed_at: null
updated_at: null
""",
        encoding="utf-8",
    )
    plan = plans / f"{task_id}.md"
    plan.write_text(
        f"""# {task_id} plan

## Request

{request.strip()}

## Approach

(Refine in Slack thread — this stub was written without Cursor SDK.)

## Out of scope

- Silent prod deploy / kubectl apply to Argo apps
- Merge from Slack

## Deploy

After human merge to `main`, Argo CD syncs (ADR-008).
""",
        encoding="utf-8",
    )
    print(path)
    return path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("create", "update"))
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--request", default="")
    p.add_argument("--feedback", default="")
    p.add_argument("--task-file", default="")
    p.add_argument("--allow-fallback", action="store_true")
    args = p.parse_args()

    repo = args.repo.resolve()
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    model = os.environ.get("FORGE_CURSOR_MODEL", "composer-2.5")
    slug = slugify(args.request or args.task_id)

    if args.mode == "create":
        prompt = CREATE_PROMPT.format(
            task_id=args.task_id,
            task_id_lower=args.task_id.lower(),
            slug=slug,
            request=args.request,
        )
        if not api_key:
            if args.allow_fallback:
                write_fallback_create(repo, args.task_id, args.request, slug)
                return 0
            print("cursor_plan: CURSOR_API_KEY missing", file=sys.stderr)
            return 1
        rc = run_sdk(prompt, str(repo), api_key, model)
        if rc != 0 and args.allow_fallback:
            write_fallback_create(repo, args.task_id, args.request, slug)
            return 0
        return rc

    # update
    if not args.task_file:
        print("cursor_plan: --task-file required for update", file=sys.stderr)
        return 1
    prompt = UPDATE_PROMPT.format(
        task_id=args.task_id,
        task_file=args.task_file,
        feedback=args.feedback,
    )
    if not api_key:
        print("cursor_plan: CURSOR_API_KEY missing (update requires SDK)", file=sys.stderr)
        return 1
    return run_sdk(prompt, str(repo), api_key, model)


if __name__ == "__main__":
    raise SystemExit(main())
