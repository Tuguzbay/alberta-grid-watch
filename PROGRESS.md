# Status & maintenance

_Last updated: 2026-10-19._ How the project runs, what needs a hand, and the caveats to keep repeating.

**Live:** https://tuguzbay.github.io/alberta-grid-watch/ ("Meta in Alberta: claims vs data")

| Part | State |
|---|---|
| Data pipeline + next-day forecasts | ✅ live, daily on GitHub Actions |
| Claims page: 4 cards, scale strip, rule-based verdicts in plain words, light/dark | ✅ live |
| Bills card: government's ~$200M fee cross-checked against AESO's 2026 Rate DTS ($194–198M) | ✅ live |
| Claim watch: Haiku finds articles, claims kept only with word-for-word quotes | ✅ live since 2026-10-18 |
| Document search `/api/ask` | ✅ built, local only (not on the public page) |
| Bill & scenario simulator | ❌ dropped, replaced by the claims page |

## How it runs

- **GitHub Actions** (`.github/workflows/daily.yml`): crons at 16:05 and 17:05 UTC. `scripts/should_run.py` lets through only the first run on or after 10:00 Mountain time that day, or a manual run. Steps:
  1. `scripts/daily.py`: AESO + weather into `hourly`, then tomorrow's forecast.
  2. `scripts/watch.py`: claim watch.
  3. `scripts/build_site.py`: the page.
  4. Commit `snapshots/` (keeps the repo active for GitHub's 60-day rule), then deploy to GitHub Pages.
  - A failed data update or claim watch still rebuilds and deploys the page, then fails the run so GitHub emails.
  - **Manual run:** Actions → Daily → Run workflow. It takes ~2–3 min; don't cancel it.
- **Secrets** (repo settings → Actions): `AESO_API_KEY`; `DATABASE_URL` (Supabase **session pooler** string, since GitHub runners have no IPv6); `ANTHROPIC_API_KEY`.
- **Local `.env`:** the same keys, with `DATABASE_URL` pointing at local Docker Postgres and `SUPABASE_URL` holding the production string. To run against production: `set -a; . ./.env; set +a; DATABASE_URL="$SUPABASE_URL" python scripts/<x>.py`.
- **Supabase** free tier (Postgres 17 + pgvector). It pauses after about a week without database activity; the daily job keeps it awake. If it ever pauses, restore it from the dashboard (possible within 1 year).

## Routine checks

- **New claims:** read them against their quotes. Hide a bad one by adding its id to `rag/hidden_claims.txt` (ids are in `site/data.json` → `watch.claims[].id`), then push.
- **"Official sources changed"** on the page means a tracked document's text changed. Check whether a number in `FACTS` (`src/gridwatch/claims.py`) came from it and needs updating. Fixed figures never update on their own.
- **Anthropic spend:** expect ≈ $0.05–0.20 per run.

## Coming up

- **~2026-10-31:** the model-health page switches from backtest to live numbers once 14 live days are scored.
- **2026-11:** Alberta moves to UTC-6 all year (tzdata 2026e). The workflows set `PYTHONTZPATH=""` so the `tzdata` package is used; check the first run after the switch.
- **2027-01-01:** AESO's new ISO tariff. Update `transmission_rr` and the `DTS_*` rates in `src/gridwatch/claims.py`, and the two AESO rows in `rag/sources.csv`.

## Known caveats (keep saying these)

- **Price model:** about 11% better than a 30-day same-hour average, but it misses spikes (>$200/MWh) by ~$440. Spikes are ~2.5% of hours and ~36% of price.
- **AESO's stored load forecast:** it's revised near real time (~0.3% error), so it isn't a day-ahead baseline.
- **"Backup" / tight hours:** dispatchable capability minus load. Wind, solar and imports aren't counted, so it's a thinner-cushion signal, not blackout risk, and not evidence about Meta.
- **Impacts:** an upper bound on energy (flat load) and a lower bound on emissions (best-gas factor). Headlines are phase 1 (970 MW); full build-out (1,800 MW) is shown alongside, with no public date.
- **Bills card:** the 7.6% share uses AESO's 2026 revenue requirement ($2,636.9M) and is an upper bound. Our $194–198M fee estimate assumes one point of delivery and the full 970 MW at every monthly system peak, and leaves out operating reserves (~$20M more at today's prices).
- **Claim watch:** AI-extracted, not reviewed by a person. The quote is verified; the summary, speaker and outlet name come from Haiku. The link hostname is shown so a wrong outlet is visible.
- **Document search:** extractive, with the threshold tuned in-sample. A high score means the topic matches, not that the answer is there.
- **AESO API limits:** 366 days per request, capacity data in 30-day chunks, metered volume ~17 days. AESO data terms are non-commercial/educational.
- **Text quoted on the page:** Government of Alberta datacentre pages are advocacy; every quote shows its publisher.
