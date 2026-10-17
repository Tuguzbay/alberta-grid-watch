import numpy as np
import pandas as pd

from gridwatch import features
from gridwatch.db import COLS

# Covers both 2025 DST switches (Mar 9, Nov 2).
IDX = pd.date_range("2025-01-01", "2025-12-31", freq="h", tz="UTC")


def test_no_feature_uses_data_after_cutoff():
    # Each value is its own timestamp in hours, so a feature's value says where it came from.
    hours = (IDX - IDX[0]) / pd.Timedelta(hours=1)
    df = pd.DataFrame({c: hours for c in COLS}, index=IDX)
    X = features.build(df, "actual")
    cut = (features.cutoff(IDX) - IDX[0]) / pd.Timedelta(hours=1)
    lag_cols = [c for c in X if c.startswith(features.TARGETS) or c.endswith("_last_known")]
    assert "dispatchable_ac_last_known" in lag_cols
    for c in lag_cols:
        known = X[c].notna()
        assert (X.loc[known, c] <= cut[known] - 1).all(), c  # hour must start before cutoff


def test_cutoff_is_10am_local_day_before_across_dst():
    ts = pd.DatetimeIndex(["2025-03-09T08:00Z", "2025-11-02T08:00Z"])  # 01:00 MST / 01:00 MDT
    assert list(features.cutoff(ts)) == [pd.Timestamp("2025-03-08T17:00Z"),  # 10:00 MST
                                         pd.Timestamp("2025-11-01T16:00Z")]  # 10:00 MDT


def test_forecast_weather_replaces_actual():
    df = pd.DataFrame({c: np.arange(len(IDX), dtype=float) for c in COLS}, index=IDX)
    df["temp_fc_edmonton"] = -1.0
    assert (features.build(df, "forecast")["temp_edmonton"] == -1).all()
    assert (features.build(df, "actual")["temp_edmonton"] != -1).all()
