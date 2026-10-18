"""Build the static site: the claims page, the model-health page, the card data, a snapshot."""

import csv
import json
from pathlib import Path

import pandas as pd
import psycopg

from gridwatch import api, claims, claims_page, db, page
from gridwatch.features import TZ

SOURCES_CSV = Path(__file__).parents[2] / "rag" / "sources.csv"


def sources(path: Path = SOURCES_CSV) -> dict[str, dict]:
    return {r["key"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def build(conn: psycopg.Connection, out: Path, snapshots: Path, now: pd.Timestamp) -> dict:
    """Write out/{index,health}.html and out/data.json, plus snapshots/<local date>.json."""
    data = claims.cards(db.hourly_frame(conn), now)
    out.mkdir(parents=True, exist_ok=True)
    snapshots.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(claims_page.render(data, sources()), encoding="utf-8")
    (out / "health.html").write_text(page.render(api.load_summary(conn, now)), encoding="utf-8")
    (out / "data.json").write_text(json.dumps(data), encoding="utf-8")
    snap = {"as_of_utc": data["as_of_utc"], "scale": data["scale"],
            "cards": [{k: c[k] for k in ("id", "headline", "verdict")} for c in data["cards"]]}
    day = now.tz_convert(TZ).strftime("%Y-%m-%d")
    (snapshots / f"{day}.json").write_text(json.dumps(snap, indent=1) + "\n", encoding="utf-8")
    return data
