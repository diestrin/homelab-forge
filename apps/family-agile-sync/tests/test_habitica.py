"""Tests for build_task_payload -- the pure Family Agile -> Habitica mapping.

The HTTP client itself is not exercised over the network (see README); its
retry loop is, though, via the injectable ``session`` -- see the bottom of
this file.
"""

from datetime import date

import pytest
import requests

from family_agile_sync.habitica import (
    MAX_RETRIES,
    MIRROR_NOTE,
    HabiticaClient,
    HabiticaError,
    build_task_payload,
    is_missing_task,
    payload_matches,
    stale_mirror_ids,
)


def test_daily_carries_the_repeat_map_and_yesterdaily():
    payload = build_task_payload(
        title="Tender la cama",
        habitica_type="daily",
        difficulty="Fácil",
        days=["L", "K", "V"],
        applies_damage=True,
    )
    assert payload["type"] == "daily"
    assert payload["frequency"] == "weekly"
    assert payload["repeat"] == {
        "m": True, "t": False, "w": True, "th": False,
        "f": True, "s": False, "su": False,
    }
    assert payload["yesterDaily"] is True


def test_optional_daily_never_applies_damage():
    payload = build_task_payload(
        title="Leer", habitica_type="daily", difficulty="Fácil", applies_damage=False
    )
    assert payload["yesterDaily"] is False


def test_habit_only_ever_adds():
    payload = build_task_payload(title="Ayudar", habitica_type="habit", difficulty="Fácil")
    assert payload["up"] is True
    assert payload["down"] is False


def test_todo_without_a_due_date_omits_the_date_field():
    payload = build_task_payload(title="Lavar el carro", habitica_type="todo", difficulty="Fácil")
    assert "date" not in payload
    assert "frequency" not in payload
    assert "up" not in payload


def test_todo_with_a_due_date_carries_it():
    payload = build_task_payload(
        title="Limpiar el refri",
        habitica_type="todo",
        difficulty="Intermedia",
        due_date=date(2026, 9, 15),
    )
    assert payload["date"] == "2026-09-15"


def test_priority_follows_difficulty():
    for difficulty, priority in (("Fácil", 1), ("Intermedia", 1.5), ("Compleja", 2)):
        payload = build_task_payload(title="x", habitica_type="habit", difficulty=difficulty)
        assert payload["priority"] == priority


def test_payload_matches_ignores_live_only_fields():
    payload = build_task_payload(
        title="Tender la cama", habitica_type="daily", difficulty="Fácil",
        days=["L"], notes=MIRROR_NOTE, applies_damage=False,
    )
    live = {**payload, "id": "abc", "completed": True, "streak": 12, "value": 1.5}
    assert payload_matches(live, payload)


def test_payload_matches_detects_a_renamed_daily():
    payload = build_task_payload(
        title="Tender la cama", habitica_type="daily", difficulty="Fácil",
        days=["L"], applies_damage=False,
    )
    live = {**payload, "text": "old name"}
    assert not payload_matches(live, payload)


def test_payload_matches_todo_date_prefix():
    payload = build_task_payload(
        title="x", habitica_type="todo", difficulty="Fácil", due_date=date(2026, 9, 15),
    )
    live = {**payload, "date": "2026-09-15T00:00:00.000Z"}
    assert payload_matches(live, payload)


def test_is_missing_task_only_matches_404():
    assert is_missing_task(HabiticaError(
        'PUT /tasks/x -> 404: {"success":false,"error":"NotFound"}'
    ))
    assert not is_missing_task(HabiticaError(
        "PUT /tasks/x failed after 4 attempts: connection dropped"
    ))


# --- stale_mirror_ids: the prune pass's decision -----------------------


def _task(tid, notes=MIRROR_NOTE):
    return {"id": tid, "notes": notes, "text": tid, "type": "daily"}


def test_stale_mirror_ids_returns_our_marked_tasks_not_in_kept():
    tasks = [_task("keep1"), _task("orphan1"), _task("orphan2")]
    assert stale_mirror_ids(tasks, {"keep1"}) == ["orphan1", "orphan2"]


def test_stale_mirror_ids_never_touches_unmarked_tasks():
    tasks = [
        _task("mine", MIRROR_NOTE),
        _task("childs-own", "mi tarea personal"),
        _task("no-notes", None),
        {"id": "empty-notes", "text": "x"},
    ]
    # only the marked one, and only because it isn't kept
    assert stale_mirror_ids(tasks, set()) == ["mine"]


def test_stale_mirror_ids_ignores_tasks_without_an_id():
    assert stale_mirror_ids([{"notes": MIRROR_NOTE}], set()) == []


def test_stale_mirror_ids_matches_on_the_note_prefix():
    # build_task_payload sets exactly MIRROR_NOTE, but a longer note still counts
    t = {"id": "x", "notes": MIRROR_NOTE + " (creado 2026-09)"}
    assert stale_mirror_ids([t], set()) == ["x"]


# --- _request: a dropped connection must be retried, not crash the run -

import family_agile_sync.habitica as habitica_module


class _FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {}
        self.text = ""
        self._data = data if data is not None else {}

    def json(self):
        return {"data": self._data}


class _FlakySession:
    """Replays a scripted sequence of exceptions/responses, one per call."""

    def __init__(self, script):
        self._script = list(script)

    def request(self, method, url, **kwargs):
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(session):
    return HabiticaClient("uid", "key", "x-client", delay_seconds=0, session=session)


def test_request_retries_past_a_dropped_connection(monkeypatch):
    monkeypatch.setattr(habitica_module.time, "sleep", lambda _s: None)
    session = _FlakySession([
        requests.exceptions.ConnectionError("Remote end closed connection"),
        _FakeResponse(200, {"id": "t1"}),
    ])
    assert _client(session)._request("GET", "/tasks/user") == {"id": "t1"}


def test_request_gives_up_after_exhausting_retries_on_connection_errors(monkeypatch):
    monkeypatch.setattr(habitica_module.time, "sleep", lambda _s: None)
    session = _FlakySession(
        [requests.exceptions.ConnectionError("boom")] * MAX_RETRIES
    )
    with pytest.raises(HabiticaError):
        _client(session)._request("GET", "/tasks/user")
