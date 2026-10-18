import csv
from pathlib import Path

import pandas as pd
import pytest

from gridwatch import claims, impacts

NOW = pd.Timestamp("2026-10-16 18:00", tz="UTC")


def frame(end="2026-10-16 17:00", headroom=500.0, tight=()):
    """Hourly frame from 2024: constant headroom, except `tight` (start, hours) spans at -100."""
    idx = pd.date_range("2024-01-01", end, freq="h", tz="UTC")
    h = pd.Series(headroom, index=idx)
    for start, hours in tight:
        i = h.index.get_loc(pd.Timestamp(start, tz="UTC"))
        h.iloc[i:i + hours] = -100.0
    load = pd.Series(10_000.0, index=idx)
    return pd.DataFrame({"pool_price": 50.0, "load_mw": load, "dispatchable_ac": load + h})


def strings(card):
    return [v for v in card.values() if isinstance(v, str)] + list(card["how"])


def test_scale_record_from_data():
    df = frame()
    df.loc[pd.Timestamp("2025-12-11 00:00", tz="UTC"), "load_mw"] = 12_785.0
    s = claims.scale(df)
    assert s["record_mw"] == 12_785.0
    assert (s["meta_mw"], s["edmonton_mw"], s["requested_mw"]) == (970, 1400, 19565)


def test_reliability_verdict_rises():
    df = frame(tight=[("2025-02-01", 10), ("2026-02-01", 100)])
    card = claims.reliability_card(df, NOW)
    assert card["verdict"] == "Getting tighter"
    assert "100 tight hours in 2026 so far" in card["headline"]


def test_reliability_verdict_zero_tight_hours():
    card = claims.reliability_card(frame(), NOW)
    assert card["verdict"] == "Not so far"
    assert card["headline"] == "0 tight hours in 2026 so far"
    assert not any(bad in s for s in strings(card) for bad in ("nan", "inf"))


def test_reliability_card_on_stale_frame():
    out = claims.cards(frame(end="2026-10-10 00:00"), NOW)
    assert out["stale"] is True
    assert [c["id"] for c in out["cards"]] == ["reliability", "bills", "emissions", "water"]
    assert claims.cards(frame(), NOW)["stale"] is False


def test_bills_card_without_denominator(monkeypatch):
    monkeypatch.setitem(claims.FACTS["transmission_rr"], "value", None)
    assert claims.bills_card(frame(), NOW)["verdict"] == "Can't verify yet"


@pytest.mark.parametrize("rr, verdict", [(2e9, "Plausible"), (5e9, "Partly true"),
                                         (1e10, "Overstated")])
def test_bills_verdict_thresholds(monkeypatch, rr, verdict):
    monkeypatch.setitem(claims.FACTS["transmission_rr"], "value", rr)
    assert claims.bills_card(frame(), NOW)["verdict"] == verdict


def test_emissions_card_matches_footprint():
    card = claims.emissions_card()
    assert f"{impacts.footprint(970)['co2_mt']:.1f}" in card["headline"]
    assert card["verdict"] == "Significant"


def test_every_card_has_sources_and_how():
    path = Path(__file__).parents[1] / "rag" / "sources.csv"
    keys = {r["key"] for r in csv.DictReader(open(path, encoding="utf-8"))}
    for card in claims.cards(frame(), NOW)["cards"]:
        assert card["sources"] and card["how"], card["id"]
        assert set(card["sources"]) <= keys, card["id"]
    assert {f["source"] for f in claims.FACTS.values()} <= keys


def test_reliability_change_condition_matches_verdict():
    tighter = claims.reliability_card(frame(tight=[("2026-02-01", 100)]), NOW)
    assert "fall back to last year's pace" in tighter["explain"]
    assert "rise above" in claims.reliability_card(frame(), NOW)["explain"]
