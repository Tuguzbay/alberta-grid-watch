"""Postgres access. DATABASE_URL is docker compose locally, Supabase in production."""

import os

import pandas as pd
import psycopg

from gridwatch.weather import CITIES

WEATHER_VARS = ("temp", "rh", "wind", "cloud", "wind100", "swrad")
WEATHER_COLS = [f"{v}_{c}" for c in CITIES for v in WEATHER_VARS]  # actuals (archive)
WEATHER_FC_COLS = [f"{v}_fc_{c}" for c in CITIES for v in WEATHER_VARS]  # day-ahead forecasts
# AESO capability: dispatchable = available (after outages) of every non-wind/solar fuel.
CAPACITY_COLS = ["dispatchable_ac", "wind_mc", "solar_mc"]
COLS = ["pool_price", "price_fc_2h", "load_mw", "load_fc_da", *CAPACITY_COLS,
        *WEATHER_COLS, *WEATHER_FC_COLS]

# One row per UTC hour, so DST repeats/skips in Mountain time can't create duplicates.
# ADD COLUMN IF NOT EXISTS lets an existing table pick up new columns.
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS hourly (
    ts_utc timestamptz PRIMARY KEY,
    updated_at timestamptz NOT NULL DEFAULT now()
);
{"".join(f"ALTER TABLE hourly ADD COLUMN IF NOT EXISTS {c} double precision;" for c in COLS)}
CREATE TABLE IF NOT EXISTS forecasts (
    ts_utc timestamptz NOT NULL,
    target text NOT NULL,
    model text NOT NULL,
    issue_date date NOT NULL,
    value double precision,
    source text NOT NULL DEFAULT 'backtest',  -- 'backtest' or 'live'
    PRIMARY KEY (ts_utc, target, model, source)
);
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
    key text PRIMARY KEY,  -- the key column in rag/sources.csv
    publisher text NOT NULL,
    title text NOT NULL,
    published text,
    url text NOT NULL,
    retrieved_on date NOT NULL,
    sha256 text NOT NULL
);
-- shortcut: no vector index, exact scan; fine for a few thousand chunks, add HNSW past that.
CREATE TABLE IF NOT EXISTS chunks (
    doc_key text NOT NULL REFERENCES documents ON DELETE CASCADE,
    ord int NOT NULL,
    page int,  -- PDF page (1-based); NULL for web pages
    text text NOT NULL,
    embedding vector(384) NOT NULL,
    PRIMARY KEY (doc_key, ord)
);
-- Last content change of a tracked document (claim watch).
ALTER TABLE documents ADD COLUMN IF NOT EXISTS changed_on date;
-- Fingerprint of the visible text: markup-only edits (e.g. CSRF tokens) aren't changes.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_sha text;
CREATE TABLE IF NOT EXISTS articles (
    url text PRIMARY KEY,  -- canonical URL (watch.canonical_url)
    title text,
    outlet text,
    published date,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL,  -- ok, unreadable, too_long, extract_failed
    source_kind text NOT NULL  -- news, official
);
CREATE TABLE IF NOT EXISTS claims (
    id text PRIMARY KEY,  -- watch.claim_id(url, quote)
    article_url text NOT NULL REFERENCES articles ON DELETE CASCADE,
    claim text NOT NULL,
    speaker text,
    quote text NOT NULL,
    topic text NOT NULL,
    numbers jsonb NOT NULL DEFAULT '[]',
    model text NOT NULL,
    extracted_at timestamptz NOT NULL DEFAULT now()
);"""


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


def hourly_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """The whole `hourly` table, indexed by ts_utc on a gap-free hourly index."""
    cur = conn.execute(f"SELECT ts_utc, {', '.join(COLS)} FROM hourly ORDER BY ts_utc")
    df = pd.DataFrame(cur.fetchall(), columns=["ts_utc", *COLS]).set_index("ts_utc")
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    return df.astype(float).asfreq("h")


def save_forecasts(conn: psycopg.Connection, fc: pd.DataFrame) -> None:
    """fc columns: ts_utc, target, model, issue_date, value, source. Replaces matching rows."""
    cols = ["ts_utc", "target", "model", "issue_date", "value", "source"]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO forecasts (ts_utc, target, model, issue_date, value, source) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (ts_utc, target, model, source) "
            "DO UPDATE SET issue_date = EXCLUDED.issue_date, value = EXCLUDED.value",
            fc[cols].itertuples(index=False))


def forecast_frame(conn: psycopg.Connection) -> pd.DataFrame:
    """Every stored forecast with its actual value (NaN until the hour settles)."""
    cur = conn.execute(
        "SELECT f.ts_utc, f.target, f.model, f.issue_date, f.value, f.source, "
        "CASE f.target WHEN 'pool_price' THEN h.pool_price WHEN 'load_mw' THEN h.load_mw END "
        "FROM forecasts f LEFT JOIN hourly h USING (ts_utc)")
    cols = ["ts_utc", "target", "model", "issue_date", "value", "source", "actual"]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df.astype({"value": float, "actual": float})
