"""Hourly weather from Open-Meteo (free, no key, non-commercial use, <10k calls/day)."""

import httpx

# Load centres + the two southern wind/solar clusters (Fort Macleod, Medicine Hat).
CITIES = {"edmonton": (53.5461, -113.4938), "calgary": (51.0447, -114.0719),
          "southwest": (49.72, -113.40), "southeast": (50.04, -110.68)}
VARIABLES = ("temperature_2m,relative_humidity_2m,wind_speed_10m,cloud_cover,"
             "wind_speed_100m,shortwave_radiation")
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
DAY_AHEAD = "_previous_day2"  # issued ~48 h before valid time, so always before a D-1 10:00 cutoff


def _hourly(url: str, city: str, start: str, end: str, hourly: str) -> dict:
    lat, lon = CITIES[city]
    r = httpx.get(
        url,
        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                "hourly": hourly, "timezone": "UTC"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["hourly"]


def history(city: str, start: str, end: str) -> dict:
    """Reanalysis archive (lags real time by a few days).

    Returns {"time": [...], var: [...]} in UTC."""
    return _hourly(ARCHIVE_URL, city, start, end, VARIABLES)


def day_ahead(city: str, start: str, end: str) -> dict:
    """Forecasts as issued ~2 days before each hour (data from 2024; earlier hours are null).

    Same shape and keys as history()."""
    h = _hourly(PREVIOUS_RUNS_URL, city, start, end,
                ",".join(v + DAY_AHEAD for v in VARIABLES.split(",")))
    return {k.removesuffix(DAY_AHEAD): v for k, v in h.items()}
