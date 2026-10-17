"""Dispatchable headroom vs price since 2025, plus flat-load scenarios. Rewrites README section.

Run: python scripts/cushion.py   (needs DATABASE_URL and a loaded `hourly` table)
"""

from gridwatch import cushion, db, readme

SINCE = "2025-01-01"  # recent market regime; 2022-23 gas prices make older hours a different curve
# Public reference points, not any one project: AESO interim large-load allocation (1,200 MW)
# and the bridging allowance to draw from the grid while own generation is built (1,600 MW).
SCENARIOS = {500: "smaller reference point", 1200: "AESO interim large-load allocation",
             1600: "bridging allowance from the grid"}

with db.connect() as conn:
    df = db.hourly_frame(conn)[SINCE:]
h, price = cushion.headroom(df), df["pool_price"]
coarse = cushion.curve(h, price, bin_mw=1000)
runs = [cushion.scenario(h, price, mw) for mw in SCENARIOS]
print(coarse.round(2).to_string())
for r in runs:
    print(r)

n = runs[0]["hours"]
lines = [
    f"Hourly data {SINCE} to {df.index.max():%Y-%m-%d}, {n:,} hours. "
    "**Headroom** = available dispatchable capability (gas, hydro, storage, other, after outages) "
    "minus Alberta Internal Load. It ignores wind, solar and imports, so the real cushion is "
    "larger. Regenerate with `python scripts/cushion.py`.",
    "", "**Price by headroom** (observed)", "",
    "| headroom (MW) | hours | mean price ($/MWh) | hours > $200 |", "|---|---:|---:|---:|"]
lines += [f"| {lo:,} to {lo + 1000:,} | {int(r.hours):,} | {r.mean_price:.0f} "
          f"| {r.spike_share:.0%} |" for lo, r in coarse.iterrows()]
lines += [
    "", "**Illustrative: add a flat, always-on load with no new generation**", "",
    "| added load | reference | hours headroom < 0 | curve-implied mean price | "
    "expected hours > $200 |", "|---|---|---:|---:|---:|",
    f"| none | today | {runs[0]['hours_below_zero_today']:,} | "
    f"${runs[0]['curve_mean_price_base']:.0f} | {runs[0]['expected_spike_hours_base']:,.0f} |"]
lines += [f"| {r['added_mw']:,} MW | {SCENARIOS[r['added_mw']]} | "
          f"{r['hours_headroom_below_zero']:,} | ${r['curve_mean_price_new']:.0f} | "
          f"{r['expected_spike_hours_new']:,.0f} |" for r in runs]
lines += ["", "Not a forecast and not about any one project. It reads prices off the observed "
          "price-vs-headroom relationship, which is a correlation: low-headroom hours are also "
          "high-demand, often cold hours. It assumes nothing else changes: no new generation "
          "(Alberta's policy expects data centres to bring their own), no change in imports, "
          "wind, solar, or how generators offer. "
          "Hours pushed below the lowest well-observed headroom "
          f"({max(r['beyond_observed'] for r in runs):,} "
          "in the largest case) are priced at that edge, so the price impact is understated there."]
readme.replace_section("cushion", "\n".join(lines))
