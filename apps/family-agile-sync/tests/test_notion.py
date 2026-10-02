"""NotionClient retries transient gateway failures.

The HTTP client is not exercised over the network. The retry loop is, via the
injectable session -- the same approach as test_habitica.py.
"""

import pytest
import requests

from family_agile_sync.notion import MAX_RETRIES, NotionClient, NotionError

import family_agile_sync.notion as notion_module


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text="nope"):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.headers = headers or {}
        self.text = text
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        return self._payload


class _FlakySession:
    """Replays a scripted sequence of exceptions or responses, one per call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(session):
    return NotionClient("token", session=session)


def test_request_retries_past_a_read_timeout(monkeypatch):
    monkeypatch.setattr(notion_module.time, "sleep", lambda _s: None)
    session = _FlakySession([
        requests.exceptions.ReadTimeout("read timed out"),
        _FakeResponse(200, {"results": []}),
    ])
    assert _client(session)._request("POST", "/databases/db/query") == {"results": []}
    assert session.calls == 2


def test_request_retries_past_a_gateway_timeout(monkeypatch):
    slept = []
    monkeypatch.setattr(notion_module.time, "sleep", slept.append)
    session = _FlakySession([
        _FakeResponse(504, text="<!DOCTYPE html><title>Notion</title>"),
        _FakeResponse(200, {"results": [{"id": "p1"}]}),
    ])
    assert _client(session)._request("POST", "/databases/db/query") == {
        "results": [{"id": "p1"}],
    }
    assert slept == [2]


def test_request_gives_up_after_exhausting_retries_on_timeouts(monkeypatch):
    monkeypatch.setattr(notion_module.time, "sleep", lambda _s: None)
    session = _FlakySession(
        [requests.exceptions.ReadTimeout("read timed out")] * MAX_RETRIES
    )
    with pytest.raises(NotionError, match="failed after"):
        _client(session)._request("POST", "/databases/db/query")
    assert session.calls == MAX_RETRIES


def test_request_does_not_retry_a_client_error(monkeypatch):
    monkeypatch.setattr(notion_module.time, "sleep", lambda _s: None)
    session = _FlakySession([
        _FakeResponse(400, text="bad filter"),
        _FakeResponse(200, {"ok": True}),
    ])
    with pytest.raises(NotionError, match="400"):
        _client(session)._request("POST", "/databases/db/query")
    assert session.calls == 1
