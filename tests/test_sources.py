import httpx
import pytest

from gridwatch import aeso, weather


def _fake_get(payload, seen):
    def get(url, params=None, headers=None, timeout=None):
        seen.update(url=url, params=params, headers=headers)
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    return get


def test_pool_price_sends_key_and_unwraps(monkeypatch):
    seen = {}
    rec = {"begin_datetime_utc": "2024-01-01 07:00", "pool_price": "45.67"}
    monkeypatch.setenv("AESO_API_KEY", "k")
    monkeypatch.setattr(httpx, "get", _fake_get({"return": {"Pool Price Report": [rec]}}, seen))
    assert aeso.pool_price("2024-01-01", "2024-01-02") == [rec]
    assert seen["headers"] == {"API-KEY": "k"}
    assert seen["params"] == {"startDate": "2024-01-01", "endDate": "2024-01-02"}


def test_aeso_http_error_raises(monkeypatch):
    monkeypatch.setenv("AESO_API_KEY", "bad")
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Response(
        401, request=httpx.Request("GET", url)))
    with pytest.raises(httpx.HTTPStatusError):
        aeso.internal_load("2024-01-01", "2024-01-02")


def test_weather_history_uses_city_coords(monkeypatch):
    seen = {}
    monkeypatch.setattr(httpx, "get", _fake_get({"hourly": {"time": ["2024-01-01T00:00"]}}, seen))
    assert weather.history("calgary", "2024-01-01", "2024-01-01") == {"time": ["2024-01-01T00:00"]}
    assert (seen["params"]["latitude"], seen["params"]["longitude"]) == weather.CITIES["calgary"]


@pytest.mark.live
def test_live_pool_price():
    rows = aeso.pool_price("2024-01-01", "2024-01-01")
    assert len(rows) == 24 and {"begin_datetime_utc", "pool_price"} <= rows[0].keys()
