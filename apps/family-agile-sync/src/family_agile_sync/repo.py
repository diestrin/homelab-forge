"""Loading Family Agile domain objects out of Notion."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from . import notion as n
from . import schema as s
from .rules import Difficulty, Event, Kind, Outcome

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Member:
    page_id: str
    name: str
    habitica_user_id: str | None
    colones_por_punto: int
    active: bool


def load_members(client: n.NotionClient, database_id: str) -> list[Member]:
    members: list[Member] = []
    for page in client.query(database_id):
        name = n.read_title(page, s.Miembros.NOMBRE)
        if not name:
            continue
        rate = n.read_number(page, s.Miembros.COLONES_POR_PUNTO)
        members.append(
            Member(
                page_id=page["id"],
                name=name,
                habitica_user_id=n.read_text(page, s.Miembros.HABITICA_USER_ID) or None,
                colones_por_punto=int(rate) if rate else 0,
                active=n.read_checkbox(page, s.Miembros.ACTIVO),
            )
        )
    return members


@dataclass(frozen=True)
class AgendaRow:
    page_id: str
    title: str
    member_ids: list[str]
    estado: str | None
    day: date | None
    habitica_task_id: str | None
    difficulty: Difficulty | None
    kind: Kind | None
    points_applied: float | None
    adjusted: bool


def _difficulty(value: str | None) -> Difficulty | None:
    try:
        return Difficulty(value) if value else None
    except ValueError:
        log.warning("unknown difficulty %r", value)
        return None


def _kind(value: str | None) -> Kind | None:
    try:
        return Kind(value) if value else None
    except ValueError:
        return None


def load_agenda(
    client: n.NotionClient,
    database_id: str,
    start: date,
    end: date,
) -> list[AgendaRow]:
    """Agenda rows whose scheduled date falls inside [start, end]."""
    filter_ = {
        "and": [
            {"property": s.Agenda.INICIA, "date": {"on_or_after": start.isoformat()}},
            {"property": s.Agenda.INICIA, "date": {"on_or_before": end.isoformat()}},
        ]
    }
    rows: list[AgendaRow] = []
    for page in client.query(database_id, filter_):
        rows.append(
            AgendaRow(
                page_id=page["id"],
                title=n.read_title(page, s.Agenda.TITULO),
                member_ids=n.read_relation_ids(page, s.Agenda.MIEMBRO),
                estado=n.read_status(page, s.Agenda.ESTADO),
                day=n.read_date(page, s.Agenda.INICIA),
                habitica_task_id=n.read_text(page, s.Agenda.HABITICA_TASK_ID) or None,
                difficulty=_difficulty(n.read_select(page, s.Agenda.DIFICULTAD))
                if s.Agenda.DIFICULTAD in page.get("properties", {})
                else None,
                kind=_kind(n.read_select(page, "Tipo")),
                points_applied=n.read_number(page, s.Agenda.PUNTOS_APLICADOS),
                adjusted=n.read_checkbox(page, s.Agenda.AJUSTADO),
            )
        )
    return rows


def to_events(rows: list[AgendaRow]) -> list[Event]:
    """Convert Agenda rows into the pure Event objects the rules operate on."""
    events: list[Event] = []
    for row in rows:
        if row.day is None or row.difficulty is None or row.kind is None:
            continue
        outcome = Outcome(row.estado) if row.estado in {o.value for o in Outcome} else Outcome.PENDING
        events.append(
            Event(
                day=row.day,
                difficulty=row.difficulty,
                kind=row.kind,
                outcome=outcome,
                adjusted_points=int(row.points_applied)
                if row.adjusted and row.points_applied is not None
                else None,
            )
        )
    return events
