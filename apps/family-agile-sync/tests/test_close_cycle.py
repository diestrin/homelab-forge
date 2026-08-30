"""close-cycle: the payday guard and the NOTION_DB_CORTE guard.

NOTION_DB_CORTE is optional in Config (Corte quincenal doesn't exist yet,
Fase 5) -- these tests only cover that both guards fire before any Notion
client is touched, so the other three jobs staying unaffected is provable
without needing Notion/Habitica fakes.
"""

from datetime import date

import pytest

from family_agile_sync.config import Config
from family_agile_sync.jobs import close_cycle as job

ANCHOR = date(2026, 8, 28)  # a Friday


def _config(*, db_corte=None, force_close=False):
    return Config(
        notion_token="t", db_miembros="m", db_rutinas="r", db_agenda="a",
        db_tareas="ta", anchor_friday=ANCHOR, habitica_client="x",
        request_delay_seconds=0, dry_run=False, force_close=force_close,
        db_corte=db_corte,
    )


def test_non_payday_returns_early_even_without_db_corte():
    """The other three jobs never touch db_corte; a non-payday Friday (or
    any other day) must not require it either."""
    result = job.run(_config(db_corte=None), today=date(2026, 8, 20))
    assert result == 0


def test_payday_without_db_corte_raises_clearly():
    with pytest.raises(RuntimeError, match="NOTION_DB_CORTE"):
        job.run(_config(db_corte=None), today=ANCHOR)


def test_force_close_without_db_corte_also_raises():
    with pytest.raises(RuntimeError, match="NOTION_DB_CORTE"):
        job.run(_config(db_corte=None, force_close=True), today=date(2026, 8, 20))
