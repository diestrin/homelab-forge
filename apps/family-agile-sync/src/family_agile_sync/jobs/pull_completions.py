"""Habitica -> Notion: record what actually happened.

Runs hourly during waking hours. It must run often: Habitica resets a Daily's
completed flag at each cron, and its export keeps the cron's timestamp rather
than the moment the child actually ticked the box. If this job only ran once a
day, work completed and reset in between would vanish.

Idempotent by construction: Agenda rows already exist in 'Pendiente' from the
routine generator, so this job only ever transitions Pendiente -> Hecha. A
re-run finds the row already Hecha and skips it, so points are never doubled.

Difficulty, kind, Paga and the per-member Habitica mirror ids are read from the
linked Rutina, never from the Agenda row (ADR-32).

Pool routines (ADR-33): the routine is mirrored to every eligible account and
the single Agenda occurrence sits unclaimed (empty Miembro). The first eligible
to tick it claims the row and their losing mirrors are deleted so nobody else
can be credited for it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient
from ..repo import Member, Routine, Tarea, load_agenda, load_members, load_routines, load_tareas
from ..rules import points_earned, signed_points

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Costa_Rica")


def _credit(routine: Routine, member: Member) -> tuple[int, int]:
    """Signed points and colones for completing this routine's occurrence."""
    if routine.paga and routine.difficulty is not None and routine.kind is not None:
        points = signed_points(routine.difficulty, routine.kind, s.ESTADO_HECHA)
    else:
        points = 0
    return points, points * member.colones_por_punto


def _hecha_props(member: Member, points: int, colones: int, *, claim: bool) -> dict:
    props = {
        s.Agenda.ESTADO: n.w_status(s.ESTADO_HECHA),
        s.Agenda.PUNTOS_APLICADOS: n.w_number(points),
        s.Agenda.COLONES: n.w_number(colones),
        s.Agenda.MARCADO_EN: n.w_date(datetime.now(TZ)),
        s.Agenda.MARCADO_POR: n.w_relation([member.page_id]),
        s.Agenda.ORIGEN: n.w_select(s.ORIGEN_HABITICA),
    }
    if claim:  # Pool: the winner also becomes the row's Miembro.
        props[s.Agenda.MIEMBRO] = n.w_relation([member.page_id])
    return props


def _tarea_agenda_props(
    tarea: Tarea, member: Member, today: date, points: int, colones: int
) -> dict:
    """A Tarea has no pre-existing Pendiente row (unlike Rutinas): completing
    it in Habitica creates the Agenda row on the spot -- steps 4-5 of the
    Tareas flow."""
    return {
        s.Agenda.TITULO: n.w_title(tarea.title),
        s.Agenda.MIEMBRO: n.w_relation([member.page_id]),
        s.Agenda.TAREA: n.w_relation([tarea.page_id]),
        s.Agenda.ESTADO: n.w_status(s.ESTADO_HECHA),
        s.Agenda.INICIA: n.w_date(today),
        s.Agenda.PUNTOS_APLICADOS: n.w_number(points),
        s.Agenda.COLONES: n.w_number(colones),
        s.Agenda.MARCADO_EN: n.w_date(datetime.now(TZ)),
        s.Agenda.MARCADO_POR: n.w_relation([member.page_id]),
        s.Agenda.ORIGEN: n.w_select(s.ORIGEN_HABITICA),
    }


def run(config: Config, today: date | None = None) -> int:
    today = today or date.today()
    client = n.NotionClient(config.notion_token)
    members = {m.page_id: m for m in load_members(client, config.db_miembros)}
    routines = load_routines(client, config.db_rutinas)
    tareas = load_tareas(client, config.db_tareas)
    rows = load_agenda(client, config.db_agenda, today, today)

    # habitica task id -> (routine, page id of the member that mirror belongs to)
    mirror: dict[str, tuple[Routine, str]] = {}
    for routine in routines.values():
        for member_id, task_id in routine.habitica_task_ids.items():
            mirror[task_id] = (routine, member_id)

    clients: dict[str, HabiticaClient | None] = {}

    def client_for(member: Member) -> HabiticaClient | None:
        if member.page_id not in clients:
            creds = habitica_credentials(member.name)
            clients[member.page_id] = (
                HabiticaClient(
                    *creds, config.habitica_client, config.request_delay_seconds
                )
                if creds
                else None
            )
        return clients[member.page_id]

    updated = 0
    claimed_pool: set[str] = set()  # routine page ids claimed during this run

    for member in [m for m in members.values() if m.active]:
        habitica = client_for(member)
        if habitica is None:
            log.info("%s has no Habitica credentials; skipping", member.name)
            continue

        completed_ids = {
            task["id"]
            for task in habitica.list_tasks()
            if task.get("completed") and task.get("id")
        }
        # Routines whose *own* mirror this member ticked.
        hit_routines = {
            mirror[tid][0].page_id: mirror[tid][0]
            for tid in completed_ids
            if tid in mirror and mirror[tid][1] == member.page_id
        }
        # Tareas whose mirror To-Do this member ticked, not yet credited.
        hit_tareas = [
            t for t in tareas.values()
            if t.member_id == member.page_id
            and t.habitica_task_id in completed_ids
            and t.estado != s.ESTADO_HECHA
        ]
        if not hit_routines and not hit_tareas:
            continue

        for routine in hit_routines.values():
            points, colones = _credit(routine, member)

            if routine.is_pool:
                if routine.page_id in claimed_pool:
                    log.info(
                        "pool %r already claimed this run; %s keeps Habitica gold only",
                        routine.name, member.name,
                    )
                    continue
                row = next(
                    (
                        r for r in rows
                        if r.estado == s.ESTADO_PENDIENTE
                        and not r.is_manual
                        and not r.member_ids
                        and routine.page_id in r.rutina_ids
                    ),
                    None,
                )
                if row is None:
                    log.info(
                        "no unclaimed pool row today for %r; %s not credited",
                        routine.name, member.name,
                    )
                    continue

                if config.dry_run:
                    log.info(
                        "[dry-run] POOL %s claimed by %s -> Hecha (%+d pts, %d colones)",
                        routine.name, member.name, points, colones,
                    )
                else:
                    client.update_page(
                        row.page_id, _hecha_props(member, points, colones, claim=True)
                    )
                    for loser_id, task_id in routine.habitica_task_ids.items():
                        if loser_id == member.page_id:
                            continue
                        loser = members.get(loser_id)
                        loser_client = client_for(loser) if loser else None
                        if loser_client is None:
                            continue
                        try:
                            loser_client.delete_task(task_id)
                        except Exception:
                            log.warning(
                                "could not remove losing mirror %s for pool %r",
                                loser_id, routine.name,
                            )
                claimed_pool.add(routine.page_id)
                updated += 1
                log.info("pool %r claimed by %s (%+d pts)", routine.name, member.name, points)
                continue

            # Personal: this member's own occurrence for today.
            row = next(
                (
                    r for r in rows
                    if member.page_id in r.member_ids
                    and r.estado == s.ESTADO_PENDIENTE
                    and not r.is_manual
                    and routine.page_id in r.rutina_ids
                ),
                None,
            )
            if row is None:
                continue

            if config.dry_run:
                log.info(
                    "[dry-run] %s: %s -> Hecha (%+d pts, %d colones)",
                    member.name, row.title, points, colones,
                )
            else:
                client.update_page(
                    row.page_id, _hecha_props(member, points, colones, claim=False)
                )
            updated += 1
            log.info("%s: %s -> Hecha (%+d pts)", member.name, row.title, points)

        # To-Dos: no pre-existing Pendiente row -- the Agenda row is created
        # here, on completion (steps 4-5 of the Tareas flow).
        for tarea in hit_tareas:
            points = points_earned(tarea.difficulty) if tarea.difficulty else 0
            colones = points * member.colones_por_punto

            if config.dry_run:
                log.info(
                    "[dry-run] %s: %s -> Hecha (%+d pts, %d colones)",
                    member.name, tarea.title, points, colones,
                )
            else:
                client.create_page(
                    config.db_agenda,
                    _tarea_agenda_props(tarea, member, today, points, colones),
                )
                client.update_page(
                    tarea.page_id, {s.Tareas.ESTADO: n.w_select(s.ESTADO_HECHA)}
                )
            updated += 1
            log.info("%s: to-do %r -> Hecha (%+d pts)", member.name, tarea.title, points)

    log.info("pull-completions finished: %d rows updated", updated)
    return updated
