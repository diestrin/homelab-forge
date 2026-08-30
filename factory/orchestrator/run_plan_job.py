#!/usr/bin/env python3
"""Execute a claimed `plan` job from the control plane queue (TASK-011).

The Slack Socket Mode client only records intent; this runner (dispatched by
the worker daemon) does the heavy lifting on the host:
  worktree → Cursor SDK planner (transcript persisted) → lint → push pinned
  branch → open-or-reuse the single plan PR → notify via control plane.

Job meta (from POST /api/v1/slack/intake): mode, request|feedback,
channel_id, thread_ts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "factory" / "scripts"))

import control_plane_client as cp  # noqa: E402
from host_secrets import load_vault_secrets  # noqa: E402
from redact import redact_text  # noqa: E402
from sdk_session import log  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cursor_plan import run_plan  # noqa: E402

GITHUB_REPO = "diestrin/homelab-forge"


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc


def log_cmd(task_id: str, cmd: list[str], proc: subprocess.CompletedProcess[str]) -> None:
    log(task_id, f"cmd={' '.join(cmd[:4])}… exit={proc.returncode}")
    if proc.returncode != 0:
        log(task_id, f"cmd stderr: {redact_text((proc.stderr or proc.stdout or '')[-800:])}")


def ensure_worktree(task_id: str, branch: str) -> Path:
    root = Path(os.environ.get("FORGE_DATA_ROOT", "/media/diestrin/data/forge"))
    wt = root / "factory" / "worktrees" / task_id
    helper = REPO_ROOT / "factory" / "scripts" / "add-task-worktree.sh"
    base = "origin/main"
    chk = run(["git", "rev-parse", "--verify", f"origin/{branch}"], cwd=REPO_ROOT)
    if chk.returncode == 0:
        base = f"origin/{branch}"
    proc = run(["bash", str(helper), str(REPO_ROOT), str(wt), branch, base])
    if proc.returncode != 0:
        raise RuntimeError(f"worktree add failed: {proc.stderr or proc.stdout}")
    return wt


def existing_pr_url(task: dict, branch: str, cwd: Path) -> str:
    """Pinned PR lookup: task artifact first, then an open PR on the branch."""
    for art in task.get("artifacts") or []:
        if art.get("kind") == "pr" and art.get("url"):
            return str(art["url"])
    proc = run(
        [
            "gh", "pr", "view", branch,
            "--repo", GITHUB_REPO,
            "--json", "url,state",
        ],
        cwd=cwd,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
            if data.get("state") == "OPEN" and data.get("url"):
                return str(data["url"])
        except json.JSONDecodeError:
            pass
    return ""


def push_branch(task_id: str, wt: Path, branch: str) -> bool:
    run(["git", "add", "factory/tasks", "factory/plans"], cwd=wt)
    status = run(["git", "status", "--porcelain"], cwd=wt)
    if status.stdout.strip():
        commit = run(
            [
                "git",
                "-c", "user.email=forge-orchestrator@localhost",
                "-c", "user.name=forge-orchestrator",
                "commit", "-m",
                f"factory({task_id}): plan (status planning)\n\nPlan job via control plane queue (ADR-011).",
            ],
            cwd=wt,
        )
        log_cmd(task_id, ["git", "commit"], commit)
    gh_token = os.environ.get("GH_TOKEN", "")
    if gh_token:
        push_url = f"https://x-access-token:{gh_token}@github.com/{GITHUB_REPO}.git"
        proc = run(["git", "push", push_url, f"HEAD:refs/heads/{branch}"], cwd=wt)
    else:
        proc = run(["git", "push", "-u", "origin", f"HEAD:refs/heads/{branch}"], cwd=wt)
    log_cmd(task_id, ["git", "push", "<redacted>", f"HEAD:refs/heads/{branch}"], proc)
    return proc.returncode == 0


def open_or_reuse_pr(task: dict, task_id: str, branch: str, title: str, plan_body: str, wt: Path) -> str:
    url = existing_pr_url(task, branch, wt)
    if url:
        log(task_id, f"reusing existing PR {url} (no gh pr create)")
        return url
    body = f"""## Factory plan (`planning`)

Task `{task_id}` is **not** worker-claimable until Slack approve.

{plan_body}

## Approve

In the Slack thread: `approve` / `lgtm` / `/forge approve`, or API `control_action approve`.

## Deploy

Human merge only. After merge to `main`, Argo CD syncs (ADR-008).
"""
    created = run(
        [
            "gh", "pr", "create",
            "--repo", GITHUB_REPO,
            "--base", "main",
            "--head", branch,
            "--title", f"factory({task_id}): {title}",
            "--body", body,
        ],
        cwd=wt,
    )
    log_cmd(task_id, ["gh", "pr", "create", "--head", branch], created)
    if created.returncode == 0 and created.stdout.strip():
        return created.stdout.strip().splitlines()[-1]
    viewed = run(
        ["gh", "pr", "view", branch, "--repo", GITHUB_REPO, "--json", "url", "-q", ".url"],
        cwd=wt,
    )
    return viewed.stdout.strip()


def fail(task_id: str, reason: str) -> int:
    reason = redact_text(reason)
    log(task_id, f"plan job FAILED: {reason}")
    try:
        cp.append_message(task_id, "orchestrator", f"Plan job failed: {reason}", author="plan-worker")
        cp.notify(task_id, f"Plan job for `{task_id}` failed: {reason}")
    except Exception as err:  # noqa: BLE001
        log(task_id, f"failure reporting failed: {err}")
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--job-id", default=None)
    p.add_argument("--meta", default="{}", help="job meta JSON")
    args = p.parse_args()
    task_id = args.task_id
    try:
        meta = json.loads(args.meta or "{}")
    except json.JSONDecodeError:
        meta = {}

    mode = str(meta.get("mode") or "create")
    request = str(meta.get("request") or "")
    feedback = str(meta.get("feedback") or "")
    channel_id = str(meta.get("channel_id") or "")
    thread_ts = str(meta.get("thread_ts") or "")
    worker_id = os.environ.get("FORGE_WORKER_ID", "plan-worker")

    try:
        task = cp.get_task(task_id)
    except cp.ControlPlaneError as err:
        return fail(task_id, f"get_task: {err}")

    if task.get("status") != "planning":
        # Post-approve threads never re-plan (TASK-011); drop stale jobs.
        log(task_id, f"skip plan job: task status={task.get('status')} (not planning)")
        return 0

    branch = str(task.get("branch") or f"factory/{task_id.lower()}")
    title = str(task.get("title") or task_id)
    log(task_id, f"plan job start mode={mode} branch={branch} job_id={args.job_id}")

    load_vault_secrets(task_id)
    if not request:
        request = str(task.get("goal") or "")

    try:
        wt = ensure_worktree(task_id, branch)
    except RuntimeError as err:
        return fail(task_id, str(err))

    task_file = ""
    if mode == "update":
        import yaml  # type: ignore

        for path in sorted((wt / "factory" / "tasks").glob("TASK-*.yaml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if doc.get("id") == task_id:
                task_file = path.name
                break
        if not task_file:
            mode = "create"  # thread iterated before the first plan landed

    rc, blocked = run_plan(
        mode,
        wt,
        task_id,
        branch,
        request=request,
        feedback=feedback,
        task_file=task_file,
        worker_id=worker_id,
        job_id=args.job_id,
        sandbox_profile=str(task.get("sandbox_profile") or "agent-cell"),
        allow_fallback=(mode == "create"),
    )
    if blocked:
        return fail(task_id, f"planner blocked: {blocked}")
    if rc != 0:
        return fail(task_id, f"planner exited rc={rc}")

    # Sync refined YAML back to the DB — everything except the pinned branch.
    import yaml  # type: ignore

    doc: dict = {}
    for path in sorted((wt / "factory" / "tasks").glob("TASK-*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if d.get("id") == task_id:
            doc = d
            break
    if doc:
        try:
            cp.update_task(
                task_id,
                {
                    "title": str(doc.get("title") or title),
                    "goal": str(doc.get("goal") or ""),
                    "acceptance_criteria": [str(x) for x in (doc.get("acceptance_criteria") or [])],
                    "notes": str(doc.get("notes") or ""),
                },
            )
        except cp.ControlPlaneError as err:
            log(task_id, f"task field sync failed: {err}")
        title = str(doc.get("title") or title)

    if not push_branch(task_id, wt, branch):
        return fail(task_id, "git push failed (auth?)")

    plan_path = wt / "factory" / "plans" / f"{task_id}.md"
    plan_body = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else "(no plan file)"
    pr_url = open_or_reuse_pr(task, task_id, branch, title, plan_body, wt)
    if not pr_url:
        return fail(task_id, "no PR URL after push (gh pr create/view failed)")

    had_pr_artifact = any(a.get("kind") == "pr" for a in task.get("artifacts") or [])
    try:
        if not had_pr_artifact:
            cp.add_artifact(task_id, "pr", f"artifacts/{task_id}-pr.txt", pr_url)
        if channel_id and thread_ts:
            cp.save_slack_thread(channel_id, thread_ts, task_id, pr_url)
        cp.append_message(task_id, "orchestrator", f"Plan PR: {pr_url}", author="plan-worker")
    except cp.ControlPlaneError as err:
        log(task_id, f"artifact/thread update failed: {err}")

    verb = "opened" if mode == "create" else "updated"
    human_only = "HUMAN-ONLY" in str(task.get("notes") or "").upper()
    try:
        cp.notify(
            task_id,
            f"*{task_id}* plan {verb} (`planning`)"
            + (" ⚠️ flagged human-only — do not approve lightly." if human_only else "")
            + f"\n• PR: {pr_url}\n"
            "• Reply in this thread to revise.\n"
            "• Approve with `approve` / `lgtm` when ready for the worker.",
        )
        cp.enqueue_job(task_id, "watch-checks", {"pr_url": pr_url, "attempt": 0})
    except cp.ControlPlaneError as err:
        log(task_id, f"notify/watch enqueue failed: {err}")

    log(task_id, f"plan job done mode={mode} pr={pr_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
