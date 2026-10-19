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
    assert card["verdict"] == "Less backup than last year"
    assert card["headline"].startswith("100 hours in 2026 when gas, hydro and storage")


def test_reliability_verdict_zero_tight_hours():
    card = claims.reliability_card(frame(), NOW)
    assert card["verdict"] == "No sign of strain"
    assert card["headline"].startswith("0 hours in 2026 when")
    assert not any(bad in s for s in strings(card) for bad in ("nan", "inf"))


def test_reliability_card_on_stale_frame():
    out = claims.cards(frame(end="2026-10-10 00:00"), NOW)
    assert out["stale"] is True
    assert [c["id"] for c in out["cards"]] == ["reliability", "bills", "emissions", "water"]
    assert claims.cards(frame(), NOW)["stale"] is False


def test_bills_card_without_denominator(monkeypatch):
    monkeypatch.setitem(claims.FACTS["transmission_rr"], "value", None)
    assert claims.bills_card(frame(), NOW)["verdict"] == "Can't check the 6% cut yet"


@pytest.mark.parametrize("rr, verdict", [(2e9, "The promised 6% cut adds up"),
                                         (5e9, "Only part of the 6% cut adds up"),
                                         (1e10, "The 6% cut doesn't add up")])
def test_bills_verdict_thresholds(monkeypatch, rr, verdict):
    monkeypatch.setitem(claims.FACTS["transmission_rr"], "value", rr)
    assert claims.bills_card(frame(), NOW)["verdict"] == verdict


def test_dts_estimate_for_meta():
    low, high = claims.dts_estimate(970)
    assert high == pytest.approx(197.7e6, rel=1e-3)  # flat 970 MW, worked by hand from Rate DTS
    assert 190e6 < low < high


def test_bills_card_cross_checks_the_fee(monkeypatch):
    assert "checks out" in claims.bills_card(frame(), NOW)["explain"]
    monkeypatch.setitem(claims.FACTS["meta_transmission_fees"], "value", 300e6)
    assert "doesn't match" in claims.bills_card(frame(), NOW)["explain"]


def test_emissions_card_matches_footprint():
    card = claims.emissions_card()
    assert f"{impacts.footprint(970)['co2_mt']:.1f}" in card["headline"]
    assert card["verdict"] == "Big: up to 16% of Alberta's power emissions"


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


def test_reliability_card_says_what_it_measures():
    text = claims.reliability_card(frame(tight=[("2026-02-01", 100)]), NOW)["explain"]
    assert "wind, solar or imports" in text and "no spare" not in text


def test_charts_stop_at_now():
    df = frame(end="2026-10-18 23:00")  # hourly also holds stored forecasts past now
    for card in claims.cards(df, NOW)["cards"]:
        if card["chart"]:
            assert card["chart"]["labels"][-1] <= "2026-10-16", card["id"]
            values = next(iter(card["chart"]["series"].values()))
            assert values and None not in values, card["id"]


def test_emissions_headline_is_conditional():
    assert claims.emissions_card()["headline"].startswith("Phase 1: up to ")


def test_scale_reports_history_start():
    assert claims.scale(frame())["history_from"] == 2024


def test_bills_skips_year_on_year_without_a_full_year_before():
    df = frame()
    assert "on the year before" in claims.bills_card(df, NOW)["headline"]
    short = df["2025-06-01":]
    assert "on the year before" not in claims.bills_card(short, NOW)["headline"]


def test_stale_when_load_stops_updating():
    df = frame()
    df.loc["2026-10-14":, "load_mw"] = float("nan")
    assert claims.cards(df, NOW)["stale"] and not claims.cards(frame(), NOW)["stale"]
