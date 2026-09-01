"""Pure business rules for the Family Agile allowance ledger.

Nothing in this module performs I/O. Every rule that decides how much money a
child earns lives here so it can be tested in isolation and reviewed as a unit.

Design note (see docs/decisions/ADR-011): these rules deliberately do NOT live
as Notion formulas. Notion formula fields return null over the API, so any
value the ledger needs is computed here and written back as a plain number.
"""

from __future__ import annotations

import calendar
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


#: (face value, failure penalty) per difficulty. The face value is what
#: optional work and to-dos earn on completion, and the notional basis for the
#: daily penalty cap. Mandatory work earns nothing on completion (see
#: ``signed_points``): it is an unavoidable household responsibility, so only
#: failing it moves the ledger. The penalty is half the face value, rounded
#: down (Casa points policy, 2026-09; supersedes the earlier "+N for doing").
POINTS: dict[Difficulty, tuple[int, int]] = {
    Difficulty.FACIL: (5, 2),
    Difficulty.INTERMEDIA: (10, 5),
    Difficulty.COMPLEJA: (25, 12),
}

DAILY_CAP_RATIO = 0.5
"""A single day may not subtract more than this share of that day's mandatory value."""


def points_earned(difficulty: Difficulty) -> int:
    """The difficulty's face value: what optional work and to-dos earn on
    completion, and the notional value the daily cap is a share of. Mandatory
    completion pays 0 regardless of difficulty -- see ``signed_points``."""
    return POINTS[Difficulty(difficulty)][0]


def points_failed(difficulty: Difficulty, kind: Kind) -> int:
    """Penalty as a positive magnitude. Only mandatory work can be penalised."""
    if Kind(kind) is not Kind.MANDATORY:
        return 0
    return POINTS[Difficulty(difficulty)][1]


def signed_points(difficulty: Difficulty, kind: Kind, outcome: Outcome) -> int:
    """The number written to Agenda.'Puntos aplicados'.

    Mandatory work is an unavoidable household responsibility: completing it
    earns nothing, and only failing it moves the ledger (Casa points policy,
    2026-09). Optional work and to-dos earn their difficulty's face value on
    completion and never subtract.
    """
    outcome = Outcome(outcome)
    if outcome is Outcome.DONE:
        if Kind(kind) is Kind.MANDATORY:
            return 0
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


# --------------------------------------------------------------------------
# Non-weekly recurrence (ADR-26)
# --------------------------------------------------------------------------
#
# A Rutina with Recurrencia = Quincenal/Mensual/Trimestral is mirrored in
# Habitica as a `todo`, never as a repeating Daily: Habitica's native
# repetition isn't confirmed to cover arbitrary month intervals, so the sync
# computes the date itself and recreates the mirror when a period turns over.
# This is the pure calendar math; the mirror's create/leave-alone lifecycle
# lives in jobs/push_definitions.py.


class Recurrencia(str, Enum):
    SEMANAL = "Semanal"
    QUINCENAL = "Quincenal"
    MENSUAL = "Mensual"
    TRIMESTRAL = "Trimestral"


NON_WEEKLY = {Recurrencia.QUINCENAL, Recurrencia.MENSUAL, Recurrencia.TRIMESTRAL}


def is_non_weekly(recurrencia: str | None) -> bool:
    try:
        return recurrencia is not None and Recurrencia(recurrencia) in NON_WEEKLY
    except ValueError:
        return False


def _add_months(day: date, months: int) -> date:
    total = day.year * 12 + (day.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    clamped_day = min(day.day, calendar.monthrange(year, month)[1])
    return date(year, month, clamped_day)


def current_todo_occurrence(
    recurrencia: str,
    vigente_desde: date,
    dia_del_mes: int | None,
    today: date,
) -> date:
    """The scheduled date of the period containing ``today``.

    This is the date the Habitica To-Do mirror should carry: the start of
    whichever Quincenal/Mensual/Trimestral window ``today`` falls in.
    ``vigente_desde`` anchors the calendar (see ADR-26) -- for Quincenal it
    counts in 14-day steps from that date; for Mensual/Trimestral it anchors
    the starting month and steps by 1 or 3 months, landing on ``dia_del_mes``
    (clamped to the days that month actually has). A period never starts
    before ``vigente_desde`` itself.
    """
    recurrencia_ = Recurrencia(recurrencia)
    if recurrencia_ not in NON_WEEKLY:
        raise ValueError(f"{recurrencia!r} is not a non-weekly recurrence")

    if recurrencia_ is Recurrencia.QUINCENAL:
        steps = max(0, (today - vigente_desde).days // 14)
        return vigente_desde + timedelta(days=steps * 14)

    if dia_del_mes is None:
        raise ValueError(f"{recurrencia_.value} requires Día del mes")

    step_months = 1 if recurrencia_ is Recurrencia.MENSUAL else 3
    months_elapsed = (today.year - vigente_desde.year) * 12 + (
        today.month - vigente_desde.month
    )
    steps = max(0, months_elapsed // step_months)
    target = _add_months(vigente_desde, steps * step_months)
    clamped_day = min(dia_del_mes, calendar.monthrange(target.year, target.month)[1])
    return date(target.year, target.month, clamped_day)


# --------------------------------------------------------------------------
# Occurrence calendar (ADR-27): does a routine fall on a given day?
# --------------------------------------------------------------------------
#
# Every other job assumes the Pendiente Agenda rows already exist. The
# generate-occurrences job is the one that creates them, and this is the pure
# calendar it walks: the v0 algorithm from ADR-27, lifted out of the one-off
# manual run into a tested function.

#: date.weekday() index (Mon=0) -> the one-letter code stored in Rutinas."Días".
#: K is miércoles, J is jueves -- Spanish initials, not English.
WEEKDAY_CODES = ("L", "M", "K", "J", "V", "S", "D")


def weekday_code(day: date) -> str:
    return WEEKDAY_CODES[day.weekday()]


def occurs_on(
    day: date,
    recurrencia: str | None,
    dias: list[str],
    vigente_desde: date | None,
    dia_del_mes: int | None,
) -> bool:
    """Whether a routine with this recurrence has an occurrence on ``day``.

    * **Semanal** -- ``day``'s weekday is listed in ``Días``.
    * **Quincenal** -- weekday listed in ``Días`` *and* ``day`` is a whole
      number of 14-day steps after ``vigente_desde``. ``vigente_desde`` always
      lands on the listed day, so a Quincenal routine fires once per fortnight
      on that weekday; extra entries in ``Días`` are inert (see ADR-27).
    * **Mensual** -- ``day.day`` equals ``dia_del_mes`` (clamped to the
      month's length) and ``day >= vigente_desde``.
    * **Trimestral** -- as Mensual, and the month is a multiple of 3 from
      ``vigente_desde``'s month.

    A ``vigente_desde`` in the future suppresses every recurrence. An unknown
    or missing ``recurrencia`` matches nothing.
    """
    try:
        rec = Recurrencia(recurrencia) if recurrencia else None
    except ValueError:
        return False
    if rec is None:
        return False
    if vigente_desde is not None and day < vigente_desde:
        return False

    if rec is Recurrencia.SEMANAL:
        return weekday_code(day) in dias

    if rec is Recurrencia.QUINCENAL:
        if vigente_desde is None or weekday_code(day) not in dias:
            return False
        return (day - vigente_desde).days % 14 == 0

    # Mensual / Trimestral
    if dia_del_mes is None:
        return False
    last_day = calendar.monthrange(day.year, day.month)[1]
    if day.day != min(dia_del_mes, last_day):
        return False
    if vigente_desde is None:
        return True
    months = (day.year - vigente_desde.year) * 12 + (day.month - vigente_desde.month)
    step = 1 if rec is Recurrencia.MENSUAL else 3
    return months >= 0 and months % step == 0
