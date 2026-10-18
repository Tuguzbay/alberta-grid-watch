"""Cards for the "Meta in Alberta: claims vs data" page: numbers, chart series and verdicts.

Verdicts come from fixed rules over the numbers below, never from a model. Every fixed fact
carries a rag/sources.csv key so the page can link the document it came from. All outputs are
JSON-safe (str, int, float, None, list, dict).
"""

import math

import pandas as pd

from gridwatch import cushion, health, impacts
from gridwatch.features import TZ

META_MW = 970

FACTS = {
    "meta_mw": {"value": META_MW, "label": "Meta campus grid draw (MW)", "source": "goa_bills"},
    "edmonton_mw": {"value": 1400, "label": "City of Edmonton load (MW)",
                    "source": "aeso_factsheet"},
    "requested_mw": {"value": 19565, "label": "Data-centre load requested (MW, as of 2026-07-30)",
                     "source": "goa_grid"},
    "meta_transmission_fees": {"value": 200e6, "label": "Meta transmission fees per year ($)",
                               "source": "goa_bills"},
    "claimed_transmission_cut": {"value": 0.06,
                                 "label": "Claimed cut to household transmission costs",
                                 "source": "goa_bills"},
    "transmission_rr": {"value": 2636.9e6,
                        "label": "AESO 2026 transmission revenue requirement ($)",
                        "source": "aeso_tariff_rr"},
}


def _num(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def _local(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_convert(TZ)


def scale(df: pd.DataFrame) -> dict:
    load = df["load_mw"].dropna()
    return {"meta_mw": META_MW, "edmonton_mw": FACTS["edmonton_mw"]["value"],
            "requested_mw": FACTS["requested_mw"]["value"], "record_mw": float(load.max()),
            "record_ts_local": _local(load.idxmax()).strftime("%Y-%m-%d %H:%M")}


def reliability_card(df: pd.DataFrame, now: pd.Timestamp) -> dict:
    h = cushion.headroom(df)
    loc = _local(now)
    # Slice bounds in UTC: the index is UTC, and mixed offsets can't be compared.
    this_start = pd.Timestamp(loc.year, 1, 1, tz=TZ).tz_convert("UTC")
    last_start = pd.Timestamp(loc.year - 1, 1, 1, tz=TZ).tz_convert("UTC")
    n_this = int((h[this_start:now] < 0).sum())
    n_last = int((h[last_start:last_start + (now - this_start)] < 0).sum())
    year_ago = now - pd.Timedelta(days=365)
    sc = cushion.scenario(h[year_ago:now], df["pool_price"][year_ago:now], META_MW)
    calm = n_this <= n_last
    daily = h.tz_convert(TZ).groupby(h.index.tz_convert(TZ).date).min().iloc[-90:]
    return {
        "id": "reliability",
        "question": "Will it cause blackouts?",
        "headline": f"{n_this:,} tight hours in {loc.year} so far",
        "verdict": "Not so far" if calm else "Getting tighter",
        "explain": (f"A tight hour is one with no spare gas, hydro or storage capacity left after "
                    f"meeting demand. Alberta had {n_this:,} this year, against {n_last:,} by "
                    f"this date last year. If {META_MW} MW ran with no new supply, tight hours "
                    f"would go from {sc['hours_below_zero_today']:,} to "
                    f"{sc['hours_headroom_below_zero']:,} a year. This verdict would change if "
                    f"tight hours {'rise above' if calm else 'fall back to'} last year's pace."),
        "chart": {"type": "line", "labels": [str(d) for d in daily.index],
                  "series": {"Lowest spare capacity that day (MW)":
                             [_num(v) for v in daily.values]}},
        "how": [
            "Spare capacity = available dispatchable capability (gas, hydro, storage, other, "
            "after outages) minus Alberta Internal Load, hour by hour, from AESO data.",
            "Wind, solar and imports aren't counted, so the real cushion is larger than shown.",
            "Meta is building its own gas plant next to the campus, which is meant to cover its "
            "load. The what-if assumes it doesn't, so it's a worst case.",
            "More tight hours doesn't by itself mean data centres caused them: weather, plant "
            "outages and overall demand growth move this number too.",
            "Tight hours are a warning sign, not blackouts: AESO has emergency steps first, and "
            "the government says large loads are cut before homes.",
        ],
        "sources": ["goa_grid", "goa_bills"],
    }


def bills_card(df: pd.DataFrame, now: pd.Timestamp) -> dict:
    p = df["pool_price"]
    yr = pd.Timedelta(days=365)
    cur, prev = p[now - yr:now].mean(), p[now - 2 * yr:now - yr].mean()
    headline = f"${cur:,.0f}/MWh over the last year"
    if prev and not math.isnan(prev) and not math.isnan(cur):
        change = cur / prev - 1
        headline += f", {'up' if change >= 0 else 'down'} {abs(change):.0%} on the year before"
    rr = FACTS["transmission_rr"]["value"]
    fees = FACTS["meta_transmission_fees"]["value"]
    if rr is None:
        verdict = "Can't verify yet"
        check = ("We couldn't find AESO's total transmission cost in a public source we could "
                 "check, so the 6% claim can't be tested yet.")
    else:
        share = fees / rr
        verdict = "Plausible" if share >= 0.06 else "Overstated" if share < 0.03 else "Partly true"
        check = (f"The government says Meta's ~${fees / 1e6:,.0f}M a year in transmission fees "
                 f"will cut the transmission part of household bills by up to 6%. That's "
                 f"{share:.1%} of AESO's ${rr / 1e9:,.2f}B transmission cost for 2026, so a cut "
                 f"of that size is {verdict.lower()}. It's an upper bound: total transmission "
                 f"costs also grow, partly to connect new loads.")
    monthly = p.tz_convert(TZ).groupby(p.index.tz_convert(TZ).strftime("%Y-%m")).mean()
    monthly = monthly[monthly.index >= "2020-01"]
    return {
        "id": "bills",
        "question": "Will my power bill go up?",
        "headline": headline,
        "verdict": verdict,
        "explain": check + " This verdict would change if the fee or cost figures are revised.",
        "chart": {"type": "bar", "labels": list(monthly.index),
                  "series": {"Average pool price ($/MWh)": [_num(v) for v in monthly.values]}},
        "how": [
            "Pool price is the wholesale price, from AESO data. Most households are on "
            "fixed-rate or regulated plans, so it isn't your bill.",
            "The 6% claim is only about the transmission line on your bill, not the whole bill.",
            "The $200M figure is the government's. We haven't checked it independently.",
        ],
        "sources": ["goa_bills"] + ([FACTS["transmission_rr"]["source"]] if rr else []),
    }


def emissions_card() -> dict:
    f = impacts.footprint(META_MW)
    share = f["share_of_ab_electricity_co2"]
    return {
        "id": "emissions",
        "question": "Is it bad for emissions?",
        "headline": f"{f['co2_mt']:.1f} Mt CO₂ a year",
        "verdict": "Significant" if share >= 0.10 else "Noticeable" if share >= 0.03 else "Small",
        "explain": (f"If all {META_MW} MW ran around the clock on new gas, it would emit about "
                    f"{f['co2_mt']:.1f} million tonnes of CO₂ a year, {share:.0%} of what "
                    f"Alberta's power sector emitted in 2023. This verdict would change if the "
                    f"campus runs below full power or buys wind and solar."),
        "chart": None,
        "how": [
            "Assumes the load runs flat all year: an upper bound on energy.",
            "Assumes Alberta's best gas plants (0.37 t/MWh): a lower bound on emissions.",
            *(f"{k}: {v}" for k, v in impacts.SOURCES.items()),
        ],
        "sources": ["goa_bills"],
    }


def water_card() -> dict:
    f = impacts.footprint(META_MW)
    lo, hi = f["water_bl_cooling tower"]
    dlo, dhi = f["water_bl_dry cooling"]
    plo, phi = f["people_equiv_cooling tower"]
    return {
        "id": "water",
        "question": "Will it drain our water?",
        "headline": f"{lo:.1f}–{hi:.1f} billion litres a year",
        "verdict": "Depends on the plant's cooling",
        "explain": (f"A gas plant powering {META_MW} MW with cooling towers would use "
                    f"{lo:.1f}–{hi:.1f} billion litres a year, about what {round(plo, -3):,.0f}–"
                    f"{round(phi, -3):,.0f} "
                    f"Albertans use. With dry cooling it's {dlo:.2f}–{dhi:.2f} billion. The "
                    f"government's 'less than a golf course' claim is about the data centre "
                    f"itself, not its power plant. This verdict would change once the plant's "
                    f"cooling design and water licence are public."),
        "chart": None,
        "how": [
            "Water here is the gas plant's cooling use only. The data centre's own cooling is "
            "separate and the government says it is closed-loop.",
            "Uses NREL's range for combined-cycle gas plants, scaled to a flat 970 MW load.",
            *(f"{k}: {v}" for k, v in impacts.SOURCES.items() if "Water" in k or "L/" in k),
        ],
        "sources": ["goa_water", "goa_bills"],
    }


def cards(df: pd.DataFrame, now: pd.Timestamp) -> dict:
    last = df["pool_price"].dropna().index.max()
    return {
        "scale": scale(df),
        "cards": [reliability_card(df, now), bills_card(df, now), emissions_card(),
                  water_card()],
        "as_of_utc": last.isoformat(),
        "stale": bool(now - last > pd.Timedelta(hours=health.STALE_HOURS)),
    }
