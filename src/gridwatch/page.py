"""The public model-health page: one self-contained HTML document."""

import json
from html import escape

EMPTY_ROW = "<tr><td colspan=3>no scored forecasts yet</td></tr>"
LABELS = {"pool_price": "Pool price ($/MWh)", "load_mw": "Alberta Internal Load (MW)"}


def _mae_table(title: str, maes: dict) -> str:
    rows = "".join(
        f"<tr><th scope='row'>{escape(LABELS[t])}</th><td>{escape(m)}</td><td>{v:,.1f}</td></tr>"
        for t, by_model in maes.items() for m, v in sorted(by_model.items(), key=lambda x: x[1]))
    return (f"<table><caption>{escape(title)}</caption><thead><tr><th scope='col'>target</th>"
            f"<th scope='col'>model</th><th scope='col'>MAE</th></tr></thead>"
            f"<tbody>{rows or EMPTY_ROW}</tbody></table>")


def render(s: dict) -> str:
    notes = "".join(f"<li class='warn'>{escape(a)}</li>" for a in s["alerts"] + s["stale"])
    status = f"<ul>{notes}</ul>" if notes else "<p class='ok'>No alerts. Data is fresh.</p>"
    src = ("live forecasts" if s["source"] == "live" else
           f"the 2025–26 backtest (live track record: {s['live_days_scored']} of 14 days needed)")
    data = json.dumps({"next": s["next_day"], "last": s["last_scored_day"]}).replace("</", "<\\/")
    charts = "".join(
        f"<figure><figcaption>{escape(LABELS[t])}: {cap}</figcaption>"
        f"<canvas id='{key}-{t}' role='img' aria-label='{escape(LABELS[t])} {cap}'>"
        "</canvas></figure>"
        for key, cap in (("next", "next-day forecast"), ("last", "latest scored day vs actual"))
        for t in LABELS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alberta Grid Watch: model health</title>
<style>
:root {{ --bg:#fff; --fg:#1b1f24; --muted:#59636e; --line:#d0d7de;
         --warn:#9a3412; --ok:#166534; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#30363d;
           --warn:#fb923c; --ok:#4ade80; }}
}}
body {{ background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, sans-serif;
        max-width:960px; margin:0 auto; padding:16px; }}
h1 {{ font-size:1.5rem; }} .muted {{ color:var(--muted); }}
.warn {{ color:var(--warn); }} .ok {{ color:var(--ok); }}
table {{ border-collapse:collapse; width:100%; margin:1rem 0; }}
caption {{ text-align:left; font-weight:600; }}
th, td {{ border-bottom:1px solid var(--line); padding:4px 8px; text-align:left; }}
td:last-child {{ text-align:right; font-variant-numeric:tabular-nums; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; }}
figure {{ margin:0; }}
</style></head><body>
<h1>Alberta Grid Watch: model health</h1>
<p class="muted">Next-day forecasts issued 10:00 Mountain time. Errors below are from {src}.
Last settled price: {escape(s["last_actual_utc"])} UTC. Last forecast issued:
{escape(s["last_issue_date"] or "none yet")}.</p>
{status}
<div class="grid">{_mae_table("Last 7 days", s["mae_7d"])}
{_mae_table("Last 30 days", s["mae_30d"])}</div>
<p class="muted">Price forecasts beat simple baselines only modestly and miss price spikes
(hours above $200/MWh). Treat them as a typical-hour guide, not a spike warning.</p>
<div class="grid">{charts}</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const D = {data};
for (const key of ["next", "last"]) for (const [t, s] of Object.entries(D[key])) {{
  const el = document.getElementById(key + "-" + t); if (!el) continue;
  const fmt = new Intl.DateTimeFormat("en-CA", {{timeZone: "America/Edmonton", hour: "2-digit"}});
  new Chart(el, {{type: "line", data: {{labels: s.ts.map(x => fmt.format(new Date(x))),
    datasets: Object.keys(s).filter(k => k !== "ts").map(k => ({{label: k, data: s[k],
      borderWidth: k === "hgb" || k === "actual" ? 2.5 : 1, pointRadius: 0}}))}},
    options: {{interaction: {{mode: "index", intersect: false}}, animation: false}}}});
}}
</script></body></html>"""
