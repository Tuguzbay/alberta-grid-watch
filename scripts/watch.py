"""Daily claim watch: changed official documents and new articles -> verified claims in the DB.

Run: python scripts/watch.py   (needs DATABASE_URL and ANTHROPIC_API_KEY). Without a key it
prints "skipped: no key" and exits 0, so local runs and forks still build the page.
"""

import csv
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("skipped: no key")
    sys.exit(0)

import anthropic  # noqa: E402

from gridwatch import db, watch  # noqa: E402

root = Path(__file__).parents[1]
sources = list(csv.DictReader(open(root / "rag" / "sources.csv", encoding="utf-8")))
with db.connect() as conn:
    summary = watch.run(conn, anthropic.Anthropic(), datetime.now(UTC), sources=sources,
                        raw_dir=root / "data" / "rag")
print(" ".join(f"{k}={v}" for k, v in summary.items()))
