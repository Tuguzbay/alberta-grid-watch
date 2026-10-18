"""Build the static site into site/ and today's snapshot into snapshots/.

Run: python scripts/build_site.py   (needs DATABASE_URL). Open site/index.html to check it.
"""

import sys
from pathlib import Path

import pandas as pd

from gridwatch import db, site

sys.stdout.reconfigure(encoding="utf-8")  # headlines contain CO₂; Windows consoles are cp1251
root = Path(__file__).parents[1]
with db.connect() as conn:
    data = site.build(conn, root / "site", root / "snapshots", pd.Timestamp.now(tz="UTC"))
for c in data["cards"]:
    print(f"{c['id']:12} {c['verdict']:30} {c['headline']}")
print(f"as of {data['as_of_utc']}{'  STALE' if data['stale'] else ''}")
