"""Postgres access. DATABASE_URL is docker compose locally, Supabase in production."""

import os

import psycopg

from gridwatch.weather import CITIES

WEATHER_COLS = [f"{v}_{c}" for c in CITIES for v in ("temp", "rh", "wind", "cloud")]
COLS = ["pool_price", "price_fc_2h", "load_mw", "load_fc_da", *WEATHER_COLS]

# One row per UTC hour, so DST repeats/skips in Mountain time can't create duplicates.
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS hourly (
    ts_utc timestamptz PRIMARY KEY,
    {", ".join(f"{c} double precision" for c in COLS)},
    updated_at timestamptz NOT NULL DEFAULT now()
)"""


def connect() -> psycopg.Connection:
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    conn.execute(SCHEMA)
    return conn


def upsert(conn: psycopg.Connection, rows: list[dict]) -> None:
    """Insert or update hours. All rows share the keys of rows[0] (ts_utc + some COLS).

    A NULL never overwrites a stored value, so a re-fetch can't erase data."""
    if not rows:
        return
    cols = list(rows[0])
    assert cols[0] == "ts_utc" and set(cols[1:]) <= set(COLS), cols
    sets = ", ".join(f"{c} = COALESCE(EXCLUDED.{c}, hourly.{c})" for c in cols[1:])
    sql = (f"INSERT INTO hourly ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           f"ON CONFLICT (ts_utc) DO UPDATE SET {sets}, updated_at = now()")
    with conn.cursor() as cur:
        cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
