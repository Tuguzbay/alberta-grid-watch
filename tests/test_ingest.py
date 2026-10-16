import os
from datetime import UTC, date, datetime
from itertools import pairwise

import psycopg
import pytest

from gridwatch import db, ingest, quality


def test_chunks_respect_aeso_366_day_limit():
    cs = list(ingest.chunks(date(2020, 1, 1), date(2022, 1, 5)))
    assert cs[0] == (date(2020, 1, 1), date(2020, 12, 31))
    assert cs[-1][1] == date(2022, 1, 5)
    assert all((e - s).days < ingest.MAX_DAYS for s, e in cs)
    assert all((b[0] - a[1]).days == 1 for a, b in pairwise(cs))  # no gaps, no overlap


def test_price_rows_parse_blank_as_none():
    rows = ingest.price_rows([{"begin_datetime_utc": "2026-10-17 01:00", "pool_price": "",
                               "forecast_pool_price": "25.01"}])
    assert rows == [{"ts_utc": datetime(2026, 10, 17, 1, tzinfo=UTC), "pool_price": None,
                     "price_fc_2h": 25.01}]


def test_weather_rows_suffix_city():
    h = {"time": ["2024-01-01T00:00"], "temperature_2m": [1.4], "relative_humidity_2m": [86],
         "wind_speed_10m": [13.2], "cloud_cover": [100]}
    assert ingest.weather_rows("calgary", h) == [{
        "ts_utc": datetime(2024, 1, 1, tzinfo=UTC), "temp_calgary": 1.4, "rh_calgary": 86,
        "wind_calgary": 13.2, "cloud_calgary": 100}]


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL")
    try:
        c = psycopg.connect(url, connect_timeout=2) if url else None
    except psycopg.OperationalError:
        c = None
    if c is None:
        pytest.skip("no Postgres at DATABASE_URL")
    # Temp table shadows any real `hourly`, so tests never touch stored data.
    c.execute(db.SCHEMA.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
    yield c
    c.close()


def t(h):
    return datetime(2025, 11, 2, h, tzinfo=UTC)


def test_upsert_is_idempotent_and_never_nulls_out(conn):
    db.upsert(conn, [{"ts_utc": t(6), "pool_price": 50.0, "price_fc_2h": 48.0}])
    db.upsert(conn, [{"ts_utc": t(6), "pool_price": 50.0, "price_fc_2h": 48.0}])
    db.upsert(conn, [{"ts_utc": t(6), "pool_price": None, "price_fc_2h": 49.0}])
    db.upsert(conn, [{"ts_utc": t(6), "load_mw": 9800.0, "load_fc_da": 9750.0}])
    assert conn.execute("SELECT count(*), pool_price, price_fc_2h, load_mw FROM hourly "
                        "GROUP BY 2, 3, 4").fetchall() == [(1, 50.0, 49.0, 9800.0)]


def test_quality_reports_gaps_and_bad_prices(conn):
    db.upsert(conn, [{"ts_utc": t(h), "pool_price": p} for h, p in [(6, 10.0), (9, 1200.0)]])
    r = quality.report(conn)
    assert r["rows"] == 2
    assert r["missing_hours"] == [t(7), t(8)]
    assert r["price_out_of_range"] == 1
    assert r["nulls"]["load_mw"] == 2
