"""Emissions and water for flat loads served by new CCGT, with Alberta context from our data.

Run: python scripts/impacts.py   (needs DATABASE_URL and a loaded `hourly` table)
"""

from gridwatch import cushion, db, impacts, readme

YEAR = 2025
REQUESTED_MW = 20000  # ~20 GW of proposed data-centre load reported in 2026 (see README sources)

with db.connect() as conn:
    df = db.hourly_frame(conn)
load = df["load_mw"]
year_twh = load[str(YEAR)].sum() / 1e6
peak_ts = load.idxmax()

rows = {mw: (label, impacts.footprint(mw)) for mw, label in cushion.SCENARIOS.items()}
rows[REQUESTED_MW] = ("all proposals reported (~20 GW)", impacts.footprint(REQUESTED_MW))
for mw, (_, f) in rows.items():
    print(mw, f)


def rng(t, fmt="{:,.1f}"):
    return f"{fmt.format(t[0])}–{fmt.format(t[1])}"


lines = [
    f"Context from our data: Alberta used **{year_twh:.1f} TWh** in {YEAR}; the record hourly "
    f"load is **{load.max():,.0f} MW** ({peak_ts.tz_convert('America/Edmonton'):%Y-%m-%d %H:%M} "
    "MT). Each row assumes the load runs flat all year (an upper bound; real data centres run "
    "close to flat) and every MWh comes from new combined-cycle gas at Alberta's best-gas "
    "benchmark (a lower bound on emissions; simple-cycle plants emit more). "
    "Regenerate with `python scripts/impacts.py`.", "",
    "| added load | reference | TWh/yr | % of AB use | CO₂ Mt/yr | % of AB power CO₂ (2023) "
    "| plant water, cooling tower (billion L/yr) | ≈ Albertans' water use "
    "| dry cooling (billion L/yr) |",
    "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
for mw, (label, f) in rows.items():
    lines.append(
        f"| {mw:,} MW | {label} | {f['twh']:.1f} | {f['twh'] / year_twh:.0%} | "
        f"{f['co2_mt']:.1f} | {f['share_of_ab_electricity_co2']:.0%} | "
        f"{rng(f['water_bl_cooling tower'])} | "
        f"{rng([round(x, -3) for x in f['people_equiv_cooling tower']], '{:,.0f}')} people | "
        f"{rng(f['water_bl_dry cooling'], '{:,.2f}')} |")
lines += ["", f"The ~20 GW of proposals is **{REQUESTED_MW / load.max():.1f}×** Alberta's record "
          "peak load. Water is the gas plant's cooling consumption only; data-centre cooling is "
          "extra and depends on design (the province's \"less than a golf course\" figure refers "
          "to the data centre, not its power plant). The MW references only set the size: "
          "grid power "
          "drawn under the bridging allowance would come from today's mix, not new CCGT.",
          "", "Sources:"]
lines += [f"- {k}: {v}" for k, v in impacts.SOURCES.items()]
lines += ["- ~20 GW proposed: National Observer (2026-03-23) and DeSmog (2026-07-23) reporting"]
readme.replace_section("impacts", "\n".join(lines))
