from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

from gridwatch import api, features, health

NOW = pd.Timestamp("2026-10-17T16:00Z")


def frame(days, source, hgb_err, base_err, start="2026-10-01"):
    """`days` of hourly load forecasts: actual 10,000 MW, models off by fixed amounts."""
    ts = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    issue = (features.local_day(ts) - pd.Timedelta(days=1)).date
    rows = []
    for model, err in (("hgb", hgb_err), ("last_week", base_err)):
        rows.append(pd.DataFrame({"ts_utc": ts, "target": "load_mw", "model": model,
                                  "issue_date": issue,
                                  "value": 10000.0 + err, "source": source, "actual": 10000.0}))
    return pd.concat(rows, ignore_index=True)


def test_alert_fires_when_model_loses_to_baseline_for_14_days():
    s = health.summary(frame(15, "live", hgb_err=300, base_err=100), NOW - pd.Timedelta(hours=2),
                       NOW)
    assert s["source"] == "live"
    assert s["alerts"] and "worse than last_week" in s["alerts"][0]
    assert s["mae_7d"]["load_mw"] == {"hgb": 300.0, "last_week": 100.0}


def test_no_alert_when_model_wins_and_backtest_used_until_enough_live_days():
    fc = pd.concat([frame(30, "backtest", 50, 100), frame(3, "live", 999, 0, "2026-10-15T06:00Z")])
    s = health.summary(fc, NOW - pd.Timedelta(hours=2), NOW)
    assert s["source"] == "backtest" and s["live_days_scored"] == 3
    assert s["alerts"] == [] and s["stale"] == []


def test_stale_data_is_flagged():
    s = health.summary(frame(3, "live", 0, 0), NOW - pd.Timedelta(days=3), NOW)
    assert any("no new settled prices" in m for m in s["stale"])


def test_unscored_live_forecast_shows_as_next_day():
    fc = frame(1, "live", 0, 0, "2026-10-18T06:00Z").assign(actual=float("nan"))  # local 10-18
    s = health.summary(fc, NOW, NOW)
    assert s["last_issue_date"] == str(date(2026, 10, 17))
    assert len(s["next_day"]["load_mw"]["hgb"]) == 24


def test_page_and_json_render(monkeypatch):
    s = health.summary(frame(15, "live", 300, 100), NOW, NOW)
    monkeypatch.setattr(api, "load_summary", lambda: s)
    c = TestClient(api.app)
    assert c.get("/api/health").json()["source"] == "live"
    html = c.get("/").text
    assert "model health" in html and "worse than last_week" in html and "<canvas" in html
