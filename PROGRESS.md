# Progress & next steps

_Last updated: 2026-10-18 (end of day)._ This is the hand-off file: read it first when resuming.

## Where things stand

**Live:** https://tuguzbay.github.io/alberta-grid-watch/ ("Meta in Alberta: claims vs data"). Repo: https://github.com/Tuguzbay/alberta-grid-watch (public). Push over HTTPS via Git Credential Manager; there's no SSH key on this PC. The `gh` CLI isn't installed: use the GitHub web UI, or the public REST API with curl for run status.

| What | State |
|---|---|
| Data pipeline + next-day forecasts (old phases 0–3) | ✅ live, runs daily on GitHub Actions |
| Claims page: 4 cards, scale strip, verdict rules, light/dark, Newsreader type (PRs #1–#3) | ✅ live |
| Claim watch: Haiku finds articles and extracts claims with word-for-word verified quotes (PR #4) | ✅ merged 2026-10-18. **Not on the live page yet:** no Daily run since the merge. The next scheduled run (10:05 MT) publishes it. |
| Document search `/api/ask` (old phase 4) | ✅ built, local only (not on the public page) |
| Bill & scenario simulator (old phase 5) | ❌ dropped, replaced by the claims page |

## Resume checklist (tomorrow)

1. **Check the 10:05 Daily run:** https://github.com/Tuguzbay/alberta-grid-watch/actions/workflows/daily.yml. It should be green, with steps guard → daily → watch → build → deploy.
2. **Check the live page** (hard refresh, Ctrl+F5). "Spotted this week" should list the 15 visible claims from the first run, plus anything new.
3. **Read any new claims** against their quotes. Hide a bad one by adding its id to `rag/hidden_claims.txt` (ids are in `site/data.json` → `watch.claims[].id`, or the Supabase `claims` table), then push.
4. **Check Anthropic spend** in the Console. Expect ≈ $0.05–0.20 per run.

## How it runs

- **GitHub Actions** (`.github/workflows/daily.yml`): crons at 16:05 and 17:05 UTC. `scripts/should_run.py` lets through only the first run on or after 10:00 Mountain time that day, or a manual run. Steps:
  1. `scripts/daily.py`: AESO + weather into `hourly`, then tomorrow's forecast.
  2. `scripts/watch.py`: claim watch.
  3. `scripts/build_site.py`: the page.
  4. Commit `snapshots/` (keeps the repo active for GitHub's 60-day rule), then deploy to GitHub Pages.
  - A failed data update or claim watch still rebuilds and deploys the page, then fails the run so GitHub emails.
  - **Manual run:** Actions → Daily → Run workflow. It takes ~2–3 min; don't cancel it.
- **Secrets** (repo settings → Actions):
  - `AESO_API_KEY`
  - `DATABASE_URL`: Supabase **session pooler** string, since GitHub runners have no IPv6
  - `ANTHROPIC_API_KEY`
- **Local `.env`:** `AESO_API_KEY`, `DATABASE_URL` (local Docker Postgres), `SUPABASE_URL` (production, same pooler string as the secret), `ANTHROPIC_API_KEY`. To run anything against production: `set -a; . ./.env; set +a; DATABASE_URL="$SUPABASE_URL" python scripts/<x>.py`.
- **Supabase** free tier (Postgres 17 + pgvector). It pauses after about a week without database activity, and the daily job keeps it awake. If it ever pauses, restore it from the dashboard (possible within 1 year).
- **Windows task `AlbertaGridWatchDaily`:** superseded by GitHub Actions and still registered. Remove it once Actions has run cleanly for a few days: `Unregister-ScheduledTask AlbertaGridWatchDaily`.

## Claim watch details

- Pipeline (`src/gridwatch/watch.py`):
  1. Haiku (`claude-haiku-4-5`) runs `web_search_20250305`, at most 3 searches.
  2. Each candidate is validated individually, and its URL canonicalised (tracking parameters dropped).
  3. Only new URLs from the last 14 days are kept, at most 8 a day. Only hosts that resolve to public addresses are fetched.
  4. Our code downloads each article. Under 150 words is `unreadable`; over 60k characters is `too_long`, never truncated.
  5. Haiku extracts claims as structured JSON. No tools; the article is treated as data.
  6. **The quote must appear word for word, on whole-word boundaries**, or the claim is dropped.
  7. Results are stored in `articles` / `claims`.
- Official documents: the 18 in `rag/sources.csv` are re-fetched daily. A change in *visible text* (`documents.text_sha`, not raw HTML: AESO's page has a per-request CSRF token) sets `changed_on`. Changed documents wait in a queue (`pending_documents`) until extracted, at most 3 a day.
- Page: "Spotted this week" is one horizontal, swipeable row of cards. Each source link opens the article scrolled to the quote and highlights it (a `#:~:text=` text fragment, anchored on 3+ word runs without quote marks or brackets; works in Chrome, Edge, Safari and Firefox 131+; older browsers just open the page top). Cards show the AI label, quote, speaker, outlet, link hostname, topic, and "Not checked yet". Also "Recent claims on this topic" inside each card, and "Official sources changed".
- First real run (2026-10-18): 4 articles (1 blocked with 403), 17 claims, 0 quotes rejected, $0.093. On a manual read, **2 summaries overstated their quote**, so they were hidden and the prompt tightened. The quote check guarantees the quote, not Haiku's one-line summary.
- Notable claim to follow up: The Energy Mix says the development permit puts the campus at **1.8 GW**. The page uses 970 MW, Meta's approved grid draw.

## Next steps (pick one tomorrow)

- [x] **Quote-first claim cards** (done in PR #6): make the verified quote the card's main text and Haiku's summary the smaller line, since the quote is the only checked part.
- [ ] **The 1.8 GW vs 970 MW question:** decide how the scale strip and cards should present it (970 MW grid draw vs 1.8 GW total campus need; the 932 MW private plant covers the gap?). Needs sources checked first.
- [ ] **Remove the Windows task** after a few clean Actions runs.
- [ ] **Deferred small fixes from the claim-watch review:**
  - cap the download size
  - join all text blocks in the discovery answer (citations can split JSON)
  - count tokens for failed calls in the cost summary
  - merge http/https and `www.` URL duplicates
  - clamp `since` in the discovery prompt
  - drop claims whose quote no longer appears after a document changes
  - hide by claim, not by (url, quote)
- [ ] **Deferred from the claims-page review:**
  - "a cut of that size is partly true" wording
  - bills year-on-year comparison with under 2 years of data
  - `allow_nan=False` in `data.json`
  - cp1251 console crash in `build_site.py` (set `PYTHONIOENCODING=utf-8`)
  - fresh-DB crash in `cushion.scenario`
  - staleness keyed on price only
- [ ] **Model-health page** (`health.html`) still has the old plain look. Restyle it to match. It switches from backtest to live numbers once 14 live days are scored (~2026-10-31).

## Known caveats (keep saying these)

- **Price model:** about 11% better than a 30-day same-hour average, but it misses spikes (>$200/MWh) by ~$440. Spikes are ~2.5% of hours and ~36% of price.
- **AESO's stored load forecast:** it's revised near real time (~0.3% error), so it isn't a day-ahead baseline.
- **"Spare capacity" / tight hours:** dispatchable capability minus load. Wind, solar and imports aren't counted, so it's a thinner-cushion signal, not blackout risk, and not evidence about Meta.
- **Impacts:** an upper bound on energy (flat load) and a lower bound on emissions (best-gas factor).
- **Bills card:** the $200M in transmission fees is the government's figure, not verified. The 7.6% share uses AESO's 2026 revenue requirement ($2,636.9M) and is an upper bound.
- **Claim watch:** AI-extracted, not reviewed by a person. The quote is verified; the summary, speaker and outlet name come from Haiku. The link hostname is shown so a wrong outlet is visible.
- **Document search:** extractive, with the threshold tuned in-sample. A high score means the topic matches, not that the answer is there.
- **Time zone:** tzdata 2026e puts Alberta on UTC-6 all year from November 2026. The workflows set `PYTHONTZPATH=""` so the `tzdata` package (not the runner's system zoneinfo) is used.
- **AESO API limits:** 366 days per request, capacity data in 30-day chunks, metered volume ~17 days. AESO data terms are non-commercial/educational.
- **Text quoted on the page:** Government of Alberta datacentre pages are advocacy; every quote shows its publisher.
