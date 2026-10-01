from datetime import date, datetime, timezone
from unittest import mock

from family_agile_sync import config


def test_local_today_uses_costa_rica_after_utc_midnight():
    # 00:30 UTC on 1 Oct is still 18:30 on 30 Sep in Costa Rica.
    utc_now = datetime(2026, 10, 1, 0, 30, tzinfo=timezone.utc)
    with mock.patch.object(config, "datetime") as fake:
        fake.now.side_effect = lambda tz: utc_now.astimezone(tz)
        assert config.local_today() == date(2026, 9, 30)
