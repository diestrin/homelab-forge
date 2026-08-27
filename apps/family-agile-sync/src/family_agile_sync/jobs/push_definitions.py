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

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient, build_task_payload
from ..repo import Member, load_members, load_routines
from ..rules import Kind

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


def run(config: Config) -> int:
    client = n.NotionClient(config.notion_token)
    members = {m.page_id: m for m in load_members(client, config.db_miembros)}
    routines = load_routines(client, config.db_rutinas)

    clients: dict[str, HabiticaClient | None] = {}
    pushed = 0

    for routine in routines.values():
        if routine.retired:
            continue
        targets = routine.targets()
        if not targets:
            log.info("routine %r has no members/eligibles; skipped", routine.name)
            continue

        habitica_type = routine.habitica_tipo or (
            "daily" if routine.kind is Kind.MANDATORY else "habit"
        )
        applies_damage = (
            routine.kind is Kind.MANDATORY
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

    log.info("push-definitions finished: %d routines synced", pushed)
    return pushed
