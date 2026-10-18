import pandas as pd

from gridwatch.features import TZ
from gridwatch.schedule import should_run


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_should_run_summer_first_cron():
    assert should_run(utc("2026-07-01 16:05"), issued_today=False, manual=False)  # 10:05 MDT


def test_should_run_summer_second_cron_skips():
    assert not should_run(utc("2026-07-01 17:05"), issued_today=True, manual=False)


# Winter cases use 2025: from November 2026 Alberta stays on UTC-6 all year (tzdata 2026e).
def test_should_run_winter_first_cron_too_early():
    assert not should_run(utc("2025-12-01 16:05"), issued_today=False, manual=False)  # 09:05 MST


def test_should_run_winter_second_cron():
    assert should_run(utc("2025-12-01 17:05"), issued_today=False, manual=False)  # 10:05 MST


def test_tz_data_knows_alberta_stays_on_utc_minus_6():
    # Fails on stale tz data (e.g. an old system zoneinfo on Linux): set PYTHONTZPATH="".
    assert utc("2026-12-01 16:05").tz_convert(TZ).hour == 10
    assert should_run(utc("2026-12-01 16:05"), issued_today=False, manual=False)


def test_should_run_late_cron_still_runs():
    assert should_run(utc("2026-07-01 17:50"), issued_today=False, manual=False)  # 11:50 MDT


def test_should_run_manual_always():
    assert should_run(utc("2026-07-01 09:00"), issued_today=True, manual=True)  # 03:00 MDT
