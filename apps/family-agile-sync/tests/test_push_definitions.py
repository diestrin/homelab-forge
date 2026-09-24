"""push-definitions: retiring a routine's mirror, and the PRUNE_HABITICA sweep.

The repo loaders and the Habitica client are faked, so the job's real
branching runs without network. The normal create/update path is covered
indirectly here and directly by test_pull_pool's shared model.
"""

from datetime import date

import pytest

from family_agile_sync import schema as s
from family_agile_sync.config import Config
from family_agile_sync.habitica import MIRROR_NOTE, HabiticaError, build_task_payload
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
             tipo=Kind.OPCIONAL, recurrencia="Semanal", dias=("L",),
             habitica_tipo="daily", modalidad=s.MODALIDAD_PERSONAL,
             elegibles=()):
    return Routine(
        page_id=pid, name=f"routine {pid}", member_ids=list(members),
        elegibles_ids=list(elegibles), kind=tipo, modalidad=modalidad, paga=True,
        difficulty=Difficulty.FACIL, recurrencia=recurrencia, dias=list(dias),
        habitica_task_ids=dict(mirror or {}), habitica_tipo=habitica_tipo,
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
    def __init__(self, tasks, *, missing_ids=(), fail_creates=(),
                 fail_update_ids=(), fail_list=False):
        self._tasks = tasks
        #: task ids that no longer exist on Habitica -- update_task on one of
        #: these raises HabiticaError, as a real 404 would.
        self._missing_ids = set(missing_ids)
        self._fail_creates = set(fail_creates)
        self._fail_update_ids = set(fail_update_ids)
        self._fail_list = fail_list
        self.created, self.updated, self.deleted = [], [], []

    def list_tasks(self, task_type=None):
        if self._fail_list:
            raise HabiticaError("GET /tasks/user failed after 4 attempts")
        return list(self._tasks)

    def create_task(self, payload):
        if payload.get("text") in self._fail_creates:
            raise HabiticaError("POST /tasks/user -> 500: boom")
        tid = f"new-{len(self.created)}"
        self.created.append(payload)
        return {"id": tid}

    def update_task(self, task_id, payload):
        if task_id in self._missing_ids:
            raise HabiticaError(
                f"PUT /tasks/{task_id} -> 404: "
                '{"success":false,"error":"NotFound","message":"Tarea no encontrada."}'
            )
        if task_id in self._fail_update_ids:
            raise HabiticaError(
                f"PUT /tasks/{task_id} failed after 4 attempts: connection dropped"
            )
        self.updated.append((task_id, payload))
        return {"id": task_id}

    def delete_task(self, task_id):
        self.deleted.append(task_id)


@pytest.fixture
def wired(monkeypatch):
    def go(config, *, routines=(), tareas=(), account_tasks=None, missing_ids=(),
           fail_creates=(), fail_update_ids=(), fail_list=False, today=None):
        notion = FakeNotion()
        hab = FakeHabitica(
            account_tasks or [], missing_ids=missing_ids,
            fail_creates=fail_creates, fail_update_ids=fail_update_ids,
            fail_list=fail_list,
        )
        monkeypatch.setattr(job, "load_members", lambda *_: [_member("luna")])
        monkeypatch.setattr(job, "load_routines",
                            lambda *_: {r.page_id: r for r in routines})
        monkeypatch.setattr(job, "load_tareas",
                            lambda *_: {t.page_id: t for t in tareas})
        monkeypatch.setattr(job.n, "NotionClient", lambda *_a, **_k: notion)
        monkeypatch.setattr(job, "habitica_credentials", lambda name: (name, "key"))
        monkeypatch.setattr(job, "HabiticaClient", lambda *a, **k: hab)
        job.run(config, today=today)
        return notion, hab

    return go


def _mirror_task(tid):
    return {"id": tid, "notes": MIRROR_NOTE, "text": tid, "type": "daily"}


def _matching_task(tid, routine):
    """A live Habitica task that already matches what push-definitions would PUT."""
    payload = build_task_payload(
        title=routine.name,
        habitica_type=routine.habitica_tipo or "daily",
        difficulty=routine.difficulty.value,
        days=routine.dias,
        notes=MIRROR_NOTE,
        applies_damage=False,
    )
    return {"id": tid, **payload, "completed": False}


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


# --- a stale weekly mirror id (deleted by hand, or a previous partial
# prune) must not crash the run -----------------------------------------


def test_update_404_on_stale_mirror_recreates_instead_of_crashing(wired):
    r = _routine("r1", mirror={"luna": "gone"})
    # Id is still in the account listing (so we attempt an update) but Habitica
    # 404s -- a race with a delete, or a stale cache. Recreate rather than die.
    stale = _matching_task("gone", r)
    stale["text"] = "old name"
    notion, hab = wired(_config(), routines=[r], account_tasks=[stale],
                        missing_ids={"gone"})
    assert hab.updated == []
    assert len(hab.created) == 1
    assert (r.page_id, {s.Rutinas.HABITICA_TASK_ID: {"rich_text": [
        {"type": "text", "text": {"content": '{"luna": "new-0"}'}}]}}) in notion.updates


def test_stored_id_absent_from_account_recreates_without_update(wired):
    r = _routine("r1", mirror={"luna": "gone"})
    notion, hab = wired(_config(), routines=[r], account_tasks=[])
    assert hab.updated == []
    assert len(hab.created) == 1
    assert (r.page_id, {s.Rutinas.HABITICA_TASK_ID: {"rich_text": [
        {"type": "text", "text": {"content": '{"luna": "new-0"}'}}]}}) in notion.updates


def test_unchanged_weekly_mirror_is_not_updated(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    _, hab = wired(_config(), routines=[r],
                   account_tasks=[_matching_task("h-live", r)])
    assert hab.updated == []
    assert hab.created == []


def test_changed_weekly_mirror_is_updated(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    live = _matching_task("h-live", r)
    live["text"] = "old name"
    _, hab = wired(_config(), routines=[r], account_tasks=[live])
    assert hab.updated == [("h-live", build_task_payload(
        title=r.name, habitica_type="daily", difficulty="Fácil",
        days=["L"], notes=MIRROR_NOTE, applies_damage=False,
    ))]
    assert hab.created == []


def test_create_failure_on_one_routine_does_not_abort_the_rest(wired):
    r1 = _routine("r1")
    r2 = _routine("r2")
    notion, hab = wired(_config(), routines=[r1, r2],
                        fail_creates={"routine r1"})
    assert [p["text"] for p in hab.created] == ["routine r2"]
    written = {page for page, _ in notion.updates}
    assert r1.page_id not in written
    assert r2.page_id in written


def test_non_404_update_error_does_not_recreate_or_abort(wired):
    r1 = _routine("r1", mirror={"luna": "h1"})
    r2 = _routine("r2", mirror={"luna": "h2"})
    live1 = _matching_task("h1", r1)
    live1["text"] = "old"
    live2 = _matching_task("h2", r2)
    live2["text"] = "old"
    _, hab = wired(
        _config(), routines=[r1, r2], account_tasks=[live1, live2],
        fail_update_ids={"h1"},
    )
    assert hab.created == []
    assert [tid for tid, _ in hab.updated] == ["h2"]


def test_list_tasks_failure_skips_member_without_aborting(wired):
    r = _routine("r1", mirror={"luna": "h-live"})
    _, hab = wired(_config(), routines=[r], fail_list=True)
    assert hab.updated == []
    assert hab.created == []


# --- weekly-todo mirror: Semanal + 'Habitica tipo' override = todo --------


def test_weekly_todo_creates_a_todo_due_on_the_next_matching_weekday(wired):
    r = _routine("r1", recurrencia="Semanal", dias=["V"], habitica_tipo="todo",
                 modalidad=s.MODALIDAD_POOL, elegibles=("luna",), members=())
    _, hab = wired(_config(), routines=[r], today=date(2026, 8, 24))  # a Monday
    assert len(hab.created) == 1
    payload = hab.created[0]
    assert payload["type"] == "todo"
    assert payload["date"] == "2026-08-28"  # the next Friday


def test_weekly_todo_leaves_an_open_mirror_alone(wired):
    r = _routine("r1", recurrencia="Semanal", dias=["V"], habitica_tipo="todo",
                 modalidad=s.MODALIDAD_POOL, elegibles=("luna",), members=(),
                 mirror={"luna": "h-open"})
    _, hab = wired(_config(), routines=[r], today=date(2026, 8, 24),
                   account_tasks=[{"id": "h-open", "completed": False}])
    assert hab.created == []
    assert hab.updated == []


def test_weekly_todo_recreates_once_the_previous_one_is_done(wired):
    r = _routine("r1", recurrencia="Semanal", dias=["V"], habitica_tipo="todo",
                 modalidad=s.MODALIDAD_POOL, elegibles=("luna",), members=(),
                 mirror={"luna": "h-done"})
    notion, hab = wired(_config(), routines=[r], today=date(2026, 8, 24),
                        account_tasks=[{"id": "h-done", "completed": True}])
    assert len(hab.created) == 1
    assert (r.page_id, {s.Rutinas.HABITICA_TASK_ID: {"rich_text": [
        {"type": "text", "text": {"content": '{"luna": "new-0"}'}}]}}) in notion.updates


def test_weekly_todo_never_applies_damage_even_if_mandatory(wired):
    r = _routine("r1", recurrencia="Semanal", dias=["V"], habitica_tipo="todo",
                 modalidad=s.MODALIDAD_POOL, elegibles=("luna",), members=(),
                 tipo=Kind.MANDATORY)
    _, hab = wired(_config(), routines=[r], today=date(2026, 8, 24))
    payload = hab.created[0]
    assert payload["type"] == "todo"
    assert "yesterDaily" not in payload


def test_semanal_without_the_todo_override_still_mirrors_as_a_habit(wired):
    """Regression: weekly_todo only kicks in when 'Habitica tipo' is
    explicitly set to todo -- a plain Opcional Semanal routine keeps
    mirroring as a Habit, same as before this feature existed."""
    r = _routine("r1", recurrencia="Semanal", dias=["V"], habitica_tipo=None,
                 modalidad=s.MODALIDAD_POOL, elegibles=("luna",), members=())
    _, hab = wired(_config(), routines=[r], today=date(2026, 8, 24))
    assert hab.created[0]["type"] == "habit"
