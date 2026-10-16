"""Hourly weather from Open-Meteo (free, no key, non-commercial use, <10k calls/day)."""

import httpx

CITIES = {"edmonton": (53.5461, -113.4938), "calgary": (51.0447, -114.0719)}
VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,cloud_cover"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def history(city: str, start: str, end: str) -> dict:
    """Reanalysis archive (lags real time by a few days).

    Returns {"time": [...], var: [...]} in UTC."""
    lat, lon = CITIES[city]
    r = httpx.get(
        ARCHIVE_URL,
        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                "hourly": VARIABLES, "timezone": "UTC"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["hourly"]
