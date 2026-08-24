"""Pure business rules for the Family Agile allowance ledger.

Nothing in this module performs I/O. Every rule that decides how much money a
child earns lives here so it can be tested in isolation and reviewed as a unit.

Design note (see docs/decisions/ADR-011): these rules deliberately do NOT live
as Notion formulas. Notion formula fields return null over the API, so any
value the ledger needs is computed here and written back as a plain number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

# --------------------------------------------------------------------------
# Difficulty / points table
# --------------------------------------------------------------------------


class Difficulty(str, Enum):
    FACIL = "Fácil"
    INTERMEDIA = "Intermedia"
    COMPLEJA = "Compleja"


class Kind(str, Enum):
    """Mandatory routines can subtract; optional ones and to-dos never do."""

    MANDATORY = "Mandatory"
    OPCIONAL = "Opcional"
    TODO = "To-Do"


class Outcome(str, Enum):
    PENDING = "Pendiente"
    DONE = "Hecha"
    FAILED = "Fallada"


#: earned points, penalty points. Penalty is half of earned, rounded down.
POINTS: dict[Difficulty, tuple[int, int]] = {
    Difficulty.FACIL: (5, 2),
    Difficulty.INTERMEDIA: (10, 5),
    Difficulty.COMPLEJA: (25, 12),
}

DAILY_CAP_RATIO = 0.5
"""A single day may not subtract more than this share of that day's mandatory value."""


def points_earned(difficulty: Difficulty) -> int:
    return POINTS[Difficulty(difficulty)][0]


def points_failed(difficulty: Difficulty, kind: Kind) -> int:
    """Penalty as a positive magnitude. Only mandatory work can be penalised."""
    if Kind(kind) is not Kind.MANDATORY:
        return 0
    return POINTS[Difficulty(difficulty)][1]


def signed_points(difficulty: Difficulty, kind: Kind, outcome: Outcome) -> int:
    """The number written to Agenda.'Puntos aplicados'."""
    outcome = Outcome(outcome)
    if outcome is Outcome.DONE:
        return points_earned(difficulty)
    if outcome is Outcome.FAILED:
        return -points_failed(difficulty, kind)
    return 0


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """One Agenda row: one member x one thing x one day."""

    day: date
    difficulty: Difficulty
    kind: Kind
    outcome: Outcome
    adjusted_points: int | None = None
    """Set when a parent overrode the result on appeal; overrides the table."""

    @property
    def points(self) -> int:
        if self.adjusted_points is not None:
            return self.adjusted_points
        return signed_points(self.difficulty, self.kind, self.outcome)


@dataclass(frozen=True)
class DayResult:
    day: date
    earned: int
    penalty_raw: int
    penalty_applied: int

    @property
    def capped(self) -> bool:
        return self.penalty_applied < self.penalty_raw


def settle_day(events: list[Event], cap_ratio: float = DAILY_CAP_RATIO) -> DayResult:
    """Apply the daily penalty cap.

    A bad day must not be able to erase the cycle: penalties for a single day
    are capped at ``cap_ratio`` of what that day's mandatory work was worth.
    Illness, exams and the unexpected happen.
    """
    if not events:
        raise ValueError("settle_day requires at least one event")

    day = events[0].day
    if any(e.day != day for e in events):
        raise ValueError("settle_day expects events from a single day")

    earned = sum(e.points for e in events if e.points > 0)
    penalty_raw = sum(-e.points for e in events if e.points < 0)

    mandatory_value = sum(
        points_earned(e.difficulty) for e in events if Kind(e.kind) is Kind.MANDATORY
    )
    cap = math.floor(mandatory_value * cap_ratio)
    penalty_applied = min(penalty_raw, cap)

    return DayResult(
        day=day,
        earned=earned,
        penalty_raw=penalty_raw,
        penalty_applied=penalty_applied,
    )


# --------------------------------------------------------------------------
# Cycle close
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CycleSummary:
    start: date
    end: date
    mandatory_assigned: int
    mandatory_done: int
    mandatory_failed: int
    optional_done: int
    todos_done: int
    points_earned: int
    points_subtracted: int
    points_net: int
    colones: int
    cap_applied: bool
    floor_applied: bool


def close_cycle(
    events: list[Event],
    start: date,
    end: date,
    colones_por_punto: int,
    cap_ratio: float = DAILY_CAP_RATIO,
) -> CycleSummary:
    """Settle one 14-day cycle for one member.

    Order matters: daily cap first, then sum, then floor at zero, then convert.
    Applying the floor before the cap would let one catastrophic day silently
    swallow penalties that the cap should have prevented from existing.
    """
    in_range = [e for e in events if start <= e.day <= end]

    by_day: dict[date, list[Event]] = {}
    for event in in_range:
        by_day.setdefault(event.day, []).append(event)

    day_results = [settle_day(day_events, cap_ratio) for day_events in by_day.values()]

    earned = sum(d.earned for d in day_results)
    subtracted = sum(d.penalty_applied for d in day_results)
    cap_applied = any(d.capped for d in day_results)

    raw_net = earned - subtracted
    net = max(0, raw_net)

    mandatory = [e for e in in_range if Kind(e.kind) is Kind.MANDATORY]

    return CycleSummary(
        start=start,
        end=end,
        mandatory_assigned=len(mandatory),
        mandatory_done=sum(1 for e in mandatory if Outcome(e.outcome) is Outcome.DONE),
        mandatory_failed=sum(
            1 for e in mandatory if Outcome(e.outcome) is Outcome.FAILED
        ),
        optional_done=sum(
            1
            for e in in_range
            if Kind(e.kind) is Kind.OPCIONAL and Outcome(e.outcome) is Outcome.DONE
        ),
        todos_done=sum(
            1
            for e in in_range
            if Kind(e.kind) is Kind.TODO and Outcome(e.outcome) is Outcome.DONE
        ),
        points_earned=earned,
        points_subtracted=subtracted,
        points_net=net,
        colones=net * colones_por_punto,
        cap_applied=cap_applied,
        floor_applied=raw_net < 0,
    )


# --------------------------------------------------------------------------
# Cycle calendar: every second Friday
# --------------------------------------------------------------------------

CYCLE_DAYS = 14


def cycle_end_for(day: date, anchor_friday: date) -> date:
    """The payday Friday that closes the cycle containing ``day``.

    ``anchor_friday`` is any payday Friday; the calendar extends in both
    directions from it in 14-day steps. A cycle is the 14 days *ending* on its
    payday, so the payday itself belongs to the cycle it closes.
    """
    if anchor_friday.weekday() != 4:
        raise ValueError("anchor_friday must be a Friday")

    delta = (day - anchor_friday).days
    # ceiling division, integer-safe for negatives
    steps = -((-delta) // CYCLE_DAYS)
    return anchor_friday + timedelta(days=steps * CYCLE_DAYS)


def cycle_bounds(day: date, anchor_friday: date) -> tuple[date, date]:
    end = cycle_end_for(day, anchor_friday)
    return end - timedelta(days=CYCLE_DAYS - 1), end


def cycle_label(day: date, anchor_friday: date) -> str:
    """Human-readable id, e.g. ``2026-C18``, used as the Corte quincenal title."""
    end = cycle_end_for(day, anchor_friday)
    year_start = date(end.year, 1, 1)
    index = ((end - year_start).days // CYCLE_DAYS) + 1
    return f"{end.year}-C{index:02d}"
