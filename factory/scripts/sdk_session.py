#!/usr/bin/env python3
"""Shared Cursor SDK session for factory agents (TASK-011).

Replaces fire-and-forget Agent.prompt with Agent.create + run.messages():
- streams a redacted transcript into the control plane agent_runs record
- supports follow-up sends in the same conversation (lint-fix loop)
- logs run/agent ids and failures to stdout for the systemd journal
- injects a runtime card so headless agents know their constraints

No secrets are ever written to the transcript or journal (redact.py).
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control_plane_client as cp  # noqa: E402
from redact import redact_obj, redact_text  # noqa: E402

EVENT_FLUSH_SIZE = 10
BLOCKED_MARKER = "FORGE_BLOCKED:"


def log(task_id: str, msg: str) -> None:
    """Journal-friendly single line, redacted, flushed for systemd."""
    print(f"forge-factory task={task_id} {redact_text(msg)}", flush=True)


def runtime_card(role: str, sandbox_profile: str, branch: str) -> str:
    """Constraints card injected into every factory agent prompt (TASK-011)."""
    role_line = {
        "plan": "plan-only: draft/revise task YAML + plan markdown. Never implement the feature.",
        "implement": "implement: code the task on the pinned branch in this worktree.",
    }.get(role, role)
    return f"""Runtime card — read before acting:
- Role: {role_line}
- Sandbox profile: {sandbox_profile} (ADR-002 layered isolation).
- You run headless via the Cursor SDK: NO TTY, no interactive prompts, nobody answers questions.
- NO host sudo: never run sudo, apt, apt-get, dnf, snap, or system package installs — they fail (PAM) and pollute logs. Use only tools already available in the worktree.
- Never modify UFW or host-watch, never `kubectl apply` Argo-managed apps, never merge to main, never force-push (ADR-002/ADR-008).
- The working branch is pinned to `{branch}` by the control plane. Never change the `branch:` field in task YAML and never create or switch branches.
- Public repo: no secrets, tokens, or real Slack user IDs in any file.
- If you cannot proceed (missing tool/secret/permission), stop and end your reply with one line: {BLOCKED_MARKER} <short reason>
"""


def _to_jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 6:
        return str(obj)
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x, depth + 1) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v, depth + 1) for k, v in obj.items()}
    for attr in ("model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return _to_jsonable(fn(), depth + 1)
            except Exception:  # noqa: BLE001
                pass
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        try:
            return _to_jsonable(dataclasses.asdict(obj), depth + 1)
        except Exception:  # noqa: BLE001
            pass
    return str(obj)


def event_from_message(msg: Any) -> dict:
    """Convert an SDK stream message into a compact redacted transcript event."""
    raw = _to_jsonable(msg)
    event: dict[str, Any] = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "type": str(getattr(msg, "type", None) or type(msg).__name__),
    }
    # Pull assistant text blocks up for readability in the dashboard.
    if isinstance(raw, dict):
        message = raw.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                texts = [
                    str(b.get("text"))
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                ]
                if texts:
                    event["text"] = "\n".join(texts)
                tools = [
                    str(b.get("name") or b.get("tool") or "tool")
                    for b in content
                    if isinstance(b, dict) and str(b.get("type", "")).startswith("tool")
                ]
                if tools:
                    event["tool"] = ", ".join(tools)
        event["detail"] = raw
    else:
        event["detail"] = raw
    return redact_obj(event)


class SdkStartupError(RuntimeError):
    pass


class SdkSession:
    """Context-managed Cursor SDK agent tied to a control plane agent_run."""

    def __init__(
        self,
        task_id: str,
        kind: str,
        cwd: str,
        api_key: str,
        model: str,
        worker_id: str | None = None,
        branch: str | None = None,
        job_id: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.kind = kind
        self.cwd = cwd
        self.api_key = api_key
        self.model = model
        self.worker_id = worker_id
        self.branch = branch
        self.job_id = job_id
        self.run_id: str | None = None
        self.agent = None
        self.last_text = ""
        self.last_status: str | None = None
        self._events: list[dict] = []
        self._reported = False

    # -- control plane plumbing -------------------------------------------

    def _create_run(self) -> None:
        if not cp.is_configured():
            log(self.task_id, f"run kind={self.kind} control plane not configured — transcript only in journal")
            return
        try:
            run = cp.create_run(
                self.task_id,
                self.kind,
                worker_id=self.worker_id,
                model=self.model,
                branch=self.branch,
                job_id=self.job_id,
            )
            self.run_id = str(run["id"])
            log(self.task_id, f"agent_run created run_id={self.run_id} kind={self.kind} branch={self.branch}")
        except Exception as err:  # noqa: BLE001
            log(self.task_id, f"agent_run create failed: {err}")

    def _flush_events(self, force: bool = False) -> None:
        if not self._events:
            return
        if not force and len(self._events) < EVENT_FLUSH_SIZE:
            return
        batch, self._events = self._events, []
        if not self.run_id:
            return
        try:
            cp.append_run_events(self.run_id, batch)
        except Exception as err:  # noqa: BLE001
            log(self.task_id, f"append_run_events failed ({len(batch)} events): {err}")

    def _record_event(self, event: dict) -> None:
        self._events.append(event)
        self._flush_events()

    def finish(self, status: str, summary: str | None = None, error: str | None = None) -> None:
        self._flush_events(force=True)
        if self._reported:
            return
        self._reported = True
        if self.run_id:
            try:
                cp.finish_run(
                    self.run_id,
                    status,
                    summary=redact_text(summary) if summary else None,
                    error=redact_text(error) if error else None,
                )
            except Exception as err:  # noqa: BLE001
                log(self.task_id, f"finish_run failed: {err}")
        log(self.task_id, f"run finished status={status} run_id={self.run_id}{' error=' + error if error else ''}")

    # -- SDK lifecycle ------------------------------------------------------

    def __enter__(self) -> "SdkSession":
        try:
            from cursor_sdk import Agent, LocalAgentOptions
        except ImportError as err:
            raise SdkStartupError(
                "cursor-sdk not installed (pip install -r factory/orchestrator/requirements.txt)"
            ) from err
        self._create_run()
        try:
            self.agent = Agent.create(
                model=self.model,
                api_key=self.api_key,
                local=LocalAgentOptions(cwd=self.cwd),
            )
            self.agent.__enter__()
        except Exception as err:  # noqa: BLE001
            self.finish("error", error=f"agent startup failed: {err}")
            raise SdkStartupError(str(err)) from err
        agent_id = getattr(self.agent, "agent_id", None)
        if self.run_id and agent_id:
            try:
                cp.update_run(self.run_id, {"agent_id": str(agent_id)})
            except Exception:  # noqa: BLE001
                pass
        log(self.task_id, f"sdk agent created agent_id={agent_id} model={self.model} cwd={self.cwd}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.agent is not None:
            try:
                self.agent.__exit__(exc_type, exc, tb)
            except Exception:  # noqa: BLE001
                pass
        if exc is not None:
            self.finish("error", error=f"{exc_type.__name__ if exc_type else 'error'}: {exc}")
        else:
            self.finish(
                "finished" if self.last_status in (None, "finished") else "error",
                summary=self.last_text[-2000:] if self.last_text else None,
            )

    def send(self, prompt: str) -> str:
        """Send a prompt, stream transcript events, wait; returns run status."""
        assert self.agent is not None
        from cursor_sdk import CursorAgentError

        self._record_event(
            redact_obj(
                {
                    "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                    "type": "prompt",
                    "text": prompt,
                }
            )
        )
        try:
            run = self.agent.send(prompt)
        except CursorAgentError as err:
            self.finish("error", error=f"send failed: {err} retryable={getattr(err, 'is_retryable', None)}")
            raise SdkStartupError(str(err)) from err

        sdk_run_id = getattr(run, "id", None)
        log(self.task_id, f"sdk run started sdk_run_id={sdk_run_id}")
        if self.run_id and sdk_run_id:
            try:
                cp.update_run(self.run_id, {"sdk_run_id": str(sdk_run_id)})
            except Exception:  # noqa: BLE001
                pass

        texts: list[str] = []
        try:
            for message in run.messages():
                event = event_from_message(message)
                if event.get("text"):
                    texts.append(str(event["text"]))
                self._record_event(event)
        except Exception as err:  # noqa: BLE001
            log(self.task_id, f"transcript stream error (continuing to wait): {err}")

        result = run.wait()
        status = str(getattr(result, "status", "finished") or "finished")
        self.last_status = status
        self.last_text = "\n".join(texts) or str(getattr(result, "result", "") or "")
        self._record_event(
            redact_obj(
                {
                    "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                    "type": "result",
                    "status": status,
                }
            )
        )
        self._flush_events(force=True)
        log(self.task_id, f"sdk run done sdk_run_id={sdk_run_id} status={status}")
        return status

    # -- helpers ------------------------------------------------------------

    def blocked_reason(self) -> str | None:
        """FORGE_BLOCKED marker from the agent's final reply, if any."""
        for line in reversed(self.last_text.splitlines()):
            if BLOCKED_MARKER in line:
                return line.split(BLOCKED_MARKER, 1)[1].strip() or "blocked"
        return None

    def ensure_lint_clean(self, repo: str, attempts: int = 2) -> bool:
        """Run repo linters; ask the same agent to fix findings (same run).

        Returns True when lint is clean, False after exhausting attempts.
        """
        lint = str(Path(__file__).resolve().parent / "lint-local.sh")
        for attempt in range(attempts + 1):
            proc = subprocess.run(
                ["bash", lint],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            log(self.task_id, f"lint-local.sh attempt={attempt} exit={proc.returncode}")
            if proc.returncode == 0:
                return True
            if attempt >= attempts:
                break
            findings = redact_text((proc.stdout + "\n" + proc.stderr)[-6000:])
            self.send(
                "Local lint (the same checks CI runs) failed. Fix every finding "
                "now — do not leave lint failures for the operator or CI. "
                "Only fix these findings:\n\n"
                f"```\n{findings}\n```"
            )
        return False
