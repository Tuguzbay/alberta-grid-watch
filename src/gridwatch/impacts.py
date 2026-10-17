"""Emissions and water for a flat load served by new combined-cycle gas generation.

Every factor is a published figure; see SOURCES. Results are simple arithmetic on them.
"""

HOURS_PER_YEAR = 8760
# TIER "good-as-best-gas" benchmark = Alberta's best CCGT. Simple-cycle plants emit more.
CO2_T_PER_MWH = 0.37
L_PER_GAL = 3.785
# NREL/Macknick et al. 2012, NGCC operational water *consumption* (gal/MWh).
WATER_GAL_PER_MWH = {"cooling tower": (130, 300), "dry cooling": (0, 4)}
AB_ELECTRICITY_MT_2023 = 19.2  # National Inventory Report 2025, Alberta electricity sector
AB_L_PER_PERSON_DAY = 330  # StatCan 2021, Alberta average daily drinking-water use per capita

SOURCES = {
    "CO2 0.37 t/MWh": "Alberta TIER regulation, electricity high-performance benchmark",
    "Water gal/MWh": "Macknick et al. 2012, Environ. Res. Lett. 7 045802 (NREL)",
    "AB electricity 19.2 Mt (2023)": "Canada National Inventory Report 2025",
    "330 L/person/day": "Statistics Canada, Survey of Drinking Water Plants 2021",
}


def footprint(mw: float, load_factor: float = 1.0) -> dict:
    """Annual energy, CO2 and water for `mw` running at `load_factor`, all from new CCGT."""
    mwh = mw * HOURS_PER_YEAR * load_factor
    person_l_per_year = AB_L_PER_PERSON_DAY * 365
    out = {"mw": mw, "twh": mwh / 1e6, "co2_mt": mwh * CO2_T_PER_MWH / 1e6,
           "share_of_ab_electricity_co2": mwh * CO2_T_PER_MWH / 1e6 / AB_ELECTRICITY_MT_2023}
    for cooling, (lo, hi) in WATER_GAL_PER_MWH.items():
        litres = (mwh * lo * L_PER_GAL, mwh * hi * L_PER_GAL)
        out[f"water_bl_{cooling}"] = tuple(x / 1e9 for x in litres)
        out[f"people_equiv_{cooling}"] = tuple(x / person_l_per_year for x in litres)
    return out
