"""Notion -> Habitica: keep the mirror tasks in step with the catalogues.

Notion owns definitions: which routines exist, whose they are, whether they are
mandatory, and what they are worth. Habitica only ever mirrors them.

A routine is mirrored once per target member: every listed Miembro for a
Personal routine (ADR-28), every Elegible for a Pool routine (ADR-33). The
per-member mirror ids are stored back on the routine as a JSON map in
'Habitica Task ID'.

Damage is switched on only for mandatory, non-pool dailies. Optional work is a
Habit (never subtracts) and a shared Pool task must not be able to penalise
five accounts for one undone chore.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient, build_task_payload
from ..repo import Member, Tarea, load_members, load_routines, load_tareas
from ..rules import Kind, current_todo_occurrence, is_non_weekly

log = logging.getLogger(__name__)


def _client_for(
    member: Member,
    cache: dict[str, HabiticaClient | None],
    config: Config,
) -> HabiticaClient | None:
    if member.page_id not in cache:
        creds = habitica_credentials(member.name)
        cache[member.page_id] = (
            HabiticaClient(*creds, config.habitica_client, config.request_delay_seconds)
            if creds
            else None
        )
    return cache[member.page_id]


def _task_status(
    member: Member,
    clients: dict[str, HabiticaClient | None],
    cache: dict[str, dict[str, bool]],
    config: Config,
) -> dict[str, bool]:
    """This member's Habitica task ids -> completed, fetched once per run."""
    if member.page_id not in cache:
        habitica = _client_for(member, clients, config)
        cache[member.page_id] = (
            {t["id"]: bool(t.get("completed")) for t in habitica.list_tasks() if t.get("id")}
            if habitica
            else {}
        )
    return cache[member.page_id]


def run(config: Config) -> int:
    client = n.NotionClient(config.notion_token)
    members = {m.page_id: m for m in load_members(client, config.db_miembros)}
    routines = load_routines(client, config.db_rutinas)
    tareas = load_tareas(client, config.db_tareas)
    today = date.today()

    clients: dict[str, HabiticaClient | None] = {}
    task_status_cache: dict[str, dict[str, bool]] = {}
    pushed = 0

    for routine in routines.values():
        if routine.retired:
            continue
        targets = routine.targets()
        if not targets:
            log.info("routine %r has no members/eligibles; skipped", routine.name)
            continue

        non_weekly = is_non_weekly(routine.recurrencia)
        occurrence_date = None
        if non_weekly:
            if routine.vigente_desde is None:
                log.info(
                    "routine %r (%s) has no Vigente desde; mirror skipped",
                    routine.name, routine.recurrencia,
                )
                continue
            try:
                occurrence_date = current_todo_occurrence(
                    routine.recurrencia, routine.vigente_desde, routine.dia_del_mes, today
                )
            except ValueError as exc:
                log.warning("routine %r: %s; mirror skipped", routine.name, exc)
                continue

        # ADR-26: Quincenal/Mensual/Trimestral always mirror as a Habitica
        # `todo`, even when Mandatory -- the sync recreates it itself, it
        # never relies on Habitica's native repetition for these intervals.
        habitica_type = "todo" if non_weekly else routine.habitica_tipo or (
            "daily" if routine.kind is Kind.MANDATORY else "habit"
        )
        applies_damage = (
            not non_weekly
            and routine.kind is Kind.MANDATORY
            and habitica_type == "daily"
            and not routine.is_pool
        )
        payload = build_task_payload(
            title=routine.name,
            habitica_type=habitica_type,
            difficulty=routine.difficulty.value if routine.difficulty else "Fácil",
            days=routine.dias,
            notes="Family Agile — no editar manualmente",
            applies_damage=applies_damage,
            due_date=occurrence_date,
        )

        ids = dict(routine.habitica_task_ids)  # member page id -> habitica task id

        for member_id in targets:
            member = members.get(member_id)
            if member is None or not member.active:
                continue
            habitica = _client_for(member, clients, config)
            if habitica is None:
                log.info("%s has no Habitica credentials; mirror skipped", member.name)
                continue

            if non_weekly:
                # Recreate only once the previous To-Do is gone or done.
                # An open one is left alone: never duplicated, never deleted
                # out from under a child mid-task, even once its period has
                # technically rolled over (Fallada is still applied through
                # Agenda/reconcile independently of this Habitica mirror).
                status = _task_status(member, clients, task_status_cache, config)
                if ids.get(member_id) in status and status[ids[member_id]] is False:
                    continue
                if config.dry_run:
                    log.info(
                        "[dry-run] %s <- %s (todo, %s)",
                        member.name, routine.name, occurrence_date,
                    )
                    continue
                created = habitica.create_task(payload)
                ids[member_id] = created.get("id", "")
                continue

            if config.dry_run:
                log.info(
                    "[dry-run] %s <- %s (%s%s)",
                    member.name, routine.name, habitica_type,
                    ", pool" if routine.is_pool else "",
                )
                continue
            if member_id in ids:
                habitica.update_task(ids[member_id], payload)
            else:
                created = habitica.create_task(payload)
                ids[member_id] = created.get("id", "")

        # A member removed from Miembro/Elegibles should lose their mirror.
        for stale_id in [mid for mid in ids if mid not in targets]:
            member = members.get(stale_id)
            habitica = _client_for(member, clients, config) if member else None
            if habitica and not config.dry_run:
                try:
                    habitica.delete_task(ids[stale_id])
                except Exception:
                    log.warning(
                        "could not delete stale mirror for %s / %s",
                        routine.name, stale_id,
                    )
            ids.pop(stale_id, None)

        if not config.dry_run and ids != routine.habitica_task_ids:
            client.update_page(
                routine.page_id,
                {s.Rutinas.HABITICA_TASK_ID: n.w_text(json.dumps(ids))},
            )
        pushed += 1

    pushed += _push_tareas(client, members, tareas, clients, config)

    log.info("push-definitions finished: %d definitions synced", pushed)
    return pushed


def _push_tareas(
    client: n.NotionClient,
    members: dict[str, Member],
    tareas: dict[str, Tarea],
    clients: dict[str, HabiticaClient | None],
    config: Config,
) -> int:
    """Mirror newly-approved Tareas as one-shot Habitica To-Dos.

    Only ever created once (step 2 of the Tareas flow): a Tarea that already
    has a Habitica Task ID is never re-pushed or updated here.
    """
    pushed = 0
    for tarea in tareas.values():
        if tarea.habitica_task_id:
            continue
        if not tarea.aprobada or tarea.difficulty is None:
            continue
        if tarea.member_id is None:
            log.info("tarea %r has no Miembro; mirror skipped", tarea.title)
            continue
        member = members.get(tarea.member_id)
        if member is None or not member.active:
            continue
        habitica = _client_for(member, clients, config)
        if habitica is None:
            log.info("%s has no Habitica credentials; tarea mirror skipped", member.name)
            continue

        payload = build_task_payload(
            title=tarea.title,
            habitica_type="todo",
            difficulty=tarea.difficulty.value,
            notes="Family Agile — no editar manualmente",
        )
        if config.dry_run:
            log.info("[dry-run] %s <- %s (to-do)", member.name, tarea.title)
            continue

        created = habitica.create_task(payload)
        client.update_page(
            tarea.page_id,
            {s.Tareas.HABITICA_TASK_ID: n.w_text(created.get("id", ""))},
        )
        pushed += 1

    return pushed
