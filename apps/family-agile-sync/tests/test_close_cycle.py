"""close-cycle: the two guards, and the Corte + sobres-deposit path.

The guard tests need no fakes -- they prove both guards fire before any Notion
client is built. The deposit tests stub the read side (loaders) and the cycle
arithmetic, and use a fake Notion client to capture every write, so the
plumbing added in ADR-013 (idempotent Corte, split by ``% de reparto``,
DISTRIBUTE flag) is checked without a live workspace.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from family_agile_sync import notion as n
from family_agile_sync import schema as s
from family_agile_sync.config import Config
from family_agile_sync.jobs import close_cycle as job
from family_agile_sync.repo import Member, Sobre
from family_agile_sync.rules import CycleSummary

ANCHOR = date(2026, 8, 28)  # a Friday
MEMBER = Member(
    page_id="mem1", name="Luna", habitica_user_id=None, colones_por_punto=10, active=True
)
SOBRES = [
    Sobre("s_gastar", "mem1", "Gastar", 0, 50),
    Sobre("s_meta", "mem1", "Meta", 0, 20),
    Sobre("s_ahorro", "mem1", "Ahorro", 0, 20),
    Sobre("s_comp", "mem1", "Compartir", 0, 10),
]


def _config(*, db_corte=None, force_close=False, db_sobres=None,
            db_movimientos=None, distribute=True, dry_run=False):
    return Config(
        notion_token="t", db_miembros="m", db_rutinas="r", db_agenda="a",
        db_tareas="ta", anchor_friday=ANCHOR, habitica_client="x",
        request_delay_seconds=0, dry_run=dry_run, force_close=force_close,
        db_corte=db_corte, db_sobres=db_sobres, db_movimientos=db_movimientos,
        distribute=distribute,
    )


def _summary(colones: int) -> CycleSummary:
    start, end = date(2026, 8, 15), ANCHOR
    net = colones // 10
    return CycleSummary(
        start=start, end=end, mandatory_assigned=0, mandatory_done=0,
        mandatory_failed=0, optional_done=0, todos_done=0,
        points_earned=net, points_subtracted=0, points_net=net, colones=colones,
        cap_applied=False, floor_applied=False,
    )


class FakeNotion:
    def __init__(self, mov_linked=None):
        self.created: list[tuple[str, dict]] = []
        self.updated: list[tuple[str, dict]] = []
        self._mov_linked = mov_linked or []
        self._n = 0

    def query(self, database_id, filter_=None):
        return iter(self._mov_linked)

    def create_page(self, database_id, properties):
        self._n += 1
        self.created.append((database_id, properties))
        return {"id": f"new{self._n}", "properties": properties}

    def update_page(self, page_id, properties):
        self.updated.append((page_id, properties))
        return {"id": page_id}


@pytest.fixture
def wired(monkeypatch):
    """Patch the read side so run() reaches the write side with one member,
    one in-window agenda row, and a controllable cycle summary + sobres."""
    fake = FakeNotion()
    state = {"summary": _summary(1000), "sobres": SOBRES, "existing": {}}

    monkeypatch.setattr(job.n, "NotionClient", lambda _token: fake)
    monkeypatch.setattr(job, "load_members", lambda *_: [MEMBER])
    monkeypatch.setattr(job, "load_routines", lambda *_: {})
    monkeypatch.setattr(job, "load_tareas", lambda *_: {})
    monkeypatch.setattr(
        job, "load_agenda", lambda *_: [SimpleNamespace(member_ids=["mem1"])]
    )
    monkeypatch.setattr(job, "load_sobres", lambda *_: state["sobres"])
    monkeypatch.setattr(
        job, "load_cortes_for_cycle", lambda *_: state["existing"]
    )
    monkeypatch.setattr(job, "to_events", lambda *_a, **_k: [])
    monkeypatch.setattr(job, "settle", lambda *_a, **_k: state["summary"])
    return fake, state


def _finance_config(**kw):
    return _config(db_corte="corte", db_sobres="sob", db_movimientos="mov",
                   force_close=True, **kw)


def _movements(fake):
    return [props for db, props in fake.created if db == "mov"]


def _tipo(props):
    return props[s.Movimientos.TIPO]["select"]["name"]


# --- the two guards (no fakes needed) -----------------------------------


def test_non_payday_returns_early_even_without_db_corte():
    assert job.run(_config(db_corte=None), today=date(2026, 8, 20)) == 0


def test_payday_without_db_corte_raises_clearly():
    with pytest.raises(RuntimeError, match="NOTION_DB_CORTE"):
        job.run(_config(db_corte=None), today=ANCHOR)


def test_force_close_without_db_corte_also_raises():
    with pytest.raises(RuntimeError, match="NOTION_DB_CORTE"):
        job.run(_config(db_corte=None, force_close=True), today=date(2026, 8, 20))


# --- the Corte + deposit path -----------------------------------------


def test_deposit_splits_the_net_across_the_sobres_by_reparto(wired):
    fake, _ = wired
    job.run(_finance_config(), today=ANCHOR)

    corte_writes = [p for db, p in fake.created if db == "corte"]
    assert len(corte_writes) == 1

    movs = _movements(fake)
    income = [m for m in movs if _tipo(m) == s.TIPO_INGRESO_MESADA]
    transfers = [m for m in movs if _tipo(m) == s.TIPO_TRANSFERENCIA_SOBRE]
    assert len(income) == 1
    assert income[0][s.Movimientos.MONTO]["number"] == 1000
    amounts = sorted(m[s.Movimientos.MONTO]["number"] for m in transfers)
    assert amounts == [100, 200, 200, 500]
    assert sum(amounts) == 1000

    # every sobre saldo bumped, then the Corte flipped to Pagado.
    saldo_updates = [u for u in fake.updated if s.Sobres.SALDO in u[1]]
    assert {pid for pid, _ in saldo_updates} == {so.page_id for so in SOBRES}
    assert any(
        props.get(s.Corte.PAGADO) == {"checkbox": True} for _, props in fake.updated
    )


def test_second_run_is_a_noop_when_the_corte_is_already_paid(wired):
    fake, state = wired
    state["existing"] = {
        "mem1": {"id": "c1", "properties": {s.Corte.PAGADO: {"checkbox": True}}}
    }
    job.run(_finance_config(), today=ANCHOR)
    assert fake.created == []
    assert fake.updated == []


def test_distribute_off_writes_the_corte_but_moves_no_money(wired):
    fake, _ = wired
    job.run(_finance_config(distribute=False), today=ANCHOR)
    assert [db for db, _ in fake.created] == ["corte"]
    assert _movements(fake) == []
    assert fake.updated == []


def test_zero_net_writes_the_corte_and_marks_it_paid(wired):
    fake, state = wired
    state["summary"] = _summary(0)
    job.run(_finance_config(), today=ANCHOR)
    assert [db for db, _ in fake.created] == ["corte"]
    assert _movements(fake) == []
    assert fake.updated == [("new1", {s.Corte.PAGADO: n.w_checkbox(True)})]


def test_member_without_sobres_records_income_but_does_not_split(wired):
    fake, state = wired
    state["sobres"] = []
    job.run(_finance_config(), today=ANCHOR)
    movs = _movements(fake)
    assert len(movs) == 1
    assert _tipo(movs[0]) == s.TIPO_INGRESO_MESADA
    assert not [u for u in fake.updated if s.Sobres.SALDO in u[1]]
    assert fake.updated[-1] == ("new1", {s.Corte.PAGADO: n.w_checkbox(True)})


def test_existing_linked_movements_only_flip_the_flag(monkeypatch, wired):
    fake, _ = wired
    fake._mov_linked = [{"id": "m0"}]
    job.run(_finance_config(), today=ANCHOR)
    assert _movements(fake) == []
    assert fake.updated == [("new1", {s.Corte.PAGADO: n.w_checkbox(True)})]


def test_dry_run_writes_nothing(wired):
    fake, _ = wired
    assert job.run(_finance_config(dry_run=True), today=ANCHOR) == 1
    assert fake.created == []
    assert fake.updated == []
