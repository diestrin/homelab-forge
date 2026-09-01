"""generate-occurrences: the ADR-27 occurrence calendar and the row it writes.

``rules.occurs_on`` is pure. The job's loaders and Notion client are replaced
with fakes, so ``run`` exercises its real branching without any network.
"""

from datetime import date, datetime

import pytest

from family_agile_sync import schema as s
from family_agile_sync.config import Config
from family_agile_sync.jobs import generate_occurrences as job
from family_agile_sync.repo import AgendaRow, Routine
from family_agile_sync.rules import Difficulty, Kind, occurs_on

MON = date(2026, 8, 24)  # a Monday -> "L"
FRI = date(2026, 8, 28)  # a Friday -> "V"


# --------------------------------------------------------------------------
# occurs_on -- pure calendar
# --------------------------------------------------------------------------


def test_semanal_matches_listed_weekdays_only():
    assert occurs_on(MON, "Semanal", ["L"], None, None)
    assert not occurs_on(MON, "Semanal", ["M"], None, None)
    assert occurs_on(FRI, "Semanal", ["L", "V"], None, None)
    assert not occurs_on(MON, "Semanal", [], None, None)


def test_quincenal_fires_every_14_days_from_vigente_desde():
    assert occurs_on(FRI, "Quincenal", ["V"], FRI, None)  # delta 0
    assert occurs_on(date(2026, 9, 11), "Quincenal", ["V"], FRI, None)  # +14
    assert not occurs_on(date(2026, 9, 4), "Quincenal", ["V"], FRI, None)  # +7
    # weekday not in Días, and no anchor at all
    assert not occurs_on(FRI, "Quincenal", ["L"], FRI, None)
    assert not occurs_on(FRI, "Quincenal", ["V"], None, None)


def test_future_vigente_desde_suppresses_everything():
    assert not occurs_on(FRI, "Quincenal", ["V"], date(2026, 9, 11), None)
    assert not occurs_on(FRI, "Semanal", ["V"], date(2026, 9, 1), None)


def test_mensual_lands_on_dia_del_mes():
    assert occurs_on(date(2026, 9, 28), "Mensual", [], date(2026, 8, 28), 28)
    assert not occurs_on(date(2026, 9, 27), "Mensual", [], date(2026, 8, 28), 28)


def test_mensual_clamps_dia_del_mes_to_the_months_length():
    # Feb 2026 has 28 days; "the 31st" resolves to the 28th.
    assert occurs_on(date(2026, 2, 28), "Mensual", [], date(2026, 1, 1), 31)
    assert not occurs_on(date(2026, 2, 27), "Mensual", [], date(2026, 1, 1), 31)


def test_trimestral_steps_by_three_months():
    assert occurs_on(date(2026, 4, 15), "Trimestral", [], date(2026, 1, 15), 15)
    assert not occurs_on(date(2026, 3, 15), "Trimestral", [], date(2026, 1, 15), 15)


def test_unknown_or_missing_recurrence_matches_nothing():
    assert not occurs_on(MON, "garbage", ["L"], None, None)
    assert not occurs_on(MON, None, ["L"], None, None)


# --------------------------------------------------------------------------
# run -- expansion, idempotency, dry-run
# --------------------------------------------------------------------------


def _cfg(*, dry_run=False, horizon=1):
    return Config(
        notion_token="t", db_miembros="m", db_rutinas="r", db_agenda="a",
        db_tareas="ta", anchor_friday=FRI, habitica_client="x",
        request_delay_seconds=0, dry_run=dry_run, force_close=False,
        generate_horizon_days=horizon, db_corte=None,
    )


def _routine(pid="R", *, modalidad="Personal", members=(), dias=("L",),
             recurrencia="Semanal", vigente_desde=None, dia_del_mes=None,
             hora="5:00 AM", categoria="Casa", retired=False):
    return Routine(
        page_id=pid, name=f"routine {pid}", member_ids=list(members),
        elegibles_ids=[], kind=Kind.OPCIONAL, modalidad=modalidad, paga=True,
        difficulty=Difficulty.FACIL, recurrencia=recurrencia, dias=list(dias),
        habitica_task_ids={}, habitica_tipo="daily", retired=retired,
        vigente_desde=vigente_desde, dia_del_mes=dia_del_mes, hora=hora,
        categoria=categoria,
    )


def _agenda_row(pid="a1", *, rutina, members=(), day=MON, origen="Notion"):
    return AgendaRow(
        page_id=pid, title=pid, member_ids=list(members), rutina_ids=[rutina],
        tarea_ids=[], estado=s.ESTADO_PENDIENTE, day=day, origen=origen,
        points_applied=None, adjusted=False,
    )


class FakeNotion:
    def __init__(self):
        self.created = []

    def create_page(self, database_id, props):
        self.created.append((database_id, props))


@pytest.fixture
def wired(monkeypatch):
    def go(routines, existing, cfg=None):
        notion = FakeNotion()
        monkeypatch.setattr(job, "load_routines",
                            lambda *_: {r.page_id: r for r in routines})
        monkeypatch.setattr(job, "load_agenda", lambda *a, **k: list(existing))
        monkeypatch.setattr(job.n, "NotionClient", lambda *a, **k: notion)
        result = job.run(cfg or _cfg(), today=MON)
        return notion, result

    return go


def test_personal_routine_generates_one_row_per_member(wired):
    r = _routine(members=("m1", "m2"))
    notion, created = wired([r], [])

    assert created == 2
    assert len(notion.created) == 2
    members = {
        p[s.Agenda.MIEMBRO]["relation"][0]["id"] for _, p in notion.created
    }
    assert members == {"m1", "m2"}
    _, props = notion.created[0]
    assert props[s.Agenda.RUTINA] == {"relation": [{"id": "R"}]}
    assert props[s.Agenda.ESTADO] == {"status": {"name": s.ESTADO_PENDIENTE}}
    assert props[s.Agenda.ORIGEN] == {"select": {"name": s.ORIGEN_NOTION}}
    assert props[s.Agenda.TABLA] == {"select": {"name": "Limpieza"}}
    assert props[s.Agenda.INICIA]["date"]["start"] == datetime(
        2026, 8, 24, 5, 0
    ).isoformat()


def test_pool_routine_generates_one_unclaimed_row(wired):
    r = _routine(pid="P", modalidad="Pool", members=())
    notion, created = wired([r], [])

    assert created == 1
    _, props = notion.created[0]
    assert props[s.Agenda.MIEMBRO] == {"relation": []}


def test_existing_row_is_not_duplicated(wired):
    r = _routine(members=("m1",))
    notion, created = wired([r], [_agenda_row(rutina="R", members=("m1",))])
    assert created == 0
    assert notion.created == []


def test_manual_row_also_suppresses_generation(wired):
    r = _routine(members=("m1",))
    existing = [_agenda_row(rutina="R", members=("m1",), origen=s.ORIGEN_MANUAL)]
    _, created = wired([r], existing)
    assert created == 0


def test_claimed_pool_row_blocks_a_second_unclaimed_row(wired):
    r = _routine(pid="P", modalidad="Pool")
    # pull-completions already filled Miembro on today's occurrence
    existing = [_agenda_row(rutina="P", members=("m1",))]
    _, created = wired([r], existing)
    assert created == 0


def test_dry_run_writes_nothing_but_counts(wired):
    r = _routine(members=("m1", "m2"))
    notion, created = wired([r], [], cfg=_cfg(dry_run=True))
    assert created == 2
    assert notion.created == []


def test_horizon_spans_multiple_days(wired):
    r = _routine(members=("m1",))
    notion, created = wired([r], [], cfg=_cfg(horizon=8))
    # Mondays in 24..31 Aug 2026: the 24th and the 31st.
    days = {p[s.Agenda.INICIA]["date"]["start"][:10] for _, p in notion.created}
    assert days == {"2026-08-24", "2026-08-31"}
    assert created == 2


def test_retired_routine_is_skipped(wired):
    r = _routine(members=("m1",), retired=True)
    _, created = wired([r], [])
    assert created == 0


def test_routine_with_no_members_generates_nothing(wired):
    r = _routine(members=())  # Personal, nobody assigned
    _, created = wired([r], [])
    assert created == 0
