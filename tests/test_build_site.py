import json

import pandas as pd

from gridwatch import db, site

NOW = pd.Timestamp("2026-10-16 18:00", tz="UTC")


def test_build_writes_all_files(conn, tmp_path):
    idx = pd.date_range(NOW - pd.Timedelta(days=400), NOW, freq="h")
    db.upsert(conn, [{"ts_utc": t, "pool_price": 40.0 + t.hour, "load_mw": 10_000.0,
                      "dispatchable_ac": 10_500.0 - 50 * (t.hour % 12)} for t in idx])
    out, snaps = tmp_path / "site", tmp_path / "snapshots"
    data = site.build(conn, out, snaps, NOW)
    assert {p.name for p in out.iterdir()} == {"index.html", "health.html", "data.json"}
    assert len(json.loads((out / "data.json").read_text(encoding="utf-8"))["cards"]) == 4
    snap = json.loads((snaps / "2026-10-16.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in snap["cards"]] == [c["id"] for c in data["cards"]]
    assert "chart" not in json.dumps(snap)
