# Progress & next steps

_Last updated: 2026-10-17._ This is the hand-off file: read it first when resuming.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Scaffold, source checks, Docker (FastAPI + Postgres/pgvector), CI | ✅ done |
| 1 | `hourly` table, backfill + daily ingest, quality report | ✅ done |
| 2 | Next-day price/load forecasts vs baselines; supply cushion; emissions & water | ✅ done |
| 3 | Live daily forecasts, model-health page (`/`, `/api/health`), scheduled task | ✅ done |
| 4 | Document search (extractive RAG) over AESO / AUC / GoA documents, `/api/ask` | ✅ built, awaiting your sign-off |
| 5 | Bill & scenario simulator (clearly hypothetical) | ⏭ next |
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

### Phase 4: document search (done 2026-10-17)
- [x] 17 documents in `rag/sources.csv` (7 AESO/AUC, 10 GoA/legislature), each URL checked. Raw copies are in `data/rag/` (gitignored).
- [x] `scripts/rag_ingest.py`: fetch → chunk (200 words, 40 overlap, per page) → local fastembed `bge-small-en-v1.5` (free) → `documents` / `chunks` tables. 313 chunks.
- [x] `POST /api/ask` returns extracted passages plus source/page, or abstains below cosine 0.70. No LLM, chosen 2026-10-17, so there's nothing to hallucinate and no API cost.
- [x] `rag/eval.jsonl` (34 questions) + `scripts/rag_eval.py`: 23/27 right source, 6/7 abstentions correct. Tuned in-sample; caveats are in the README.
- [ ] Possible next steps: hybrid keyword + vector search (names like "Olds"/"Synapse" are missed when reworded); a fresh held-out question set; an `/ask` box on the page; refresh docs on a schedule (`rag_ingest.py` skips unchanged files).
- Missing from the corpus: the final levy law (Bill 12, Financial Statutes Amendment Act (No. 2), 2025). The levy engagement page is the July 2025 consultation.

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
- **Document search:** it's extractive and the threshold was tuned in-sample. A high score means the topic matches, not that the answer is in the passage. GoA datacentres pages are advocacy.
- **AESO API limits:** 366 days per request, capacity data in 30-day chunks, metered volume ~17 days. AESO data terms are non-commercial/educational.
