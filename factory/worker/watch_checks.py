#!/usr/bin/env python3
"""Watch GitHub checks on a factory PR until green or budget expires (TASK-011).

Runs as a claimed `watch-checks` job. On red checks it asks the control plane
to enqueue a fix implement run on the same branch/PR (then a re-watch), so the
operator never has to paste "CI is failing" into Slack. Slack is notified only
when green, when fix retries are exhausted, or on watch timeout.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "factory" / "scripts"))

import control_plane_client as cp  # noqa: E402
from host_secrets import load_vault_secrets  # noqa: E402
from redact import redact_text  # noqa: E402
from sdk_session import log  # noqa: E402

GITHUB_REPO = "diestrin/homelab-forge"

GREEN = {"SUCCESS", "NEUTRAL", "SKIPPED"}
RED = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def resolve_pr_url(task: dict, branch: str, meta: dict) -> str:
    if meta.get("pr_url"):
        return str(meta["pr_url"])
    for art in task.get("artifacts") or []:
        if art.get("kind") == "pr" and art.get("url"):
            return str(art["url"])
    proc = _run(["gh", "pr", "view", branch, "--repo", GITHUB_REPO, "--json", "url", "-q", ".url"])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def poll_checks(pr_url: str) -> tuple[str, list[dict]]:
    """Returns (state, failed_checks). state: green|red|pending|unknown."""
    proc = _run(["gh", "pr", "view", pr_url, "--repo", GITHUB_REPO, "--json", "statusCheckRollup"])
    if proc.returncode != 0:
        return "unknown", []
    try:
        rollup = json.loads(proc.stdout).get("statusCheckRollup") or []
    except json.JSONDecodeError:
        return "unknown", []
    if not rollup:
        return "pending", []
    failed: list[dict] = []
    pending = False
    for check in rollup:
        status = str(check.get("status") or "").upper()
        conclusion = str(check.get("conclusion") or "").upper()
        name = str(check.get("name") or check.get("context") or "check")
        if status and status != "COMPLETED":
            pending = True
            continue
        if conclusion in RED:
            failed.append({"name": name, "link": str(check.get("detailsUrl") or check.get("targetUrl") or "")})
        elif conclusion and conclusion not in GREEN:
            pending = True
    if failed:
        return "red", failed
    if pending:
        return "pending", []
    return "green", []


def failure_summary(pr_url: str, failed: list[dict]) -> str:
    lines = [f"- {f['name']}: {f['link']}" for f in failed]
    checks = _run(["gh", "pr", "checks", pr_url, "--repo", GITHUB_REPO])
    excerpt = (checks.stdout or "")[-2000:]
    return redact_text("\n".join(lines) + ("\n\n" + excerpt if excerpt else ""))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--job-id", default=None)
    p.add_argument("--meta", default="{}")
    args = p.parse_args()
    task_id = args.task_id
    try:
        meta = json.loads(args.meta or "{}")
    except json.JSONDecodeError:
        meta = {}
    attempt = int(meta.get("attempt") or 0)
    max_fixes = int(os.environ.get("FORGE_CI_FIX_ATTEMPTS", "2"))
    poll_seconds = int(os.environ.get("FORGE_CI_POLL_SECONDS", "60"))
    timeout_minutes = int(os.environ.get("FORGE_CI_WATCH_TIMEOUT_MINUTES", "45"))

    try:
        task = cp.get_task(task_id)
    except cp.ControlPlaneError as err:
        log(task_id, f"watch: get_task failed: {err}")
        return 1

    branch = str(task.get("branch") or f"factory/{task_id.lower()}")
    load_vault_secrets(task_id, need_cursor=False)
    pr_url = resolve_pr_url(task, branch, meta)
    if not pr_url:
        log(task_id, "watch: no PR to watch — nothing to do")
        return 0

    log(task_id, f"watch start pr={pr_url} attempt={attempt} timeout={timeout_minutes}m poll={poll_seconds}s")
    deadline = time.monotonic() + timeout_minutes * 60

    while True:
        state, failed = poll_checks(pr_url)
        log(task_id, f"watch poll pr={pr_url} state={state} failed={len(failed)}")

        if state == "green":
            try:
                cp.append_message(task_id, "system", f"CI green on {pr_url}", author="watch-checks")
                cp.notify(
                    task_id,
                    f"✅ CI green on {pr_url} for `{task_id}`.\n"
                    "Next step: human review + merge (ADR-008 — the factory never merges).",
                )
            except cp.ControlPlaneError as err:
                log(task_id, f"watch: notify failed: {err}")
            return 0

        if state == "red":
            summary = failure_summary(pr_url, failed)
            names = ", ".join(f["name"] for f in failed)
            if attempt >= max_fixes:
                try:
                    cp.append_message(
                        task_id, "system",
                        f"CI still red on {pr_url} after {attempt} fix attempt(s): {names}",
                        author="watch-checks",
                    )
                    cp.notify(
                        task_id,
                        f"❌ CI still failing on {pr_url} for `{task_id}` after {attempt} automated fix "
                        f"attempt(s): {names}\nOperator attention needed.",
                    )
                except cp.ControlPlaneError as err:
                    log(task_id, f"watch: notify failed: {err}")
                return 0
            # Enqueue a fix run on the same branch/PR + re-watch after it pushes.
            # Task message only — Slack is not pinged for intermediate attempts.
            try:
                cp.append_message(
                    task_id, "system",
                    f"CI red on {pr_url} ({names}); enqueued fix run attempt {attempt + 1}/{max_fixes}.",
                    author="watch-checks",
                )
                cp.enqueue_job(
                    task_id,
                    "implement",
                    {
                        "fix": True,
                        "fix_context": summary,
                        "pr_url": pr_url,
                        "watch_attempt": attempt + 1,
                    },
                )
            except cp.ControlPlaneError as err:
                log(task_id, f"watch: fix enqueue failed: {err}")
                return 1
            log(task_id, f"watch: fix run enqueued attempt={attempt + 1} checks={names}")
            return 0

        if time.monotonic() > deadline:
            try:
                cp.append_message(
                    task_id, "system",
                    f"CI watch timed out after {timeout_minutes}m on {pr_url} (state={state}).",
                    author="watch-checks",
                )
                cp.notify(
                    task_id,
                    f"⏱ CI watch for `{task_id}` timed out after {timeout_minutes}m on {pr_url} "
                    f"(last state: {state}). Operator attention needed.",
                )
            except cp.ControlPlaneError as err:
                log(task_id, f"watch: notify failed: {err}")
            return 0

        time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
