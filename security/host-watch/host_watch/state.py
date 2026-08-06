from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class StateStore:
    """Persists previous findings / counters so we only alert on new items."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "state.json"
        self._data: dict[str, Any] = {
            "findings": {},
            "cpu_hits": {},
            "ipinfo_cache": {},
            "last_run": None,
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupt state: start fresh but keep a backup.
            backup = self.path.with_suffix(".json.bak")
            try:
                self.path.replace(backup)
            except OSError:
                pass

    def save(self) -> None:
        self._data["last_run"] = time.time()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def findings(self) -> dict[str, Any]:
        return self._data.setdefault("findings", {})

    @property
    def cpu_hits(self) -> dict[str, Any]:
        return self._data.setdefault("cpu_hits", {})

    @property
    def ipinfo_cache(self) -> dict[str, Any]:
        return self._data.setdefault("ipinfo_cache", {})

    def mark_finding(self, key: str, payload: dict[str, Any]) -> bool:
        """Return True if this finding is new (should notify)."""
        existing = self.findings.get(key)
        self.findings[key] = {
            **payload,
            "first_seen": (existing or {}).get("first_seen", time.time()),
            "last_seen": time.time(),
            "count": int((existing or {}).get("count", 0)) + 1,
        }
        return existing is None

    def prune_missing(self, active_keys: set[str]) -> None:
        for key in list(self.findings.keys()):
            if key not in active_keys:
                del self.findings[key]

    def bump_cpu(self, key: str) -> int:
        hits = int(self.cpu_hits.get(key, 0)) + 1
        self.cpu_hits[key] = hits
        return hits

    def clear_cpu(self, key: str) -> None:
        self.cpu_hits.pop(key, None)

    def prune_cpu(self, active_keys: set[str]) -> None:
        for key in list(self.cpu_hits.keys()):
            if key not in active_keys:
                del self.cpu_hits[key]
