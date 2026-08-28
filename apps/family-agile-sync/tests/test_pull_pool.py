"""pull-completions: Pool first-wins + loser cleanup, and the Personal path.

The three repo loaders and both API clients are replaced with fakes, so this
drives the job's real branching without any network.
"""

from datetime import date

import pytest

from family_agile_sync import schema as s
from family_agile_sync.config import Config
from family_agile_sync.jobs import pull_completions as job
from family_agile_sync.repo import AgendaRow, Member, Routine, Tarea
from family_agile_sync.rules import Difficulty, Kind

TODAY = date(2026, 8, 24)


def _config():
    return Config(
        notion_token="t", db_miembros="m", db_rutinas="r", db_agenda="a",
        db_tareas="ta", db_corte="c", anchor_friday=date(2026, 8, 28),
        habitica_client="x", request_delay_seconds=0, dry_run=False,
        force_close=False,
    )


def _member(pid, rate=10):
    return Member(page_id=pid, name=pid.upper(), habitica_user_id=None,
                  colones_por_punto=rate, active=True)


def _routine(pid="R", *, modalidad, kind, mirror, difficulty=Difficulty.INTERMEDIA,
             members=(), elegibles=()):
    return Routine(
        page_id=pid, name=f"routine {pid}", member_ids=list(members),
        elegibles_ids=list(elegibles), kind=kind, modalidad=modalidad, paga=True,
        difficulty=difficulty, recurrencia="Semanal", dias=["L"],
        habitica_task_ids=dict(mirror), habitica_tipo="daily", retired=False,
    )


def _row(pid="a1", *, members, rutina, estado=s.ESTADO_PENDIENTE):
    return AgendaRow(
        page_id=pid, title=pid, member_ids=list(members), rutina_ids=[rutina],
        tarea_ids=[], estado=estado, day=TODAY, origen=None,
        points_applied=None, adjusted=False,
    )


def _tarea(pid="t1", *, member, habitica_task_id, difficulty=Difficulty.INTERMEDIA,
           estado=None, aprobada=True):
    return Tarea(
        page_id=pid, title=pid, member_id=member, difficulty=difficulty,
        aprobada=aprobada, habitica_task_id=habitica_task_id, estado=estado,
    )


class FakeNotion:
    def __init__(self):
        self.updates = []
        self.created = []

    def update_page(self, page_id, props):
        self.updates.append((page_id, props))

    def create_page(self, database_id, props):
        self.created.append((database_id, props))


class FakeHabitica:
    def __init__(self, completed):
        self._completed = completed
        self.deleted = []

    def list_tasks(self, task_type=None):
        return [{"id": tid, "completed": True} for tid in self._completed]

    def delete_task(self, task_id):
        self.deleted.append(task_id)


@pytest.fixture
def wired(monkeypatch):
    """Returns a helper that installs fakes for a given scenario and runs the job."""
    state = {}

    def go(members, routines, rows, completed_by_member, tareas=()):
        notion = FakeNotion()
        habiticas = {name: FakeHabitica(completed_by_member.get(name, []))
                     for name in {m.name for m in members}}

        monkeypatch.setattr(job, "load_members", lambda *_: list(members))
        monkeypatch.setattr(job, "load_routines", lambda *_: {r.page_id: r for r in routines})
        monkeypatch.setattr(job, "load_tareas", lambda *_: {t.page_id: t for t in tareas})
        monkeypatch.setattr(job, "load_agenda", lambda *a, **k: list(rows))
        monkeypatch.setattr(job.n, "NotionClient", lambda *_a, **_k: notion)
        monkeypatch.setattr(job, "habitica_credentials", lambda name: (name, "key"))
        monkeypatch.setattr(job, "HabiticaClient",
                            lambda user, key, *a, **k: habiticas[user])

        result = job.run(_config(), today=TODAY)
        state.update(notion=notion, habiticas=habiticas, result=result)
        return state

    return go


def test_pool_first_completer_wins_and_losers_mirror_is_deleted(wired):
    m1, m2 = _member("m1"), _member("m2")
    r = _routine(modalidad=s.MODALIDAD_POOL, kind=Kind.OPCIONAL,
                 elegibles=("m1", "m2"), mirror={"m1": "h1", "m2": "h2"})
    row = _row(members=[], rutina="R")  # unclaimed pool occurrence

    st = wired([m1, m2], [r], [row], {"M1": ["h1"], "M2": ["h2"]})

    assert st["result"] == 1
    assert len(st["notion"].updates) == 1
    page_id, props = st["notion"].updates[0]
    assert page_id == "a1"
    assert props[s.Agenda.ESTADO] == {"status": {"name": s.ESTADO_HECHA}}
    assert props[s.Agenda.MIEMBRO] == {"relation": [{"id": "m1"}]}
    assert props[s.Agenda.PUNTOS_APLICADOS] == {"number": 10}
    assert props[s.Agenda.COLONES] == {"number": 100}
    # m1 won: m2's mirror is removed, m1's is left alone.
    assert st["habiticas"]["M2"].deleted == ["h2"]
    assert st["habiticas"]["M1"].deleted == []


def test_pool_second_completer_in_same_run_is_not_credited(wired):
    m1, m2 = _member("m1"), _member("m2")
    r = _routine(modalidad=s.MODALIDAD_POOL, kind=Kind.OPCIONAL,
                 elegibles=("m1", "m2"), mirror={"m1": "h1", "m2": "h2"})
    st = wired([m1, m2], [r], [_row(members=[], rutina="R")],
              {"M1": ["h1"], "M2": ["h2"]})
    # Exactly one credit even though both ticked their mirror.
    assert st["result"] == 1
    assert len(st["notion"].updates) == 1


def test_personal_completion_credits_without_claiming_membership(wired):
    m1 = _member("m1")
    r = _routine(modalidad=s.MODALIDAD_PERSONAL, kind=Kind.MANDATORY,
                 members=("m1",), mirror={"m1": "hp"}, difficulty=Difficulty.FACIL)
    st = wired([m1], [r], [_row(members=["m1"], rutina="R")], {"M1": ["hp"]})

    assert st["result"] == 1
    _, props = st["notion"].updates[0]
    assert props[s.Agenda.PUNTOS_APLICADOS] == {"number": 5}
    assert s.Agenda.MIEMBRO not in props  # personal rows already have their member


def test_nothing_completed_writes_nothing(wired):
    m1 = _member("m1")
    r = _routine(modalidad=s.MODALIDAD_PERSONAL, kind=Kind.MANDATORY,
                 members=("m1",), mirror={"m1": "hp"})
    st = wired([m1], [r], [_row(members=["m1"], rutina="R")], {"M1": []})
    assert st["result"] == 0
    assert st["notion"].updates == []


# --- Tareas: the Agenda row doesn't pre-exist, it's created on completion --


def test_tarea_completion_creates_agenda_row_and_marks_tarea_hecha(wired):
    m1 = _member("m1")
    t = _tarea(member="m1", habitica_task_id="td1", difficulty=Difficulty.INTERMEDIA)
    st = wired([m1], [], [], {"M1": ["td1"]}, tareas=[t])

    assert st["result"] == 1
    assert len(st["notion"].created) == 1
    db_id, props = st["notion"].created[0]
    assert db_id == "a"
    assert props[s.Agenda.TAREA] == {"relation": [{"id": "t1"}]}
    assert props[s.Agenda.MIEMBRO] == {"relation": [{"id": "m1"}]}
    assert props[s.Agenda.PUNTOS_APLICADOS] == {"number": 10}
    assert props[s.Agenda.COLONES] == {"number": 100}
    assert st["notion"].updates == [
        ("t1", {s.Tareas.ESTADO: {"select": {"name": s.ESTADO_HECHA}}})
    ]


def test_tarea_already_hecha_is_not_recredited(wired):
    m1 = _member("m1")
    t = _tarea(member="m1", habitica_task_id="td1", estado=s.ESTADO_HECHA)
    st = wired([m1], [], [], {"M1": ["td1"]}, tareas=[t])
    assert st["result"] == 0
    assert st["notion"].created == []


def test_tarea_for_a_different_member_is_not_credited(wired):
    m1, m2 = _member("m1"), _member("m2")
    t = _tarea(member="m2", habitica_task_id="td1")
    st = wired([m1, m2], [], [], {"M1": ["td1"], "M2": []}, tareas=[t])
    assert st["result"] == 0
    assert st["notion"].created == []
