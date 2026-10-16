"""Data-quality report over the `hourly` table."""

import psycopg

from gridwatch.db import COLS

PRICE_FLOOR, PRICE_CAP = 0, 999.99  # Alberta pool price limits, $/MWh


def report(conn: psycopg.Connection) -> dict:
    """Missing hours in the stored span, NULLs per column for past hours, out-of-range prices.

    Duplicate hours can't exist: ts_utc is the primary key."""
    first, last, rows = conn.execute(
        "SELECT min(ts_utc), max(ts_utc), count(*) FROM hourly").fetchone()
    missing = [r[0] for r in conn.execute(
        "SELECT g FROM generate_series(%s::timestamptz, %s, '1 hour') g "
        "EXCEPT SELECT ts_utc FROM hourly ORDER BY 1", (first, last))] if rows else []
    counts = ", ".join(f"count(*) - count({c})" for c in COLS)
    nulls = conn.execute(f"SELECT {counts} FROM hourly WHERE ts_utc < now()").fetchone()
    bad_price = conn.execute(
        "SELECT count(*) FROM hourly WHERE pool_price NOT BETWEEN %s AND %s",
        (PRICE_FLOOR, PRICE_CAP)).fetchone()[0]
    return {"first": first, "last": last, "rows": rows, "missing_hours": missing,
            "nulls": {c: n for c, n in zip(COLS, nulls, strict=True) if n},
            "price_out_of_range": bad_price}
