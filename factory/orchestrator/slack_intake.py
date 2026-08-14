#!/usr/bin/env python3
"""Slack Socket Mode factory orchestrator (ADR-009 + ADR-010).

Slash commands only for new work (`/forge plan …`). Ordinary channel messages are ignored.
Thread replies continue plan feedback / approve. State lives in Postgres via control plane API.

Secrets from env (systemd + Vault — never git):
  SLACK_BOT_TOKEN, SLACK_APP_TOKEN, FORGE_SLACK_ALLOWLIST
  FORGE_CONTROL_PLANE_URL, FORGE_API_TOKEN
  CURSOR_API_KEY (optional), GH_TOKEN (optional)

No Ingress / Events Request URL — Socket Mode outbound WebSocket only.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "factory" / "scripts"))

import control_plane_client as cp  # noqa: E402

APPROVE_RE = re.compile(r"(?i)^\s*(approve|lgtm|/forge\s+approve)\s*$")
HUMAN_ONLY_RE = re.compile(
    r"(?i)\b(ssh|ufw|vault\s+unseal|host-watch|force-?push|kubectl\s+apply)\b"
)
# Slack slash payload: command="/forge", text="plan …" (the command name is not in text).
PLAN_CMD_RE = re.compile(r"(?i)^(?:/forge\s+)?plan\s+(.+)$")


def die(msg: str) -> None:
    print(f"slack_intake: {msg}", file=sys.stderr)
    sys.exit(1)


def repo_root() -> Path:
    return Path(os.environ.get("FORGE_REPO_ROOT", REPO_ROOT)).resolve()


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
    got = subprocess.run([str(fetch)], env=env, text=True, capture_output=True, check=False)
    if got.returncode == 0 and got.stdout.strip():
        os.environ["CURSOR_API_KEY"] = got.stdout.strip()


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


def task_worktree_path(task_id: str) -> Path:
    root = Path(os.environ.get("FORGE_DATA_ROOT", "/media/diestrin/data/forge"))
    return root / "factory" / "worktrees" / task_id


def ensure_task_worktree(repo: Path, task_id: str, branch: str) -> Path:
    wt = task_worktree_path(task_id)
    helper = repo / "factory" / "scripts" / "add-task-worktree.sh"
    proc = run(["bash", str(helper), str(repo), str(wt), branch], check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "worktree add failed")
    return wt


def open_or_update_plan_pr(repo: Path, task_id: str, branch: str, title: str, plan_body: str) -> str:
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
                f"factory({task_id}): plan (status planning)\n\nSlack orchestrator plan PR.",
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

In the Slack thread: `approve` / `lgtm` / `/forge approve`, or API `control_action approve`.

## Deploy

Human merge only. After merge to `main`, Argo CD syncs (ADR-008).
"""
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


def persist_orchestrator_reply(task_id: str, body: str) -> None:
    cp.append_message(task_id, "orchestrator", body, author="slack-orchestrator")


def handle_new_plan(say, channel: str, thread_ts: str, text: str) -> None:
    repo = repo_root()
    ensure_cursor_key()
    mint_github_token(repo)

    task_id = cp.next_task_id()
    branch = f"factory/{task_id.lower()}"
    human_only = bool(HUMAN_ONLY_RE.search(text))

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

    # Read plan artifacts from worktree for DB + PR
    import yaml  # type: ignore

    task_file = wt / "factory" / "tasks" / f"{task_id}.yaml"
    for p in (wt / "factory" / "tasks").glob("TASK-*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if d.get("id") == task_id:
            task_file = p
            break
    if not task_file.is_file():
        say(text=f"Plan runner finished but no task file for `{task_id}`", thread_ts=thread_ts)
        return

    doc = yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
    title = str(doc.get("title") or text[:60])
    branch = str(doc.get("branch") or branch)
    ac = doc.get("acceptance_criteria") or []
    notes = str(doc.get("notes") or "")
    if human_only and "HUMAN-ONLY" not in notes:
        notes += "\nHUMAN-ONLY intent detected; do not approve without operator review.\n"

    plan_path = wt / "factory" / "plans" / f"{task_id}.md"
    plan_body = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else "(no plan file)"

    cp.create_task(
        {
            "id": task_id,
            "title": title,
            "goal": str(doc.get("goal") or text),
            "acceptance_criteria": [str(x) for x in ac],
            "sandbox_profile": doc.get("sandbox_profile") or "agent-cell",
            "repo_path": doc.get("repo_path") or ".",
            "status": "planning",
            "risk_level": doc.get("risk_level") or "low",
            "branch": branch,
            "notes": notes,
            "initial_message": f"Slack plan request: {text[:500]}",
            "message_source": "slack",
            "author": "slack-orchestrator",
        }
    )

    pr_url = open_or_update_plan_pr(repo, task_id, branch, title, plan_body)
    cp.save_slack_thread(channel, thread_ts, task_id, pr_url or None)
    if pr_url:
        cp.append_message(task_id, "orchestrator", f"Plan PR: {pr_url}", author="slack-orchestrator")

    reply = (
        f"*{task_id}* plan opened (`planning`)"
        + (" ⚠️ flagged human-only — do not approve lightly." if human_only else "")
        + f"\n• PR: {pr_url or '(push/PR failed)'}\n"
        "• Reply in this thread to revise.\n"
        "• Approve with `approve` / `lgtm` when ready for the worker."
    )
    persist_orchestrator_reply(task_id, reply)
    say(text=reply, thread_ts=thread_ts)


def handle_thread_feedback(say, channel: str, thread_ts: str, text: str) -> None:
    task_id = cp.get_slack_thread_task(channel, thread_ts)
    if not task_id:
        return

    if APPROVE_RE.match(text):
        try:
            cp.approve(task_id, actor="slack")
        except cp.ControlPlaneError as err:
            say(text=f"Approve failed: {err}", thread_ts=thread_ts)
            return
        pr_url = ""
        msgs = cp.list_messages(task_id)
        for m in msgs:
            body = str(m.get("body") or "")
            if body.startswith("Plan PR:"):
                pr_url = body.split("Plan PR:", 1)[1].strip()
                break
        reply = (
            f"`{task_id}` → *proposed* (worker-claimable).\n"
            f"PR: {pr_url or '(see plan PR on GitHub)'}\n"
            "Worker will implement via Cursor SDK and update the same PR."
        )
        persist_orchestrator_reply(task_id, reply)
        say(text=reply, thread_ts=thread_ts)
        return

    repo = repo_root()
    ensure_cursor_key()
    mint_github_token(repo)
    wt = task_worktree_path(task_id)
    plan_repo = wt if wt.is_dir() else repo
    task_file_name = f"{task_id}.yaml"
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

    import yaml  # type: ignore

    task_file = plan_repo / "factory" / "tasks" / task_file_name
    doc = yaml.safe_load(task_file.read_text(encoding="utf-8")) if task_file.is_file() else {}
    title = str(doc.get("title") or task_id)
    branch = str(doc.get("branch") or f"factory/{task_id.lower()}")
    plan_path = plan_repo / "factory" / "plans" / f"{task_id}.md"
    plan_body = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else ""
    pr_url = open_or_update_plan_pr(repo, task_id, branch, title, plan_body)
    if pr_url:
        cp.update_slack_thread_pr(channel, thread_ts, pr_url)

    cp.append_message(task_id, "slack", text, author="operator")
    cp.update_task(
        task_id,
        {
            "goal": str(doc.get("goal") or ""),
            "acceptance_criteria": [str(x) for x in (doc.get("acceptance_criteria") or [])],
            "notes": str(doc.get("notes") or ""),
        },
    )

    reply = f"Updated `{task_id}` plan. PR: {pr_url}"
    persist_orchestrator_reply(task_id, reply)
    say(text=reply, thread_ts=thread_ts)


def main() -> None:
    if not cp.is_configured():
        die("FORGE_CONTROL_PLANE_URL and FORGE_API_TOKEN required (ADR-010)")

    bot_token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    app_token = os.environ.get("SLACK_APP_TOKEN", "").strip()
    if not bot_token or not app_token:
        die("SLACK_BOT_TOKEN and SLACK_APP_TOKEN required")
    if not allowlist():
        die("FORGE_SLACK_ALLOWLIST required")

    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        die("slack-bolt not installed")

    app = App(token=bot_token)

    @app.command("/forge")
    def on_forge(ack, command, say):  # type: ignore[no-untyped-def]
        ack()
        user = command.get("user_id") or ""
        if user not in allowlist():
            return
        text = (command.get("text") or "").strip()
        channel = command.get("channel_id") or ""

        if re.match(r"(?i)^approve\s*$", text):
            say(text="Use `approve` in the plan thread, not `/forge approve` at channel level.")
            return

        m = PLAN_CMD_RE.match(text)
        if not m:
            say(
                text=(
                    "Usage:\n"
                    "• `/forge plan <describe the work>` — open a planning task\n"
                    "• In the plan thread: reply to revise, or `approve` / `lgtm` to queue worker"
                )
            )
            return

        request_text = m.group(1).strip()
        # say() uses chat.postMessage and returns SlackResponse (dict-like, not dict).
        result = say(text=f"Planning: _{request_text[:120]}_…")
        thread_ts = result.get("ts") if result is not None else None
        if not thread_ts:
            say(text="Failed to open plan thread")
            return
        try:
            handle_new_plan(say, channel, thread_ts, request_text)
        except cp.ControlPlaneError as err:
            say(text=f"Control plane error: {err}", thread_ts=thread_ts)
        except Exception as err:
            say(text=f"Plan failed: {err}", thread_ts=thread_ts)

    @app.event("message")
    def on_message(event, say):  # type: ignore[no-untyped-def]
        # Thread feedback only — ignore top-level channel messages (ADR-010)
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
        if not thread_ts or thread_ts == ts:
            return
        handle_thread_feedback(say, channel, thread_ts, text)

    print("slack_intake: starting Socket Mode (slash + threads only)", flush=True)
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
