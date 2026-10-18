"""Download every document in rag/sources.csv, chunk, embed and store it.

Run: python scripts/rag_ingest.py [--force]   (needs DATABASE_URL). Unchanged documents are
skipped unless --force (use it after changing chunking or the model); documents removed from
the CSV are deleted. Raw files are kept in data/rag/.
"""

import csv
import sys
from pathlib import Path

from gridwatch import db, rag

root = Path(__file__).parents[1]
sources = list(csv.DictReader(open(root / "rag" / "sources.csv", encoding="utf-8")))
raw = root / "data" / "rag"
raw.mkdir(parents=True, exist_ok=True)

with db.connect() as conn:
    conn.execute("DELETE FROM documents WHERE key <> ALL(%s)", ([s["key"] for s in sources],))
    for src in sources:
        try:
            content = rag.fetch(src["url"])
        except Exception as e:  # one dead link shouldn't stop the rest
            print(f"{src['key']:24} FETCH FAILED: {e}")
            continue
        (raw / src["key"]).write_bytes(content)
        n = rag.store(conn, src, content, force="--force" in sys.argv)
        words = sum(len(t.split()) for _, t in rag.pages(content))
        status = "unchanged" if n is None else f"{n} chunks"
        # Few words usually means a JS-rendered page or a soft 404: check by hand.
        check = "  CHECK: little text" if words < 150 else ""
        print(f"{src['key']:24} {words:6} words  {status}{check}")
    total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
print(f"{len(sources)} sources, {total} chunks in db")
