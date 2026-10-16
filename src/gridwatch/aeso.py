"""Thin client for the AESO public API (https://apimgw.aeso.ca/public).

Auth is an `API-KEY` header. Dates are YYYY-MM-DD; records carry
`begin_datetime_utc` and `begin_datetime_mpt`.
"""

import os

import httpx

BASE_URL = "https://apimgw.aeso.ca/public"


def _get(path: str, start: str, end: str) -> dict:
    r = httpx.get(
        f"{BASE_URL}/{path}",
        params={"startDate": start, "endDate": end},
        headers={"API-KEY": os.environ["AESO_API_KEY"]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["return"]


def pool_price(start: str, end: str) -> list[dict]:
    """Hourly pool price ($/MWh). `forecast_pool_price` is AESO's short-horizon
    (~2 h ahead) forecast, not a day-ahead one."""
    return _get("poolprice-api/v1.1/price/poolPrice", start, end)["Pool Price Report"]


def internal_load(start: str, end: str) -> list[dict]:
    """Hourly Alberta Internal Load (MW), actual + AESO day-ahead forecast."""
    return _get("actualforecast-api/v1/load/albertaInternalLoad", start, end)[
        "Actual Forecast Report"
    ]
