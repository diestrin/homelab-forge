"""Mark yesterday's unfinished mandatory work as failed.

A Daily can only be known failed after Habitica's cron has passed the child's
Day Start, so this runs once a day and only ever looks backwards.

Three deliberate restraints:

* Only mandatory work is ever marked Fallada. Optional work and to-dos left
  undone stay Pendiente and are worth nothing -- absence is neutral.
* Rows whose Origen is Manual are never touched, so a parent marking directly
  in Notion always wins over this job.
* Difficulty, kind and Paga come from the linked Rutina, not the Agenda row
  (ADR-32). A routine that does not pay is still marked Fallada for the day
  board, but with zero points.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from .. import notion as n
from .. import schema as s
from ..config import Config
from ..repo import load_agenda, load_members, load_routines
from ..rules import Kind, signed_points

log = logging.getLogger(__name__)


def run(config: Config, target_day: date | None = None) -> int:
    day = target_day or (date.today() - timedelta(days=1))
    client = n.NotionClient(config.notion_token)
    members = {m.page_id: m for m in load_members(client, config.db_miembros)}
    routines = load_routines(client, config.db_rutinas)
    rows = load_agenda(client, config.db_agenda, day, day)

    failed = 0
    for row in rows:
        if row.estado != s.ESTADO_PENDIENTE or row.is_manual:
            continue

        routine = row.routine(routines)
        if routine is None or routine.kind is not Kind.MANDATORY:
            continue

        member = next((members[mid] for mid in row.member_ids if mid in members), None)
        if member is None:
            log.warning("row %s has no known member; skipped", row.title)
            continue

        if routine.paga and routine.difficulty is not None:
            points = signed_points(routine.difficulty, Kind.MANDATORY, s.ESTADO_FALLADA)
        else:
            points = 0
        colones = points * member.colones_por_punto

        if config.dry_run:
            log.info("[dry-run] %s -> Fallada (%+d pts)", row.title, points)
            failed += 1
            continue

        client.update_page(
            row.page_id,
            {
                s.Agenda.ESTADO: n.w_status(s.ESTADO_FALLADA),
                s.Agenda.PUNTOS_APLICADOS: n.w_number(points),
                s.Agenda.COLONES: n.w_number(colones),
            },
        )
        failed += 1

    log.info("reconcile finished for %s: %d rows marked Fallada", day, failed)
    return failed
