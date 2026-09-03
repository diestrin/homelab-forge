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
from collections import defaultdict
from datetime import date

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import MIRROR_NOTE, HabiticaClient, build_task_payload, stale_mirror_ids
from ..repo import Member, Routine, Tarea, load_members, load_routines, load_tareas
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
    #: member page id -> every mirror id the live catalogue still points to.
    #: Used by the optional prune pass to spot orphaned Habitica tasks.
    kept: dict[str, set[str]] = defaultdict(set)

    for routine in routines.values():
        if routine.retired:
            _drop_retired_mirror(routine, members, clients, client, config)
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
            notes=MIRROR_NOTE,
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

        for mid, tid in ids.items():
            if tid and mid in targets:
                kept[mid].add(tid)

        if not config.dry_run and ids != routine.habitica_task_ids:
            client.update_page(
                routine.page_id,
                {s.Rutinas.HABITICA_TASK_ID: n.w_text(json.dumps(ids))},
            )
        pushed += 1

    pushed += _push_tareas(client, members, tareas, clients, config, kept)

    if config.prune_habitica:
        _prune_orphan_mirrors(members, kept, clients, config)

    log.info("push-definitions finished: %d definitions synced", pushed)
    return pushed


def _drop_retired_mirror(
    routine: Routine,
    members: dict[str, Member],
    clients: dict[str, HabiticaClient | None],
    client: n.NotionClient,
    config: Config,
) -> None:
    """Delete the Habitica mirrors of a routine that has been retired
    (``Vigente hasta`` set) and clear its ``Habitica Task ID`` map.

    ``push-definitions`` used to just skip retired routines, which left their
    mirrors on the children's accounts forever.
    """
    if not routine.habitica_task_ids:
        return
    for member_id, task_id in routine.habitica_task_ids.items():
        member = members.get(member_id)
        habitica = _client_for(member, clients, config) if member else None
        if config.dry_run:
            log.info("[dry-run] retire mirror %s <- %s", member_id, routine.name)
            continue
        if habitica and task_id:
            try:
                habitica.delete_task(task_id)
            except Exception:
                log.warning("could not delete retired mirror %s / %s",
                            routine.name, member_id)
    if not config.dry_run:
        client.update_page(
            routine.page_id, {s.Rutinas.HABITICA_TASK_ID: n.w_text("{}")}
        )


def _prune_orphan_mirrors(
    members: dict[str, Member],
    kept: dict[str, set[str]],
    clients: dict[str, HabiticaClient | None],
    config: Config,
) -> None:
    """Delete every Family Agile mirror an account still carries that no live
    routine or tarea references (PRUNE_HABITICA).

    Only tasks whose ``notes`` mark them as ours are ever touched -- a task a
    child made for themselves is never in scope.
    """
    for member in members.values():
        if not member.active:
            continue
        habitica = _client_for(member, clients, config)
        if habitica is None:
            continue
        orphans = stale_mirror_ids(habitica.list_tasks(), kept.get(member.page_id, set()))
        for task_id in orphans:
            if config.dry_run:
                log.info("[dry-run] prune orphan mirror %s / %s", member.name, task_id)
                continue
            try:
                habitica.delete_task(task_id)
            except Exception:
                log.warning("could not prune orphan mirror %s / %s",
                            member.name, task_id)
        if orphans:
            log.info("pruned %d orphan mirror(s) from %s", len(orphans), member.name)


def _push_tareas(
    client: n.NotionClient,
    members: dict[str, Member],
    tareas: dict[str, Tarea],
    clients: dict[str, HabiticaClient | None],
    config: Config,
    kept: dict[str, set[str]],
) -> int:
    """Mirror newly-approved Tareas as one-shot Habitica To-Dos.

    Only ever created once (step 2 of the Tareas flow): a Tarea that already
    has a Habitica Task ID is never re-pushed or updated here.
    """
    pushed = 0
    for tarea in tareas.values():
        if tarea.habitica_task_id:
            if tarea.member_id:
                kept[tarea.member_id].add(tarea.habitica_task_id)
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
            notes=MIRROR_NOTE,
        )
        if config.dry_run:
            log.info("[dry-run] %s <- %s (to-do)", member.name, tarea.title)
            continue

        created = habitica.create_task(payload)
        new_id = created.get("id", "")
        client.update_page(
            tarea.page_id, {s.Tareas.HABITICA_TASK_ID: n.w_text(new_id)}
        )
        if new_id:
            kept[tarea.member_id].add(new_id)
        pushed += 1

    return pushed
