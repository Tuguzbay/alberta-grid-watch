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


def test_build_excludes_hidden_claims(conn, tmp_path):
    from gridwatch import watch

    test_build_writes_all_files(conn, tmp_path)  # fills hourly
    claim = watch.ExtractedClaim(claim="c", speaker="s", quote="q " * 10, topic="bills",
                                 numbers=[])
    for url in ("https://a.ca/1", "https://a.ca/2"):
        watch.save_article(conn, url, "T", "CBC", NOW.date(), "ok", "news")
        watch.save_claims(conn, url, [claim])
    hidden = tmp_path / "hidden.txt"
    hidden.write_text(f"# comment\n{watch.claim_id('https://a.ca/1', claim.quote)}\n\n")
    data = site.build(conn, tmp_path / "s2", tmp_path / "n2", pd.Timestamp.now(tz="UTC"),
                      hidden_file=hidden)
    urls = [c["url"] for c in data["watch"]["claims"]]
    assert urls == ["https://a.ca/2"] and data["watch"]["per_card"]["bills"][0]["url"] == urls[0]
