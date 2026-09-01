from datetime import date

import pytest

from family_agile_sync.rules import (
    Difficulty,
    Event,
    Kind,
    Outcome,
    Recurrencia,
    close_cycle,
    current_todo_occurrence,
    cycle_bounds,
    cycle_label,
    is_non_weekly,
    points_failed,
    settle_day,
    signed_points,
)

D = date(2026, 8, 24)


def ev(difficulty, kind, outcome, day=D, adjusted=None):
    return Event(
        day=day,
        difficulty=difficulty,
        kind=kind,
        outcome=outcome,
        adjusted_points=adjusted,
    )


# --- points table ---------------------------------------------------------


def test_mandatory_earns_nothing_and_only_fails_for_points():
    """An unavoidable responsibility: completing it pays 0, failing it costs
    the penalty column (half the difficulty's face value, rounded down)."""
    for difficulty, penalty in (
        (Difficulty.FACIL, 2),
        (Difficulty.INTERMEDIA, 5),
        (Difficulty.COMPLEJA, 12),
    ):
        assert signed_points(difficulty, Kind.MANDATORY, Outcome.DONE) == 0
        assert signed_points(difficulty, Kind.MANDATORY, Outcome.FAILED) == -penalty


@pytest.mark.parametrize("kind", [Kind.OPCIONAL, Kind.TODO])
def test_optional_and_todo_earn_face_value_and_never_fail(kind):
    for difficulty, face in (
        (Difficulty.FACIL, 5),
        (Difficulty.INTERMEDIA, 10),
        (Difficulty.COMPLEJA, 25),
    ):
        assert signed_points(difficulty, kind, Outcome.DONE) == face
        assert signed_points(difficulty, kind, Outcome.FAILED) == 0


@pytest.mark.parametrize("kind", [Kind.OPCIONAL, Kind.TODO])
def test_only_mandatory_can_subtract(kind):
    """Absence is neutral: optional work and to-dos never cost money."""
    assert points_failed(Difficulty.COMPLEJA, kind) == 0
    assert signed_points(Difficulty.COMPLEJA, kind, Outcome.FAILED) == 0


def test_pending_is_worth_nothing_either_way():
    assert signed_points(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.PENDING) == 0


def test_appeal_overrides_the_table():
    event = ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.FAILED, adjusted=0)
    assert event.points == 0


# --- daily cap ------------------------------------------------------------


def test_daily_cap_limits_penalties_to_half_the_days_mandatory_value():
    # Day worth 45 points of mandatory work -> cap 22.
    events = [
        ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.FAILED),
        ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.FAILED),
        ev(Difficulty.INTERMEDIA, Kind.MANDATORY, Outcome.FAILED),
        ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.FAILED),
    ]
    result = settle_day(events)
    assert result.penalty_raw == 2 + 2 + 5 + 12  # 21
    assert result.penalty_applied == 21  # under the cap of 22
    assert not result.capped


def test_cap_is_inert_under_the_current_table():
    """Failing an entire day still lands under the cap, by construction.

    Because every penalty is half of its earned value (rounded down), the sum
    of a day's penalties can never exceed floor(mandatory_value / 2), which is
    exactly the cap. The cap is therefore a guard against future recalibration
    and against appeals that add penalties -- not an active rule today.
    """
    events = [ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.FAILED) for _ in range(4)]
    result = settle_day(events)
    assert result.penalty_raw == 48  # cap would be floor(100 * 0.5) = 50
    assert result.penalty_applied == 48
    assert not result.capped


def test_cap_bites_when_penalties_are_made_heavier():
    """Same day, stricter ratio: proves the guard actually engages."""
    events = [ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.FAILED) for _ in range(4)]
    result = settle_day(events, cap_ratio=0.25)  # cap = floor(100 * 0.25) = 25
    assert result.penalty_raw == 48
    assert result.penalty_applied == 25
    assert result.capped


def test_optional_work_does_not_raise_the_cap():
    """The cap is a share of mandatory value only, so optional wins can't fund penalties."""
    events = [
        ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.FAILED),
        ev(Difficulty.COMPLEJA, Kind.OPCIONAL, Outcome.DONE),
    ]
    result = settle_day(events, cap_ratio=0.25)
    assert result.earned == 25
    # cap is floor(5 * 0.25) = 1, not floor(30 * 0.25) = 7
    assert result.penalty_applied == 1
    assert result.capped


def test_settle_day_rejects_mixed_days():
    with pytest.raises(ValueError):
        settle_day(
            [
                ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.DONE, day=date(2026, 8, 1)),
                ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.DONE, day=date(2026, 8, 2)),
            ]
        )


# --- cycle close ----------------------------------------------------------


def test_perfect_cycle_pays_everything():
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    events = [
        ev(Difficulty.INTERMEDIA, Kind.OPCIONAL, Outcome.DONE, day=start)
        for _ in range(3)
    ]
    summary = close_cycle(events, start, end, colones_por_punto=10)
    assert summary.points_earned == 30
    assert summary.points_net == 30
    assert summary.colones == 300
    assert not summary.floor_applied


def test_completing_mandatory_work_adds_nothing_to_the_cycle():
    """Doing your duty keeps the ledger where it was -- no reward, no debt."""
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    events = [
        ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.DONE, day=start)
        for _ in range(4)
    ]
    summary = close_cycle(events, start, end, colones_por_punto=10)
    assert summary.mandatory_done == 4
    assert summary.points_earned == 0
    assert summary.points_net == 0
    assert summary.colones == 0


def test_cycle_never_closes_negative():
    """The floor is non-negotiable: debt destroys any incentive to catch up."""
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    events = []
    for offset in range(10):
        day = date(2026, 8, 15 + offset)
        events += [ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.FAILED, day=day)]
    summary = close_cycle(events, start, end, colones_por_punto=10)
    assert summary.points_net == 0
    assert summary.colones == 0
    assert summary.floor_applied


def test_events_outside_the_window_are_ignored():
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    inside = ev(Difficulty.FACIL, Kind.OPCIONAL, Outcome.DONE, day=date(2026, 8, 20))
    outside = ev(Difficulty.FACIL, Kind.OPCIONAL, Outcome.DONE, day=date(2026, 9, 1))
    summary = close_cycle([inside, outside], start, end, colones_por_punto=10)
    assert summary.points_earned == 5


def test_counters_split_by_kind():
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    events = [
        ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.DONE, day=start),
        ev(Difficulty.FACIL, Kind.MANDATORY, Outcome.FAILED, day=start),
        ev(Difficulty.INTERMEDIA, Kind.OPCIONAL, Outcome.DONE, day=start),
        ev(Difficulty.COMPLEJA, Kind.TODO, Outcome.DONE, day=start),
    ]
    summary = close_cycle(events, start, end, colones_por_punto=10)
    assert summary.mandatory_assigned == 2
    assert summary.mandatory_done == 1
    assert summary.mandatory_failed == 1
    assert summary.optional_done == 1
    assert summary.todos_done == 1


# --- cycle calendar -------------------------------------------------------

ANCHOR = date(2026, 8, 28)  # a Friday


def test_payday_belongs_to_the_cycle_it_closes():
    start, end = cycle_bounds(ANCHOR, ANCHOR)
    assert end == ANCHOR
    assert start == date(2026, 8, 15)
    assert (end - start).days == 13


def test_day_after_payday_starts_the_next_cycle():
    start, end = cycle_bounds(date(2026, 8, 29), ANCHOR)
    assert start == date(2026, 8, 29)
    assert end == date(2026, 9, 11)


def test_calendar_extends_backwards_from_the_anchor():
    start, end = cycle_bounds(date(2026, 8, 14), ANCHOR)
    assert end == date(2026, 8, 14)
    assert start == date(2026, 8, 1)


def test_anchor_must_be_a_friday():
    with pytest.raises(ValueError):
        cycle_bounds(ANCHOR, date(2026, 8, 27))


def test_cycle_label_is_stable_across_the_period():
    assert cycle_label(date(2026, 8, 20), ANCHOR) == cycle_label(ANCHOR, ANCHOR)


# --- non-weekly recurrence (ADR-26) ----------------------------------------


def test_is_non_weekly():
    assert not is_non_weekly(Recurrencia.SEMANAL.value)
    assert not is_non_weekly(None)
    assert not is_non_weekly("garbage")
    for value in (Recurrencia.QUINCENAL, Recurrencia.MENSUAL, Recurrencia.TRIMESTRAL):
        assert is_non_weekly(value.value)


def test_quincenal_steps_in_14_day_blocks_from_the_anchor():
    anchor = date(2026, 8, 1)
    assert current_todo_occurrence("Quincenal", anchor, None, anchor) == anchor
    assert current_todo_occurrence(
        "Quincenal", anchor, None, date(2026, 8, 10)
    ) == anchor  # still inside the first block
    assert current_todo_occurrence(
        "Quincenal", anchor, None, date(2026, 8, 15)
    ) == date(2026, 8, 15)  # exactly the next block
    assert current_todo_occurrence(
        "Quincenal", anchor, None, date(2026, 8, 28)
    ) == date(2026, 8, 15)


def test_quincenal_never_precedes_vigente_desde():
    anchor = date(2026, 8, 15)
    assert current_todo_occurrence(
        "Quincenal", anchor, None, date(2026, 8, 1)
    ) == anchor


def test_mensual_lands_on_dia_del_mes_each_month():
    anchor = date(2026, 6, 1)
    assert current_todo_occurrence("Mensual", anchor, 15, date(2026, 8, 20)) == date(
        2026, 8, 15
    )
    assert current_todo_occurrence("Mensual", anchor, 15, date(2026, 9, 1)) == date(
        2026, 9, 15
    )


def test_mensual_clamps_dia_del_mes_to_the_days_the_month_has():
    anchor = date(2026, 1, 1)
    assert current_todo_occurrence("Mensual", anchor, 31, date(2026, 2, 10)) == date(
        2026, 2, 28
    )  # February has no 31st


def test_trimestral_steps_by_three_months_from_the_anchor_month():
    anchor = date(2026, 1, 10)
    assert current_todo_occurrence(
        "Trimestral", anchor, 10, date(2026, 3, 1)
    ) == date(2026, 1, 10)  # still inside the first quarter
    assert current_todo_occurrence(
        "Trimestral", anchor, 10, date(2026, 4, 10)
    ) == date(2026, 4, 10)
    assert current_todo_occurrence(
        "Trimestral", anchor, 10, date(2026, 8, 30)
    ) == date(2026, 7, 10)


def test_mensual_and_trimestral_require_dia_del_mes():
    with pytest.raises(ValueError):
        current_todo_occurrence("Mensual", date(2026, 1, 1), None, date(2026, 1, 1))


def test_semanal_is_rejected():
    """Semanal stays a Habitica daily; this function is only for the other three."""
    with pytest.raises(ValueError):
        current_todo_occurrence("Semanal", date(2026, 1, 1), None, date(2026, 1, 1))
