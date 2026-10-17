# Alberta Grid & Data Centre Watch

A public tool that uses real data to answer what large new loads, like proposed AI data centres, could mean for Alberta's grid and power prices.

> Scenario outputs are **illustrative**, not predictions, and nothing here attributes a causal price impact to any specific project.

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
```

## Architecture
_TODO (Phase 6): diagram._

## Results
<!-- results:start -->
Next-day forecasts issued 10:00 MT on D-1, monthly walk-forward, 2025-01-01 to 2026-10-16 (UTC). Test hours use day-ahead *forecast* weather only. Regenerate with `python scripts/backtest.py`.

**load_mw** (MW), 15,688 hours

| model | MAE | RMSE | MAPE % |
|---|---:|---:|---:|
| hgb | 158.8 | 205.6 | 1.5 |
| two_days_ago | 300.1 | 390.4 | 2.9 |
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
