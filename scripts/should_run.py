"""Daily-job guard for GitHub Actions: prints run=true|false to $GITHUB_OUTPUT.

Run: python scripts/should_run.py [--manual]   (needs DATABASE_URL).
"""

import os
import sys

import pandas as pd

from gridwatch import db, schedule

now = pd.Timestamp.now(tz="UTC")
with db.connect() as conn:
    issued = schedule.issued_today(conn, now)
run = schedule.should_run(now, issued, manual="--manual" in sys.argv)
print(f"now {now:%Y-%m-%d %H:%M} UTC, issued today: {issued}, run: {run}")
with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
    f.write(f"run={'true' if run else 'false'}\n")
