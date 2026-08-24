"""Notion -> Habitica: keep the mirror tasks in step with the catalogues.

Notion owns definitions: which routines exist, whose they are, whether they are
mandatory, and what they are worth. Habitica only ever mirrors them.

Damage is switched on for mandatory dailies and off for everything else. That
one flag is the difference between the system that failed (silent penalties by
default) and this one.
"""

from __future__ import annotations

import logging

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient, build_task_payload
from ..repo import load_members

log = logging.getLogger(__name__)


def run(config: Config) -> int:
    client = n.NotionClient(config.notion_token)
    members = {m.page_id: m for m in load_members(client, config.db_miembros) if m.active}

    pushed = 0
    clients: dict[str, HabiticaClient] = {}

    for page in client.query(config.db_rutinas):
        vigente_hasta = n.read_date(page, s.Rutinas.VIGENTE_HASTA)
        if vigente_hasta is not None:
            continue  # retired routine: leave Habitica alone

        member_ids = n.read_relation_ids(page, s.Rutinas.MIEMBRO)
        member = next((members[mid] for mid in member_ids if mid in members), None)
        if member is None:
            continue

        if member.name not in clients:
            credentials = habitica_credentials(member.name)
            if not credentials:
                continue
            clients[member.name] = HabiticaClient(
                *credentials, config.habitica_client, config.request_delay_seconds
            )
        habitica = clients[member.name]

        title = n.read_title(page, s.Rutinas.NOMBRE)
        kind = n.read_select(page, s.Rutinas.TIPO) or "Opcional"
        difficulty = n.read_select(page, s.Rutinas.DIFICULTAD) or "Fácil"
        habitica_type = n.read_select(page, s.Rutinas.HABITICA_TIPO) or (
            "daily" if kind == "Mandatory" else "habit"
        )
        days = n.read_multi_select(page, s.Rutinas.DIAS)
        existing_id = n.read_text(page, s.Rutinas.HABITICA_TASK_ID) or None

        payload = build_task_payload(
            title=title,
            habitica_type=habitica_type,
            difficulty=difficulty,
            days=days,
            notes="Family Agile — no editar manualmente",
            applies_damage=(kind == "Mandatory" and habitica_type == "daily"),
        )

        if config.dry_run:
            log.info("[dry-run] %s: %s %s", member.name, habitica_type, title)
            pushed += 1
            continue

        if existing_id:
            habitica.update_task(existing_id, payload)
        else:
            created = habitica.create_task(payload)
            client.update_page(
                page["id"],
                {s.Rutinas.HABITICA_TASK_ID: n.w_text(created.get("id", ""))},
            )
        pushed += 1

    log.info("push-definitions finished: %d routines synced", pushed)
    return pushed
