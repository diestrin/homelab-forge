"""Notion API client, narrowed to what the ledger needs.

Notion is the system of record for the allowance. Habitica reports what
happened; Notion decides what it is worth and stores the result.

Only plain property types are read or written. Formula and rollup properties
return null over the API, so every value the ledger depends on is stored as a
number, select or relation.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterator

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionError(RuntimeError):
    pass


class NotionClient:
    def __init__(self, token: str, session: requests.Session | None = None) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self._session = session or requests.Session()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        response = self._session.request(
            method, f"{BASE_URL}{path}", headers=self._headers, timeout=30, **kwargs
        )
        if not response.ok:
            raise NotionError(
                f"{method} {path} -> {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    def query(self, database_id: str, filter_: dict | None = None) -> Iterator[dict]:
        """Yield every page of a database, following pagination."""
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            payload = self._request("POST", f"/databases/{database_id}/query", json=body)
            yield from payload.get("results", [])
            if not payload.get("has_more"):
                return
            cursor = payload.get("next_cursor")

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._request(
            "PATCH", f"/pages/{page_id}", json={"properties": properties}
        )

    def create_page(self, database_id: str, properties: dict) -> dict:
        return self._request(
            "POST",
            "/pages",
            json={"parent": {"database_id": database_id}, "properties": properties},
        )


# --------------------------------------------------------------------------
# Property readers -- tolerant of empty cells, never raise on missing data
# --------------------------------------------------------------------------


def read_title(page: dict, name: str) -> str:
    parts = page.get("properties", {}).get(name, {}).get("title", []) or []
    return "".join(p.get("plain_text", "") for p in parts).strip()


def read_text(page: dict, name: str) -> str:
    parts = page.get("properties", {}).get(name, {}).get("rich_text", []) or []
    return "".join(p.get("plain_text", "") for p in parts).strip()


def read_select(page: dict, name: str) -> str | None:
    value = page.get("properties", {}).get(name, {}).get("select")
    return value.get("name") if value else None


def read_status(page: dict, name: str) -> str | None:
    value = page.get("properties", {}).get(name, {}).get("status")
    return value.get("name") if value else None


def read_number(page: dict, name: str) -> float | None:
    return page.get("properties", {}).get(name, {}).get("number")


def read_checkbox(page: dict, name: str) -> bool:
    return bool(page.get("properties", {}).get(name, {}).get("checkbox"))


def read_multi_select(page: dict, name: str) -> list[str]:
    values = page.get("properties", {}).get(name, {}).get("multi_select") or []
    return [v.get("name") for v in values]


def read_relation_ids(page: dict, name: str) -> list[str]:
    values = page.get("properties", {}).get(name, {}).get("relation") or []
    return [v.get("id") for v in values]


def read_date(page: dict, name: str) -> date | None:
    value = page.get("properties", {}).get(name, {}).get("date")
    if not value or not value.get("start"):
        return None
    return date.fromisoformat(value["start"][:10])


# --------------------------------------------------------------------------
# Property writers
# --------------------------------------------------------------------------


def w_text(value: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def w_title(value: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def w_select(value: str | None) -> dict:
    return {"select": {"name": value} if value else None}


def w_status(value: str) -> dict:
    return {"status": {"name": value}}


def w_number(value: float | None) -> dict:
    return {"number": value}


def w_checkbox(value: bool) -> dict:
    return {"checkbox": bool(value)}


def w_relation(page_ids: list[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids]}


def w_date(value: date | datetime | None) -> dict:
    if value is None:
        return {"date": None}
    return {"date": {"start": value.isoformat()}}
