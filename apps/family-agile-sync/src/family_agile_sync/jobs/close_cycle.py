"""Settle one 14-day cycle, write the Corte quincenal row, and deposit the
member's net into their sobres.

This is the only job that decides money. It runs every second Friday.

The arithmetic lives in rules.py; this job is plumbing around it. Order is
fixed and matters: daily cap, then sum, then floor at zero, then convert to
colones using the member's own rate, then split across sobres by their
``% de reparto`` (ADR-013).

Idempotence: a payday run can be retried. The Corte row is looked up before it
is written, and the deposit only runs for a Corte that is not yet ``Pagado``
and has no movements linked to it -- so a second run is a no-op.
"""

from __future__ import annotations

import logging
from datetime import date

from .. import notion as n
from .. import schema as s
from ..config import Config
from ..repo import (
    load_agenda,
    load_cortes_for_cycle,
    load_members,
    load_routines,
    load_sobres,
    load_tareas,
    to_events,
)
from ..rules import close_cycle as settle
from ..rules import cycle_bounds, cycle_label, plan_deposits

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

    if not config.db_corte:
        raise RuntimeError(
            "NOTION_DB_CORTE is not set -- Corte quincenal doesn't exist yet. "
            "close-cycle cannot write a summary without it; the other three "
            "jobs don't need this value and are unaffected."
        )

    client = n.NotionClient(config.notion_token)
    members = [m for m in load_members(client, config.db_miembros) if m.active]
    routines = load_routines(client, config.db_rutinas)
    tareas = load_tareas(client, config.db_tareas)
    rows = load_agenda(client, config.db_agenda, start, end)
    existing_cortes = load_cortes_for_cycle(client, config.db_corte, start)

    has_finance = bool(config.db_sobres and config.db_movimientos)
    sobres = load_sobres(client, config.db_sobres) if has_finance else []
    will_deposit = has_finance and config.distribute
    if has_finance and not config.distribute:
        log.info("DISTRIBUTE is off: writing Corte rows, moving no money")
    elif not has_finance:
        log.info(
            "NOTION_DB_SOBRES / NOTION_DB_MOVIMIENTOS not both set: "
            "writing Corte rows only, no sobres deposit"
        )

    written = 0
    for member in members:
        member_rows = [r for r in rows if member.page_id in r.member_ids]
        if not member_rows:
            continue

        summary = settle(
            to_events(member_rows, routines, tareas), start, end, member.colones_por_punto
        )
        member_sobres = [
            (so.page_id, so.pct) for so in sobres if so.member_id == member.page_id
        ]
        plan = plan_deposits(summary.colones, member_sobres)

        log.info(
            "%s %s: %d earned, %d subtracted, %d net -> %d colones%s%s%s",
            label,
            member.name,
            summary.points_earned,
            summary.points_subtracted,
            summary.points_net,
            summary.colones,
            " [cap]" if summary.cap_applied else "",
            " [floor]" if summary.floor_applied else "",
            f" -> {_plan_repr(plan)}" if will_deposit else "",
        )

        if config.dry_run:
            written += 1
            continue

        corte = existing_cortes.get(member.page_id)
        if corte is None:
            corte = client.create_page(
                config.db_corte, _corte_props(label, member, start, end, summary)
            )
        corte_id = corte["id"]

        if will_deposit and not n.read_checkbox(corte, s.Corte.PAGADO):
            _deposit(client, config, member, summary, plan, sobres, label, end, corte_id)

        written += 1

    log.info("close-cycle finished for %s: %d summaries", label, written)
    return written


def _corte_props(label, member, start, end, summary) -> dict:
    return {
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
    }


def _deposit(client, config, member, summary, plan, sobres, label, end, corte_id) -> None:
    """Move ``summary.colones`` into ``member``'s sobres, once.

    Writes an 'Ingreso mesada' movement for the whole net, then a
    'Transferencia a sobre' movement plus a Saldo bump for each envelope's
    share, then flips the Corte's ``Pagado``. Guarded so a retry does nothing:
    if any movement is already linked to this Corte, only the flag is set.
    """
    if summary.colones <= 0:
        client.update_page(corte_id, {s.Corte.PAGADO: n.w_checkbox(True)})
        return

    linked = next(
        client.query(
            config.db_movimientos,
            {"property": s.Movimientos.CORTE, "relation": {"contains": corte_id}},
        ),
        None,
    )
    if linked is not None:
        log.info("%s %s: movements already exist for this Corte; skipping deposit",
                 label, member.name)
        client.update_page(corte_id, {s.Corte.PAGADO: n.w_checkbox(True)})
        return

    fecha = n.w_date(end)
    corte_rel = n.w_relation([corte_id])
    member_rel = n.w_relation([member.page_id])

    client.create_page(
        config.db_movimientos,
        {
            s.Movimientos.MOVIMIENTO: n.w_title(f"{label} — mesada de {member.name}"),
            s.Movimientos.MIEMBRO: member_rel,
            s.Movimientos.TIPO: n.w_select(s.TIPO_INGRESO_MESADA),
            s.Movimientos.MONTO: n.w_number(plan.income),
            s.Movimientos.FECHA: fecha,
            s.Movimientos.DESCRIPCION: n.w_text(
                f"Cierre de ciclo {label}: {summary.points_net} pts netos"
            ),
            s.Movimientos.CORTE: corte_rel,
        },
    )

    saldos = {so.page_id: so.saldo for so in sobres}
    for sobre_id, amount in plan.per_sobre:
        client.update_page(
            sobre_id,
            {s.Sobres.SALDO: n.w_number(saldos.get(sobre_id, 0) + amount)},
        )
        client.create_page(
            config.db_movimientos,
            {
                s.Movimientos.MOVIMIENTO: n.w_title(f"{label} — reparto a sobre"),
                s.Movimientos.MIEMBRO: member_rel,
                s.Movimientos.TIPO: n.w_select(s.TIPO_TRANSFERENCIA_SOBRE),
                s.Movimientos.MONTO: n.w_number(amount),
                s.Movimientos.FECHA: fecha,
                s.Movimientos.SOBRE_DESTINO: n.w_relation([sobre_id]),
                s.Movimientos.CORTE: corte_rel,
            },
        )

    if plan.unallocated:
        log.warning(
            "%s %s has no sobres; %d colones recorded as income but not split",
            label, member.name, plan.unallocated,
        )

    client.update_page(corte_id, {s.Corte.PAGADO: n.w_checkbox(True)})


def _plan_repr(plan) -> str:
    if plan.unallocated:
        return f"{plan.unallocated} colones unallocated (no sobres)"
    if not plan.per_sobre:
        return "nothing to deposit"
    return " + ".join(str(amount) for _, amount in plan.per_sobre)
