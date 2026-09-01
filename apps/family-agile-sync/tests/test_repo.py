"""Tests for the Agenda -> Rutina join, the Paga gate and mirror targeting
(ADR-32, ADR-15, ADR-28, ADR-33).

These exercise pure functions in repo; the Notion client is never touched.
"""

from datetime import date

from family_agile_sync.repo import (
    AgendaRow,
    Routine,
    Tarea,
    _parse_task_ids,
    to_events,
)
from family_agile_sync.rules import Difficulty, Kind, Outcome

D = date(2026, 8, 24)


def routine(page_id="r1", *, paga=True, difficulty=Difficulty.INTERMEDIA,
            kind=Kind.MANDATORY, modalidad="Personal", member_ids=("m1",),
            elegibles_ids=(), habitica_task_ids=None):
    return Routine(
        page_id=page_id,
        name=f"routine {page_id}",
        member_ids=list(member_ids),
        elegibles_ids=list(elegibles_ids),
        kind=kind,
        modalidad=modalidad,
        paga=paga,
        difficulty=difficulty,
        recurrencia="Semanal",
        dias=["L", "K", "V"],
        habitica_task_ids=habitica_task_ids or {},
        habitica_tipo="daily",
        retired=False,
    )


def row(page_id="a1", *, rutina_ids=("r1",), tarea_ids=(), estado="Hecha", day=D,
        origen=None, points_applied=None, adjusted=False):
    return AgendaRow(
        page_id=page_id,
        title=f"row {page_id}",
        member_ids=["m1"],
        rutina_ids=list(rutina_ids),
        tarea_ids=list(tarea_ids),
        estado=estado,
        day=day,
        origen=origen,
        points_applied=points_applied,
        adjusted=adjusted,
    )


def tarea(page_id="t1", *, difficulty=Difficulty.INTERMEDIA, aprobada=True):
    return Tarea(
        page_id=page_id,
        title=f"tarea {page_id}",
        member_id="m1",
        difficulty=difficulty,
        aprobada=aprobada,
        habitica_task_id="hd1",
        estado=None,
    )


def test_difficulty_and_kind_come_from_the_linked_routine():
    routines = {"r1": routine(difficulty=Difficulty.COMPLEJA, kind=Kind.MANDATORY)}
    events = to_events([row(estado="Fallada")], routines)
    assert len(events) == 1
    assert events[0].difficulty is Difficulty.COMPLEJA
    assert events[0].kind is Kind.MANDATORY
    assert events[0].outcome is Outcome.FAILED
    # -12 proves both flowed through: the difficulty sets the magnitude and the
    # Mandatory kind is what lets it subtract at all.
    assert events[0].points == -12


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


# --- Agenda -> Tarea join: To-Dos, anti-inflation rule -------------------


def test_row_linked_to_an_approved_tarea_becomes_a_todo_event():
    tareas = {"t1": tarea(difficulty=Difficulty.COMPLEJA)}
    events = to_events(
        [row(rutina_ids=(), tarea_ids=("t1",), estado="Hecha")], {}, tareas
    )
    assert len(events) == 1
    assert events[0].kind is Kind.TODO
    assert events[0].difficulty is Difficulty.COMPLEJA
    assert events[0].points == 25


def test_unapproved_tarea_is_dropped():
    tareas = {"t1": tarea(aprobada=False)}
    assert to_events([row(rutina_ids=(), tarea_ids=("t1",))], {}, tareas) == []


def test_tarea_without_difficulty_is_dropped():
    tareas = {"t1": tarea(difficulty=None)}
    assert to_events([row(rutina_ids=(), tarea_ids=("t1",))], {}, tareas) == []


def test_todo_never_subtracts_even_when_failed():
    """Kind.TODO: absence is neutral, same rule as rules.points_failed."""
    tareas = {"t1": tarea()}
    events = to_events(
        [row(rutina_ids=(), tarea_ids=("t1",), estado="Fallada")], {}, tareas
    )
    assert events[0].points == 0


def test_row_with_neither_routine_nor_tarea_is_dropped():
    assert to_events([row(rutina_ids=(), tarea_ids=())], {}, {}) == []
    assert to_events([row(rutina_ids=(), tarea_ids=("ghost",))], {}, {}) == []


def test_routine_takes_precedence_when_a_row_somehow_links_both():
    tareas = {"t1": tarea(difficulty=Difficulty.FACIL)}
    events = to_events(
        [row(rutina_ids=("r1",), tarea_ids=("t1",), estado="Hecha")],
        {"r1": routine(difficulty=Difficulty.COMPLEJA)},
        tareas,
    )
    assert len(events) == 1
    assert events[0].kind is Kind.MANDATORY
    assert events[0].difficulty is Difficulty.COMPLEJA


def test_is_manual_flag():
    assert row(origen="Manual").is_manual
    assert not row(origen="Habitica").is_manual
    assert not row(origen=None).is_manual


def test_is_pool_flag():
    assert routine(modalidad="Pool").is_pool
    assert not routine(modalidad="Personal").is_pool


# --- mirror targeting (ADR-28 personal multi, ADR-33 pool) ------------------


def test_personal_routine_targets_every_listed_member():
    r = routine(modalidad="Personal", member_ids=("m1", "m2", "m3"),
                elegibles_ids=("m9",))
    assert r.targets() == ["m1", "m2", "m3"]


def test_pool_routine_targets_the_eligibles_not_the_members():
    r = routine(modalidad="Pool", member_ids=(), elegibles_ids=("m1", "m2"))
    assert r.targets() == ["m1", "m2"]


def test_routine_with_no_targets_is_empty():
    assert routine(modalidad="Personal", member_ids=()).targets() == []
    assert routine(modalidad="Pool", member_ids=("m1",), elegibles_ids=()).targets() == []


# --- Habitica Task ID map parsing -----------------------------------------


def test_parse_task_ids_reads_the_json_map():
    assert _parse_task_ids('{"m1": "abc", "m2": "def"}') == {"m1": "abc", "m2": "def"}


def test_parse_task_ids_tolerates_empty_and_legacy_values():
    assert _parse_task_ids("") == {}
    assert _parse_task_ids("   ") == {}
    assert _parse_task_ids("legacy-single-id") == {}  # pre-map value -> recreated
    assert _parse_task_ids('["a", "b"]') == {}
    assert _parse_task_ids('{"m1": "abc", "": "x", "m2": ""}') == {"m1": "abc"}
