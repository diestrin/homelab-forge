"""Configuration, sourced entirely from the environment.

Secrets never live in git and never live in Notion. In the cluster they arrive
as a Kubernetes Secret projected from Vault by External Secrets (ADR-007).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Config:
    notion_token: str
    db_miembros: str
    db_rutinas: str
    db_agenda: str
    db_tareas: str
    anchor_friday: date
    habitica_client: str
    """X-Client header value: '<owner UserID>-<tool name>', required by Habitica."""
    request_delay_seconds: int
    dry_run: bool
    force_close: bool
    """Bypass the payday guard in close-cycle; for the parallel dry run only."""
    distribute: bool = True
    """close-cycle only: also deposit each member's cycle net into their sobres
    (ADR-013). ``DISTRIBUTE=0`` writes the Corte quincenal rows but moves no
    money -- the parallel run that Fase 4 needs, where ``DRY_RUN=1`` is no use
    because it writes nothing to compare against."""
    generate_horizon_days: int = 14
    """How many days ahead generate-occurrences materialises Agenda rows.
    ADR-27's rule is 'at least 7 so the weekly view is never empty'; 14 keeps a
    fortnight of runway and lines up with the Quincenal step."""
    db_corte: str | None = None
    """Corte quincenal database id. Only close-cycle needs it, and only on an
    actual payday -- the other three jobs never touch it. Left unset,
    push-definitions, pull-completions and reconcile run normally; close-cycle
    raises clearly the first time it actually needs to write a Corte row."""
    db_sobres: str | None = None
    db_movimientos: str | None = None
    """💵 Sobres / 🔁 Movimientos database ids. close-cycle deposits the cycle
    net into the sobres module only when both are set and ``distribute`` is on
    (ADR-013); missing either, it still writes the Corte rows and just logs
    that the deposit was skipped."""

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            notion_token=_require("NOTION_TOKEN"),
            db_miembros=_require("NOTION_DB_MIEMBROS"),
            db_rutinas=_require("NOTION_DB_RUTINAS"),
            db_agenda=_require("NOTION_DB_AGENDA"),
            db_tareas=_require("NOTION_DB_TAREAS"),
            db_corte=_optional("NOTION_DB_CORTE"),
            db_sobres=_optional("NOTION_DB_SOBRES"),
            db_movimientos=_optional("NOTION_DB_MOVIMIENTOS"),
            anchor_friday=date.fromisoformat(_require("CYCLE_ANCHOR_FRIDAY")),
            habitica_client=_require("HABITICA_CLIENT"),
            request_delay_seconds=_int("HABITICA_REQUEST_DELAY", 30),
            generate_horizon_days=_int("GENERATE_HORIZON_DAYS", 14),
            dry_run=os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"},
            force_close=os.environ.get("FORCE_CLOSE", "").lower() in {"1", "true", "yes"},
            distribute=os.environ.get("DISTRIBUTE", "").lower()
            not in {"0", "false", "no"},
        )


def habitica_credentials(member_name: str) -> tuple[str, str] | None:
    """Per-member Habitica credentials, e.g. HABITICA_LUCAS_USER / _KEY.

    Returns None when the member has no account (or has not been onboarded
    yet), so jobs can skip them instead of failing the whole run.
    """
    slug = member_name.strip().upper().replace(" ", "_")
    user = os.environ.get(f"HABITICA_{slug}_USER", "").strip()
    key = os.environ.get(f"HABITICA_{slug}_KEY", "").strip()
    if not user or not key:
        return None
    return user, key
