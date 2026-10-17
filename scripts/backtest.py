"""Walk-forward backtest from 2025-01: saves forecasts to Postgres, writes README results.

Run: python scripts/backtest.py   (needs DATABASE_URL and a loaded `hourly` table)
"""

from gridwatch import backtest, db, readme

FIRST_MONTH = "2025-01"
UNITS = {"pool_price": "$/MWh", "load_mw": "MW"}


def table(m) -> str:
    lines = []
    for target, g in m.groupby(level="target", sort=False):
        u = UNITS[target]
        extra = "MAPE %" if target == "load_mw" else f"MAE when price > ${backtest.SPIKE}"
        lines += [f"\n**{target}** ({u}), {g['n'].iloc[0]:,} hours\n",
                  f"| model | MAE | RMSE | {extra} |", "|---|---:|---:|---:|"]
        for (_, model), r in g.iterrows():
            x = r["mape"] if target == "load_mw" else r["spike_mae"]
            lines.append(f"| {model} | {r['mae']:.1f} | {r['rmse']:.1f} | {x:.1f} |")
    return "\n".join(lines)


with db.connect() as conn:
    df = db.hourly_frame(conn)
    fc = backtest.run(df, FIRST_MONTH)
    db.save_forecasts(conn, fc)
m = backtest.metrics(fc)
print(m.round(2).to_string())

span = f"{fc['ts_utc'].min():%Y-%m-%d} to {fc['ts_utc'].max():%Y-%m-%d} (UTC)"
body = (f"Next-day forecasts issued 10:00 MT on D-1, monthly walk-forward, {span}. "
        "Test hours use day-ahead *forecast* weather only. "
        "Regenerate with `python scripts/backtest.py`.\n" + table(m))
readme.replace_section("results", body)
