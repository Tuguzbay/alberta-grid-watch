"""Dispatchable headroom vs pool price, and what a flat added load would do to it.

headroom = available dispatchable capability (gas, hydro, storage, other, after outages)
           - Alberta Internal Load.
Wind, solar and imports are not counted, so true supply cushion is larger than this.
Illustrative only: an empirical price-vs-headroom curve, not a market model.
"""

import pandas as pd

# Public reference points, not any one project: AESO interim large-load allocation (1,200 MW)
# and the bridging allowance to draw from the grid while own generation is built (1,600 MW).
SCENARIOS = {500: "smaller reference point", 1200: "AESO interim large-load allocation",
             1600: "bridging allowance from the grid"}
BIN_MW = 250
SPIKE = 200  # $/MWh


def headroom(df: pd.DataFrame) -> pd.Series:
    return (df["dispatchable_ac"] - df["load_mw"]).rename("headroom_mw")


def curve(h: pd.Series, price: pd.Series, bin_mw: int = BIN_MW) -> pd.DataFrame:
    """Mean price and spike share per headroom bin (bins labelled by lower edge)."""
    ok = h.notna() & price.notna()
    b = (h[ok] // bin_mw * bin_mw).astype(int)
    p = price[ok]
    return pd.DataFrame({"hours": p.groupby(b).size(), "mean_price": p.groupby(b).mean(),
                         "spike_share": (p > SPIKE).groupby(b).mean()})


def scenario(h: pd.Series, price: pd.Series, added_mw: float, min_hours: int = 20) -> dict:
    """Shift every hour's headroom down by added_mw and read prices off the empirical curve.

    Bins with fewer than min_hours observations are unreliable, so hours that land in (or below)
    them are counted as `beyond_observed` and priced at the lowest reliable bin (an underestimate).
    """
    c = curve(h, price)
    reliable = c[c["hours"] >= min_hours]
    lo = reliable.index.min()
    ok = h.notna() & price.notna()
    h = h[ok]

    def lookup(x: pd.Series) -> pd.DataFrame:
        bins = (x // BIN_MW * BIN_MW).clip(lower=lo).astype(int)
        # Nearest reliable bin for gaps inside the range.
        return reliable.iloc[reliable.index.get_indexer(bins, method="nearest")]

    shifted = h - added_mw
    base, new = lookup(h), lookup(shifted)
    return {
        "added_mw": added_mw,
        "hours": len(h),
        "hours_headroom_below_zero": int((shifted < 0).sum()),
        "hours_below_zero_today": int((h < 0).sum()),
        "beyond_observed": int((shifted < lo).sum()),
        "curve_mean_price_base": float(base["mean_price"].mean()),
        "curve_mean_price_new": float(new["mean_price"].mean()),
        "expected_spike_hours_base": float(base["spike_share"].sum()),
        "expected_spike_hours_new": float(new["spike_share"].sum()),
    }
