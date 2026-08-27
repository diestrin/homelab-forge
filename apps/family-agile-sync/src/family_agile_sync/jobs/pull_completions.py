"""Habitica -> Notion: record what actually happened.

Runs hourly during waking hours. It must run often: Habitica resets a Daily's
completed flag at each cron, and its export keeps the cron's timestamp rather
than the moment the child actually ticked the box. If this job only ran once a
day, work completed and reset in between would vanish.

Idempotent by construction: Agenda rows already exist in 'Pendiente' from the
routine generator, so this job only ever transitions Pendiente -> Hecha. A
re-run finds the row already Hecha and skips it, so points are never doubled.

Difficulty, kind and the Habitica mirror id are read from the linked Rutina,
never from the Agenda row (ADR-32).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient
from ..repo import load_agenda, load_members, load_routines
from ..rules import signed_points

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Costa_Rica")


def run(config: Config, today: date | None = None) -> int:
    today = today or date.today()
    client = n.NotionClient(config.notion_token)
    members = [m for m in load_members(client, config.db_miembros) if m.active]
    routines = load_routines(client, config.db_rutinas)
    rows = load_agenda(client, config.db_agenda, today, today)

    # Habitica task id -> routine, for matching completions back to the catalogue.
    mirror_to_routine = {
        r.habitica_task_id: r for r in routines.values() if r.habitica_task_id
    }

    updated = 0
    for member in members:
        credentials = habitica_credentials(member.name)
        if not credentials:
            log.info("%s has no Habitica credentials; skipping", member.name)
            continue

        user_id, api_key = credentials
        habitica = HabiticaClient(
            user_id, api_key, config.habitica_client, config.request_delay_seconds
        )

        completed_ids = {
            task["id"]
            for task in habitica.list_tasks()
            if task.get("completed") and task.get("id")
        }
        completed_routines = {
            mirror_to_routine[tid].page_id
            for tid in completed_ids
            if tid in mirror_to_routine
        }
        if not completed_routines:
            continue

        for row in rows:
            if member.page_id not in row.member_ids:
                continue
            if row.estado != s.ESTADO_PENDIENTE or row.is_manual:
                continue
            routine = row.routine(routines)
            if routine is None or routine.page_id not in completed_routines:
                continue

            if routine.paga and routine.difficulty is not None and routine.kind is not None:
                points = signed_points(routine.difficulty, routine.kind, s.ESTADO_HECHA)
            else:
                points = 0
            colones = points * member.colones_por_punto

            if config.dry_run:
                log.info(
                    "[dry-run] %s: %s -> Hecha (%+d pts, %d colones)",
                    member.name, row.title, points, colones,
                )
                updated += 1
                continue

            client.update_page(
                row.page_id,
                {
                    s.Agenda.ESTADO: n.w_status(s.ESTADO_HECHA),
                    s.Agenda.PUNTOS_APLICADOS: n.w_number(points),
                    s.Agenda.COLONES: n.w_number(colones),
                    s.Agenda.MARCADO_EN: n.w_date(datetime.now(TZ)),
                    s.Agenda.MARCADO_POR: n.w_relation([member.page_id]),
                    s.Agenda.ORIGEN: n.w_select(s.ORIGEN_HABITICA),
                },
            )
            updated += 1
            log.info("%s: %s -> Hecha (%+d pts)", member.name, row.title, points)

    log.info("pull-completions finished: %d rows updated", updated)
    return updated
