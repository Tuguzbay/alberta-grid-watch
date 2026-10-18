"""Download every document in rag/sources.csv, chunk, embed and store it.

Run: python scripts/rag_ingest.py [--force]   (needs DATABASE_URL). Unchanged documents are
skipped unless --force (use it after changing chunking or the model); documents removed from
the CSV are deleted. Raw files are kept in data/rag/. The daily claim watch runs this too.
"""

import csv
import sys
from pathlib import Path

from gridwatch import db, rag

root = Path(__file__).parents[1]
sources = list(csv.DictReader(open(root / "rag" / "sources.csv", encoding="utf-8")))

with db.connect() as conn:
    changed = rag.ingest_all(conn, sources, root / "data" / "rag", force="--force" in sys.argv)
    total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
print(f"{len(sources)} sources, {total} chunks in db, changed: {', '.join(changed) or 'none'}")
