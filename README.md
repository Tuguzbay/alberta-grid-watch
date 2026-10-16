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
```

## Architecture
_TODO (Phase 6): diagram._

## Results
_TODO (Phase 2+): model vs baselines tables._
