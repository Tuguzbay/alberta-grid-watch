"""Phase 0 smoke test: confirm every data source answers with the shape we expect.

Usage: AESO_API_KEY=... python scripts/check_sources.py
"""

import sys

from gridwatch import aeso, weather

checks = {
    "AESO pool price": lambda: aeso.pool_price("2024-01-01", "2024-01-02"),
    "AESO internal load": lambda: aeso.internal_load("2024-01-01", "2024-01-02"),
    "Open-Meteo Edmonton": lambda: weather.history("edmonton", "2024-01-01", "2024-01-01"),
    "Open-Meteo Calgary": lambda: weather.history("calgary", "2024-01-01", "2024-01-01"),
}

failed = False
for name, fn in checks.items():
    try:
        data = fn()
        if isinstance(data, list):
            n, sample = len(data), data[0]
        else:
            n, sample = len(data["time"]), {k: v[:2] for k, v in data.items()}
        print(f"OK   {name}: {n} rows; sample={sample}")
    except Exception as e:  # report every source, don't stop at the first failure
        failed = True
        print(f"FAIL {name}: {e!r}")
sys.exit(failed)
