"""When the daily GitHub Actions job should do real work.

Cron runs in UTC at 16:05 and 17:05, so one of them lands at 10:05 Mountain time whether Alberta
is on UTC-6 or UTC-7 (tzdata 2026e: UTC-6 all year from November 2026). GitHub can start a scheduled run late, so the rule is "on or after 10:00
local and nothing issued yet today", not "exactly at 10:00".
"""

import pandas as pd
import psycopg

from gridwatch.features import TZ


def should_run(now_utc: pd.Timestamp, issued_today: bool, manual: bool) -> bool:
    return manual or (now_utc.tz_convert(TZ).hour >= 10 and not issued_today)


def issued_today(conn: psycopg.Connection, now_utc: pd.Timestamp) -> bool:
    """A live forecast made today (issue_date is the local date it was issued)."""
    row = conn.execute("SELECT 1 FROM forecasts WHERE source = 'live' AND issue_date = %s LIMIT 1",
                       (now_utc.tz_convert(TZ).date(),)).fetchone()
    return row is not None
