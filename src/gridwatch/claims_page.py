"""The public "Meta in Alberta: claims vs data" page: one self-contained HTML document.

Look: an old broadsheet (masthead, rules, serif headlines, drop caps, newsprint grain) crossed
with a modern product page (white space, rounded pills, one blue accent). Inspired by both,
imitating neither: no logos, and the page says it isn't affiliated with Meta.
"""

import json
import re
from html import escape
from urllib.parse import quote, urlsplit

import pandas as pd

from gridwatch.features import TZ
from gridwatch.health import STALE_HOURS

REPO = "https://github.com/Tuguzbay/alberta-grid-watch"
FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;"
         "0,6..72,600;0,6..72,800;1,6..72,500&family=Figtree:wght@400;600;700;800&display=swap")
# Newsprint grain: a tiny SVG noise tile at ~7% opacity.
GRAIN = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
         "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'"
         " stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .0"
         "7 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/sv"
         "g%3E")
# Chip colour by what the verdict means for residents; anything else is neutral.
# Keyed by the text before ":" so a verdict can carry its number ("Big: up to 16% of ...").
TONE = {"No sign of strain": "good", "The promised 6% cut adds up": "good", "Small": "good",
        "Less backup than last year": "warn", "The 6% cut doesn't add up": "warn", "Big": "warn"}
# Colour and type tokens, shared with the model-health page.
LIGHT = """--paper:#f3eee3; --sheet:#fbf8f1; --ink:#161513; --ink-2:#4a463f; --rule:#cfc6b4;
    --accent:#0a5cff; --accent-soft:#e3ecff; --shadow:#0004;
    --good:#0f6b3a; --good-bg:#dff2e5; --warn:#8a4b00; --warn-bg:#fdebd0;
    --neutral:#3d4450; --neutral-bg:#e6e8ec; color-scheme:light;
    --serif:"Newsreader", Georgia, serif; --ui:"Figtree", "Segoe UI", system-ui, sans-serif;"""
DARK = """--paper:#121110; --sheet:#1b1a18; --ink:#efe9dc; --ink-2:#bbb4a5; --rule:#3a3631;
    --accent:#7aa3ff; --accent-soft:#1d2a46; --shadow:#0009;
    --good:#86dba6; --good-bg:#16352a; --warn:#ffc47e; --warn-bg:#3d2a12;
    --neutral:#cdd2da; --neutral-bg:#2c3038; color-scheme:dark;"""
SUN = ("<svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='4.5'/><path d='M12 "
       "1.5v3M12 19.5v3M1.5 12h3M19.5 12h3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1M4.6 19.4l2.1-2.1M17.3"
       " 6.7l2.1-2.1'/></svg>")
CHEVRON = "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M9 5l7 7-7 7'/></svg>"
MOON = "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z'/></svg>"  # noqa: E501


TOPIC_LABEL = {"bills": "Bills", "reliability": "Reliability", "emissions": "Emissions",
               "water": "Water", "land_community": "Land & community",
               "jobs_economy": "Jobs & economy", "other": "Other"}
CARD_LABEL = {"bills": "Power bills", "reliability": "Blackouts", "emissions": "Emissions",
              "water": "Water"}
AI_LABEL = ("Found and summarised automatically by AI (Claude Haiku) from public articles. "
            "Not reviewed by a person. Quotes are checked word-for-word against the source.")


def _safe_url(url: str) -> str:
    """Only http(s) links reach the page; anything else renders as plain text."""
    return url if url.lower().startswith(("http://", "https://")) else ""


def _at_quote(url: str, text: str) -> str:
    """Link that scrolls to and highlights the quote (a URL text fragment, `#:~:text=`).
    Browsers match literally, so anchor on runs of words without quote marks or brackets
    (pages use curly apostrophes, our text has straight ones and "[pdf]"-style link labels),
    as start,end words so line breaks or links inside the quote still match."""
    def enc(words: list[str]) -> str:
        return quote(" ".join(words), safe="").replace("-", "%2D")  # '-' and ',' are syntax
    runs: list[list[str]] = [[]]
    for w in text.split():
        if re.search(r"['\"‘’“”\[\]]", w):
            runs.append([])
        else:
            runs[-1].append(w)
    runs = [r for r in runs if len(r) >= 3] or [r for r in runs if r]  # "The" alone is vague
    base = url.split("#")[0]
    if not runs:
        return base
    if len(runs) == 1 and len(runs[0]) <= 8:
        return f"{base}#:~:text={enc(runs[0])}"
    return f"{base}#:~:text={enc(runs[0][:4])},{enc(runs[-1][-4:])}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _claim(c: dict, related: bool = True) -> str:
    url = _safe_url(c["url"])
    source = escape(f"{c['outlet']} · {c['published'] or 'date unknown'}")
    href = escape(_at_quote(url, c["quote"])) if url else ""
    link = (f"<a href=\"{href}\" title=\"Opens the article at this quote\">{source}</a>"
            if url else source)
    # The outlet name comes from the AI; the hostname shows where the link really goes.
    host = urlsplit(url).hostname if url else None
    if host:
        link += f" <span class=\"host\">{escape(host.removeprefix('www.'))}</span>"
    card = c["topic"] if c["topic"] in CARD_LABEL else None
    rel = (f"<a class=\"rel\" href=\"#{card}\">Related data: see {CARD_LABEL[card]} ↓</a>"
           if related and card else "")
    topic = escape(TOPIC_LABEL.get(c["topic"], "Other"))
    # Quote first: it's the only part checked word for word; the summary is the AI's reading.
    return (f"<li class=\"claim\"><blockquote>{escape(c['quote'])}</blockquote>"
            f"<p class=\"what\"><span>AI summary</span> {escape(c['claim'])}</p>"
            f"<p class=\"who\">{escape(c['speaker'])} · {link}</p>"
            f"<p class=\"tags\"><span class=\"tag\">{topic}</span>"
            f"<span class=\"chip neutral\">Not checked yet</span>{rel}</p></li>")


def _changed(s: dict) -> str:
    url = _safe_url(s["url"])
    title = f"<a href=\"{escape(url)}\">{escape(s['title'])}</a>" if url else escape(s["title"])
    return f"<li>{escape(s['publisher'])}, {title}, changed on {escape(s['changed_on'])}</li>"


def _carousel(items: str, label: str) -> str:
    """A swipeable row. The bar (count, progress, arrows) is shown by the page script."""
    arrows = "".join(f"<button class=\"car-btn{' prev' if d < 0 else ''}\" type=\"button\" "
                     f"data-dir=\"{d}\" aria-label=\"{'Previous' if d < 0 else 'Next'} claims\">"
                     f"{CHEVRON}</button>" for d in (-1, 1))
    return (f"<div class=\"carousel\"><div class=\"car-bar\" hidden>"
            f"<span class=\"car-count\" aria-live=\"polite\"></span>"
            f"<span class=\"car-track\"><span class=\"car-fill\"></span></span>{arrows}</div>"
            f"<ol class=\"claims scroller\" tabindex=\"0\" aria-label=\"{label}, scroll "
            f"sideways\">{items}</ol></div>")


def _spotted(w: dict) -> str:
    n, m = w.get("week_count", 0), w.get("week_sources", 0)
    head = (f"{_plural(n, 'new claim')} from {_plural(m, 'source')} this week" if n
            else "No new claims this week.")
    items = "".join(_claim(c) for c in w.get("claims", []))
    lines = "".join(_changed(s) for s in w.get("changed_sources", []))
    return (f"<section id=\"spotted\" class=\"spotted reveal\" aria-labelledby=\"spotted-h\">"
            f"<h2 class=\"kicker\" id=\"spotted-h\">Spotted this week</h2>"
            f"<p class=\"spot-head\">{escape(head)}</p><p class=\"ai\">{AI_LABEL}</p>"
            + (_carousel(items, "Claims spotted this week") if items else "")
            + (f"<h3>Official sources changed</h3><ul class=\"changed\">{lines}</ul>"
               if lines else "")
            + "</section>")


def _recent(claims: list[dict]) -> str:
    if not claims:
        return ""
    items = "".join(_claim(c, related=False) for c in claims)
    return (f"<div class=\"recent\"><h3>Recent claims on this topic ({len(claims)})</h3>"
            f"<ol class=\"claims\">{items}</ol></div>")


def _split(text: str) -> tuple[str, str]:
    """First sentence (the short answer) and the rest."""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _sources(keys: list[str], sources: dict[str, dict]) -> str:
    return "".join(
        f"<li><a href=\"{escape(sources[k]['url'])}\">{escape(sources[k]['title'])}</a>"
        f"<span>{escape(sources[k]['publisher'])}</span></li>" for k in keys)


def _chip(verdict: str) -> str:
    tone = TONE.get(verdict.split(":")[0], "neutral")
    return f"<span class=\"chip {tone}\">{escape(verdict)}</span>"


def _glance(cards: list[dict], w: dict) -> str:
    spotted = (f"<li><a href=\"#spotted\"><span class=\"num\">{len(cards) + 1:02d}</span>"
               f"<span class=\"q\">Spotted this week</span><span class=\"chip neutral\">"
               f"{_plural(w.get('week_count', 0), 'new claim')}</span></a></li>")
    rows = "".join(
        f"<li><a href=\"#{escape(c['id'])}\"><span class=\"num\">{i:02d}</span>"
        f"<span class=\"q\">{escape(c['question'])}</span>{_chip(c['verdict'])}</a></li>"
        for i, c in enumerate(cards, 1)) + spotted
    return (f"<nav class=\"glance\" aria-label=\"At a glance\"><h2 class=\"kicker\">At a glance"
            f"</h2><ol>{rows}</ol></nav>")


def _scale(s: dict) -> str:
    items = [(s["meta_mw"], "Meta campus", "phase 1 grid draw"),
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
            f"scale. Meta's first phase alone would draw about two-thirds of what Edmonton "
            f"uses. At full build-out the campus needs {s['meta_full_mw']:,} MW, from the grid "
            f"plus its own generation. The requests add up to more than Alberta has ever used "
            f"at once.</p></section>")


def _card(i: int, c: dict, sources: dict[str, dict], recent: list[dict] = ()) -> str:
    lead, rest = _split(c["explain"])
    label = escape(next(iter(c["chart"]["series"]))) if c["chart"] else ""
    chart = (f"<figure class=\"chart\"><canvas id=\"chart-{escape(c['id'])}\" role=\"img\" "
             f"aria-label=\"{label}\"></canvas><figcaption>{label}</figcaption></figure>"
             if c["chart"] else "")
    how = "".join(f"<li>{escape(x)}</li>" for x in c["how"])
    rest_p = f"<p>{escape(rest)}</p>" if rest else ""
    return f"""<article id="{escape(c['id'])}" class="story reveal">
<header><span class="num">{i:02d}</span><h2>{escape(c['question'])}</h2></header>
<div class="cols">
  <div class="figure"><p class="big">{escape(c['headline'])}</p>{_chip(c['verdict'])}</div>
  <div class="text"><p class="lead">{escape(lead)}</p>{rest_p}</div>
</div>
{chart}
{_recent(list(recent))}
<details class="more"><summary>How we know &amp; sources</summary>
  <div class="more-body">
    <div><h3>Method and caveats</h3><ul>{how}</ul></div>
    <div><h3>Sources</h3><ul class="src">{_sources(c['sources'], sources)}</ul></div>
  </div>
</details>
</article>"""


def render(data: dict, sources: dict[str, dict]) -> str:
    as_of_txt = pd.Timestamp(data["as_of_utc"]).tz_convert(TZ).strftime("%Y-%m-%d %H:%M")
    stale = (f"<p class='alert' role='alert'>This data isn't up to date: the last settled AESO "
             f"price is from {escape(as_of_txt)} Mountain time.</p>" if data["stale"] else
             # Shown by the script below if the daily job itself stops publishing.
             f"<p id=\"stale-live\" hidden class='alert' role='alert'>This page hasn't updated "
             f"in over {STALE_HOURS} hours, so the numbers below may be out of date.</p>")
    w = data.get("watch") or {}
    per_card = w.get("per_card", {})
    cards = "\n".join(_card(i, c, sources, per_card.get(c["id"], []))
                      for i, c in enumerate(data["cards"], 1))
    charts = json.dumps({c["id"]: c["chart"] for c in data["cards"] if c["chart"]})
    charts = charts.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meta in Alberta: claims vs data</title>
<meta name="description" content="Worries and promises about Meta's Alberta data centre,
checked against grid data. An independent project.">
<script>
// Before first paint: apply a saved theme choice and mark that scripts run (for scroll reveal).
document.documentElement.classList.add("js");
try {{
  const t = localStorage.getItem("theme");
  if (t) document.documentElement.dataset.theme = t;
}} catch (e) {{}}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>
:root {{ {LIGHT}
  --ease:cubic-bezier(.2,.8,.2,1);
  --grain:url("{GRAIN}");
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ {DARK} }} }}
:root[data-theme="dark"] {{ {DARK} }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--paper) var(--grain); color:var(--ink);
        font:400 19px/1.6 var(--serif); -webkit-font-smoothing:antialiased;
        transition:background-color .4s var(--ease), color .4s var(--ease); }}
.page {{ max-width:1040px; margin:0 auto; padding:0 16px 64px; }}
a {{ color:var(--accent); text-underline-offset:3px; }}
.kicker {{ font:700 .78rem/1 var(--ui); letter-spacing:.16em; text-transform:uppercase;
           color:var(--ink-2); margin:0 0 18px; }}

/* Masthead: an old broadsheet's rules and edition line. */
.masthead {{ text-align:center; padding:28px 0 0; }}
.edition {{ display:flex; justify-content:space-between; align-items:center; gap:4px 12px;
            flex-wrap:wrap; font:600 .74rem/1.4 var(--ui); letter-spacing:.08em;
            text-transform:uppercase; color:var(--ink-2); border-top:3px double var(--ink);
            border-bottom:1px solid var(--ink); padding:6px 2px; }}
.theme {{ display:inline-flex; align-items:center; gap:8px; font:700 .74rem/1 var(--ui);
          letter-spacing:.08em; text-transform:uppercase; color:var(--ink); cursor:pointer;
          background:var(--sheet); border:1px solid var(--rule); border-radius:99px;
          padding:6px 12px 6px 8px; transition:background .25s, transform .25s var(--ease); }}
.theme:hover {{ transform:translateY(-1px); background:var(--accent-soft); }}
.theme:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
.theme svg {{ width:16px; height:16px; fill:none; stroke:currentColor; stroke-width:2;
              stroke-linecap:round; transition:transform .5s var(--ease); }}
.theme:hover svg {{ transform:rotate(25deg); }}
.masthead h1 {{ font:800 clamp(2.5rem, 9vw, 5.4rem)/.98 var(--serif); letter-spacing:-.02em;
                margin:22px 0 10px; }}
.masthead h1 em {{ font-style:italic; font-weight:500; }}
.dek {{ font:400 clamp(1.08rem, 2.4vw, 1.32rem)/1.5 var(--serif); color:var(--ink-2);
        max-width:640px; margin:0 auto 26px; }}
.masthead .rule {{ border:0; border-top:1px solid var(--ink); border-bottom:3px double var(--ink);
                   height:5px; margin:0; }}
.alert {{ font:600 .95rem/1.4 var(--ui); background:var(--warn-bg); color:var(--warn);
          border-radius:14px; padding:12px 16px; margin:20px 0 0; text-align:left; }}

/* Front page: at-a-glance beside how-big. */
.front {{ display:grid; grid-template-columns:1fr; gap:22px; margin:30px 0 8px; }}
@media (min-width:860px) {{ .front {{ grid-template-columns:1.05fr 1fr; }} }}
.glance, .scale, .chart {{ background:var(--sheet); border:1px solid var(--rule);
  border-radius:22px; box-shadow:0 18px 40px -30px var(--shadow);
  transition:transform .35s var(--ease), box-shadow .35s var(--ease), background-color .4s; }}
.glance, .scale {{ padding:22px; min-width:0; }}
.glance:hover, .scale:hover, .chart:hover {{ transform:translateY(-3px);
  box-shadow:0 26px 50px -30px var(--shadow); }}
.glance {{ display:flex; flex-direction:column; }}
.glance ol {{ list-style:none; margin:0; padding:0; flex:1; display:flex; flex-direction:column;
              justify-content:space-around; }}
.glance li + li {{ border-top:1px solid var(--rule); }}
.glance a {{ display:grid; grid-template-columns:auto 1fr; gap:6px 14px; align-items:center;
             padding:14px 8px; color:var(--ink); text-decoration:none; border-radius:12px;
             transition:background .25s, padding .3s var(--ease); }}
.glance a:hover, .glance a:focus-visible {{ background:var(--accent-soft); padding-left:14px; }}
.glance .q {{ font:600 1.06rem/1.3 var(--ui); }}
.glance .chip {{ grid-column:2; justify-self:start; }}
.num {{ font:italic 500 1.05rem/1 var(--serif); color:var(--ink-2); }}
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
                      animation:grow 1.2s var(--ease) both .35s; }}
.scale li:first-child .bar::after {{ background:var(--ink); }}
.note {{ font:400 .9rem/1.5 var(--ui); color:var(--ink-2); margin:18px 0 0; }}

/* Stories: one per worry, set like newspaper sections. */
.story {{ border-top:3px double var(--ink); padding:34px 0 30px; margin-top:34px;
          scroll-margin-top:12px; }}
.story header {{ display:flex; align-items:baseline; gap:16px; margin-bottom:22px; }}
.story header .num {{ font-size:1.6rem; }}
.story h2 {{ font:800 clamp(1.9rem, 4.6vw, 3rem)/1.05 var(--serif); letter-spacing:-.015em;
             margin:0; }}
.cols {{ display:grid; grid-template-columns:1fr; gap:22px; }}
@media (min-width:860px) {{
  .cols {{ grid-template-columns:minmax(260px, .8fr) 1.2fr; gap:40px; }}
  .cols .text {{ border-left:1px solid var(--rule); padding-left:40px; }}
}}
.big {{ font:800 clamp(1.6rem, 4vw, 2.3rem)/1.12 var(--ui); letter-spacing:-.02em;
        margin:0 0 14px; font-variant-numeric:tabular-nums; }}
.lead {{ font:600 1.22rem/1.5 var(--serif); margin:0 0 12px; }}
.lead::first-letter {{ font:800 3.3em/.8 var(--serif); float:left; margin:.07em .08em 0 0; }}
.text p:not(.lead) {{ color:var(--ink-2); margin:0; }}
.chip {{ display:inline-flex; align-items:center; gap:8px; border-radius:99px; padding:6px 14px;
         font:700 .86rem/1.25 var(--ui); transition:transform .25s var(--ease); }}
.chip::before {{ content:""; flex:none; width:8px; height:8px; border-radius:50%;
                 background:currentColor; }}
.good {{ color:var(--good); background:var(--good-bg); }}
.warn {{ color:var(--warn); background:var(--warn-bg); }}
.neutral {{ color:var(--neutral); background:var(--neutral-bg); }}
.chart {{ margin:28px 0 0; padding:18px 14px 10px; }}
/* Fixed-height box: Chart.js with maintainAspectRatio false sizes to its parent. */
.chart .plot {{ position:relative; height:260px; }}
.chart figcaption {{ font:600 .82rem/1.4 var(--ui); color:var(--ink-2); padding-top:6px; }}

/* One panel for method and sources; opens smoothly where the browser supports it. */
.more {{ margin-top:20px; background:var(--sheet); border:1px solid var(--rule);
         border-radius:18px; font:400 .95rem/1.55 var(--ui); interpolate-size:allow-keywords;
         transition:border-color .3s; }}
.more:hover {{ border-color:var(--accent); }}
.more::details-content {{ block-size:0; overflow:hidden;
  transition:block-size .45s var(--ease), content-visibility .45s allow-discrete; }}
.more[open]::details-content {{ block-size:auto; }}
.more summary {{ cursor:pointer; font-weight:700; padding:14px 18px; list-style:none;
                 display:flex; justify-content:space-between; align-items:center;
                 border-radius:18px; }}
.more summary::-webkit-details-marker {{ display:none; }}
.more summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
.more summary::after {{ content:""; width:9px; height:9px; border-right:2px solid currentColor;
  border-bottom:2px solid currentColor; transform:translateY(-3px) rotate(45deg);
  transition:transform .35s var(--ease); }}
.more[open] summary::after {{ transform:translateY(2px) rotate(225deg); }}
.more-body {{ display:grid; grid-template-columns:1fr; gap:6px 32px; padding:0 18px 16px; }}
@media (min-width:760px) {{ .more-body {{ grid-template-columns:1.3fr 1fr; }} }}
.more[open] .more-body {{ animation:fade .45s var(--ease); }}
.more h3 {{ font:700 .74rem/1 var(--ui); letter-spacing:.14em; text-transform:uppercase;
            color:var(--ink-2); margin:6px 0 10px; }}
.more ul {{ margin:0 0 8px; padding-left:18px; color:var(--ink-2); }}
.more li + li {{ margin-top:6px; }}
.src li span {{ display:block; font-size:.82rem; color:var(--ink-2); }}

/* Spotted this week: AI-extracted claims, each with its verified quote. */
.spotted {{ border-top:3px double var(--ink); margin-top:34px; padding-top:28px; }}
.spot-head {{ font:800 clamp(1.5rem, 3.6vw, 2.1rem)/1.15 var(--serif); margin:0 0 8px; }}
.ai {{ font:400 .88rem/1.5 var(--ui); color:var(--ink-2); margin:0 0 18px; max-width:720px; }}
.claims {{ list-style:none; margin:0; padding:0; display:grid; gap:14px;
           grid-template-columns:repeat(auto-fill, minmax(min(100%, 300px), 1fr)); }}
/* One swipeable row instead of a tall grid: each card a fixed width, snapping into place. */
.scroller {{ display:flex; overflow-x:auto; scroll-snap-type:x mandatory;
             overscroll-behavior-x:contain; padding:4px 2px 14px; scrollbar-width:thin; }}
.scroller .claim {{ flex:0 0 min(84%, 320px); scroll-snap-align:start; }}
/* Carousel: the page script adds .js, which swaps the scrollbar for count + progress + arrows
   and fades whichever edge still has cards behind it. */
.carousel.js .scroller {{ scrollbar-width:none; --fl:0px; --fr:56px; padding-bottom:6px;
  -webkit-mask-image:linear-gradient(90deg, transparent, #000 var(--fl),
                                     #000 calc(100% - var(--fr)), transparent);
  mask-image:linear-gradient(90deg, transparent, #000 var(--fl),
                             #000 calc(100% - var(--fr)), transparent); }}
.carousel.js .scroller::-webkit-scrollbar {{ display:none; }}
.carousel.js .scroller.mid, .carousel.js .scroller.end {{ --fl:40px; }}
.carousel.js .scroller.end {{ --fr:0px; }}
.car-bar {{ display:flex; align-items:center; gap:12px; margin:0 0 14px; }}
.car-bar[hidden] {{ display:none; }}
.car-count {{ font:700 .78rem/1 var(--ui); letter-spacing:.08em; color:var(--ink-2);
              font-variant-numeric:tabular-nums; white-space:nowrap; }}
.car-track {{ flex:1; height:3px; border-radius:99px; background:var(--rule); overflow:hidden; }}
.car-fill {{ display:block; height:100%; width:0; border-radius:inherit; background:var(--accent);
             transition:width .35s var(--ease); }}
.car-btn {{ inline-size:40px; block-size:40px; display:grid; place-items:center; flex:none;
            border-radius:50%; border:1px solid var(--rule); background:var(--sheet);
            color:var(--ink); cursor:pointer; box-shadow:0 2px 10px -4px var(--shadow);
            transition:transform .25s var(--ease), background .25s, opacity .25s; }}
.car-btn:hover:not(:disabled) {{ transform:translateY(-1px); background:var(--accent-soft); }}
.car-btn:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
.car-btn:disabled {{ opacity:.35; cursor:default; box-shadow:none; }}
.car-btn svg {{ width:18px; height:18px; fill:none; stroke:currentColor; stroke-width:2.2;
                stroke-linecap:round; stroke-linejoin:round; }}
.car-btn.prev svg {{ transform:scaleX(-1); }}
.scroller:focus-visible {{ outline:2px solid var(--accent); outline-offset:4px;
                           border-radius:18px; }}
.claim {{ background:var(--sheet); border:1px solid var(--rule); border-radius:18px;
          padding:16px 18px; display:flex; flex-direction:column; gap:8px;
          transition:transform .3s var(--ease), border-color .3s; }}
.claim:hover {{ transform:translateY(-2px); border-color:var(--accent); }}
.claim blockquote {{ margin:0; padding-left:12px; border-left:3px solid var(--accent);
                     font:italic 400 1.08rem/1.5 var(--serif); color:var(--ink); }}
.claim .what {{ font:400 .88rem/1.4 var(--ui); color:var(--ink-2); margin:0; }}
.claim .what span {{ font:700 .68rem/1 var(--ui); letter-spacing:.12em; text-transform:uppercase;
                     margin-right:4px; }}
.claim blockquote::before {{ content:"“"; }}
.claim blockquote::after {{ content:"”"; }}
.claim .who {{ font:400 .85rem/1.4 var(--ui); color:var(--ink-2); margin:0; }}
.claim .tags {{ display:flex; flex-wrap:wrap; gap:6px 8px; align-items:center; margin:2px 0 0; }}
.tag {{ font:700 .72rem/1 var(--ui); letter-spacing:.1em; text-transform:uppercase;
        color:var(--ink-2); border:1px solid var(--rule); border-radius:99px; padding:5px 9px; }}
.claim .chip {{ font-size:.76rem; padding:4px 10px; }}
.rel {{ font:600 .82rem/1.2 var(--ui); }}
.host {{ font:600 .74rem/1 var(--ui); color:var(--ink-2); border:1px solid var(--rule);
         border-radius:6px; padding:2px 6px; margin-left:4px; white-space:nowrap; }}
.changed {{ font:400 .92rem/1.6 var(--ui); color:var(--ink-2); padding-left:18px; }}
.spotted h3, .recent h3 {{ font:700 .74rem/1 var(--ui); letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink-2); margin:22px 0 12px; }}
.recent {{ margin-top:22px; }}

footer {{ border-top:3px double var(--ink); margin-top:20px; padding-top:18px;
          font:400 .9rem/1.6 var(--ui); color:var(--ink-2); columns:2 300px; column-gap:40px;
          column-rule:1px solid var(--rule); }}
footer p {{ margin:0 0 10px; break-inside:avoid; }}

@keyframes grow {{ from {{ width:0; }} }}
@keyframes rise {{ from {{ opacity:0; transform:translateY(14px); }} }}
@keyframes fade {{ from {{ opacity:0; transform:translateY(-6px); }} }}
.masthead, .front > * {{ animation:rise .8s var(--ease) both; }}
.front > :nth-child(1) {{ animation-delay:.12s; }}
.front > :nth-child(2) {{ animation-delay:.22s; }}
/* Scroll reveal: only once the script runs, so the page never hides content without it. */
.js .reveal {{ opacity:0; transform:translateY(24px);
               transition:opacity .8s var(--ease), transform .8s var(--ease); }}
.js .reveal.in {{ opacity:1; transform:none; }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation:none !important; transition:none !important; }}
  .js .reveal {{ opacity:1; transform:none; }}
  html {{ scroll-behavior:auto; }}
}}
</style></head><body>
<div class="page">
<header class="masthead">
  <div class="edition"><span>Independent · Updated daily</span>
    <span>Data as of {escape(as_of_txt)} MT</span>
    <button class="theme" id="theme-toggle" type="button" aria-label="Switch to dark mode">
      <span class="ico">{MOON}</span><span class="txt">Dark</span></button></div>
  <h1>Meta in Alberta: <em>claims vs data</em></h1>
  <p class="dek">Meta is building a large AI data centre in Sturgeon County. We check the
  worries people raise, and the promises the government makes, against Alberta grid data.</p>
  <hr class="rule">
  {stale}
</header>
<div class="front">{_glance(data["cards"], w)}{_scale(data["scale"])}</div>
{_spotted(w)}
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

// Scroll reveal; without IntersectionObserver everything is shown at once.
const items = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window) {{
  const io = new IntersectionObserver(es => es.forEach(e => {{
    if (e.isIntersecting) {{ e.target.classList.add("in"); io.unobserve(e.target); }}
  }}), {{rootMargin: "0px 0px -8% 0px"}});
  items.forEach(el => io.observe(el));
}} else items.forEach(el => el.classList.add("in"));

// Carousels: count, progress and arrows; edge fades only where cards are hidden.
document.querySelectorAll(".carousel").forEach(car => {{
  const row = car.querySelector(".scroller"), cards = row.children, n = cards.length;
  const bar = car.querySelector(".car-bar"), count = car.querySelector(".car-count");
  const fill = car.querySelector(".car-fill"), [prev, next] = car.querySelectorAll(".car-btn");
  const calm = matchMedia("(prefers-reduced-motion: reduce)");
  car.classList.add("js"); bar.hidden = false;
  function update() {{
    const step = n > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : row.clientWidth;
    const max = row.scrollWidth - row.clientWidth, x = row.scrollLeft;
    const first = Math.round(x / step);
    const shown = Math.max(1, Math.floor((row.clientWidth + 8) / step));
    const last = x >= max - 2 ? n : Math.min(n, first + shown);
    count.textContent = n <= shown ? `${{n}} of ${{n}}` : `${{first + 1}}–${{last}} of ${{n}}`;
    fill.style.width = `${{100 * (x + row.clientWidth) / row.scrollWidth}}%`;
    prev.disabled = x <= 2; next.disabled = x >= max - 2;
    row.classList.toggle("mid", x > 2 && x < max - 2); row.classList.toggle("end", x >= max - 2);
  }}
  [prev, next].forEach(b => b.addEventListener("click", () => row.scrollBy({{
    left: b.dataset.dir * row.clientWidth * .9, behavior: calm.matches ? "auto" : "smooth"}})));
  row.addEventListener("scroll", update, {{passive: true}});
  addEventListener("resize", update); update();
}});

// Theme switch: follows the system until the visitor picks, then remembers the pick.
const root = document.documentElement, btn = document.getElementById("theme-toggle");
const sun = {json.dumps(SUN)}, moon = {json.dumps(MOON)};
const isDark = () => root.dataset.theme ? root.dataset.theme === "dark"
  : matchMedia("(prefers-color-scheme: dark)").matches;
function syncButton() {{
  const dark = isDark();
  btn.querySelector(".ico").innerHTML = dark ? sun : moon;
  btn.querySelector(".txt").textContent = dark ? "Light" : "Dark";
  btn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
}}
btn.addEventListener("click", () => {{
  root.dataset.theme = isDark() ? "light" : "dark";
  try {{ localStorage.setItem("theme", root.dataset.theme); }} catch (e) {{}}
  syncButton(); drawCharts();
}});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {{
  if (!root.dataset.theme) {{ syncButton(); drawCharts(); }}
}});
syncButton();
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const C = {charts};
const made = [];
function drawCharts() {{
  if (!window.Chart) return;
  made.splice(0).forEach(ch => ch.destroy());
  const css = getComputedStyle(root), v = name => css.getPropertyValue(name).trim();
  Chart.defaults.font.family = "Figtree, system-ui, sans-serif";
  Chart.defaults.color = v("--ink-2");
  for (const [id, c] of Object.entries(C)) {{
    const el = document.getElementById("chart-" + id); if (!el) continue;
    let box = el.parentElement;
    if (!box.classList.contains("plot")) {{
      box = document.createElement("div"); box.className = "plot";
      el.replaceWith(box); box.appendChild(el);
    }}
    made.push(new Chart(el, {{type: c.type, data: {{labels: c.labels,
      datasets: Object.entries(c.series).map(([label, data]) => ({{label, data,
        borderColor: v("--accent"),
        backgroundColor: c.type === "bar" ? v("--accent") : v("--accent-soft"),
        fill: c.type === "line" ? "origin" : false, tension: .25, borderWidth: 2,
        borderRadius: 3, pointRadius: 0, pointHoverRadius: 5}}))}},
      options: {{maintainAspectRatio: false,
        animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false
          : {{duration: 900, easing: "easeOutQuart"}},
        interaction: {{mode: "index", intersect: false}},
        plugins: {{legend: {{display: false}}}},
        scales: {{x: {{ticks: {{maxTicksLimit: box.clientWidth < 500 ? 4 : 7, maxRotation: 0}},
                      grid: {{display: false}}}},
                  y: {{grid: {{color: v("--rule")}}, border: {{display: false}}}}}}}}}}));
  }}
}}
drawCharts();
</script></body></html>"""
