"""The public "Meta in Alberta: claims vs data" page: one self-contained HTML document.

Look: an old broadsheet (masthead, rules, serif headlines, drop caps, newsprint grain) crossed
with a modern product page (white space, rounded pills, one blue accent). Inspired by both,
imitating neither: no logos, and the page says it isn't affiliated with Meta.
"""

import json
import re
from html import escape

import pandas as pd

from gridwatch.features import TZ
from gridwatch.health import STALE_HOURS

REPO = "https://github.com/Tuguzbay/alberta-grid-watch"
FONTS = ("https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700..900;"
         "1,500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Figtree:wght@"
         "400;600;700;800&display=swap")
# Newsprint grain: a tiny SVG noise tile at ~7% opacity.
GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
         "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'"
         " stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .0"
         "7 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/sv"
         "g%3E")
# Chip colour by what the verdict means for residents; anything else is neutral.
TONE = {"Not so far": "good", "Plausible": "good", "Small": "good",
        "More hours leaning on wind, solar and imports": "warn", "Overstated": "warn",
        "Significant": "warn"}


def _split(text: str) -> tuple[str, str]:
    """First sentence (the short answer) and the rest."""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _sources(keys: list[str], sources: dict[str, dict]) -> str:
    return "".join(
        f"<li><a href=\"{escape(sources[k]['url'])}\">{escape(sources[k]['title'])}</a>"
        f"<span>{escape(sources[k]['publisher'])}</span></li>" for k in keys)


def _chip(verdict: str) -> str:
    return f"<span class=\"chip {TONE.get(verdict, 'neutral')}\">{escape(verdict)}</span>"


def _glance(cards: list[dict]) -> str:
    rows = "".join(
        f"<li><a href=\"#{escape(c['id'])}\"><span class=\"num\">{i:02d}</span>"
        f"<span class=\"q\">{escape(c['question'])}</span>{_chip(c['verdict'])}</a></li>"
        for i, c in enumerate(cards, 1))
    return (f"<nav class=\"glance\" aria-label=\"At a glance\"><h2 class=\"kicker\">At a glance"
            f"</h2><ol>{rows}</ol></nav>")


def _scale(s: dict) -> str:
    items = [(s["meta_mw"], "Meta campus", "grid draw"),
             (s["edmonton_mw"], "City of Edmonton", "typical load"),
             (s["record_mw"], f"Highest hour since {s['history_from']}",
              f"all of Alberta, {s['record_ts_local']}"),
             (s["requested_mw"], "Data-centre requests", "load asking to connect")]
    top = max(v for v, _, _ in items)
    bars = "".join(
        f"<li style=\"--w:{v / top:.1%}\"><span class=\"label\">{escape(name)}"
        f"<small>{escape(note)}</small></span><span class=\"bar\"></span>"
        f"<b>{v:,.0f}<small> MW</small></b></li>" for v, name, note in items)
    return (f"<section class=\"scale\" aria-labelledby=\"scale-h\"><h2 class=\"kicker\" "
            f"id=\"scale-h\">How big is it?</h2><ul>{bars}</ul><p class=\"note\">Bars drawn to "
            f"scale. Meta alone would draw about two-thirds of what Edmonton uses; the "
            f"requests add up to more than Alberta has ever used at once.</p></section>")


def _card(i: int, c: dict, sources: dict[str, dict]) -> str:
    lead, rest = _split(c["explain"])
    label = escape(next(iter(c["chart"]["series"]))) if c["chart"] else ""
    chart = (f"<figure class=\"chart\"><canvas id=\"chart-{escape(c['id'])}\" role=\"img\" "
             f"aria-label=\"{label}\"></canvas><figcaption>{label}</figcaption></figure>"
             if c["chart"] else "")
    how = "".join(f"<li>{escape(x)}</li>" for x in c["how"])
    rest_p = f"<p>{escape(rest)}</p>" if rest else ""
    return f"""<article id="{escape(c['id'])}" class="story">
<header><span class="num">{i:02d}</span><h2>{escape(c['question'])}</h2></header>
<div class="cols">
  <div class="figure"><p class="big">{escape(c['headline'])}</p>{_chip(c['verdict'])}</div>
  <div class="text"><p class="lead">{escape(lead)}</p>{rest_p}</div>
</div>
{chart}
<div class="fine">
  <details><summary>How we know</summary><ul>{how}</ul></details>
  <details><summary>Sources</summary><ul class="src">{_sources(c['sources'], sources)}</ul>
  </details>
</div>
</article>"""


def render(data: dict, sources: dict[str, dict]) -> str:
    as_of_txt = pd.Timestamp(data["as_of_utc"]).tz_convert(TZ).strftime("%Y-%m-%d %H:%M")
    stale = (f"<p class='alert' role='alert'>This data isn't up to date: the last settled AESO "
             f"price is from {escape(as_of_txt)} Mountain time.</p>" if data["stale"] else
             # Shown by the script below if the daily job itself stops publishing.
             f"<p id=\"stale-live\" hidden class='alert' role='alert'>This page hasn't updated "
             f"in over {STALE_HOURS} hours, so the numbers below may be out of date.</p>")
    cards = "\n".join(_card(i, c, sources) for i, c in enumerate(data["cards"], 1))
    charts = json.dumps({c["id"]: c["chart"] for c in data["cards"] if c["chart"]})
    charts = charts.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meta in Alberta: claims vs data</title>
<meta name="description" content="Worries and promises about Meta's Alberta data centre,
checked against grid data. An independent project.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>
:root {{
  --paper:#f3eee3; --sheet:#fbf8f1; --ink:#161513; --ink-2:#4a463f; --rule:#cfc6b4;
  --accent:#0a5cff; --accent-soft:#e3ecff;
  --good:#0f6b3a; --good-bg:#dff2e5; --warn:#8a4b00; --warn-bg:#fdebd0;
  --neutral:#3d4450; --neutral-bg:#e6e8ec;
  --head:"Playfair Display", "Didot", Georgia, serif; --body:"Source Serif 4", Georgia, serif;
  --ui:"Figtree", "Segoe UI", system-ui, sans-serif;
  --grain:url("{GRAIN}");
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper:#121110; --sheet:#1b1a18; --ink:#efe9dc; --ink-2:#bbb4a5; --rule:#3a3631;
    --accent:#7aa3ff; --accent-soft:#1d2a46;
    --good:#86dba6; --good-bg:#16352a; --warn:#ffc47e; --warn-bg:#3d2a12;
    --neutral:#cdd2da; --neutral-bg:#2c3038;
  }}
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--paper) var(--grain); color:var(--ink);
        font:18px/1.6 var(--body); -webkit-font-smoothing:antialiased; }}
.page {{ max-width:1040px; margin:0 auto; padding:0 16px 64px; }}
a {{ color:var(--accent); text-underline-offset:3px; }}
.kicker {{ font:700 .78rem/1 var(--ui); letter-spacing:.16em; text-transform:uppercase;
           color:var(--ink-2); margin:0 0 18px; }}

/* Masthead: an old broadsheet's rules and edition line. */
.masthead {{ text-align:center; padding:28px 0 0; }}
.edition {{ display:flex; justify-content:space-between; gap:4px 12px; flex-wrap:wrap;
            font:600 .74rem/1.4 var(--ui); letter-spacing:.08em; text-transform:uppercase;
            color:var(--ink-2); border-top:3px double var(--ink);
            border-bottom:1px solid var(--ink); padding:8px 2px; }}
.masthead h1 {{ font:900 clamp(2.5rem, 9vw, 5.6rem)/.95 var(--head); letter-spacing:-.01em;
                margin:22px 0 10px; }}
.masthead h1 em {{ font-style:italic; font-weight:500; }}
.dek {{ font:400 clamp(1.05rem, 2.4vw, 1.3rem)/1.5 var(--body); color:var(--ink-2);
        max-width:640px; margin:0 auto 26px; }}
.masthead .rule {{ border:0; border-top:1px solid var(--ink); border-bottom:3px double var(--ink);
                   height:5px; margin:0; }}
.alert {{ font:600 .95rem/1.4 var(--ui); background:var(--warn-bg); color:var(--warn);
          border-radius:14px; padding:12px 16px; margin:20px 0 0; text-align:left; }}

/* Front page: at-a-glance beside how-big. */
.front {{ display:grid; grid-template-columns:1fr; gap:22px; margin:30px 0 8px; }}
@media (min-width:860px) {{ .front {{ grid-template-columns:1.05fr 1fr; }} }}
.glance, .scale {{ background:var(--sheet); border:1px solid var(--rule); border-radius:22px;
                   padding:22px; box-shadow:0 18px 40px -30px #0005; min-width:0; }}
.glance {{ display:flex; flex-direction:column; }}
.glance ol {{ list-style:none; margin:0; padding:0; flex:1; display:flex; flex-direction:column;
              justify-content:space-around; }}
.glance li + li {{ border-top:1px solid var(--rule); }}
.glance a {{ display:grid; grid-template-columns:auto 1fr; gap:6px 14px; align-items:center;
             padding:14px 8px; color:var(--ink); text-decoration:none; border-radius:12px;
             transition:background .2s; }}
.glance a:hover, .glance a:focus-visible {{ background:var(--accent-soft); }}
.glance .q {{ font:600 1.08rem/1.3 var(--ui); }}
.glance .chip {{ grid-column:2; justify-self:start; }}
.num {{ font:500 1rem/1 var(--head); font-style:italic; color:var(--ink-2); }}
.glance .num {{ grid-row:span 2; align-self:start; padding-top:3px; }}

.scale ul {{ list-style:none; margin:0; padding:0; display:grid; gap:16px; }}
.scale li {{ display:grid; grid-template-columns:1fr auto; gap:6px 12px; align-items:end; }}
.scale .label {{ font:600 .98rem/1.2 var(--ui); }}
.scale .label small {{ display:block; font-weight:400; color:var(--ink-2); font-size:.82rem; }}
.scale b {{ font:800 1.2rem/1 var(--ui); font-variant-numeric:tabular-nums; }}
.scale b small {{ font-weight:600; font-size:.75rem; color:var(--ink-2); }}
.scale .bar {{ grid-column:1 / -1; height:12px; border-radius:99px; background:var(--accent-soft);
               position:relative; overflow:hidden; }}
.scale .bar::after {{ content:""; position:absolute; inset:0 auto 0 0; width:var(--w);
                      min-width:6px; border-radius:99px; background:var(--accent);
                      animation:grow 1.1s cubic-bezier(.2,.8,.2,1) both .3s; }}
.scale li:first-child .bar::after {{ background:var(--ink); }}
.note {{ font:400 .9rem/1.5 var(--ui); color:var(--ink-2); margin:18px 0 0; }}

/* Stories: one per worry, set like newspaper sections. */
.story {{ border-top:3px double var(--ink); padding:34px 0 30px; margin-top:34px;
          scroll-margin-top:12px; }}
.story header {{ display:flex; align-items:baseline; gap:16px; margin-bottom:22px; }}
.story header .num {{ font-size:1.5rem; }}
.story h2 {{ font:800 clamp(1.8rem, 4.6vw, 2.9rem)/1.05 var(--head); margin:0; }}
.cols {{ display:grid; grid-template-columns:1fr; gap:22px; }}
@media (min-width:860px) {{
  .cols {{ grid-template-columns:minmax(260px, .8fr) 1.2fr; gap:40px; }}
  .cols .text {{ border-left:1px solid var(--rule); padding-left:40px; }}
}}
.big {{ font:800 clamp(1.6rem, 4vw, 2.3rem)/1.12 var(--ui); letter-spacing:-.02em;
        margin:0 0 14px; font-variant-numeric:tabular-nums; }}
.lead {{ font:600 1.2rem/1.5 var(--body); margin:0 0 12px; }}
.lead::first-letter {{ font:900 3.4em/.8 var(--head); float:left; margin:.06em .08em 0 0; }}
.text p:not(.lead) {{ color:var(--ink-2); margin:0; }}
.chip {{ display:inline-flex; align-items:center; gap:8px; border-radius:99px; padding:6px 14px;
         font:700 .86rem/1.25 var(--ui); }}
.chip::before {{ content:""; flex:none; width:8px; height:8px; border-radius:50%;
                 background:currentColor; }}
.good {{ color:var(--good); background:var(--good-bg); }}
.warn {{ color:var(--warn); background:var(--warn-bg); }}
.neutral {{ color:var(--neutral); background:var(--neutral-bg); }}
.chart {{ margin:28px 0 0; background:var(--sheet); border:1px solid var(--rule);
          border-radius:22px; padding:18px 14px 10px; }}
/* Fixed-height box: Chart.js with maintainAspectRatio false sizes to its parent. */
.chart .plot {{ position:relative; height:260px; }}
.chart figcaption {{ font:600 .82rem/1.4 var(--ui); color:var(--ink-2); padding-top:6px; }}
.fine {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }}
.fine details {{ flex:1 1 280px; background:var(--sheet); border:1px solid var(--rule);
                 border-radius:16px; padding:0 16px; font:400 .95rem/1.5 var(--ui); }}
.fine summary {{ cursor:pointer; font-weight:700; padding:12px 0; list-style:none; }}
.fine summary::-webkit-details-marker {{ display:none; }}
.fine summary::after {{ content:"+"; float:right; font-weight:400; }}
.fine details[open] summary::after {{ content:"–"; }}
.fine ul {{ margin:0 0 14px; padding-left:18px; color:var(--ink-2); }}
.src li span {{ display:block; font-size:.82rem; color:var(--ink-2); }}

footer {{ border-top:3px double var(--ink); margin-top:20px; padding-top:18px;
          font:400 .9rem/1.6 var(--ui); color:var(--ink-2); columns:2 300px; column-gap:40px;
          column-rule:1px solid var(--rule); }}
footer p {{ margin:0 0 10px; break-inside:avoid; }}

@keyframes grow {{ from {{ width:0; }} }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(14px); }} }}
.masthead, .front > *, .story {{ animation:rise .7s cubic-bezier(.2,.8,.2,1) both; }}
.front > :nth-child(1) {{ animation-delay:.12s; }}
.front > :nth-child(2) {{ animation-delay:.22s; }}
.story {{ animation-delay:.3s; }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation:none !important; transition:none !important; }}
  html {{ scroll-behavior:auto; }}
}}
</style></head><body>
<div class="page">
<header class="masthead">
  <div class="edition"><span>Independent · Updated daily</span>
    <span>Alberta grid edition</span><span>Data as of {escape(as_of_txt)} MT</span></div>
  <h1>Meta in Alberta: <em>claims vs data</em></h1>
  <p class="dek">Meta is building a large AI data centre in Sturgeon County. We check the
  worries people raise, and the promises the government makes, against Alberta grid data.</p>
  <hr class="rule">
  {stale}
</header>
<div class="front">{_glance(data["cards"])}{_scale(data["scale"])}</div>
<main data-as-of="{escape(data['as_of_utc'])}">
{cards}
</main>
<footer>
  <p>Data as of {escape(as_of_txt)} Mountain time, from the AESO public API (non-commercial,
  educational use) and the documents linked in each section. Verdicts come from fixed rules
  over these numbers, not from opinion.</p>
  <p>An independent student project, not affiliated with Meta, AESO or the Government of
  Alberta. Forecast accuracy: <a href="health.html">model track record</a>. Code and method:
  <a href="{REPO}">GitHub</a>.</p>
</footer>
</div>
<script>
const asOf = Date.parse(document.querySelector("[data-as-of]").dataset.asOf);
const live = document.getElementById("stale-live");
if (live && Date.now() - asOf > {STALE_HOURS} * 3600e3) live.hidden = false;
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const C = {charts};
const css = getComputedStyle(document.documentElement);
const v = name => css.getPropertyValue(name).trim();
Chart.defaults.font.family = "Figtree, system-ui, sans-serif";
Chart.defaults.color = v("--ink-2");
for (const [id, c] of Object.entries(C)) {{
  const el = document.getElementById("chart-" + id); if (!el) continue;
  const box = document.createElement("div"); box.className = "plot";
  el.replaceWith(box); box.appendChild(el);
  new Chart(el, {{type: c.type, data: {{labels: c.labels,
    datasets: Object.entries(c.series).map(([label, data]) => ({{label, data,
      borderColor: v("--accent"),
      backgroundColor: c.type === "bar" ? v("--accent") : v("--accent-soft"),
      fill: c.type === "line" ? "origin" : false, tension: .25, borderWidth: 2,
      borderRadius: 3, pointRadius: 0}}))}},
    options: {{animation: false, maintainAspectRatio: false,
      interaction: {{mode: "index", intersect: false}},
      plugins: {{legend: {{display: false}}}},
      scales: {{x: {{ticks: {{maxTicksLimit: box.clientWidth < 500 ? 4 : 7, maxRotation: 0}},
                    grid: {{display: false}}}},
                y: {{grid: {{color: v("--rule")}}, border: {{display: false}}}}}}}}}});
}}
</script></body></html>"""
