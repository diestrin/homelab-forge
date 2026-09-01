"""Loading Family Agile domain objects out of Notion.

Agenda rows carry only the *result* of an occurrence (points applied, colones,
when/who marked it). Everything that defines what the occurrence is worth --
difficulty, mandatory-vs-optional, whether it pays at all, the Habitica mirror
id -- lives on the linked Rutina (or Tarea) and is resolved here by following
the relation. See ADR-32.
"""

from __future__ import annotations

import json
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
    dias: list[str]
    #: Habitica mirror task id per member page id. A Personal routine with two
    #: members, or a Pool routine with three eligibles, has that many mirrors.
    habitica_task_ids: dict[str, str]
    habitica_tipo: str | None
    retired: bool
    #: Anchor for Quincenal/Mensual/Trimestral (ADR-26); unused for Semanal.
    vigente_desde: date | None = None
    dia_del_mes: int | None = None
    #: Start time as free text ("5:00 AM"); the occurrence generator parses it
    #: onto Agenda.Inicia. None -> the generated row carries a date only.
    hora: str | None = None
    #: Rutinas.Categoría, used only to tag the generated Agenda row's Tabla.
    categoria: str | None = None

    @property
    def is_pool(self) -> bool:
        return self.modalidad == s.MODALIDAD_POOL

    def targets(self) -> list[str]:
        """Member page ids this routine should be mirrored to in Habitica.

        Pool: every eligible member (whoever finishes first claims the single
        occurrence). Personal: every listed member, each with an independent
        occurrence of their own (ADR-28).
        """
        return list(self.elegibles_ids if self.is_pool else self.member_ids)


def _parse_task_ids(raw: str) -> dict[str, str]:
    """Read the per-member mirror map stored as JSON in 'Habitica Task ID'.

    Tolerates an empty cell and legacy single-string values (from before the
    map existed); either yields an empty map, so the next push recreates the
    mirrors cleanly.
    """
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        log.warning("Habitica Task ID is not the expected JSON map: %r", raw[:80])
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if k and v}


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
            dias=n.read_multi_select(page, s.Rutinas.DIAS),
            habitica_task_ids=_parse_task_ids(
                n.read_text(page, s.Rutinas.HABITICA_TASK_ID)
            ),
            habitica_tipo=n.read_select(page, s.Rutinas.HABITICA_TIPO),
            retired=n.read_date(page, s.Rutinas.VIGENTE_HASTA) is not None,
            vigente_desde=n.read_date(page, s.Rutinas.VIGENTE_DESDE),
            dia_del_mes=_dia_del_mes(n.read_number(page, s.Rutinas.DIA_DEL_MES)),
            hora=n.read_text(page, s.Rutinas.HORA) or None,
            categoria=n.read_select(page, s.Rutinas.CATEGORIA),
        )
    return routines


def _dia_del_mes(value: float | None) -> int | None:
    return int(value) if value else None


# --------------------------------------------------------------------------
# Tareas catalogue -- one-off To-Dos (ADR: Tareas anti-inflation rule). The
# definition side of a punctual, non-recurring occurrence, same role Rutina
# plays for recurring ones.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tarea:
    page_id: str
    title: str
    member_id: str | None
    difficulty: Difficulty | None
    aprobada: bool
    habitica_task_id: str | None
    estado: str | None


def load_tareas(client: n.NotionClient, database_id: str) -> dict[str, Tarea]:
    """Every to-do in the catalogue, indexed by its Notion page id.

    Only a Tarea with a Dificultad and ``Aprobada = sí`` ever pays -- the
    anti-inflation rule: a To-Do created straight in Habitica, with no mirror
    row here, is worth gold but zero colones.
    """
    tareas: dict[str, Tarea] = {}
    for page in client.query(database_id):
        member_ids = n.read_relation_ids(page, s.Tareas.MIEMBRO)
        tareas[page["id"]] = Tarea(
            page_id=page["id"],
            title=n.read_title(page, s.Tareas.TITULO),
            member_id=member_ids[0] if member_ids else None,
            difficulty=_difficulty(n.read_select(page, s.Tareas.DIFICULTAD)),
            aprobada=n.read_checkbox(page, s.Tareas.APROBADA),
            habitica_task_id=n.read_text(page, s.Tareas.HABITICA_TASK_ID) or None,
            estado=n.read_select(page, s.Tareas.ESTADO),
        )
    return tareas


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

    def tarea(self, tareas: dict[str, Tarea]) -> Tarea | None:
        """The linked Tarea, if any of this row's relations resolves."""
        for tid in self.tarea_ids:
            if tid in tareas:
                return tareas[tid]
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


def _outcome(row: AgendaRow) -> Outcome:
    return (
        Outcome(row.estado)
        if row.estado in {o.value for o in Outcome}
        else Outcome.PENDING
    )


def _adjusted_points(row: AgendaRow) -> int | None:
    return (
        int(row.points_applied)
        if row.adjusted and row.points_applied is not None
        else None
    )


def to_events(
    rows: list[AgendaRow],
    routines: dict[str, Routine],
    tareas: dict[str, Tarea] | None = None,
) -> list[Event]:
    """Convert Agenda rows into the pure Event objects the rules operate on.

    A row becomes a ledger event by resolving to either a Rutina that pays
    (``Paga``) or a Tarea that is ``Aprobada`` with a Dificultad set -- the
    anti-inflation rule for To-Dos. Everything else -- unlinked rows, routines
    or tareas that don't pay -- is worth nothing and is dropped here rather
    than reaching the money rules.
    """
    tareas = tareas or {}
    events: list[Event] = []
    for row in rows:
        if row.day is None:
            continue

        routine = row.routine(routines)
        if routine is not None:
            if not routine.paga:
                continue
            if routine.difficulty is None or routine.kind is None:
                log.warning(
                    "routine %r lacks difficulty/kind; row %r ignored",
                    routine.name,
                    row.title,
                )
                continue
            events.append(
                Event(
                    day=row.day,
                    difficulty=routine.difficulty,
                    kind=routine.kind,
                    outcome=_outcome(row),
                    adjusted_points=_adjusted_points(row),
                )
            )
            continue

        tarea = row.tarea(tareas)
        if tarea is not None:
            if not tarea.aprobada or tarea.difficulty is None:
                continue
            events.append(
                Event(
                    day=row.day,
                    difficulty=tarea.difficulty,
                    kind=Kind.TODO,
                    outcome=_outcome(row),
                    adjusted_points=_adjusted_points(row),
                )
            )
            continue

        log.warning("agenda row %r has no known routine or tarea; ignored", row.title)
    return events
