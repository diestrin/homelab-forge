"""Tests for build_task_payload -- the pure Family Agile -> Habitica mapping.

The HTTP client itself is not exercised here (see README); this only covers
the payload shape for each Habitica task type.
"""

from datetime import date

from family_agile_sync.habitica import build_task_payload


def test_daily_carries_the_repeat_map_and_yesterdaily():
    payload = build_task_payload(
        title="Tender la cama",
        habitica_type="daily",
        difficulty="Fácil",
        days=["L", "K", "V"],
        applies_damage=True,
    )
    assert payload["type"] == "daily"
    assert payload["frequency"] == "weekly"
    assert payload["repeat"] == {
        "m": True, "t": False, "w": True, "th": False,
        "f": True, "s": False, "su": False,
    }
    assert payload["yesterDaily"] is True


def test_optional_daily_never_applies_damage():
    payload = build_task_payload(
        title="Leer", habitica_type="daily", difficulty="Fácil", applies_damage=False
    )
    assert payload["yesterDaily"] is False


def test_habit_only_ever_adds():
    payload = build_task_payload(title="Ayudar", habitica_type="habit", difficulty="Fácil")
    assert payload["up"] is True
    assert payload["down"] is False


def test_todo_without_a_due_date_omits_the_date_field():
    payload = build_task_payload(title="Lavar el carro", habitica_type="todo", difficulty="Fácil")
    assert "date" not in payload
    assert "frequency" not in payload
    assert "up" not in payload


def test_todo_with_a_due_date_carries_it():
    payload = build_task_payload(
        title="Limpiar el refri",
        habitica_type="todo",
        difficulty="Intermedia",
        due_date=date(2026, 9, 15),
    )
    assert payload["date"] == "2026-09-15"


def test_priority_follows_difficulty():
    for difficulty, priority in (("Fácil", 1), ("Intermedia", 1.5), ("Compleja", 2)):
        payload = build_task_payload(title="x", habitica_type="habit", difficulty=difficulty)
        assert payload["priority"] == priority
