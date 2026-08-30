#!/usr/bin/env python3
"""Cursor SDK planner for factory plan jobs (ADR-009 / ADR-011, TASK-011).

Modes:
  create  — draft task YAML + short plan markdown from an operator request
  update  — revise existing task YAML + plan given thread feedback

The branch is pinned by the control plane at intake and passed in; the planner
must never invent or rewrite it (TASK-009 #16→#19 / TASK-010 #18→#20 regression).
Runs stream a redacted transcript to the control plane agent_runs record.
Does not push or open PRs (the plan job runner does).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sdk_session import SdkSession, SdkStartupError, log, runtime_card  # noqa: E402

CREATE_PROMPT = """{runtime_card}
You are the homelab-forge factory orchestrator (ADR-004 / ADR-009) in PLAN mode.

Given the operator request below, produce TWO files in the working directory:
1) factory/tasks/{task_id}-{slug}.yaml — a valid factory task with:
   - id: {task_id}
   - status: planning  (NOT proposed — workers must not claim yet)
   - clear goal + measurable acceptance_criteria
   - sandbox_profile + risk_level from the orchestrator playbook table
   - repo_path: .
   - budget_minutes (default 30, raise if needed)
   - branch: {branch}   ← copy EXACTLY; this is pinned by the control plane
   - worker_hook: null
   - notes: capture decisions; mention the Slack thread iterates the plan
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

UPDATE_PROMPT = """{runtime_card}
You are the homelab-forge factory orchestrator updating an existing plan (PLAN mode).

Task id: {task_id}
Revise factory/tasks/{task_file} and factory/plans/{task_id}.md according to the
operator feedback below. Keep status: planning. Keep branch: {branch} exactly as it is.
Do not implement the feature. No secrets in files.

Feedback:
---
{feedback}
---
"""


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "request").strip("-")


def write_fallback_create(repo: Path, task_id: str, request: str, slug: str, branch: str) -> Path:
    """Deterministic stub when SDK unavailable — still schema-valid planning task."""
    tasks = repo / "factory" / "tasks"
    plans = repo / "factory" / "plans"
    tasks.mkdir(parents=True, exist_ok=True)
    plans.mkdir(parents=True, exist_ok=True)
    path = tasks / f"{task_id}-{slug}.yaml"
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
  Created by plan-job fallback (Cursor SDK unavailable).
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
    log(task_id, f"fallback plan files written: {path.name}")
    return path


def enforce_pinned_branch(repo: Path, task_id: str, branch: str) -> None:
    """Rewrite the branch field back to the pin if the planner changed it."""
    import yaml  # type: ignore

    for path in (repo / "factory" / "tasks").glob("TASK-*.yaml"):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if doc.get("id") != task_id:
            continue
        if str(doc.get("branch") or "") != branch:
            log(task_id, f"planner rewrote branch to {doc.get('branch')!r} — restoring pin {branch}")
            doc["branch"] = branch
            path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")


def run_plan(
    mode: str,
    repo: Path,
    task_id: str,
    branch: str,
    request: str = "",
    feedback: str = "",
    task_file: str = "",
    worker_id: str | None = None,
    job_id: str | None = None,
    sandbox_profile: str = "agent-cell",
    allow_fallback: bool = False,
    lint_attempts: int = 2,
) -> tuple[int, str | None]:
    """Run the planner. Returns (exit code, blocked reason or None)."""
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    model = os.environ.get("FORGE_CURSOR_MODEL", "composer-2.5")
    slug = slugify(request or task_id)
    card = runtime_card("plan", sandbox_profile, branch)

    if mode == "create":
        prompt = CREATE_PROMPT.format(
            runtime_card=card, task_id=task_id, slug=slug, branch=branch, request=request
        )
    else:
        if not task_file:
            log(task_id, "plan update requires task_file")
            return 1, None
        prompt = UPDATE_PROMPT.format(
            runtime_card=card, task_id=task_id, task_file=task_file, branch=branch, feedback=feedback
        )

    if not api_key:
        if mode == "create" and allow_fallback:
            write_fallback_create(repo, task_id, request, slug, branch)
            return 0, None
        log(task_id, "CURSOR_API_KEY missing")
        return 1, None

    try:
        with SdkSession(
            task_id,
            "plan",
            str(repo),
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
                return 2, blocked
            if status == "error":
                return 2, None
            enforce_pinned_branch(repo, task_id, branch)
            if not session.ensure_lint_clean(str(repo), attempts=lint_attempts):
                return 3, "lint failures remain after fix attempts"
            enforce_pinned_branch(repo, task_id, branch)
    except SdkStartupError as err:
        if mode == "create" and allow_fallback:
            write_fallback_create(repo, task_id, request, slug, branch)
            return 0, None
        log(task_id, f"planner startup failed: {err}")
        return 1, None
    return 0, None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("create", "update"))
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--branch", required=True, help="pinned branch from the control plane")
    p.add_argument("--request", default="")
    p.add_argument("--feedback", default="")
    p.add_argument("--task-file", default="")
    p.add_argument("--worker-id", default=None)
    p.add_argument("--job-id", default=None)
    p.add_argument("--sandbox-profile", default="agent-cell")
    p.add_argument("--allow-fallback", action="store_true")
    args = p.parse_args()

    rc, blocked = run_plan(
        args.mode,
        args.repo.resolve(),
        args.task_id,
        args.branch,
        request=args.request,
        feedback=args.feedback,
        task_file=args.task_file,
        worker_id=args.worker_id,
        job_id=args.job_id,
        sandbox_profile=args.sandbox_profile,
        allow_fallback=args.allow_fallback,
    )
    if blocked:
        print(f"cursor_plan: blocked: {blocked}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
