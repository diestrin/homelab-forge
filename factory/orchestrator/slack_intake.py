#!/usr/bin/env python3
"""Slack Socket Mode intake — thin client (ADR-009 / ADR-011, TASK-011).

This process only records intent: slash commands and thread replies POST to
the control plane (`/api/v1/slack/intake`). The control plane creates/updates
tasks, pins branches, enqueues plan/implement/watch/notify jobs, and is the
only path that posts agent progress and failures back to Slack.

This client must NOT call the Cursor SDK, git, or gh.

Secrets from env (systemd + Vault — never git):
  SLACK_BOT_TOKEN, SLACK_APP_TOKEN, FORGE_SLACK_ALLOWLIST
  FORGE_CONTROL_PLANE_URL, FORGE_API_TOKEN

No Ingress / Events Request URL — Socket Mode outbound WebSocket only.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "factory" / "scripts"))

import control_plane_client as cp  # noqa: E402
from redact import redact_text  # noqa: E402

# Slack slash payload: command="/forge", text="plan …" (the command name is not in text).
PLAN_CMD_RE = re.compile(r"(?i)^(?:/forge\s+)?plan\s+(.+)$")


def die(msg: str) -> None:
    print(f"slack_intake: {msg}", file=sys.stderr)
    sys.exit(1)


def log(msg: str) -> None:
    """Journal line (systemd): redacted, no Slack user IDs."""
    print(f"slack_intake: {redact_text(msg)}", flush=True)


def allowlist() -> set[str]:
    raw = os.environ.get("FORGE_SLACK_ALLOWLIST", "").strip()
    return {x.strip() for x in raw.split(",") if x.strip()}


def post_intake(kind: str, channel: str, thread_ts: str, text: str) -> dict:
    # Author is a role label, not the Slack user id (public dashboard).
    return cp.slack_intake(kind, channel, thread_ts, text, author="operator")


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
            res = post_intake("plan", channel, thread_ts, request_text)
            task = res.get("task") or {}
            log(
                f"intake action=plan task={task.get('id')} branch={task.get('branch')} "
                f"job={res.get('job_id')} channel={channel}"
            )
        except cp.ControlPlaneError as err:
            log(f"intake plan failed: {err}")
            say(text=f"Control plane intake failed: {err}", thread_ts=thread_ts)

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
        try:
            res = post_intake("thread_reply", channel, thread_ts, text)
            task = res.get("task") or {}
            log(
                f"intake action={res.get('action')} task={task.get('id')} "
                f"status={task.get('status')} job={res.get('job_id')} channel={channel}"
            )
        except cp.ControlPlaneError as err:
            # Threads without a task binding are normal chatter — stay quiet.
            if "no task bound" in str(err):
                return
            log(f"intake thread_reply failed: {err}")
            say(text=f"Control plane intake failed: {err}", thread_ts=thread_ts)

    log("starting Socket Mode (thin intake: slash + threads → control plane API)")
    SocketModeHandler(app, app_token).start()


if __name__ == "__main__":
    main()
