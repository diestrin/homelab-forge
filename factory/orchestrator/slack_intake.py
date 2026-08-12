#!/usr/bin/env python3
"""Slack Socket Mode factory orchestrator (ADR-009).

Flow:
  channel message (allowlisted user) → Cursor SDK plan → task YAML status=planning
  → open/update plan PR → reply in Slack thread
  thread reply → revise plan + PR
  approve (button or keyword) → status proposed → workers may claim

Secrets from env (loaded by systemd after Vault fetch — never from git):
  SLACK_BOT_TOKEN, SLACK_APP_TOKEN, FORGE_SLACK_ALLOWLIST (comma user ids)
  CURSOR_API_KEY (optional if --allow-fallback)
  FORGE_REPO_ROOT — git common repo the orchestrator reads (do not checkout
  plan branches here; that steals the operator Cursor worktree). Plan commits
  happen in factory/worktrees/TASK-NNN.

No Ingress / Events Request URL — Socket Mode outbound WebSocket only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

APPROVE_RE = re.compile(r"(?i)^\s*(approve|lgtm|/forge\s+approve)\s*$")
HUMAN_ONLY_RE = re.compile(
    r"(?i)\b(ssh|ufw|vault\s+unseal|host-watch|force-?push|kubectl\s+apply)\b"
)


def die(msg: str) -> None:
    print(f"slack_intake: {msg}", file=sys.stderr)
    sys.exit(1)


def repo_root() -> Path:
    return Path(os.environ.get("FORGE_REPO_ROOT", os.getcwd())).resolve()


def allowlist() -> set[str]:
    raw = os.environ.get("FORGE_SLACK_ALLOWLIST", "").strip()
    return {x.strip() for x in raw.split(",") if x.strip()}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=check,
    )


def ensure_cursor_key() -> None:
    if os.environ.get("CURSOR_API_KEY"):
        return
    login = repo_root() / "factory" / "scripts" / "vault-agent-login.sh"
    fetch = repo_root() / "factory" / "scripts" / "fetch-cursor-key.sh"
    if not fetch.is_file():
        return
    env = os.environ.copy()
    if not env.get("VAULT_TOKEN") and login.is_file():
        tok = run([str(login), "--print-token"], check=False)
        if tok.returncode == 0 and tok.stdout.strip():
            env["VAULT_TOKEN"] = tok.stdout.strip()
            env["VAULT_ADDR"] = env.get("VAULT_ADDR", "http://127.0.0.1:8200")
    got = subprocess.run(
        [str(fetch)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if got.returncode == 0 and got.stdout.strip():
        os.environ["CURSOR_API_KEY"] = got.stdout.strip()


def next_task_id(repo: Path) -> str:
    out = run(
        [sys.executable, str(repo / "factory/scripts/task_lib.py"), "--repo", str(repo), "next-id"]
    )
    return out.stdout.strip()


def find_task_file(repo: Path, task_id: str) -> Path | None:
    for p in (repo / "factory" / "tasks").glob("TASK-*.yaml"):
        text = p.read_text(encoding="utf-8")
        if re.search(rf"^id:\s*{re.escape(task_id)}\s*$", text, re.M):
            return p
    return None


def thread_binding_path() -> Path:
    root = Path(os.environ.get("FORGE_DATA_ROOT", "/media/diestrin/data/forge"))
    d = root / "factory" / "slack-threads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_binding(channel: str, thread_ts: str, task_id: str, pr_url: str, task_file: str) -> None:
    path = thread_binding_path() / f"{channel}_{thread_ts}.json"
    path.write_text(
        json.dumps(
            {"task_id": task_id, "pr_url": pr_url, "task_file": task_file, "channel": channel, "thread_ts": thread_ts},
            indent=2,
        ),
        encoding="utf-8",
    )


def load_binding(channel: str, thread_ts: str) -> dict | None:
    path = thread_binding_path() / f"{channel}_{thread_ts}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def task_worktree_path(task_id: str) -> Path:
    root = Path(os.environ.get("FORGE_DATA_ROOT", "/media/diestrin/data/forge"))
    return root / "factory" / "worktrees" / task_id


def ensure_task_worktree(repo: Path, task_id: str, branch: str) -> Path:
    """Isolated worktree for plan commits. Never checks out BRANCH in `repo` (Cursor clone)."""
    wt = task_worktree_path(task_id)
    helper = repo / "factory" / "scripts" / "add-task-worktree.sh"
    proc = run(["bash", str(helper), str(repo), str(wt), branch], check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "worktree add failed")
    return wt


def open_or_update_plan_pr(repo: Path, task_id: str, branch: str, title: str, plan_body: str) -> str:
    """Commit planning artifacts on a branch and open/update a PR. Returns PR URL."""
    wt = ensure_task_worktree(repo, task_id, branch)
    run(["git", "fetch", "origin", "main"], cwd=wt, check=False)
    run(["git", "add", "factory/tasks", "factory/plans"], cwd=wt, check=False)
    status = run(["git", "status", "--porcelain"], cwd=wt, check=False)
    if status.stdout.strip():
        run(
            [
                "git",
                "-c",
                "user.email=forge-orchestrator@localhost",
                "-c",
                "user.name=forge-orchestrator",
                "commit",
                "-m",
                f"factory({task_id}): plan (status planning)\n\nSlack orchestrator plan PR. Not claimable until approved.",
            ],
            cwd=wt,
            check=False,
        )
    gh_token = os.environ.get("GH_TOKEN", "")
    if gh_token:
        push_url = f"https://x-access-token:{gh_token}@github.com/diestrin/homelab-forge.git"
        run(["git", "push", push_url, f"HEAD:refs/heads/{branch}"], cwd=wt, check=False)
    else:
        run(["git", "push", "-u", "origin", f"HEAD:refs/heads/{branch}"], cwd=wt, check=False)

    body = f"""## Factory plan (`planning`)

Task `{task_id}` is **not** worker-claimable until Slack approve.

{plan_body}

## Approve

In the Slack thread: `approve` / `lgtm` / `/forge approve`, or run
`./forge factory approve {task_id}` then `./forge factory sync`.

## Deploy

Human merge only. After merge to `main`, Argo CD syncs (ADR-008). Do not kubectl-apply.
"""
    # create or view PR
    created = run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            "diestrin/homelab-forge",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            f"factory({task_id}): {title}",
            "--body",
            body,
        ],
        cwd=repo,
        check=False,
    )
    if created.returncode == 0 and created.stdout.strip():
        return created.stdout.strip().splitlines()[-1]
    viewed = run(
        ["gh", "pr", "view", branch, "--repo", "diestrin/homelab-forge", "--json", "url", "-q", ".url"],
        cwd=repo,
        check=False,
    )
    return viewed.stdout.strip()


def mint_github_token(repo: Path) -> None:
    if os.environ.get("GH_TOKEN"):
        return
    login = repo / "factory/scripts/vault-agent-login.sh"
    mint = repo / "factory/scripts/github-app-token.sh"
    if not mint.is_file():
        return
    env = os.environ.copy()
    if not env.get("VAULT_TOKEN") and login.is_file():
        tok = run([str(login), "--print-token"], check=False)
        if tok.returncode == 0 and tok.stdout.strip():
            env["VAULT_TOKEN"] = tok.stdout.strip()
            env.setdefault("VAULT_ADDR", "http://127.0.0.1:8200")
    got = subprocess.run([str(mint)], env=env, text=True, capture_output=True, check=False)
    if got.returncode == 0 and got.stdout.strip():
        os.environ["GH_TOKEN"] = got.stdout.strip()
        os.environ["GH_PROMPT_DISABLED"] = "1"


def read_yaml_field(path: Path, field: str) -> str:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        val = data.get(field, "")
        return str(val) if val is not None else ""
    except Exception:  # noqa: BLE001
        m = re.search(rf"^{field}:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        return m.group(1).strip(" '\"") if m else ""


def mirror_task_yaml_to_repo(repo: Path, task_file: Path) -> None:
    """Keep a copy in FORGE_REPO_ROOT so the worker daemon can claim without checking out the plan branch."""
    dest_dir = repo / "factory" / "tasks"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / task_file.name
    if dest.resolve() != task_file.resolve():
        dest.write_text(task_file.read_text(encoding="utf-8"), encoding="utf-8")


def handle_new_request(say, channel: str, thread_ts: str, user: str, text: str) -> None:
    repo = repo_root()
    ensure_cursor_key()
    mint_github_token(repo)
    task_id = next_task_id(repo)
    human_only = bool(HUMAN_ONLY_RE.search(text))
    branch = f"factory/{task_id.lower()}"
    try:
        wt = ensure_task_worktree(repo, task_id, branch)
    except RuntimeError as err:
        say(text=f"Failed to create worktree for `{task_id}`: {err}", thread_ts=thread_ts)
        return
    cmd = [
        sys.executable,
        str(repo / "factory/orchestrator/cursor_plan.py"),
        "create",
        "--repo",
        str(wt),
        "--task-id",
        task_id,
        "--request",
        text,
        "--allow-fallback",
    ]
    proc = run(cmd, cwd=wt, check=False)
    if proc.returncode != 0:
        say(text=f"Failed to draft plan for `{task_id}`: {proc.stderr[-500:]}", thread_ts=thread_ts)
        return
    task_file = find_task_file(wt, task_id)
    if not task_file:
        say(text=f"Plan runner finished but no task file for `{task_id}`", thread_ts=thread_ts)
        return
    if human_only:
        # Annotate notes — keep planning; never auto-approve
        notes_extra = "\n  HUMAN-ONLY intent detected; do not approve into worker queue without operator review.\n"
        raw = task_file.read_text(encoding="utf-8")
        if "HUMAN-ONLY" not in raw:
            task_file.write_text(raw.replace("notes: |", "notes: |" + notes_extra, 1), encoding="utf-8")
    title = read_yaml_field(task_file, "title") or text[:60]
    branch = read_yaml_field(task_file, "branch") or branch
    plan_path = wt / "factory" / "plans" / f"{task_id}.md"
    plan_body = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else "(no plan file)"
    run([sys.executable, str(repo / "factory/scripts/task_lib.py"), "--repo", str(wt), "validate"], check=False)
    pr_url = open_or_update_plan_pr(repo, task_id, branch, title, plan_body)
    mirror_task_yaml_to_repo(repo, task_file)
    save_binding(channel, thread_ts, task_id, pr_url, task_file.name)
    run([str(repo / "forge"), "factory", "sync"], cwd=repo, check=False)
    warn = " ⚠️ flagged human-only — do not approve lightly." if human_only else ""
    say(
        text=(
            f"*{task_id}* plan opened (`planning`){warn}\n"
            f"• PR: {pr_url or '(push/PR failed — check host gh/Vault)'}\n"
            f"• Reply in this thread to revise the plan.\n"
            f"• Approve with `approve` / `lgtm` when ready for the Cursor SDK worker."
        ),
        thread_ts=thread_ts,
    )


def handle_thread_feedback(say, channel: str, thread_ts: str, text: str) -> None:
    binding = load_binding(channel, thread_ts)
    if not binding:
        return
    repo = repo_root()
    task_id = binding["task_id"]
    if APPROVE_RE.match(text):
        proc = run(
            [sys.executable, str(repo / "factory/scripts/task_lib.py"), "--repo", str(repo), "approve", task_id],
            check=False,
        )
        if proc.returncode != 0:
            say(text=f"Approve failed: {proc.stderr or proc.stdout}", thread_ts=thread_ts)
            return
        # Commit status bump on plan worktree (never checkout the plan branch in the Cursor clone)
        wt = task_worktree_path(task_id)
        task_file = find_task_file(wt if wt.is_dir() else repo, task_id) or find_task_file(repo, task_id)
        if task_file:
            branch = read_yaml_field(task_file, "branch")
            approve_cwd = wt if wt.is_dir() else repo
            if branch:
                run(
                    [sys.executable, str(repo / "factory/scripts/task_lib.py"), "--repo", str(approve_cwd), "approve", task_id],
                    check=False,
                )
                run(["git", "add", "factory/tasks"], cwd=approve_cwd, check=False)
                run(
                    [
                        "git",
                        "-c",
                        "user.email=forge-orchestrator@localhost",
                        "-c",
                        "user.name=forge-orchestrator",
                        "commit",
                        "-m",
                        f"factory({task_id}): approve plan → proposed",
                    ],
                    cwd=approve_cwd,
                    check=False,
                )
                mint_github_token(repo)
                if os.environ.get("GH_TOKEN"):
                    push_url = f"https://x-access-token:{os.environ['GH_TOKEN']}@github.com/diestrin/homelab-forge.git"
                    run(["git", "push", push_url, f"HEAD:refs/heads/{branch}"], cwd=approve_cwd, check=False)
                else:
                    run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], cwd=approve_cwd, check=False)
            mirror_task_yaml_to_repo(repo, task_file)
        run([str(repo / "forge"), "factory", "sync"], cwd=repo, check=False)
        say(
            text=(
                f"`{task_id}` → *proposed* (worker-claimable).\n"
                f"PR: {binding.get('pr_url')}\n"
                "Worker will pick it up and implement via Cursor SDK, then update the same PR."
            ),
            thread_ts=thread_ts,
        )
        return

    ensure_cursor_key()
    mint_github_token(repo)
    task_file_name = binding.get("task_file", "")
    wt = task_worktree_path(task_id)
    plan_repo = wt if wt.is_dir() else repo
    proc = run(
        [
            sys.executable,
            str(repo / "factory/orchestrator/cursor_plan.py"),
            "update",
            "--repo",
            str(plan_repo),
            "--task-id",
            task_id,
            "--task-file",
            task_file_name,
            "--feedback",
            text,
        ],
        cwd=plan_repo,
        check=False,
    )
    if proc.returncode != 0:
        say(text=f"Plan update failed: {proc.stderr[-500:]}", thread_ts=thread_ts)
        return
    task_file = find_task_file(plan_repo, task_id)
    title = read_yaml_field(task_file, "title") if task_file else task_id
    branch = read_yaml_field(task_file, "branch") if task_file else ""
    plan_path = plan_repo / "factory" / "plans" / f"{task_id}.md"
    plan_body = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else ""
    pr_url = open_or_update_plan_pr(repo, task_id, branch, title, plan_body) if branch else binding.get("pr_url", "")
    if task_file:
        mirror_task_yaml_to_repo(repo, task_file)
    if pr_url:
        binding["pr_url"] = pr_url
        save_binding(channel, thread_ts, task_id, pr_url, task_file_name)
    run([str(repo / "forge"), "factory", "sync"], cwd=repo, check=False)
    say(text=f"Updated `{task_id}` plan. PR: {pr_url}", thread_ts=thread_ts)


def main() -> None:
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    app_token = os.environ.get("SLACK_APP_TOKEN", "").strip()
    if not bot_token or not app_token:
        die("SLACK_BOT_TOKEN and SLACK_APP_TOKEN required (from Vault secret/forge/agents/slack)")
    if not allowlist():
        die("FORGE_SLACK_ALLOWLIST required (comma-separated Slack user IDs)")

    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        die("slack-bolt not installed (see factory/orchestrator/requirements.txt)")

    app = App(token=bot_token)

    @app.event("message")
    def on_message(event, say):  # type: ignore[no-untyped-def]
        if event.get("subtype"):
            return
        user = event.get("user") or ""
        if user not in allowlist():
            return
        text = (event.get("text") or "").strip()
        if not text:
            return
        channel = event.get("channel") or ""
        ts = event.get("ts") or ""
        thread_ts = event.get("thread_ts")
        if thread_ts and thread_ts != ts:
            handle_thread_feedback(say, channel, thread_ts, text)
            return
        # Top-level channel message → new plan
        handle_new_request(say, channel, ts, user, text)

    print("slack_intake: starting Socket Mode", flush=True)
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
