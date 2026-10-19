# Alberta Grid & Data Centre Watch

**Meta in Alberta: claims vs data.** A public page, rebuilt every day, that checks the worries people raise about Meta's AI data centre in Sturgeon County, and the promises the government makes about it, against Alberta grid data and public documents.

**Live:** https://tuguzbay.github.io/alberta-grid-watch/ (rebuilt daily)

> Scenario outputs are **illustrative**, not predictions, and nothing here attributes a causal price impact to any specific project.

How it runs, what needs maintenance, and the caveats: [PROGRESS.md](PROGRESS.md).

## Parts
1. **Claims page** (the live site): four questions (blackouts, power bills, emissions, water), each with a headline number, a verdict in plain words ("Less backup than last year", "The promised 6% cut adds up"), a chart, "How we know" and its sources, plus a "How big is it?" scale strip. Verdicts come from fixed rules over the numbers, never from a model. Broadsheet-meets-product-page design, light/dark switch.
   - **Power bills:** the government says Meta pays ~$200M a year in transmission fees, cutting the transmission part of household bills by up to 6%. The card checks the share against AESO's 2026 transmission cost ($2.64B, so 7.6%) and recomputes the fee itself from AESO's 2026 Rate DTS: **$194–198M a year** for 970 MW, so the government's figure checks out.
   - **Meta's size:** per the government's [By the numbers](https://www.alberta.ca/datacentres/numbers) page, **970 MW** is Meta's AESO-approved phase 1 grid allocation and **1,800 MW** the campus draw at full build-out (grid plus on-site generation, no date given). The Greenlight gas plant is 932 MW nameplate. The blackouts card and scale strip use 970 MW (what the grid carries). Emissions and water headlines are phase 1, with the full build-out figure beside them.
2. **Claim watch**: every day, Claude Haiku finds new articles and changed official documents and extracts the claims they make. A claim is published only if its quote appears word for word in the source. Shown in "Spotted this week" (a swipeable carousel) and inside each card. Each card leads with the verified quote; Haiku's one-line summary follows, marked "AI summary". Source links open the article scrolled to the quote and highlight it.
3. **Pool price & demand forecasting**: next-day hourly forecasts against simple baselines, with a model-health page (`health.html`, same look as the claims page).
4. **Document search**: an extractive `/api/ask` over the AESO, AUC and Government of Alberta documents in [rag/sources.csv](rag/sources.csv). It runs locally and isn't on the public page.

## Data sources
| Source | Use | Terms |
|---|---|---|
| [AESO public API](https://developer-apim.aeso.ca/) | pool price, Alberta Internal Load | free key; non-commercial/educational use |
| [Open-Meteo](https://open-meteo.com/) | hourly weather, Edmonton & Calgary | free, non-commercial, CC BY 4.0, <10k calls/day |
| AESO / AUC / GoA documents ([rag/sources.csv](rag/sources.csv)) | document search, claim sources | public documents; quoted with source links |
| News found by Claude Haiku web search | claim watch | short verbatim quotes with links to the original |
| [Claude API](https://platform.claude.com/) (`claude-haiku-4-5`) | finding articles, extracting claims | paid, about $1–3/month, capped in code |

## Dev setup
```bash
cp .env.example .env            # add AESO_API_KEY
python -m venv .venv && . .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
pytest                          # offline tests (DB tests skip if Postgres isn't up)
pytest -m live                  # hits real AESO API
set -a; . ./.env; set +a        # load the key into the shell
python scripts/check_sources.py # check every data source responds
docker compose up --build       # API on :8000, Postgres+pgvector on :5432
python scripts/ingest.py --start 2020-01-01   # backfill `hourly` (~1 min), prints quality report
python scripts/ingest.py        # daily update: re-fetches last 7 days (safe to rerun)
python scripts/backtest.py      # walk-forward backtest, rewrites Results below
python scripts/cushion.py       # supply-cushion analysis, rewrites its README section
python scripts/impacts.py       # emissions/water arithmetic, rewrites its README section
python scripts/daily.py         # ingest + forecast tomorrow (safe to rerun)
# model-health page: http://localhost:8000/  (JSON: /api/health)
python scripts/rag_ingest.py    # fetch, chunk, embed rag/sources.csv (--force after chunking changes)
python scripts/rag_eval.py      # retrieval eval + abstention threshold sweep
curl -X POST localhost:8000/api/ask -H 'content-type: application/json' -d '{"q":"What is a tethered data centre?"}'
python scripts/watch.py         # claim watch (needs ANTHROPIC_API_KEY; skips cleanly without)
python scripts/build_site.py    # writes site/ (index.html, health.html, data.json) + snapshot
DATABASE_URL="$SUPABASE_URL" python scripts/watch.py   # run against production (Supabase)
```

## Architecture
```
GitHub Actions, daily at 10:05 Mountain time (.github/workflows/daily.yml)
  should_run.py   guard: after 10:00 local and not yet issued today (or a manual run)
  daily.py        AESO + Open-Meteo -> Supabase `hourly`; next-day forecast -> `forecasts`
  watch.py        official docs in rag/sources.csv re-checked (visible-text fingerprint)
                  + Haiku web search -> our fetch -> Haiku extraction -> whole-word quote check
                  -> `articles` / `claims`
  build_site.py   claims.py (numbers + verdict rules) + claims_page.py -> site/index.html
                  page.py -> site/health.html; data.json; snapshots/YYYY-MM-DD.json (committed)
  deploy-pages    site/ -> https://tuguzbay.github.io/alberta-grid-watch/
Supabase Postgres + pgvector: hourly, forecasts, documents, chunks, articles, claims
```
If the data update or claim watch fails, the page still rebuilds from the last good data (with a stale warning after 36 h) and the run fails afterwards, so GitHub emails.

## Results
<!-- results:start -->
Next-day forecasts issued 10:00 MT on D-1, monthly walk-forward, 2025-01-01 to 2026-10-16 (UTC). Test hours use day-ahead *forecast* weather only. Regenerate with `python scripts/backtest.py`.

**load_mw** (MW), 15,689 hours

| model | MAE | RMSE | MAPE % |
|---|---:|---:|---:|
| hgb | 158.8 | 205.6 | 1.5 |
| two_days_ago | 300.0 | 390.3 | 2.9 |
| last_week | 316.6 | 409.8 | 3.0 |

**pool_price** ($/MWh), 15,688 hours

| model | MAE | RMSE | MAE when price > $200 |
|---|---:|---:|---:|
| hgb | 32.3 | 88.2 | 436.4 |
| mean_30d | 36.3 | 95.3 | 480.4 |
| two_days_ago | 44.2 | 130.0 | 500.5 |
| last_week | 45.2 | 130.2 | 493.7 |
<!-- results:end -->

**Reading these honestly (2025-01 to 2026-10 run):**
- Load: the model roughly halves the naive baselines' error (1.5% vs 2.9% MAPE).
- Price: the model beats a 30-day same-hour average by ~11% MAE, helped by day-ahead hub-height
  wind/solar-radiation forecasts at the southern wind/solar clusters and AESO outage data.
  It still misses spikes by ~$440/MWh: hours above $200 are ~2.5% of hours but ~36% of total
  price, and depend on forced outages, imports and offer behaviour the model can't see a day ahead.
- AESO's own load forecast is **not** a baseline: its stored values have ~0.3% error since 2022,
  so they appear to be revised close to real time, not frozen at day-ahead.

## Supply cushion: what a large new load does to grid headroom
<!-- cushion:start -->
Hourly data 2025-01-01 to 2026-10-17, 15,695 hours. **Headroom** = available dispatchable capability (gas, hydro, storage, other, after outages) minus Alberta Internal Load. It ignores wind, solar and imports, so the real cushion is larger. Regenerate with `python scripts/cushion.py`.

**Price by headroom** (observed)

| headroom (MW) | hours | mean price ($/MWh) | hours > $200 |
|---|---:|---:|---:|
| -2,000 to -1,000 | 19 | 193 | 21% |
| -1,000 to 0 | 1,011 | 78 | 8% |
| 0 to 1,000 | 4,467 | 54 | 5% |
| 1,000 to 2,000 | 6,373 | 32 | 1% |
| 2,000 to 3,000 | 3,446 | 23 | 0% |
| 3,000 to 4,000 | 379 | 18 | 0% |

**Illustrative: add a flat, always-on load with no new generation**

| added load | reference | hours headroom < 0 | curve-implied mean price | expected hours > $200 |
|---|---|---:|---:|---:|
| none | today | 1,030 | $39 | 394 |
| 500 MW | smaller reference point | 2,870 | $49 | 615 |
| 1,200 MW | AESO interim large-load allocation | 6,744 | $64 | 941 |
| 1,600 MW | bridging allowance from the grid | 9,343 | $73 | 1,097 |

Not a forecast and not about any one project. It reads prices off the observed price-vs-headroom relationship, which is a correlation: low-headroom hours are also high-demand, often cold hours. It assumes nothing else changes: no new generation (Alberta's policy expects data centres to bring their own), no change in imports, wind, solar, or how generators offer. Hours pushed below the lowest well-observed headroom (3,308 in the largest case) are priced at that edge, so the price impact is understated there.
<!-- cushion:end -->

## Emissions and water: if the added load runs on new gas generation
<!-- impacts:start -->
Context from our data: Alberta used **90.4 TWh** in 2025; the record hourly load is **12,785 MW** (2025-12-11 17:00 MT). Each row assumes the load runs flat all year (an upper bound; real data centres run close to flat) and every MWh comes from new combined-cycle gas at Alberta's best-gas benchmark (a lower bound on emissions; simple-cycle plants emit more). Regenerate with `python scripts/impacts.py`.

| added load | reference | TWh/yr | % of AB use | CO₂ Mt/yr | % of AB power CO₂ (2023) | plant water, cooling tower (billion L/yr) | ≈ Albertans' water use | dry cooling (billion L/yr) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 500 MW | smaller reference point | 4.4 | 5% | 1.6 | 8% | 2.2–5.0 | 18,000–41,000 people | 0.00–0.07 |
| 1,200 MW | AESO interim large-load allocation | 10.5 | 12% | 3.9 | 20% | 5.2–11.9 | 43,000–99,000 people | 0.00–0.16 |
| 1,600 MW | bridging allowance from the grid | 14.0 | 16% | 5.2 | 27% | 6.9–15.9 | 57,000–132,000 people | 0.00–0.21 |
| 20,000 MW | all proposals reported (~20 GW) | 175.2 | 194% | 64.8 | 338% | 86.2–198.9 | 716,000–1,652,000 people | 0.00–2.65 |

The ~20 GW of proposals is **1.6×** Alberta's record peak load. Water is the gas plant's cooling consumption only; data-centre cooling is extra and depends on design (the province's "less than a golf course" figure refers to the data centre, not its power plant). The MW references only set the size: grid power drawn under the bridging allowance would come from today's mix, not new CCGT.

Sources:
- CO2 0.37 t/MWh: Alberta TIER regulation, electricity high-performance benchmark
- Water gal/MWh: Macknick et al. 2012, Environ. Res. Lett. 7 045802 (NREL)
- AB electricity 19.2 Mt (2023): Canada National Inventory Report 2025
- 330 L/person/day: Statistics Canada, Survey of Drinking Water Plants 2021
- ~20 GW proposed: National Observer (2026-03-23) and DeSmog (2026-07-23) reporting
<!-- impacts:end -->

## Document search: how well it works
Local embeddings (`BAAI/bge-small-en-v1.5` via fastembed, free, CPU), 313 chunks of about 200 words, cosine search in pgvector. [rag/eval.jsonl](rag/eval.jsonl) has 34 questions: 27 the documents answer and 7 they don't (4 off-topic, 3 on-topic but not covered).

| Threshold | Answerable: right source returned | Unanswerable: abstained |
|---|---|---|
| 0.68 | 24/27 | 4/7 |
| **0.70 (used)** | **23/27** | **6/7** |
| 0.72 | 22/27 | 6/7 |

Caveats:
- **Tuned in-sample.** The threshold was picked on these same 34 questions, so expect worse on new ones. The scores are tightly bunched, so rewording a question can drop it under the line. "Why did the AUC *reject* the Olds power plant?" scores 0.674 and gets abstained on, while "...*deny* the Synapse power plant in Olds?" scores 0.768.
- **Similarity measures topic, not whether the answer is there.** "What is the AESO's total transmission revenue requirement for 2026?" isn't answered by any document, but it scores 0.77 against the connection guide, so the search returns off-target passages instead of abstaining. Read the passage before you trust it.
- **Some sources are advocacy.** The Government of Alberta datacentres pages are written to persuade (for example, "Not one dollar ... is charged to your household"). Every passage shows its publisher, so you can weigh it.

## Claim watch: new claims from the news, checked word for word
Every day, Claude Haiku (via Anthropic's web search tool) looks for new articles about Meta's Alberta data centre and Alberta data-centre policy, and re-reads the tracked official documents. The job downloads each article itself and asks Haiku for the claims it makes, each with a quote. **A claim is published only if its quote appears word for word in the article** (after normalising quotes and spacing). Haiku never judges truth: every claim shows "Not checked yet", its source and its quote, under a label saying it was extracted by AI and not reviewed. Bad claims can be hidden by id (`rag/hidden_claims.txt`); hiding also covers the same quote under any other URL, such as a wire story on another outlet. Capped at 3 searches and 8 articles a day, about $1–3/month.

Guards:
- **Downloads:** capped at 25 MB, and only from hosts with public addresses.
- **Duplicates:** http/https and `www.` variants of a URL count as one article.
- **Changed documents:** when an official document changes, its claims whose quote is gone are dropped.
- **Cost:** extraction calls `messages.create` with a JSON schema and validates the answer itself, so the cost summary also counts the tokens of answers that get rejected.

Source links use a URL text fragment (`#:~:text=start,end`). The anchors skip words containing quote marks or brackets, because pages use curly apostrophes where our text has straight ones. They work in Chrome, Edge, Safari and Firefox 131+; older browsers open the top of the page.

First real run (2026-10-18): 4 articles found (1 blocked by its publisher), 17 claims, 0 quotes rejected, $0.093. On a manual read, 2 summaries overstated their quote ("invested" for "plans to invest"), so they were hidden and the prompt was tightened. The quote check protects the quote, not the summary.

