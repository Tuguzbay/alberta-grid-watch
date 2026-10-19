"""Cards for the "Meta in Alberta: claims vs data" page: numbers, chart series and verdicts.

Verdicts come from fixed rules over the numbers below, never from a model. Every fixed fact
carries a rag/sources.csv key so the page can link the document it came from. All outputs are
JSON-safe (str, int, float, None, list, dict).
"""

import math

import pandas as pd

from gridwatch import cushion, health, impacts
from gridwatch.features import TZ

META_MW = 970  # phase 1, AESO-approved grid allocation
META_FULL_MW = 1800  # full build-out, grid plus on-site generation over time

FACTS = {
    "meta_mw": {"value": META_MW, "label": "Meta phase 1 grid draw (MW)", "source": "goa_numbers"},
    "meta_full_mw": {"value": META_FULL_MW,
                     "label": "Meta campus draw at full build-out, grid plus on-site (MW)",
                     "source": "goa_numbers"},
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

# AESO Rate DTS effective 2026-01-01 (source key aeso_rate_dts), in $.
DTS_PER_MW_MONTH = 10_927 + 2_987 + 50  # bulk coincident demand, regional capacity, other support
DTS_PER_MWH = 1.23 + 0.93 + 0.15  # bulk energy, regional energy, voltage control
DTS_POD_MONTH = 15_562  # substation fraction 1
DTS_POD_TIERS = [(7.5, 5_122), (9.5, 3_037), (23, 2_033), (math.inf, 1_252)]  # (MW, $/MW/month)


def dts_estimate(mw: float) -> tuple[float, float]:
    """Yearly Rate DTS connection charge for a load of `mw`, at 80% and 100% load factor.

    Assumes one point of delivery and the full `mw` at every monthly system peak. Excludes the
    operating reserve and constraint charges, which follow the pool price.
    """
    pod, left = DTS_POD_MONTH, mw
    for size, rate in DTS_POD_TIERS:
        pod += min(left, size) * rate
        left -= min(left, size)
    fixed = 12 * (mw * DTS_PER_MW_MONTH + pod)
    return tuple(fixed + mw * 8760 * lf * DTS_PER_MWH for lf in (0.8, 1.0))


def _num(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def _local(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_convert(TZ)


def _first_full_day(index: pd.DatetimeIndex) -> pd.Timestamp:
    first = _local(index.min())
    return first if first == first.normalize() else first.normalize() + pd.Timedelta(days=1)


def scale(df: pd.DataFrame) -> dict:
    load = df["load_mw"].dropna()
    return {"meta_mw": META_MW, "meta_full_mw": META_FULL_MW,
            "edmonton_mw": FACTS["edmonton_mw"]["value"],
            "requested_mw": FACTS["requested_mw"]["value"], "record_mw": float(load.max()),
            "record_ts_local": _local(load.idxmax()).strftime("%Y-%m-%d %H:%M"),
            "history_from": _first_full_day(load.index).year}


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
    # hourly also holds stored forecasts past now; chart only settled history.
    past = h[:now].tz_convert(TZ)
    daily = past.groupby(past.index.date).min().dropna().iloc[-90:]
    return {
        "id": "reliability",
        "question": "Will it cause blackouts?",
        "headline": f"{n_this:,} hours in {loc.year} when gas, hydro and storage alone fell short",
        "verdict": "No sign of strain" if calm else "Less backup than last year",
        "explain": (f"In these hours, available gas, hydro and storage couldn't cover demand on "
                    f"their own, so wind, solar or imports filled the gap. That's a thinner "
                    f"cushion, not a blackout. Alberta had {n_this:,} such hours this year, "
                    f"against {n_last:,} by this date last year. If {META_MW} MW ran with no new "
                    f"supply, they would go from {sc['hours_below_zero_today']:,} to "
                    f"{sc['hours_headroom_below_zero']:,} a year. This verdict would change if "
                    f"they {'rise above' if calm else 'fall back to'} last year's pace."),
        "chart": {"type": "line", "labels": [str(d) for d in daily.index],
                  "series": {"Lowest spare capacity that day (MW)":
                             [_num(v) for v in daily.values]}},
        "how": [
            "Spare capacity = available dispatchable capability (gas, hydro, storage, other, "
            "after outages) minus Alberta Internal Load, hour by hour, from AESO data.",
            "Wind, solar and imports aren't counted as cushion, because they can't be called on "
            "at will. Hours like these are normal on sunny or windy days.",
            "Meta is building its own gas plant next to the campus, which is meant to cover its "
            "load. The what-if assumes it doesn't, so it's a worst case.",
            "More of these hours doesn't by itself mean data centres caused them: weather, plant "
            "outages and overall demand growth move this number too.",
            "They're a warning sign, not blackouts: AESO has emergency steps first, and "
            "the government says large loads are cut before homes.",
        ],
        "sources": ["goa_grid", "goa_numbers"],
    }


def bills_card(df: pd.DataFrame, now: pd.Timestamp) -> dict:
    p = df["pool_price"]
    yr = pd.Timedelta(days=365)
    before = p[now - 2 * yr:now - yr]
    cur, prev = p[now - yr:now].mean(), before.mean()
    headline = f"${cur:,.0f}/MWh over the last year"
    full_year = before.count() >= 0.9 * 365 * 24  # a part-year isn't "the year before"
    if full_year and prev and not math.isnan(prev) and not math.isnan(cur):
        change = cur / prev - 1
        headline += f", {'up' if change >= 0 else 'down'} {abs(change):.0%} on the year before"
    rr = FACTS["transmission_rr"]["value"]
    fees = FACTS["meta_transmission_fees"]["value"]
    if rr is None:
        verdict = "Can't check the 6% cut yet"
        check = ("We couldn't find AESO's total transmission cost in a public source we could "
                 "check, so the 6% claim can't be tested yet.")
    else:
        share = fees / rr
        verdict = ("The promised 6% cut adds up" if share >= 0.06
                   else "The 6% cut doesn't add up" if share < 0.03
                   else "Only part of the 6% cut adds up")
        check = (f"The government says Meta's ~${fees / 1e6:,.0f}M a year in transmission fees "
                 f"will cut the transmission part of household bills by up to 6%. That's "
                 f"{share:.1%} of AESO's ${rr / 1e9:,.2f}B transmission cost for 2026, so "
                 + ("a 6% cut is plausible" if share >= 0.06
                    else "a 6% cut looks overstated" if share < 0.03
                    else "the fees could cover only part of a 6% cut")
                 + ". It's an upper bound: total transmission "
                 "costs also grow, partly to connect new loads.")
    low, high = dts_estimate(META_MW)
    ours = f"${low / 1e6:,.0f}–{high / 1e6:,.0f}M"
    if 0.9 * low <= fees <= 1.1 * high:
        check += (f" Our own estimate from AESO's 2026 rates is {ours} a year, so the "
                  f"government's ~${fees / 1e6:,.0f}M checks out.")
    else:
        check += (f" Our own estimate from AESO's 2026 rates is {ours} a year, which doesn't "
                  f"match the government's ~${fees / 1e6:,.0f}M.")
    past = p[:now].tz_convert(TZ)
    monthly = past.groupby(past.index.strftime("%Y-%m")).mean().dropna()
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
            f"Our fee estimate applies AESO's 2026 Rate DTS to {META_MW} MW: the full draw at "
            "every monthly system peak, one point of delivery, and 80–100% average use. It "
            "leaves out operating reserves, which follow the pool price (roughly $20M more at "
            "today's prices).",
        ],
        "sources": ["goa_bills"] + ([FACTS["transmission_rr"]["source"]] if rr else [])
        + ["aeso_rate_dts"],
    }


def emissions_card() -> dict:
    f, full = impacts.footprint(META_MW), impacts.footprint(META_FULL_MW)
    share = f["share_of_ab_electricity_co2"]
    return {
        "id": "emissions",
        "question": "Is it bad for emissions?",
        "headline": f"Phase 1: up to {f['co2_mt']:.1f} Mt CO₂ a year if it all ran on gas",
        "verdict": ("Big" if share >= 0.10 else "Noticeable" if share >= 0.03 else "Small")
        + f": up to {share:.0%} of Alberta's power emissions",
        "explain": (f"If all {META_MW} MW ran around the clock on new gas, it would emit about "
                    f"{f['co2_mt']:.1f} million tonnes of CO₂ a year, {share:.0%} of what "
                    f"Alberta's power sector emitted in 2023. That's phase 1; at full build-out "
                    f"({META_FULL_MW:,} MW) it would be about {full['co2_mt']:.1f} million tonnes, "
                    f"{full['share_of_ab_electricity_co2']:.0%}. This verdict would change if the "
                    f"campus runs below full power or buys wind and solar."),
        "chart": None,
        "how": [
            "Assumes the load runs flat all year: an upper bound on energy.",
            "Assumes Alberta's best gas plants (0.37 t/MWh): a lower bound on emissions.",
            f"Phase 1 is Meta's {META_MW} MW AESO-approved grid allocation. Full build-out is "
            f"{META_FULL_MW:,} MW from the grid plus on-site generation, per the government; it "
            f"hasn't said when.",
            *(f"{k}: {v}" for k, v in impacts.SOURCES.items()),
        ],
        "sources": ["goa_numbers"],
    }


def water_card() -> dict:
    f, full = impacts.footprint(META_MW), impacts.footprint(META_FULL_MW)
    lo, hi = f["water_bl_cooling tower"]
    flo, fhi = full["water_bl_cooling tower"]
    dlo, dhi = f["water_bl_dry cooling"]
    plo, phi = f["people_equiv_cooling tower"]
    return {
        "id": "water",
        "question": "Will it drain our water?",
        "headline": f"Phase 1: {lo:.1f}–{hi:.1f} billion litres a year",
        "verdict": "Depends on the plant's cooling",
        "explain": (f"A gas plant powering {META_MW} MW with cooling towers would use "
                    f"{lo:.1f}–{hi:.1f} billion litres a year, about what {round(plo, -3):,.0f}–"
                    f"{round(phi, -3):,.0f} "
                    f"Albertans use. With dry cooling it's {dlo:.2f}–{dhi:.2f} billion. At full "
                    f"build-out ({META_FULL_MW:,} MW) cooling towers would use {flo:.1f}–{fhi:.1f} "
                    f"billion. The "
                    f"government's 'less than a golf course' claim is about the data centre "
                    f"itself, not its power plant. This verdict would change once the plant's "
                    f"cooling design and water licence are public."),
        "chart": None,
        "how": [
            "Water here is the gas plant's cooling use only. The data centre's own cooling is "
            "separate and the government says it is closed-loop.",
            f"Uses NREL's range for combined-cycle gas plants, scaled to a flat {META_MW} MW load "
            f"(phase 1) and {META_FULL_MW:,} MW (full build-out).",
            *(f"{k}: {v}" for k, v in impacts.SOURCES.items() if "Water" in k or "L/" in k),
        ],
        "sources": ["goa_water", "goa_numbers"],
    }


def cards(df: pd.DataFrame, now: pd.Timestamp) -> dict:
    # The older of the two: the page is only as fresh as its stalest input.
    last = min(df[c][:now].dropna().index.max() for c in ("pool_price", "load_mw"))
    return {
        "scale": scale(df),
        "cards": [reliability_card(df, now), bills_card(df, now), emissions_card(),
                  water_card()],
        "as_of_utc": last.isoformat(),
        "stale": bool(now - last > pd.Timedelta(hours=health.STALE_HOURS)),
    }
