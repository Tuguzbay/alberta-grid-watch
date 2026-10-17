import numpy as np
import pandas as pd

from gridwatch import cushion

IDX = pd.date_range("2025-01-01", periods=4000, freq="h", tz="UTC")


def synthetic():
    # Headroom sweeps 0..4000 MW; price falls linearly with headroom, spikes below 500 MW.
    h = pd.Series(np.linspace(0, 4000, len(IDX)), index=IDX)
    price = 300 - h * 0.07
    return h, price


def test_headroom_is_dispatchable_minus_load():
    df = pd.DataFrame({"dispatchable_ac": [9000.0], "load_mw": [10000.0]})
    assert cushion.headroom(df).tolist() == [-1000.0]


def test_curve_bins_by_lower_edge():
    h, price = synthetic()
    c = cushion.curve(h, price, bin_mw=1000)
    assert list(c.index) == [0, 1000, 2000, 3000, 4000]
    assert c["mean_price"].is_monotonic_decreasing
    assert c.loc[0, "spike_share"] > 0 and c.loc[3000, "spike_share"] == 0


def test_scenario_raises_price_and_counts_hours_below_zero():
    h, price = synthetic()
    none, big = cushion.scenario(h, price, 0), cushion.scenario(h, price, 1000)
    assert none["curve_mean_price_new"] == none["curve_mean_price_base"]
    assert big["curve_mean_price_new"] > big["curve_mean_price_base"]
    assert big["expected_spike_hours_new"] > big["expected_spike_hours_base"]
    assert big["hours_headroom_below_zero"] == (h < 1000).sum()
    assert big["beyond_observed"] == (h - 1000 < 0).sum()  # nothing was observed below 0 MW
