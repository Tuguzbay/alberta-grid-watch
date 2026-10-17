# Progress & next steps

_Last updated: 2026-10-16._ This is the hand-off file: read it first when resuming.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Scaffold, source checks, Docker (FastAPI + Postgres/pgvector), CI | ✅ done |
| 1 | `hourly` table, backfill + daily ingest, quality report | ✅ done |
| 2 | Next-day price/load forecasts vs baselines; supply cushion; emissions & water | ✅ done |
| 3 | Live daily forecasts, model-health page (`/`, `/api/health`), scheduled task | ✅ done |
| 4 | RAG assistant over AESO / AUC / Government of Alberta documents | ⏭ next |
| 5 | Bill & scenario simulator (clearly hypothetical) | ⬜ |
| 6 | Deploy: Supabase, hosted API, GitHub Actions schedule, architecture diagram | ⬜ |

Repo: https://github.com/Tuguzbay/alberta-grid-watch (public). Push over HTTPS (Git Credential Manager); there's no SSH key on this PC.

## What runs by itself

- Windows scheduled task **AlbertaGridWatchDaily**, 10:00 daily (PC on Alberta time). It runs `scripts/run_daily.ps1`: loads `.env`, starts the Docker `db` container, runs `scripts/daily.py`, and appends to `logs/daily.log`. A missed run starts when the PC is next on. It needs Docker Desktop running.
  - Check: `Get-ScheduledTaskInfo AlbertaGridWatchDaily` and `logs/daily.log` (each run ends with `ok` or `FAILED: …`).
  - Re-register: `powershell -File scripts/register_task.ps1`. Remove: `Unregister-ScheduledTask AlbertaGridWatchDaily`.
- Health page: `docker compose up -d`, then http://localhost:8000/. It switches from backtest to live numbers once 14 live days are scored (~2026-10-31).

## Resume checklist

1. Start Docker Desktop, then `docker compose up -d`.
2. Check `logs/daily.log` to confirm the scheduled runs succeeded. The page shows a warning if data is >36 h stale.
3. `pytest` (DB tests need Postgres up).

## Next steps

### Housekeeping (quick)
- [ ] After ~2 weeks of live runs: add an "AESO day-ahead (frozen at 10:00)" row to the load comparison. `daily.py` stores it as model `aeso`, source `live`.

### Phase 4: RAG assistant
- [ ] Pick the document set (AESO large-load / interim connection policy, AUC decisions, GoA data-centre pages and regulations) and record the source URL and date for each.
- [ ] Ingest: download → chunk → embed → pgvector table (`documents`, `chunks`). Choose the embedding model (local vs API) and note its cost.
- [ ] Answer endpoint: retrieve → answer **only** from retrieved chunks with citations; abstain when nothing relevant clears a score threshold.
- [ ] Eval set: ~30 questions with expected sources, including ones the documents don't answer (must abstain). Report citation accuracy and abstention rate.

### Phase 5: bill & scenario simulator
- [ ] Bill: energy (pool-price pass-through) + transmission + distribution + riders for a typical ~600 kWh/month household; cite the rate sources.
- [ ] Scenarios: reuse `cushion.scenario` and `impacts.footprint`; sliders for added MW, share served by own generation, and gas vs grid supply. Label everything hypothetical.
- [ ] Still-open data point: the transmission-fee claim (Meta ~$200M/yr in fees vs "up to 6% off" transmission costs). This needs AESO's total transmission revenue requirement as the denominator.

### Phase 6: deploy
- [ ] Supabase Postgres (+pgvector); run the backfill against it (~16 min).
- [ ] Host the API (e.g. Render/Fly/Railway free tier). The Dockerfile already reads `$PORT`.
- [ ] GitHub Actions cron for `daily.py` against Supabase. Cron runs in UTC, so add a guard for the 10:00 MT DST shift. Then retire the Windows task.
- [ ] README: architecture diagram, live URL, data-terms note (AESO non-commercial).

## Known caveats (keep saying these)

- **Price model:** about 11% better than a 30-day same-hour average, but it misses spikes (>$200/MWh) by ~$440. Spikes are ~2.5% of hours and ~36% of price.
- **AESO's stored load forecast:** it's revised near real time (~0.3% error), so it isn't a day-ahead baseline.
- **Supply cushion:** it ignores wind, solar and imports, and it's a correlation, not causation.
- **Impacts:** they're an upper bound on energy (flat load) and a lower bound on emissions (best-gas factor).
- **Reruns of `daily.py`:** a rerun after 10:00 retrains on the extra settled hours and replaces that day's live forecast. Features still respect the 10:00 cutoff.
- **AESO API limits:** 366 days per request, capacity data in 30-day chunks, metered volume ~17 days. AESO data terms are non-commercial/educational.
