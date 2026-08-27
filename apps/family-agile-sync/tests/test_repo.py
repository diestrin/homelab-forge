"""Tests for the Agenda -> Rutina join and the Paga gate (ADR-32, ADR-15).

These exercise the pure conversion in repo.to_events; the Notion client is
never touched.
"""

from datetime import date

from family_agile_sync.repo import AgendaRow, Routine, to_events
from family_agile_sync.rules import Difficulty, Kind, Outcome

D = date(2026, 8, 24)


def routine(page_id="r1", *, paga=True, difficulty=Difficulty.INTERMEDIA,
            kind=Kind.MANDATORY, modalidad="Personal"):
    return Routine(
        page_id=page_id,
        name=f"routine {page_id}",
        member_ids=["m1"],
        elegibles_ids=[],
        kind=kind,
        modalidad=modalidad,
        paga=paga,
        difficulty=difficulty,
        recurrencia="Semanal",
        habitica_task_id=f"h-{page_id}",
        habitica_tipo="daily",
        retired=False,
    )


def row(page_id="a1", *, rutina_ids=("r1",), estado="Hecha", day=D,
        origen=None, points_applied=None, adjusted=False):
    return AgendaRow(
        page_id=page_id,
        title=f"row {page_id}",
        member_ids=["m1"],
        rutina_ids=list(rutina_ids),
        tarea_ids=[],
        estado=estado,
        day=day,
        origen=origen,
        points_applied=points_applied,
        adjusted=adjusted,
    )


def test_difficulty_and_kind_come_from_the_linked_routine():
    routines = {"r1": routine(difficulty=Difficulty.COMPLEJA, kind=Kind.MANDATORY)}
    events = to_events([row(estado="Hecha")], routines)
    assert len(events) == 1
    assert events[0].difficulty is Difficulty.COMPLEJA
    assert events[0].kind is Kind.MANDATORY
    assert events[0].outcome is Outcome.DONE
    assert events[0].points == 25


def test_row_whose_routine_does_not_pay_is_dropped():
    routines = {"r1": routine(paga=False)}
    assert to_events([row()], routines) == []


def test_row_with_no_resolvable_routine_is_dropped():
    assert to_events([row(rutina_ids=())], {"r1": routine()}) == []
    assert to_events([row(rutina_ids=("ghost",))], {"r1": routine()}) == []


def test_row_whose_routine_lacks_difficulty_is_dropped():
    routines = {"r1": routine(difficulty=None)}
    assert to_events([row()], routines) == []


def test_unknown_estado_is_treated_as_pending():
    events = to_events([row(estado=None)], {"r1": routine()})
    assert events[0].outcome is Outcome.PENDING
    assert events[0].points == 0


def test_adjusted_points_override_the_table():
    r = row(estado="Fallada", adjusted=True, points_applied=0)
    events = to_events([r], {"r1": routine(kind=Kind.MANDATORY)})
    assert events[0].points == 0  # would be -5 from the table


def test_is_manual_flag():
    assert row(origen="Manual").is_manual
    assert not row(origen="Habitica").is_manual
    assert not row(origen=None).is_manual


def test_is_pool_flag():
    assert routine(modalidad="Pool").is_pool
    assert not routine(modalidad="Personal").is_pool
