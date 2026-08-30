"""Habitica API v3 client.

Only v3 is used: v4 is incomplete, unsuitable for third-party tools, and may
change or be blocked without notice.

Two rules from Habitica's API guidelines are enforced here rather than left to
callers: every request carries an X-Client header, and background scripts pace
themselves between calls.

This client never calls /api/v3/cron. Running cron on a user's behalf applies
damage for every incomplete Daily, which would penalise children for our
scheduling rather than their behaviour.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://habitica.com/api/v3"
MAX_RETRIES = 4


class HabiticaError(RuntimeError):
    pass


class HabiticaClient:
    def __init__(
        self,
        user_id: str,
        api_key: str,
        client_header: str,
        delay_seconds: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self._user_id = user_id
        self._headers = {
            "x-api-user": user_id,
            "x-api-key": api_key,
            "x-client": client_header,
            "content-type": "application/json",
        }
        self._delay = delay_seconds
        self._session = session or requests.Session()
        self._last_call: float | None = None

    # -- plumbing ---------------------------------------------------------

    def _pace(self) -> None:
        if self._last_call is None:
            return
        elapsed = time.monotonic() - self._last_call
        remaining = self._delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{BASE_URL}{path}"
        for attempt in range(1, MAX_RETRIES + 1):
            self._pace()
            response = self._session.request(
                method, url, headers=self._headers, timeout=30, **kwargs
            )
            self._last_call = time.monotonic()

            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", self._delay))
                log.warning("rate limited on %s, waiting %ss", path, wait)
                time.sleep(wait)
                continue

            if response.status_code >= 500 and attempt < MAX_RETRIES:
                backoff = 2**attempt
                log.warning("habitica %s on %s, retrying in %ss",
                            response.status_code, path, backoff)
                time.sleep(backoff)
                continue

            if not response.ok:
                raise HabiticaError(
                    f"{method} {path} -> {response.status_code}: {response.text[:300]}"
                )

            payload = response.json()
            return payload.get("data")

        raise HabiticaError(f"{method} {path} failed after {MAX_RETRIES} attempts")

    # -- reads ------------------------------------------------------------

    def list_tasks(self, task_type: str | None = None) -> list[dict]:
        params = {"type": task_type} if task_type else None
        return self._request("GET", "/tasks/user", params=params) or []

    def user_stats(self) -> dict:
        return self._request("GET", "/user?userFields=stats,preferences") or {}

    # -- writes -----------------------------------------------------------

    def create_task(self, payload: dict) -> dict:
        return self._request("POST", "/tasks/user", json=payload)

    def update_task(self, task_id: str, payload: dict) -> dict:
        return self._request("PUT", f"/tasks/{task_id}", json=payload)

    def delete_task(self, task_id: str) -> None:
        self._request("DELETE", f"/tasks/{task_id}")


def build_task_payload(
    *,
    title: str,
    habitica_type: str,
    difficulty: str,
    days: list[str] | None = None,
    notes: str = "",
    applies_damage: bool = True,
    due_date: date | None = None,
) -> dict:
    """Translate a Family Agile routine or tarea into a Habitica task.

    ``applies_damage`` maps to Habitica's per-task damage confirmation. It is
    switched off for everything except mandatory dailies: optional work must
    never be able to cost a child money for simply not happening.

    ``due_date`` only applies to ``habitica_type == "todo"``: a Tareas To-Do
    uses it for ``Fecha límite``, and a non-weekly Rutina (ADR-26) uses it for
    the occurrence date the sync itself computed.
    """
    priority = {"Fácil": 1, "Intermedia": 1.5, "Compleja": 2}.get(difficulty, 1)
    payload: dict[str, Any] = {
        "text": title,
        "type": habitica_type,
        "priority": priority,
        "notes": notes,
    }
    if habitica_type == "daily":
        payload["frequency"] = "weekly"
        payload["repeat"] = _repeat_map(days or [])
        payload["everyX"] = 1
        # Yesterdailies: allow marking yesterday's work before cron judges it.
        payload["yesterDaily"] = applies_damage
    if habitica_type == "habit":
        payload["up"] = True
        payload["down"] = False  # optional work only ever adds
    if habitica_type == "todo" and due_date is not None:
        payload["date"] = due_date.isoformat()
    return payload


_DAY_KEYS = {"L": "m", "M": "t", "K": "w", "J": "th", "V": "f", "S": "s", "D": "su"}


def _repeat_map(days: list[str]) -> dict[str, bool]:
    active = {_DAY_KEYS[d] for d in days if d in _DAY_KEYS}
    return {key: key in active for key in _DAY_KEYS.values()}
