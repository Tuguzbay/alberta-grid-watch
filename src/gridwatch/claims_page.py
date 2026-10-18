"""The public "Meta in Alberta: claims vs data" page: one self-contained HTML document."""

import json
from html import escape

import pandas as pd

from gridwatch.features import TZ
from gridwatch.health import STALE_HOURS

REPO = "https://github.com/Tuguzbay/alberta-grid-watch"
# Badge colour by what the verdict means for residents; anything else is neutral.
TONE = {"Not so far": "good", "Plausible": "good", "Small": "good",
        "Getting tighter": "bad", "Overstated": "bad", "Significant": "bad"}


def _sources(keys: list[str], sources: dict[str, dict]) -> str:
    items = "".join(
        f"<li><a href=\"{escape(sources[k]['url'])}\">{escape(sources[k]['title'])}</a> "
        f"<span class='muted'>({escape(sources[k]['publisher'])})</span></li>" for k in keys)
    return f"<ul class='src'>{items}</ul>"


def _card(c: dict, sources: dict[str, dict]) -> str:
    chart = (f"<div class='chart'><canvas id='chart-{escape(c['id'])}' role='img' "
             f"aria-label='{escape(next(iter(c['chart']['series'])))}'></canvas></div>"
             if c["chart"] else "")
    how = "".join(f"<li>{escape(x)}</li>" for x in c["how"])
    return f"""<article>
<h2>{escape(c['question'])}</h2>
<p class="headline">{escape(c['headline'])}</p>
<p><span class="badge {TONE.get(c['verdict'], 'neutral')}">{escape(c['verdict'])}</span></p>
<p>{escape(c['explain'])}</p>
{chart}
<details><summary>How we know</summary><ul>{how}</ul></details>
<h3>Sources</h3>{_sources(c['sources'], sources)}
</article>"""


def render(data: dict, sources: dict[str, dict]) -> str:
    s = data["scale"]
    as_of = pd.Timestamp(data["as_of_utc"]).tz_convert(TZ).strftime("%Y-%m-%d %H:%M")
    stale = (f"<p class='warn' role='alert'>This data isn't up to date: the last settled AESO "
             f"price is from {escape(as_of)} Mountain time.</p>" if data["stale"] else
             # Shown by the script below if the daily job itself stops publishing.
             f"<p id=\"stale-live\" hidden class='warn' role='alert'>This page hasn't updated "
             f"in over {STALE_HOURS} hours, so the numbers below may be out of date.</p>")
    tiles = "".join(
        f"<div class='tile'><b>{v:,.0f} MW</b><span>{escape(label)}</span></div>"
        for v, label in ((s["meta_mw"], "Meta campus grid draw"),
                         (s["edmonton_mw"], "City of Edmonton load"),
                         (s["record_mw"], f"Highest hour since {s['history_from']} "
                                          f"({s['record_ts_local']})"),
                         (s["requested_mw"], "data-centre load requested")))
    cards = "\n".join(_card(c, sources) for c in data["cards"])
    charts = json.dumps({c["id"]: c["chart"] for c in data["cards"] if c["chart"]})
    charts = charts.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meta in Alberta: claims vs data</title>
<meta name="description" content="Worries and promises about Meta's Alberta data centre,
checked against grid data.">
<style>
:root {{ --bg:#fbfaf7; --card:#fff; --fg:#1b1f24; --muted:#59636e; --line:#e2ded6;
         --accent:#1d4ed8; --good:#166534; --good-bg:#dcfce7; --bad:#9a3412;
         --bad-bg:#ffedd5; --neutral:#334155; --neutral-bg:#e2e8f0; --warn:#9a3412; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0d1117; --card:#161b22; --fg:#e6edf3; --muted:#9198a1; --line:#30363d;
           --accent:#60a5fa; --good:#4ade80; --good-bg:#14532d; --bad:#fdba74;
           --bad-bg:#7c2d12; --neutral:#cbd5e1; --neutral-bg:#334155; --warn:#fb923c; }}
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); font:17px/1.55 system-ui, sans-serif;
        max-width:880px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:clamp(1.6rem, 5vw, 2.3rem); line-height:1.15; margin:0 0 .4rem; }}
h2 {{ font-size:1.35rem; margin:0 0 .25rem; }} h3 {{ font-size:.95rem; margin:1rem 0 .25rem; }}
a {{ color:var(--accent); }} .muted {{ color:var(--muted); }} .warn {{ color:var(--warn); }}
.lede {{ color:var(--muted); font-size:1.05rem; margin:0 0 1.5rem; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:12px;
          margin:0 0 2rem; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
         padding:12px 14px; }}
.tile b {{ display:block; font-size:1.35rem; font-variant-numeric:tabular-nums; }}
.tile span {{ color:var(--muted); font-size:.9rem; }}
article {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:20px; margin:0 0 20px; }}
.headline {{ font-size:1.6rem; font-weight:700; margin:.25rem 0; }}
.badge {{ display:inline-block; border-radius:999px; padding:2px 12px; font-weight:600;
          font-size:.9rem; }}
.good {{ color:var(--good); background:var(--good-bg); }}
.bad {{ color:var(--bad); background:var(--bad-bg); }}
.neutral {{ color:var(--neutral); background:var(--neutral-bg); }}
/* Fixed-height box: Chart.js with maintainAspectRatio false sizes to its parent. */
.chart {{ position:relative; height:240px; margin:.5rem 0; }}
details {{ border-top:1px solid var(--line); padding-top:.5rem; margin-top:.75rem; }}
summary {{ cursor:pointer; font-weight:600; }}
ul {{ padding-left:1.2rem; }} .src {{ font-size:.92rem; margin:0; }}
footer {{ color:var(--muted); font-size:.9rem; border-top:1px solid var(--line);
          padding-top:1rem; }}
</style></head><body>
<header>
<h1>Meta in Alberta: claims vs data</h1>
<p class="lede">Meta is building a large AI data centre in Sturgeon County. This page checks
the worries people raise, and the promises the government makes, against Alberta grid data.
The numbers update daily.</p>
{stale}
</header>
<section class="tiles" aria-label="How big is it?">{tiles}</section>
<main data-as-of="{escape(data['as_of_utc'])}">
{cards}
</main>
<footer>
<p>Data as of {escape(as_of)} Mountain time, from the AESO public API (non-commercial,
educational use) and the documents linked on each card. Verdicts come from fixed rules over
these numbers. Forecast accuracy: <a href="health.html">model track record</a>.
Code and method: <a href="{REPO}">GitHub</a>.</p>
</footer>
<script>
const asOf = Date.parse(document.querySelector("[data-as-of]").dataset.asOf);
const live = document.getElementById("stale-live");
if (live && Date.now() - asOf > {STALE_HOURS} * 3600e3) live.hidden = false;
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const C = {charts};
const css = getComputedStyle(document.documentElement);
const color = css.getPropertyValue("--accent").trim(), grid = css.getPropertyValue("--line").trim();
const muted = css.getPropertyValue("--muted").trim();
for (const [id, c] of Object.entries(C)) {{
  const el = document.getElementById("chart-" + id); if (!el) continue;
  new Chart(el, {{type: c.type, data: {{labels: c.labels,
    datasets: Object.entries(c.series).map(([label, data]) => ({{label, data,
      borderColor: color, backgroundColor: color, borderWidth: 1.5, pointRadius: 0}}))}},
    options: {{animation: false, maintainAspectRatio: false,
      interaction: {{mode: "index", intersect: false}},
      plugins: {{legend: {{labels: {{color: muted}}}}}},
      scales: {{x: {{ticks: {{color: muted, maxTicksLimit: 8}}, grid: {{color: grid}}}},
                y: {{ticks: {{color: muted}}, grid: {{color: grid}}}}}}}}}});
}}
</script></body></html>"""
