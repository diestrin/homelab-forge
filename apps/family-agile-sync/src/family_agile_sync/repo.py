"""Loading Family Agile domain objects out of Notion.

Agenda rows carry only the *result* of an occurrence (points applied, colones,
when/who marked it). Everything that defines what the occurrence is worth --
difficulty, mandatory-vs-optional, whether it pays at all, the Habitica mirror
id -- lives on the linked Rutina (or Tarea) and is resolved here by following
the relation. See ADR-32.
"""

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


# --------------------------------------------------------------------------
# Rutinas catalogue -- the definition side of an occurrence
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Routine:
    page_id: str
    name: str
    member_ids: list[str]
    elegibles_ids: list[str]
    kind: Kind | None
    modalidad: str | None
    paga: bool
    difficulty: Difficulty | None
    recurrencia: str | None
    habitica_task_id: str | None
    habitica_tipo: str | None
    retired: bool

    @property
    def is_pool(self) -> bool:
        return self.modalidad == s.MODALIDAD_POOL


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


def load_routines(client: n.NotionClient, database_id: str) -> dict[str, Routine]:
    """Every routine in the catalogue, indexed by its Notion page id."""
    routines: dict[str, Routine] = {}
    for page in client.query(database_id):
        routines[page["id"]] = Routine(
            page_id=page["id"],
            name=n.read_title(page, s.Rutinas.NOMBRE),
            member_ids=n.read_relation_ids(page, s.Rutinas.MIEMBRO),
            elegibles_ids=n.read_relation_ids(page, s.Rutinas.ELEGIBLES),
            kind=_kind(n.read_select(page, s.Rutinas.TIPO)),
            modalidad=n.read_select(page, s.Rutinas.MODALIDAD),
            paga=n.read_checkbox(page, s.Rutinas.PAGA),
            difficulty=_difficulty(n.read_select(page, s.Rutinas.DIFICULTAD)),
            recurrencia=n.read_select(page, s.Rutinas.RECURRENCIA),
            habitica_task_id=n.read_text(page, s.Rutinas.HABITICA_TASK_ID) or None,
            habitica_tipo=n.read_select(page, s.Rutinas.HABITICA_TIPO),
            retired=n.read_date(page, s.Rutinas.VIGENTE_HASTA) is not None,
        )
    return routines


# --------------------------------------------------------------------------
# Agenda -- the occurrence side (result only)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AgendaRow:
    page_id: str
    title: str
    member_ids: list[str]
    rutina_ids: list[str]
    tarea_ids: list[str]
    estado: str | None
    day: date | None
    origen: str | None
    points_applied: float | None
    adjusted: bool

    @property
    def is_manual(self) -> bool:
        """A parent recorded this directly in Notion; the sync must not touch it."""
        return self.origen == s.ORIGEN_MANUAL

    def routine(self, routines: dict[str, Routine]) -> Routine | None:
        """The linked Rutina, if any of this row's relations resolves."""
        for rid in self.rutina_ids:
            if rid in routines:
                return routines[rid]
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
                rutina_ids=n.read_relation_ids(page, s.Agenda.RUTINA),
                tarea_ids=n.read_relation_ids(page, s.Agenda.TAREA),
                estado=n.read_status(page, s.Agenda.ESTADO),
                day=n.read_date(page, s.Agenda.INICIA),
                origen=n.read_select(page, s.Agenda.ORIGEN),
                points_applied=n.read_number(page, s.Agenda.PUNTOS_APLICADOS),
                adjusted=n.read_checkbox(page, s.Agenda.AJUSTADO),
            )
        )
    return rows


def to_events(
    rows: list[AgendaRow], routines: dict[str, Routine]
) -> list[Event]:
    """Convert Agenda rows into the pure Event objects the rules operate on.

    A row only becomes a ledger event when it resolves to a routine that pays
    (``Paga``) and carries a difficulty and kind. Everything else -- unlinked
    rows, routines that exist only for the day board -- is worth nothing and is
    dropped here rather than reaching the money rules.
    """
    events: list[Event] = []
    for row in rows:
        if row.day is None:
            continue
        routine = row.routine(routines)
        if routine is None:
            log.warning("agenda row %r has no known routine; ignored", row.title)
            continue
        if not routine.paga:
            continue
        if routine.difficulty is None or routine.kind is None:
            log.warning(
                "routine %r lacks difficulty/kind; row %r ignored",
                routine.name,
                row.title,
            )
            continue
        outcome = (
            Outcome(row.estado)
            if row.estado in {o.value for o in Outcome}
            else Outcome.PENDING
        )
        events.append(
            Event(
                day=row.day,
                difficulty=routine.difficulty,
                kind=routine.kind,
                outcome=outcome,
                adjusted_points=int(row.points_applied)
                if row.adjusted and row.points_applied is not None
                else None,
            )
        )
    return events
