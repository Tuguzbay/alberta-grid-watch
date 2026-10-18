"""Build the static site: the claims page, the model-health page, the card data, a snapshot."""

import csv
import json
from pathlib import Path

import pandas as pd
import psycopg

from gridwatch import api, claims, claims_page, db, page, watch
from gridwatch.features import TZ

SOURCES_CSV = Path(__file__).parents[2] / "rag" / "sources.csv"
HIDDEN_CLAIMS = Path(__file__).parents[2] / "rag" / "hidden_claims.txt"


def sources(path: Path = SOURCES_CSV) -> dict[str, dict]:
    return {r["key"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def hidden_ids(path: Path = HIDDEN_CLAIMS) -> set[str]:
    """Claim ids to keep off the page: one per line, # comments and blank lines ignored."""
    if not path.exists():
        return set()
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return {line for line in lines if line and not line.startswith("#")}


def watch_data(conn: psycopg.Connection, now: pd.Timestamp, hidden: set[str]) -> dict:
    month, week = now - pd.Timedelta(days=30), now - pd.Timedelta(days=7)
    recent = watch.recent_claims(conn, month.to_pydatetime(), hidden)
    this_week = watch.recent_claims(conn, week.to_pydatetime(), hidden)
    per_card: dict[str, list] = {}
    for c in recent:
        card = watch.CARD_FOR_TOPIC.get(c["topic"])
        if card and len(per_card.setdefault(card, [])) < 3:
            per_card[card].append(c)
    return {"claims": recent, "week_count": len(this_week),
            "week_sources": len({c["url"] for c in this_week}), "per_card": per_card,
            "changed_sources": watch.changed_sources(conn, month.date())}


def build(conn: psycopg.Connection, out: Path, snapshots: Path, now: pd.Timestamp,
          hidden_file: Path = HIDDEN_CLAIMS) -> dict:
    """Write out/{index,health}.html and out/data.json, plus snapshots/<local date>.json."""
    data = claims.cards(db.hourly_frame(conn), now)
    data["watch"] = watch_data(conn, now, hidden_ids(hidden_file))
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
