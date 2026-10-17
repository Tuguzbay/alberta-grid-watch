# Alberta Grid & Data Centre Watch

A public tool that uses real data to answer what large new loads, like proposed AI data centres, could mean for Alberta's grid and power prices.

> Scenario outputs are **illustrative**, not predictions, and nothing here attributes a causal price impact to any specific project.

Status and next steps: [PROGRESS.md](PROGRESS.md).

## Parts
1. **Pool price & demand forecasting**: next-day hourly forecasts compared against simple baselines, with a public model-health page. *(Phases 1–3)*
2. **RAG assistant**: cited answers drawn from AESO, AUC and Government of Alberta documents. It abstains when the documents don't cover a question. *(Phase 4)*
3. **Bill & scenario simulator**: clearly labelled as hypothetical. *(Phase 5)*

## Data sources
| Source | Use | Terms |
|---|---|---|
| [AESO public API](https://developer-apim.aeso.ca/) | pool price, Alberta Internal Load | free key; non-commercial/educational use |
| [Open-Meteo](https://open-meteo.com/) | hourly weather, Edmonton & Calgary | free, non-commercial, CC BY 4.0, <10k calls/day |

## Dev setup
```bash
cp .env.example .env            # add AESO_API_KEY
python -m venv .venv && . .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
pytest                          # offline tests (DB tests skip if Postgres isn't up)
pytest -m live                  # hits real AESO API
set -a; . ./.env; set +a        # load the key into the shell
python scripts/check_sources.py # Phase 0 source check
docker compose up --build       # API on :8000, Postgres+pgvector on :5432
python scripts/ingest.py --start 2020-01-01   # backfill `hourly` (~1 min), prints quality report
python scripts/ingest.py        # daily update: re-fetches last 7 days (safe to rerun)
python scripts/backtest.py      # Phase 2 walk-forward backtest, rewrites Results below
python scripts/cushion.py       # supply-cushion analysis, rewrites its README section
python scripts/impacts.py       # emissions/water arithmetic, rewrites its README section
python scripts/daily.py         # 10:00 MT daily: ingest + forecast tomorrow (safe to rerun)
# model-health page: http://localhost:8000/  (JSON: /api/health)
powershell -File scripts/register_task.ps1   # Windows: run daily.py at 10:00 automatically
```

## Architecture
_TODO (Phase 6): diagram._

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
