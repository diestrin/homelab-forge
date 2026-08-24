"""Habitica -> Notion: record what actually happened.

Runs hourly during waking hours. It must run often: Habitica resets a Daily's
completed flag at each cron, and its export keeps the cron's timestamp rather
than the moment the child actually ticked the box. If this job only ran once a
day, work completed and reset in between would vanish.

Idempotent by construction: Agenda rows already exist in 'Pendiente' from the
routine generator, so this job only ever transitions Pendiente -> Hecha. A
re-run finds the row already Hecha and skips it, so points are never doubled.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from .. import notion as n
from .. import schema as s
from ..config import Config, habitica_credentials
from ..habitica import HabiticaClient
from ..repo import load_agenda, load_members
from ..rules import signed_points

log = logging.getLogger(__name__)


def run(config: Config, today: date | None = None) -> int:
    today = today or date.today()
    client = n.NotionClient(config.notion_token)
    members = [m for m in load_members(client, config.db_miembros) if m.active]
    rows = load_agenda(client, config.db_agenda, today, today)

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
        if not completed_ids:
            continue

        pending = [
            row
            for row in rows
            if member.page_id in row.member_ids
            and row.estado == s.ESTADO_PENDIENTE
            and row.habitica_task_id in completed_ids
        ]

        for row in pending:
            if row.difficulty is None or row.kind is None:
                log.warning("row %s lacks difficulty/kind; left pending", row.title)
                continue

            points = signed_points(row.difficulty, row.kind, "Hecha")
            colones = points * member.colones_por_punto

            if config.dry_run:
                log.info("[dry-run] %s -> Hecha (%+d pts, %d colones)",
                         row.title, points, colones)
                updated += 1
                continue

            client.update_page(
                row.page_id,
                {
                    s.Agenda.ESTADO: n.w_status(s.ESTADO_HECHA),
                    s.Agenda.PUNTOS_APLICADOS: n.w_number(points),
                    s.Agenda.COLONES: n.w_number(colones),
                    s.Agenda.MARCADO_EN: n.w_date(datetime.now().astimezone()),
                    s.Agenda.ORIGEN: n.w_select(s.ORIGEN_HABITICA),
                },
            )
            updated += 1
            log.info("%s: %s -> Hecha (%+d pts)", member.name, row.title, points)

    log.info("pull-completions finished: %d rows updated", updated)
    return updated
