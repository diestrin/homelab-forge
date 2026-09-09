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
    nth_weekday_of_month,
    plan_deposits,
    points_done,
    points_failed,
    settle_day,
    signed_points,
    split_by_weights,
    week_of_month,
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


def test_mandatory_earns_a_small_acknowledgement_and_fails_for_more():
    """An unavoidable responsibility: completing it pays a small fixed amount
    by difficulty (1/2/3), failing it costs the penalty column (half the
    difficulty's face value, rounded down)."""
    for difficulty, done, penalty in (
        (Difficulty.FACIL, 1, 2),
        (Difficulty.INTERMEDIA, 2, 5),
        (Difficulty.COMPLEJA, 3, 12),
    ):
        assert signed_points(difficulty, Kind.MANDATORY, Outcome.DONE) == done
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


def test_points_done_splits_mandatory_from_the_rest():
    """Mandatory completion pays the small 1/2/3 table; everything else pays
    the difficulty's full face value."""
    for difficulty, small, face in (
        (Difficulty.FACIL, 1, 5),
        (Difficulty.INTERMEDIA, 2, 10),
        (Difficulty.COMPLEJA, 3, 25),
    ):
        assert points_done(difficulty, Kind.MANDATORY) == small
        assert points_done(difficulty, Kind.OPCIONAL) == face
        assert points_done(difficulty, Kind.TODO) == face


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


def test_completing_mandatory_work_earns_its_small_acknowledgement():
    """Doing your duty pays a token amount -- 3 points per Compleja here."""
    start, end = date(2026, 8, 15), date(2026, 8, 28)
    events = [
        ev(Difficulty.COMPLEJA, Kind.MANDATORY, Outcome.DONE, day=start)
        for _ in range(4)
    ]
    summary = close_cycle(events, start, end, colones_por_punto=10)
    assert summary.mandatory_done == 4
    assert summary.points_earned == 12
    assert summary.points_net == 12
    assert summary.colones == 120


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


# --- depositing the cycle net into the sobres (ADR-013) ------------------


def test_split_by_weights_is_exact_and_gives_the_remainder_to_the_biggest():
    # 1000 by 50/20/20/10 divides cleanly.
    assert split_by_weights(1000, [50, 20, 20, 10]) == [500, 200, 200, 100]
    # 1234 does not: floors are 617/246/246/123 = 1232, remainder 2 -> biggest.
    parts = split_by_weights(1234, [50, 20, 20, 10])
    assert parts == [619, 246, 246, 123]
    assert sum(parts) == 1234


def test_split_by_weights_handles_degenerate_input():
    assert split_by_weights(0, [50, 50]) == [0, 0]
    assert split_by_weights(-10, [50, 50]) == [0, 0]
    assert split_by_weights(100, [0, 0]) == [0, 0]
    assert split_by_weights(100, [1]) == [100]


def test_split_by_weights_breaks_ties_by_position():
    # equal weights, remainder 1 -> first weight wins the extra colon.
    assert split_by_weights(10, [1, 1, 1]) == [4, 3, 3]


def test_plan_deposits_orders_by_weight_so_the_remainder_is_stable():
    sobres = [("ahorro", 20), ("gastar", 50), ("compartir", 10), ("meta", 20)]
    plan = plan_deposits(1234, sobres)
    assert plan.income == 1234
    assert plan.unallocated == 0
    assert dict(plan.per_sobre) == {
        "gastar": 619,
        "ahorro": 246,
        "meta": 246,
        "compartir": 123,
    }
    assert sum(a for _, a in plan.per_sobre) == 1234


def test_plan_deposits_with_no_sobres_leaves_the_money_unallocated():
    plan = plan_deposits(500, [])
    assert plan.income == 500
    assert plan.per_sobre == []
    assert plan.unallocated == 500


def test_plan_deposits_drops_zero_shares():
    plan = plan_deposits(3, [("gastar", 50), ("meta", 20), ("ahorro", 20), ("compartir", 10)])
    # 3 colones, weights sum 100: floors 1/0/0/0, remainder 2 -> gastar.
    assert plan.per_sobre == [("gastar", 3)]


def test_plan_deposits_normalises_weights_that_do_not_sum_to_100():
    plan = plan_deposits(90, [("a", 1), ("b", 2)])
    assert dict(plan.per_sobre) == {"b": 60, "a": 30}
    assert plan.unallocated == 0


# --- Mensual on the Días weekday, week-of-month fixed by Vigente desde (ADR-43)


def test_week_of_month_counts_the_weekdays_own_occurrence():
    assert week_of_month(date(2026, 9, 4)) == 1    # 1st Friday
    assert week_of_month(date(2026, 9, 11)) == 2
    assert week_of_month(date(2026, 9, 25)) == 4
    assert week_of_month(date(2026, 5, 29)) == 5   # a 5th Friday exists in May


def test_nth_weekday_of_month_finds_the_date_and_clamps_short_months():
    # Friday = weekday 4. 2nd Friday of Oct 2026 is the 9th.
    assert nth_weekday_of_month(2026, 10, 4, 2) == date(2026, 10, 9)
    # 5th Friday of June 2026 -> only 4 exist -> last one, June 26.
    assert nth_weekday_of_month(2026, 6, 4, 5) == date(2026, 6, 26)
    # 1st Monday of Sept 2026.
    assert nth_weekday_of_month(2026, 9, 0, 1) == date(2026, 9, 7)


def test_current_todo_occurrence_monthly_by_weekday():
    anchor = date(2026, 9, 11)  # 2nd Friday
    # today inside October -> 2nd Friday of October
    assert current_todo_occurrence(
        "Mensual", anchor, None, date(2026, 10, 20), ["V"]
    ) == date(2026, 10, 9)
    # today inside the anchor month -> the anchor's own occurrence
    assert current_todo_occurrence(
        "Mensual", anchor, None, date(2026, 9, 30), ["V"]
    ) == date(2026, 9, 11)


def test_current_todo_occurrence_trimestral_by_weekday_steps_three_months():
    anchor = date(2026, 9, 11)  # 2nd Friday
    assert current_todo_occurrence(
        "Trimestral", anchor, None, date(2026, 11, 1), ["V"]
    ) == date(2026, 9, 11)  # still in the first quarter
    assert current_todo_occurrence(
        "Trimestral", anchor, None, date(2026, 12, 20), ["V"]
    ) == date(2026, 12, 11)


def test_current_todo_occurrence_dia_del_mes_still_wins():
    assert current_todo_occurrence(
        "Mensual", date(2026, 8, 28), 15, date(2026, 10, 1), ["V"]
    ) == date(2026, 10, 15)


def test_current_todo_occurrence_needs_dia_del_mes_or_a_weekday():
    with pytest.raises(ValueError):
        current_todo_occurrence("Mensual", date(2026, 1, 1), None, date(2026, 1, 1))
    with pytest.raises(ValueError):
        current_todo_occurrence("Mensual", date(2026, 1, 1), None, date(2026, 1, 1), [])
