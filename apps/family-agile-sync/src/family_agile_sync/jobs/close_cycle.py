"""Settle one 14-day cycle and write the Corte quincenal row.

This is the only job that decides money. It runs every second Friday.

The arithmetic lives in rules.py; this job is plumbing around it. Order is
fixed and matters: daily cap, then sum, then floor at zero, then convert to
colones using the member's own rate.
"""

from __future__ import annotations

import logging
from datetime import date

from .. import notion as n
from .. import schema as s
from ..config import Config
from ..repo import load_agenda, load_members, load_routines, load_tareas, to_events
from ..rules import close_cycle as settle
from ..rules import cycle_bounds, cycle_label

log = logging.getLogger(__name__)


def run(config: Config, today: date | None = None) -> int:
    today = today or date.today()
    start, end = cycle_bounds(today, config.anchor_friday)
    label = cycle_label(today, config.anchor_friday)

    # Cron cannot express "every second Friday", so the CronJob fires every
    # Friday and the calendar decides here. Without this guard the job would
    # write a summary -- and a payment -- every week.
    if today != end and not config.force_close:
        log.info("%s is not a payday (cycle %s closes %s); nothing to do",
                 today, label, end)
        return 0

    client = n.NotionClient(config.notion_token)
    members = [m for m in load_members(client, config.db_miembros) if m.active]
    routines = load_routines(client, config.db_rutinas)
    tareas = load_tareas(client, config.db_tareas)
    rows = load_agenda(client, config.db_agenda, start, end)

    written = 0
    for member in members:
        member_rows = [r for r in rows if member.page_id in r.member_ids]
        if not member_rows:
            continue

        summary = settle(
            to_events(member_rows, routines, tareas), start, end, member.colones_por_punto
        )

        log.info(
            "%s %s: %d earned, %d subtracted, %d net -> %d colones%s%s",
            label,
            member.name,
            summary.points_earned,
            summary.points_subtracted,
            summary.points_net,
            summary.colones,
            " [cap]" if summary.cap_applied else "",
            " [floor]" if summary.floor_applied else "",
        )

        if config.dry_run:
            written += 1
            continue

        client.create_page(
            config.db_corte,
            {
                s.Corte.CICLO: n.w_title(f"{label} — {member.name}"),
                s.Corte.MIEMBRO: n.w_relation([member.page_id]),
                s.Corte.DESDE: n.w_date(start),
                s.Corte.HASTA: n.w_date(end),
                s.Corte.MANDATORY_ASIGNADAS: n.w_number(summary.mandatory_assigned),
                s.Corte.MANDATORY_CUMPLIDAS: n.w_number(summary.mandatory_done),
                s.Corte.MANDATORY_FALLADAS: n.w_number(summary.mandatory_failed),
                s.Corte.OPCIONALES: n.w_number(summary.optional_done),
                s.Corte.TODOS: n.w_number(summary.todos_done),
                s.Corte.PUNTOS_GANADOS: n.w_number(summary.points_earned),
                s.Corte.PUNTOS_RESTADOS: n.w_number(summary.points_subtracted),
                s.Corte.PUNTOS_NETOS: n.w_number(summary.points_net),
                s.Corte.COLONES: n.w_number(summary.colones),
                s.Corte.TOPE_APLICADO: n.w_checkbox(summary.cap_applied),
                s.Corte.PISO_APLICADO: n.w_checkbox(summary.floor_applied),
                s.Corte.PAGADO: n.w_checkbox(False),
            },
        )
        written += 1

    log.info("close-cycle finished for %s: %d summaries", label, written)
    return written
