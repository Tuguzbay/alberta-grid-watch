"""Model-health summary: rolling errors, model-vs-baseline alerts, data freshness."""

import pandas as pd

MIN_LIVE_DAYS = 14  # until live has this many scored days, show the backtest instead
ALERT_DAYS = 14
STALE_HOURS = 36


def _mae(fc: pd.DataFrame) -> dict:
    """{target: {model: MAE}} over scored rows."""
    s = fc.dropna(subset=["actual", "value"])
    m = (s["value"] - s["actual"]).abs().groupby([s["target"], s["model"]]).mean()
    return {t: g.droplevel(0).round(2).to_dict() for t, g in m.groupby(level=0)}


def summary(fc: pd.DataFrame, last_actual: pd.Timestamp, now: pd.Timestamp) -> dict:
    """fc: rows from db.forecast_frame. last_actual: latest hour with a settled pool price."""
    scored = fc.dropna(subset=["actual"])
    live_days = scored.loc[scored["source"] == "live", "issue_date"].nunique()
    source = "live" if live_days >= MIN_LIVE_DAYS else "backtest"
    use = scored[scored["source"] == source]
    end = use["ts_utc"].max() if len(use) else now

    def window(days):
        return use[use["ts_utc"] > end - pd.Timedelta(days=days)]

    alerts = []
    for target, maes in _mae(window(ALERT_DAYS)).items():
        best = min((v, k) for k, v in maes.items() if k != "hgb")
        if "hgb" in maes and maes["hgb"] > best[0]:
            alerts.append(f"{target}: model MAE {maes['hgb']:.1f} is worse than "
                          f"{best[1]} ({best[0]:.1f}) over the last {ALERT_DAYS} days")

    live = fc[fc["source"] == "live"]
    last_issue = live["issue_date"].max() if len(live) else None
    tomorrow = live[live["issue_date"] == last_issue] if last_issue else live.iloc[0:0]
    # Most recent forecast day with at least one settled hour.
    recent = use[use["issue_date"] == use["issue_date"].max()] if len(use) else use

    stale = []
    if now - last_actual > pd.Timedelta(hours=STALE_HOURS):
        stale.append(f"no new settled prices since {last_actual:%Y-%m-%d %H:%M} UTC")
    if last_issue is None or now.date() - last_issue > pd.Timedelta(hours=STALE_HOURS):
        stale.append(f"no live forecast issued since {last_issue or 'ever'}")

    return {
        "source": source, "live_days_scored": int(live_days),
        "mae_7d": _mae(window(7)), "mae_30d": _mae(window(30)),
        "alerts": alerts, "stale": stale,
        "last_actual_utc": last_actual.isoformat(),
        "last_issue_date": str(last_issue) if last_issue else None,
        "next_day": _series(tomorrow), "last_scored_day": _series(recent, with_actual=True),
    }


def _series(fc: pd.DataFrame, with_actual: bool = False) -> dict:
    """{target: {"ts": [...], model: [...], "actual": [...]}} for charts."""
    out = {}
    for target, g in fc.groupby("target"):
        wide = g.pivot_table(index="ts_utc", columns="model", values="value").sort_index()
        d = {"ts": [t.isoformat() for t in wide.index]}
        d |= {m: [None if pd.isna(v) else round(v, 1) for v in wide[m]] for m in wide}
        if with_actual:
            a = g.drop_duplicates("ts_utc").set_index("ts_utc")["actual"].reindex(wide.index)
            d["actual"] = [None if pd.isna(v) else round(v, 1) for v in a]
        out[target] = d
    return out
