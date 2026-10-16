"""Load hourly data into Postgres, then print the quality report.

Backfill: python scripts/ingest.py --start 2020-01-01
Daily:    python scripts/ingest.py            (re-fetches the last 7 days to pick up revisions)
Needs AESO_API_KEY and DATABASE_URL.
"""

import argparse
from datetime import date, timedelta
from pprint import pprint

from gridwatch import db, ingest, quality

p = argparse.ArgumentParser()
p.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=7))
p.add_argument("--end", type=date.fromisoformat, default=date.today())
args = p.parse_args()

with db.connect() as conn:
    ingest.ingest(conn, args.start, args.end)
    r = quality.report(conn)
    print(f"{r.pop('rows')} rows, {r['first']} .. {r['last']}, "
          f"{len(r['missing_hours'])} missing hours")
    pprint({**r, "missing_hours": r["missing_hours"][:20]})
