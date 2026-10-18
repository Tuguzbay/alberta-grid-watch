"""The public model-health page: one self-contained HTML document.

Same look as the claims page (shared fonts, colour tokens and newsprint grain), plainer layout.
"""

import json
from html import escape

from gridwatch.claims_page import DARK, FONTS, GRAIN, LIGHT

EMPTY_ROW = "<tr><td colspan=3>No scored forecasts yet.</td></tr>"
LABELS = {"pool_price": "Pool price ($/MWh)", "load_mw": "Alberta Internal Load (MW)"}


def _mae_table(title: str, maes: dict) -> str:
    rows = "".join(
        f"<tr><th scope='row'>{escape(LABELS[t])}</th><td>{escape(m)}</td><td>{v:,.1f}</td></tr>"
        for t, by_model in maes.items() for m, v in sorted(by_model.items(), key=lambda x: x[1]))
    return (f"<div class='sheet'><table><caption>{escape(title)}</caption><thead><tr>"
            f"<th scope='col'>Target</th><th scope='col'>Model</th><th scope='col'>MAE</th></tr>"
            f"</thead><tbody>{rows or EMPTY_ROW}</tbody></table></div>")


def render(s: dict) -> str:
    notes = "".join(f"<li>{escape(a)}</li>" for a in s["alerts"] + s["stale"])
    status = (f"<ul class='alert' role='alert'>{notes}</ul>" if notes
              else "<p class='ok'><span class='dot'></span>No alerts. Data is fresh.</p>")
    src = ("live forecasts" if s["source"] == "live" else
           f"the 2025–26 backtest (live track record: {s['live_days_scored']} of 14 days needed)")
    data = json.dumps({"next": s["next_day"], "last": s["last_scored_day"]}).replace("</", "<\\/")
    charts = "".join(
        f"<figure class='sheet'><figcaption>{escape(LABELS[t])}<small>{cap}</small></figcaption>"
        f"<div class='plot'><canvas id='{key}-{t}' role='img' "
        f"aria-label='{escape(LABELS[t])} {cap}'></canvas></div></figure>"
        for key, cap in (("next", "next-day forecast"), ("last", "latest scored day vs actual"))
        for t in LABELS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alberta Grid Watch: model health</title>
<script>
// Same saved theme choice as the claims page.
try {{
  const t = localStorage.getItem("theme");
  if (t) document.documentElement.dataset.theme = t;
}} catch (e) {{}}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>
:root {{ {LIGHT} --grain:url("{GRAIN}"); }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ {DARK} }} }}
:root[data-theme="dark"] {{ {DARK} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper) var(--grain); color:var(--ink);
        font:400 18px/1.6 var(--serif); -webkit-font-smoothing:antialiased; }}
.page {{ max-width:1040px; margin:0 auto; padding:0 16px 64px; }}
a {{ color:var(--accent); text-underline-offset:3px; }}
header {{ border-bottom:3px double var(--ink); padding:28px 0 18px; margin-bottom:22px; }}
.kicker {{ font:700 .78rem/1 var(--ui); letter-spacing:.16em; text-transform:uppercase;
           color:var(--ink-2); margin:0 0 12px; }}
h1 {{ font:800 clamp(2rem, 6vw, 3.4rem)/1.02 var(--serif); letter-spacing:-.02em;
      margin:0 0 12px; }}
.dek {{ color:var(--ink-2); max-width:720px; margin:0; }}
.ok, .alert {{ font:600 .95rem/1.4 var(--ui); border-radius:14px; padding:12px 16px;
               margin:0 0 22px; }}
.ok {{ background:var(--good-bg); color:var(--good); display:flex; align-items:center;
       gap:10px; }}
.dot {{ inline-size:8px; block-size:8px; border-radius:50%; background:currentColor; }}
.alert {{ background:var(--warn-bg); color:var(--warn); padding-left:34px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 320px), 1fr));
         gap:18px; margin:0 0 22px; }}
.sheet {{ background:var(--sheet); border:1px solid var(--rule); border-radius:22px;
          box-shadow:0 18px 40px -30px var(--shadow); padding:20px 22px; margin:0;
          min-width:0; }}
table {{ border-collapse:collapse; width:100%; font:400 .92rem/1.4 var(--ui); }}
caption, figcaption {{ text-align:left; font:700 .78rem/1 var(--ui); letter-spacing:.14em;
                       text-transform:uppercase; color:var(--ink-2); margin:0 0 12px; }}
figcaption small {{ display:block; font:400 .9rem/1.3 var(--ui); letter-spacing:0;
                    text-transform:none; margin-top:6px; }}
th, td {{ border-bottom:1px solid var(--rule); padding:7px 6px; text-align:left; }}
thead th {{ font-weight:700; color:var(--ink-2); }}
tbody tr:last-child > * {{ border-bottom:0; }}
td:last-child, thead th:last-child {{ text-align:right; font-variant-numeric:tabular-nums; }}
.charts {{ grid-template-columns:repeat(auto-fit, minmax(min(100%, 440px), 1fr)); }}
.plot {{ position:relative; height:240px; }}
.note {{ font:400 .92rem/1.55 var(--ui); color:var(--ink-2); max-width:760px; }}
</style></head><body>
<div class="page">
<header>
  <p class="kicker"><a href="index.html">← Meta in Alberta: claims vs data</a></p>
  <h1>Model health</h1>
  <p class="dek">Next-day forecasts issued 10:00 Mountain time. Errors below are from {src}.
  Last settled price: {escape(s["last_actual_utc"][:16].replace("T", " "))} UTC.
  Last forecast issued: {escape(s["last_issue_date"] or "none yet")}.</p>
</header>
{status}
<div class="grid">{_mae_table("Last 7 days", s["mae_7d"])}
{_mae_table("Last 30 days", s["mae_30d"])}</div>
<p class="note">Price forecasts beat simple baselines only modestly and miss price spikes
(hours above $200/MWh). Treat them as a typical-hour guide, not a spike warning.</p>
<div class="grid charts">{charts}</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const D = {data};
if (window.Chart) {{
  const css = getComputedStyle(document.documentElement), v = n => css.getPropertyValue(n).trim();
  Chart.defaults.font.family = "Figtree, system-ui, sans-serif";
  Chart.defaults.color = v("--ink-2");
  // Our model and the actual stand out; baselines stay quiet.
  const colour = k => k === "actual" ? v("--ink") : k === "hgb" ? v("--accent")
    : v("--ink-2") + "66";  // tokens are #rrggbb, so this adds ~40% alpha
  const fmt = new Intl.DateTimeFormat("en-CA", {{timeZone: "America/Edmonton", hour: "2-digit"}});
  for (const key of ["next", "last"]) for (const [t, s] of Object.entries(D[key])) {{
    const el = document.getElementById(key + "-" + t); if (!el) continue;
    new Chart(el, {{type: "line", data: {{labels: s.ts.map(x => fmt.format(new Date(x))),
      datasets: Object.keys(s).filter(k => k !== "ts").map(k => ({{label: k, data: s[k],
        borderColor: colour(k), backgroundColor: colour(k), tension: .25, pointRadius: 0,
        borderWidth: k === "hgb" || k === "actual" ? 2.5 : 1.5}}))}},
      options: {{maintainAspectRatio: false, animation: false,
        interaction: {{mode: "index", intersect: false}},
        plugins: {{legend: {{labels: {{boxWidth: 12, boxHeight: 2}}}}}},
        scales: {{x: {{ticks: {{maxTicksLimit: 8, maxRotation: 0}}, grid: {{display: false}}}},
                  y: {{grid: {{color: v("--rule")}}, border: {{display: false}}}}}}}}}});
  }}
}}
</script></body></html>"""
