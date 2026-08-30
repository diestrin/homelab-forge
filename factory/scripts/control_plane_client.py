#!/usr/bin/env python3
"""HTTP client for forge-site control plane API (ADR-010)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ControlPlaneError(RuntimeError):
    pass


def _base_url() -> str:
    url = os.environ.get("FORGE_CONTROL_PLANE_URL", "http://127.0.0.1:3000").rstrip("/")
    return url


def _token() -> str:
    tok = os.environ.get("FORGE_API_TOKEN", "").strip()
    if not tok:
        raise ControlPlaneError("FORGE_API_TOKEN required for control plane API")
    return tok


def _request(method: str, path: str, body: dict | None = None) -> Any:
    url = f"{_base_url()}/api/v1{path}"
    data = None
    headers = {"Accept": "application/json", "Authorization": f"Bearer {_token()}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        raise ControlPlaneError(f"{method} {path} → {err.code}: {detail}") from err


def is_configured() -> bool:
    return bool(os.environ.get("FORGE_CONTROL_PLANE_URL") and os.environ.get("FORGE_API_TOKEN"))


def list_tasks() -> list[dict]:
    return _request("GET", "/tasks").get("tasks", [])


def get_task(task_id: str) -> dict:
    return _request("GET", f"/tasks/{task_id}")["task"]


def create_task(payload: dict) -> dict:
    return _request("POST", "/tasks", payload)["task"]


def update_task(task_id: str, patch: dict) -> dict:
    return _request("PATCH", f"/tasks/{task_id}", patch)["task"]


def append_message(task_id: str, source: str, body: str, author: str | None = None) -> dict:
    return _request(
        "POST",
        f"/tasks/{task_id}/messages",
        {"source": source, "body": body, "author": author},
    )["message"]


def list_messages(task_id: str) -> list[dict]:
    return _request("GET", f"/tasks/{task_id}/messages").get("messages", [])


def next_task_id() -> str:
    tasks = list_tasks()
    max_n = 0
    for t in tasks:
        tid = str(t.get("id") or "")
        if tid.startswith("TASK-"):
            try:
                max_n = max(max_n, int(tid.split("-", 1)[1]))
            except ValueError:
                pass
    return f"TASK-{max_n + 1:03d}"


def approve(task_id: str, actor: str | None = None) -> dict:
    return _request(
        "POST",
        f"/tasks/{task_id}/actions",
        {"action": "approve", "actor": actor},
    )


def claim(worker_id: str, task_id: str | None = None, via_queue: bool = False) -> dict | None:
    body: dict[str, Any] = {"worker_id": worker_id, "via_queue": via_queue}
    if task_id:
        body["task_id"] = task_id
    data = _request("POST", "/jobs/claim", body)
    if not data.get("claimed"):
        return None
    return data.get("task")


def claim_job(worker_id: str, kinds: list[str]) -> dict | None:
    """Claim the next queued job of the given kinds (TASK-011 multi-kind worker).

    Returns {"job": {...}, "task": {...}} or None when the queues are empty.
    """
    data = _request(
        "POST",
        "/jobs/claim",
        {"worker_id": worker_id, "via_queue": True, "kinds": kinds},
    )
    if not data.get("claimed") or not data.get("job"):
        # Fallback path may claim a proposed task without a queue job.
        if data.get("claimed") and data.get("task"):
            return {"job": None, "task": data["task"]}
        return None
    return {"job": data["job"], "task": data.get("task")}


def set_status(task_id: str, status: str, assignee: str | None = None) -> dict:
    patch: dict[str, Any] = {"status": status}
    if assignee is not None:
        patch["assignee_agent"] = assignee
    return update_task(task_id, patch)


def add_artifact(task_id: str, kind: str, path: str, url: str | None = None) -> dict:
    art = {"kind": kind, "path": path}
    if url:
        art["url"] = url
    return update_task(task_id, {"artifact": art})


def save_slack_thread(channel: str, thread_ts: str, task_id: str, pr_url: str | None = None) -> None:
    _request(
        "POST",
        "/slack/threads",
        {
            "channel_id": channel,
            "thread_ts": thread_ts,
            "task_id": task_id,
            "pr_url": pr_url,
        },
    )


def get_slack_thread_task(channel: str, thread_ts: str) -> str | None:
    try:
        data = _request(
            "GET",
            f"/slack/threads?channel_id={channel}&thread_ts={thread_ts}",
        )
        return str(data["binding"]["task_id"])
    except ControlPlaneError:
        return None


def update_slack_thread_pr(channel: str, thread_ts: str, pr_url: str) -> None:
    task_id = get_slack_thread_task(channel, thread_ts)
    if not task_id:
        return
    save_slack_thread(channel, thread_ts, task_id, pr_url)


# --- TASK-011: Slack intake, durable agent runs, notify, job enqueue ---


def slack_intake(kind: str, channel_id: str, thread_ts: str, text: str, author: str = "operator") -> dict:
    """Record Slack intent on the control plane (thin intake client)."""
    return _request(
        "POST",
        "/slack/intake",
        {
            "kind": kind,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "text": text,
            "author": author,
        },
    )


def create_run(
    task_id: str,
    kind: str,
    worker_id: str | None = None,
    model: str | None = None,
    branch: str | None = None,
    job_id: str | None = None,
) -> dict:
    return _request(
        "POST",
        "/runs",
        {
            "task_id": task_id,
            "kind": kind,
            "worker_id": worker_id,
            "model": model,
            "branch": branch,
            "job_id": job_id,
        },
    )["run"]


def append_run_events(run_id: str, events: list[dict]) -> None:
    if not events:
        return
    _request("POST", f"/runs/{run_id}/events", {"events": events})


def update_run(run_id: str, patch: dict) -> dict:
    return _request("PATCH", f"/runs/{run_id}", patch)["run"]


def finish_run(
    run_id: str,
    status: str,
    summary: str | None = None,
    error: str | None = None,
    agent_id: str | None = None,
    sdk_run_id: str | None = None,
) -> dict:
    patch: dict[str, Any] = {"status": status}
    if summary is not None:
        patch["summary"] = summary
    if error is not None:
        patch["error"] = error
    if agent_id is not None:
        patch["agent_id"] = agent_id
    if sdk_run_id is not None:
        patch["sdk_run_id"] = sdk_run_id
    return update_run(run_id, patch)


def list_runs(task_id: str) -> list[dict]:
    return _request("GET", f"/tasks/{task_id}/runs").get("runs", [])


def notify(task_id: str, body: str) -> None:
    """Report progress/failure; control plane posts to the bound Slack thread."""
    _request("POST", f"/tasks/{task_id}/notify", {"body": body})


def enqueue_job(task_id: str, kind: str, meta: dict | None = None) -> str | None:
    data = _request("POST", f"/tasks/{task_id}/jobs", {"kind": kind, "meta": meta or {}})
    return data.get("job_id")
