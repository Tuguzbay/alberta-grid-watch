"""Daily run, meant for 10:00 Mountain time: ingest, then forecast tomorrow (local day).

Run: python scripts/daily.py   (needs AESO_API_KEY and DATABASE_URL). Safe to rerun.
"""

from datetime import timedelta

import pandas as pd

from gridwatch import backtest, db, features, ingest

today = pd.Timestamp.now(tz=features.TZ).date()
tomorrow = today + timedelta(days=1)

with db.connect() as conn:
    # Through the day after tomorrow: weather is fetched by UTC date, and local "tomorrow"
    # ends at 06:00 UTC the next day. This also stores tomorrow's AESO load forecast.
    ingest.ingest(conn, today - timedelta(days=7), tomorrow + timedelta(days=1))
    fc = backtest.forecast_day(db.hourly_frame(conn), pd.Timestamp(tomorrow))
    db.save_forecasts(conn, fc)
print(f"forecast {tomorrow}: {len(fc)} rows")
print(fc.groupby(["target", "model"])["value"].agg(["size", "mean"]).round(1).to_string())
