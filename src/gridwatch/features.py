"""Features for next-day forecasts issued at 10:00 Mountain time on day D-1.

Every feature for a target hour on local day D uses only data known before that cutoff.
"""

import holidays
import pandas as pd

from gridwatch.db import CAPACITY_COLS, WEATHER_COLS, WEATHER_FC_COLS

TZ = "America/Edmonton"
CUTOFF_HOUR = 10
TARGETS = ("pool_price", "load_mw")
LAGS = (48, 72, 168)  # t-48h is on D-2 for every hour of D, so always before the cutoff
MEAN_DAYS = range(2, 32)  # same hour on D-2 .. D-31


def local_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Naive local midnight of each hour's Mountain-time day."""
    return index.tz_convert(TZ).tz_localize(None).normalize()


def cutoff(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC issue time for each target hour: 10:00 local on the day before."""
    naive = local_day(index) - pd.Timedelta(days=1) + pd.Timedelta(hours=CUTOFF_HOUR)
    return naive.tz_localize(TZ).tz_convert("UTC")  # 10:00 is never a DST gap/repeat


def build(df: pd.DataFrame, weather: str) -> pd.DataFrame:
    """weather="actual" (training) or "forecast" (testing/live). Same column names either way."""
    X = pd.DataFrame(index=df.index)
    # Hour starting 08:00 is the latest one surely settled and published by 10:00.
    last_known = cutoff(df.index) - pd.Timedelta(hours=2)
    for t in TARGETS:
        s = df[t]
        for k in LAGS:
            X[f"{t}_lag{k}"] = s.shift(k)
        X[f"{t}_mean30"] = pd.concat([s.shift(24 * k) for k in MEAN_DAYS], axis=1).mean(axis=1)
        X[f"{t}_last_known"] = s.reindex(last_known).to_numpy()
    for c in CAPACITY_COLS:  # outages/capacity as known at the cutoff, carried forward
        X[f"{c}_last_known"] = df[c].reindex(last_known).to_numpy()

    local = df.index.tz_convert(TZ)
    X["hour"], X["dow"], X["month"] = local.hour, local.dayofweek, local.month
    ab = holidays.Canada(subdiv="AB", years=range(local.year.min(), local.year.max() + 1))
    X["holiday"] = [d in ab for d in local.date]

    src = WEATHER_COLS if weather == "actual" else WEATHER_FC_COLS
    X[WEATHER_COLS] = df[src].to_numpy()
    return X
