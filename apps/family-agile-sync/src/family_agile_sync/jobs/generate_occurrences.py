"""Notion -> Notion: materialise Agenda occurrences from the Rutinas catalogue.

Every other job in this service assumes the ``Pendiente`` Agenda rows already
exist -- ``pull-completions`` transitions them, ``reconcile`` fails them,
``close-cycle`` settles them. This is the job that creates them.

It walks the active catalogue and, for every day in a rolling horizon, creates
one Agenda row per routine occurrence (ADR-27's v0 algorithm, now
``rules.occurs_on``):

* **Personal** routine -> one row per listed ``Miembro`` (ADR-28), each an
  independent occurrence.
* **Pool** routine -> one unclaimed row (empty ``Miembro``); whoever finishes
  first claims it in ``pull-completions`` (ADR-33).

Idempotent by construction: it only ever *creates*, never updates. An
occurrence that already has a row -- generated on an earlier run, or entered by
hand -- is skipped, and a row a parent set to ``Origen = Manual`` is left
untouched like everywhere else in the sync.

Non-weekly routines (Quincenal/Mensual/Trimestral) get their Agenda rows here
too: ``reconcile`` needs them to fail a missed mandatory window. The separate
Habitica ``todo`` mirror those routines carry is ``push-definitions``' concern
(ADR-26) and does not depend on this job.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from .. import notion as n
from .. import schema as s
from ..config import Config
from ..repo import Routine, load_agenda, load_routines
from ..rules import occurs_on

log = logging.getLogger(__name__)

#: Rutinas.Categoría -> Agenda.Tabla. Best-effort tagging for the day board;
#: no job reads Tabla. Only the unambiguous mapping is kept -- an unmapped
#: category leaves Tabla unset rather than inventing an option.
_TABLA_BY_CATEGORIA = {"Casa": "Limpieza"}


def _parse_hora(value: str | None) -> time | None:
    """``"5:00 AM"`` / ``"17:30"`` -> ``time``; anything else -> ``None``."""
    if not value:
        return None
    text = " ".join(value.strip().upper().replace(".", "").split())
    for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%H"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    log.warning("unparseable Hora %r; row gets a date only", value)
    return None


def _inicia(day: date, hora: time | None) -> datetime | date:
    return datetime.combine(day, hora) if hora is not None else day


def _targets(routine: Routine) -> list[str | None]:
    """The ``Miembro`` value for each row this routine's occurrence produces.

    Pool -> a single unclaimed row (``None``). Personal -> one row per listed
    member. A Personal routine with no members produces nothing.
    """
    return [None] if routine.is_pool else list(routine.member_ids)


def _row_props(routine: Routine, day: date, member_id: str | None) -> dict:
    props = {
        s.Agenda.TITULO: n.w_title(routine.name),
        s.Agenda.RUTINA: n.w_relation([routine.page_id]),
        s.Agenda.MIEMBRO: n.w_relation([member_id] if member_id else []),
        s.Agenda.ESTADO: n.w_status(s.ESTADO_PENDIENTE),
        s.Agenda.INICIA: n.w_date(_inicia(day, _parse_hora(routine.hora))),
        s.Agenda.ORIGEN: n.w_select(s.ORIGEN_NOTION),
    }
    tabla = _TABLA_BY_CATEGORIA.get(routine.categoria or "")
    if tabla:
        props[s.Agenda.TABLA] = n.w_select(tabla)
    return props


def run(config: Config, today: date | None = None) -> int:
    today = today or date.today()
    last_day = today + timedelta(days=config.generate_horizon_days - 1)

    client = n.NotionClient(config.notion_token)
    routines = load_routines(client, config.db_rutinas)
    existing = load_agenda(client, config.db_agenda, today, last_day)

    # What already occupies a slot, so nothing is created twice:
    #   personal -> (routine id, member id, iso day)
    #   pool     -> (routine id, iso day)   -- claimed or not
    seen_personal: set[tuple[str, str, str]] = set()
    seen_pool: set[tuple[str, str]] = set()
    for row in existing:
        if row.day is None:
            continue
        iso = row.day.isoformat()
        for rid in row.rutina_ids:
            seen_pool.add((rid, iso))
            for mid in row.member_ids:
                seen_personal.add((rid, mid, iso))

    created = 0
    for routine in routines.values():
        if routine.retired:
            continue
        targets = _targets(routine)
        if not targets:
            log.info("routine %r has no members; nothing to generate", routine.name)
            continue

        day = today
        while day <= last_day:
            if occurs_on(
                day,
                routine.recurrencia,
                routine.dias,
                routine.vigente_desde,
                routine.dia_del_mes,
            ):
                iso = day.isoformat()
                for member_id in targets:
                    if routine.is_pool:
                        if (routine.page_id, iso) in seen_pool:
                            continue
                    elif (routine.page_id, member_id, iso) in seen_personal:
                        continue

                    if config.dry_run:
                        log.info(
                            "[dry-run] + Agenda | %s | %s | %s",
                            iso, routine.name, member_id or "pool",
                        )
                    else:
                        client.create_page(
                            config.db_agenda, _row_props(routine, day, member_id)
                        )
                    created += 1
                    if routine.is_pool:
                        seen_pool.add((routine.page_id, iso))
                    else:
                        seen_personal.add((routine.page_id, member_id, iso))
            day += timedelta(days=1)

    log.info(
        "generate-occurrences finished: %d rows created for %s..%s",
        created, today, last_day,
    )
    return created
