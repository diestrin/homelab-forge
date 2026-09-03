"""push-definitions: retiring a routine's mirror, and the PRUNE_HABITICA sweep.

The repo loaders and the Habitica client are faked, so the job's real
branching runs without network. The normal create/update path is covered
indirectly here and directly by test_pull_pool's shared model.
"""

from datetime import date

import pytest

from family_agile_sync import schema as s
from family_agile_sync.config import Config
from family_agile_sync.habitica import MIRROR_NOTE
from family_agile_sync.jobs import push_definitions as job
from family_agile_sync.repo import Member, Routine, Tarea
from family_agile_sync.rules import Difficulty, Kind


def _config(*, dry_run=False, prune_habitica=False):
    return Config(
        notion_token="t", db_miembros="m", db_rutinas="r", db_agenda="a",
        db_tareas="ta", anchor_friday=date(2026, 8, 28), habitica_client="x",
        request_delay_seconds=0, dry_run=dry_run, force_close=False,
        prune_habitica=prune_habitica,
    )


def _member(pid):
    return Member(page_id=pid, name=pid, habitica_user_id=None,
                  colones_por_punto=10, active=True)


def _routine(pid, *, retired=False, mirror=None, members=("luna",),
             tipo=Kind.OPCIONAL):
    return Routine(
        page_id=pid, name=f"routine {pid}", member_ids=list(members),
        elegibles_ids=[], kind=tipo, modalidad=s.MODALIDAD_PERSONAL, paga=True,
        difficulty=Difficulty.FACIL, recurrencia="Semanal", dias=["L"],
        habitica_task_ids=dict(mirror or {}), habitica_tipo="daily",
        retired=retired,
    )


def _tarea(pid, *, member, habitica_task_id):
    return Tarea(page_id=pid, title=pid, member_id=member,
                 difficulty=Difficulty.FACIL, aprobada=True,
                 habitica_task_id=habitica_task_id, estado=None)


class FakeNotion:
    def __init__(self):
        self.updates = []

    def update_page(self, page_id, props):
        self.updates.append((page_id, props))


class FakeHabitica:
    def __init__(self, tasks):
        self._tasks = tasks
        self.created, self.updated, self.deleted = [], [], []

    def list_tasks(self, task_type=None):
        return list(self._tasks)

    def create_task(self, payload):
        tid = f"new-{len(self.created)}"
        self.created.append(payload)
        return {"id": tid}

    def update_task(self, task_id, payload):
        self.updated.append((task_id, payload))
        return {"id": task_id}

    def delete_task(self, task_id):
        self.deleted.append(task_id)


@pytest.fixture
def wired(monkeypatch):
    def go(config, *, routines=(), tareas=(), account_tasks=None):
        notion = FakeNotion()
        hab = FakeHabitica(account_tasks or [])
        monkeypatch.setattr(job, "load_members", lambda *_: [_member("luna")])
        monkeypatch.setattr(job, "load_routines",
                            lambda *_: {r.page_id: r for r in routines})
        monkeypatch.setattr(job, "load_tareas",
                            lambda *_: {t.page_id: t for t in tareas})
        monkeypatch.setattr(job.n, "NotionClient", lambda *_a, **_k: notion)
        monkeypatch.setattr(job, "habitica_credentials", lambda name: (name, "key"))
        monkeypatch.setattr(job, "HabiticaClient", lambda *a, **k: hab)
        job.run(config)
        return notion, hab

    return go


def _mirror_task(tid):
    return {"id": tid, "notes": MIRROR_NOTE, "text": tid, "type": "daily"}


# --- retiring a routine's mirror --------------------------------------


def test_retired_routine_mirror_is_deleted_and_the_map_cleared(wired):
    r = _routine("r1", retired=True, mirror={"luna": "h-old"})
    notion, hab = wired(_config(), routines=[r], account_tasks=[_mirror_task("h-old")])
    assert hab.deleted == ["h-old"]
    assert (r.page_id, {s.Rutinas.HABITICA_TASK_ID: {"rich_text": [
        {"type": "text", "text": {"content": "{}"}}]}}) in notion.updates


def test_retired_routine_without_a_mirror_is_a_noop(wired):
    r = _routine("r1", retired=True, mirror={})
    notion, hab = wired(_config(), routines=[r])
    assert hab.deleted == []
    assert notion.updates == []


def test_dry_run_deletes_nothing_when_retiring(wired):
    r = _routine("r1", retired=True, mirror={"luna": "h-old"})
    notion, hab = wired(_config(dry_run=True), routines=[r])
    assert hab.deleted == []
    assert notion.updates == []


# --- PRUNE_HABITICA sweep -------------------------------------------


def test_prune_off_by_default_leaves_orphans_alone(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    _, hab = wired(_config(prune_habitica=False), routines=[r],
                   account_tasks=[_mirror_task("h-live"), _mirror_task("h-orphan")])
    assert hab.deleted == []


def test_prune_deletes_only_marked_orphans(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    t = _tarea("t1", member="luna", habitica_task_id="h-tarea")
    account = [
        _mirror_task("h-live"),                 # referenced by the routine
        _mirror_task("h-tarea"),                # referenced by the tarea
        _mirror_task("h-orphan"),               # ours, unreferenced -> delete
        {"id": "childs-own", "notes": "mi lista", "text": "x"},  # not ours -> keep
    ]
    _, hab = wired(_config(prune_habitica=True), routines=[r], tareas=[t],
                   account_tasks=account)
    assert hab.deleted == ["h-orphan"]


def test_prune_in_dry_run_deletes_nothing(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    _, hab = wired(_config(dry_run=True, prune_habitica=True), routines=[r],
                   account_tasks=[_mirror_task("h-live"), _mirror_task("h-orphan")])
    assert hab.deleted == []
