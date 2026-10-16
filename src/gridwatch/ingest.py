"""Fetch AESO + Open-Meteo hours and upsert them into the `hourly` table."""

from datetime import UTC, date, datetime, timedelta

import psycopg

from gridwatch import aeso, db, weather

MAX_DAYS = 366  # AESO rejects longer ranges ("maximum of 366 days of data"); end date is inclusive


def chunks(start: date, end: date, days: int = MAX_DAYS):
    while start <= end:
        stop = min(start + timedelta(days=days - 1), end)
        yield start, stop
        start = stop + timedelta(days=1)


def _num(s):
    # AESO sends "" for hours that haven't happened yet.
    return None if s in ("", None) else float(s)


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def price_rows(recs: list[dict]) -> list[dict]:
    return [{"ts_utc": _ts(r["begin_datetime_utc"]), "pool_price": _num(r["pool_price"]),
             "price_fc_2h": _num(r["forecast_pool_price"])} for r in recs]


def load_rows(recs: list[dict]) -> list[dict]:
    return [{"ts_utc": _ts(r["begin_datetime_utc"]), "load_mw": _num(r["alberta_internal_load"]),
             "load_fc_da": _num(r["forecast_alberta_internal_load"])} for r in recs]


def weather_rows(city: str, h: dict) -> list[dict]:
    src = {"temp": "temperature_2m", "rh": "relative_humidity_2m",
           "wind": "wind_speed_10m", "cloud": "cloud_cover"}
    return [{"ts_utc": _ts(t), **{f"{k}_{city}": h[v][i] for k, v in src.items()}}
            for i, t in enumerate(h["time"])]


def ingest(conn: psycopg.Connection, start: date, end: date) -> None:
    """Commits per chunk, so an interrupted backfill keeps what it already loaded."""
    for s, e in chunks(start, end):
        a, b = s.isoformat(), e.isoformat()
        db.upsert(conn, price_rows(aeso.pool_price(a, b)))
        db.upsert(conn, load_rows(aeso.internal_load(a, b)))
        for city in weather.CITIES:
            db.upsert(conn, weather_rows(city, weather.history(city, a, b)))
        conn.commit()
        print(f"loaded {a}..{b}", flush=True)
