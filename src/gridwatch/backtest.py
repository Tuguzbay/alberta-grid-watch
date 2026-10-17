"""Monthly walk-forward backtest: model vs naive baselines for next-day price and load."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from gridwatch import features
from gridwatch.db import WEATHER_COLS

# Baseline name -> feature column suffix. A baseline's forecast is just that feature.
BASELINES = {
    "pool_price": {"last_week": "lag168", "two_days_ago": "lag48", "mean_30d": "mean30"},
    "load_mw": {"last_week": "lag168", "two_days_ago": "lag48"},
}
SPIKE = 200  # $/MWh; price MAE is also reported for hours above this


def run(df: pd.DataFrame, first_month: str) -> pd.DataFrame:
    """Forecast every settled hour from first_month on, retraining at each month start.

    Training uses actual weather; test hours use day-ahead forecast weather only.
    Returns rows: ts_utc, target, model, issue_date, value, actual."""
    Xa, Xf = features.build(df, "actual"), features.build(df, "forecast")
    day = features.local_day(df.index)
    month = day.to_period("M")
    out = []
    for target in features.TARGETS:
        y = df[target]
        for m in pd.period_range(first_month, month[y.notna()].max(), freq="M"):
            train = (day < m.start_time) & y.notna()
            test = (month == m) & y.notna()
            assert Xf.loc[test, WEATHER_COLS].notna().all().all(), f"weather forecast gap in {m}"
            model = HistGradientBoostingRegressor(random_state=0).fit(Xa[train], y[train])
            preds = {"hgb": model.predict(Xf[test])}
            preds |= {name: Xf.loc[test, f"{target}_{col}"].to_numpy()
                      for name, col in BASELINES[target].items()}
            for name, v in preds.items():
                out.append(pd.DataFrame({
                    "ts_utc": df.index[test], "target": target, "model": name,
                    "issue_date": (day[test] - pd.Timedelta(days=1)).date,
                    "value": v, "actual": y[test].to_numpy()}))
    return pd.concat(out, ignore_index=True)


def metrics(fc: pd.DataFrame) -> pd.DataFrame:
    err = fc["value"] - fc["actual"]
    fc = fc.assign(ae=err.abs(), se=err**2, ape=(err / fc["actual"]).abs() * 100,
                   spike_ae=err.abs().where(fc["actual"] > SPIKE))
    m = fc.groupby(["target", "model"]).agg(
        n=("ae", "size"), mae=("ae", "mean"), rmse=("se", "mean"),
        mape=("ape", "mean"), spike_mae=("spike_ae", "mean"))
    m["rmse"] = np.sqrt(m["rmse"])
    m.loc["pool_price", "mape"] = np.nan  # prices touch $0, so % error is meaningless
    m.loc["load_mw", "spike_mae"] = np.nan
    return m.sort_values(["target", "mae"])
