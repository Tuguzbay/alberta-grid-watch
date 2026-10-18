# Claims-vs-Data Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public static page, "Meta in Alberta: claims vs data", rebuilt daily by GitHub Actions from Supabase and served on GitHub Pages.

**Architecture:** `claims.py` turns the `hourly` DataFrame plus fixed, sourced facts into card dicts. `claims_page.py` renders them to one self-contained HTML file. `scripts/build_site.py` writes `site/` and a daily snapshot. A workflow runs `daily.py`, builds, commits the snapshot, and deploys Pages.

**Tech Stack:** Python 3.12, pandas, psycopg, Chart.js 4.4.1 (cdnjs), GitHub Actions, GitHub Pages, Supabase Postgres + pgvector.

**Spec:** `docs/superpowers/specs/2026-10-17-claims-page-design.md`

## Global Constraints

- Plain language first. Every card has a "How we know" `<details>` expander with method and caveats.
- Every fixed number on the page links to its source document via a `rag/sources.csv` key.
- Verdicts come only from rules in `claims.py`, never from a model. Each verdict says what would change it.
- Meta's grid draw is 970 MW, the scenario load used everywhere.
- Charts use Chart.js 4.4.1 from `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js`. No other external scripts.
- The page works at phone width (16px side gutter, no horizontal scroll) and in light and dark mode.
- Footer: link to `health.html`, the repo, the AESO non-commercial/educational data-terms note, "data as of …".
- The existing stale rule applies: no settled price for more than 36 h (`health.STALE_HOURS`) shows a warning.
- No Claude co-author trailers on commits.
- **Spec refinement:** the spec says "run only at 10:00". GitHub cron can be late by up to an hour, so the guard is "local time ≥ 10:00 America/Edmonton and no live forecast issued today, or a manual run". Cron fires at 16:05 and 17:05 UTC. Task 5 updates the spec line.

## Review Focus

1. **Missing recent data** (AESO outage, failed ingest): cards still render from the last good hour and show a stale warning. Pinned in Task 2 (`test_reliability_card_on_stale_frame`) and Task 3 (`test_page_shows_stale_warning`).
2. **No tight hours at all in the comparison window**: the verdict and explanation still read correctly (no "0% more", no divide-by-zero). Pinned in Task 2 (`test_reliability_verdict_zero_tight_hours`).
3. **Transmission revenue requirement not found**: the bills card says "Can't verify yet" with the reason instead of computing a share. Pinned in Task 2 (`test_bills_card_without_denominator`).
4. **Delayed or doubled cron runs across DST**: exactly one real run per local day. Pinned in Task 5 (`test_should_run_*`).
5. **Source text with HTML characters** (`&`, `<`, quotes in titles such as "Phase 2A: Large Load Integration | BYOG Process"): escaped, never injected. Pinned in Task 3 (`test_page_escapes_text`).

---

### Task 1: Research the three open facts

**Files:**
- Modify: `docs/superpowers/specs/2026-10-17-claims-page-design.md` (add a "Research results" section)
- Modify: `rag/sources.csv` (add the transmission-cost source if found)

**Interfaces:**
- Produces: `TRANSMISSION_RR` (annual AESO transmission revenue requirement in $, with year and `rag/sources.csv` key), or the decision that it's unavailable. Also confirmed Supabase pause rule and GitHub 60-day rule, with source URLs.

- [ ] **Step 1:** Find AESO's annual wires-cost / transmission revenue requirement in an AESO ISO tariff application, AESO rate schedule, or AUC tariff decision, preferably for 2025 or 2026. Record the value, year, document title and URL. Verify the number appears in the document itself, not only in news coverage.
- [ ] **Step 2:** If found, add a row to `rag/sources.csv` (key `aeso_tariff_rr`, publisher AESO or AUC) and run `python scripts/rag_ingest.py`. Expected: the new key prints with a chunk count, and no `FETCH FAILED`.
- [ ] **Step 3:** Confirm from Supabase docs the free-tier inactivity pause rule and what counts as activity. Confirm from GitHub docs that scheduled workflows in public repos are disabled after 60 days without repository activity, and that commits count as activity. Record the doc URLs.
- [ ] **Step 4:** Write the findings into the spec under "Research results". If the Supabase rule contradicts the design, stop and raise it with the user before Task 4.
- [ ] **Step 5:** Commit: `git commit -m "Claims page: research results"`

### Task 2: `claims.py`: card data and verdict rules

**Files:**
- Create: `src/gridwatch/claims.py`
- Test: `tests/test_claims.py`

**Interfaces:**
- Consumes: `cushion.headroom(df) -> Series`, `cushion.scenario(h, price, added_mw) -> dict` (keys `hours_headroom_below_zero`, `hours_below_zero_today`, `curve_mean_price_base`, `curve_mean_price_new`, `hours`), `impacts.footprint(mw) -> dict` (keys `co2_mt`, `share_of_ab_electricity_co2`, `water_bl_cooling tower`, `water_bl_dry cooling`, `people_equiv_cooling tower`), `features.TZ`.
- Produces:
  - `META_MW = 970`
  - `FACTS: dict[str, dict]`: each `{"value": float | None, "label": str, "source": str}`. Keys: `meta_mw` (970, `goa_bills`), `edmonton_mw` (1400, `aeso_factsheet`), `requested_mw` (19565, `goa_grid`, label notes "as of 2026-07-30"), `meta_transmission_fees` (200e6, `goa_bills`), `claimed_transmission_cut` (0.06, `goa_bills`), `transmission_rr` (value from Task 1 or `None`, `aeso_tariff_rr` or `""`).
  - `Card = dict` with keys `id, question, headline, verdict, explain, chart, how, sources`. `chart` is `{"type": "line" | "bar", "labels": list[str], "series": {name: list[float | None]}}` or `None`. `how` is `list[str]`. `sources` is `list[str]` of source keys.
  - `scale(df) -> dict`: `{"meta_mw", "edmonton_mw", "requested_mw", "record_mw", "record_ts_local"}`.
  - `reliability_card(df, now: pd.Timestamp) -> Card`
  - `bills_card(df, now: pd.Timestamp) -> Card`
  - `emissions_card() -> Card`
  - `water_card() -> Card`
  - `cards(df, now) -> dict`: `{"scale": ..., "cards": [reliability, bills, emissions, water], "as_of_utc": str, "stale": bool}`. `stale` = last non-null `pool_price` hour older than `health.STALE_HOURS`.

Rules (exact):
- **Reliability.** "Tight hour" = headroom < 0. Compare tight hours from Jan 1 local of `now`'s year to `now` against the same calendar span one year earlier. Headline: `"{n} tight hours in {year} so far"`. Verdict `"Not so far"` if this year ≤ last year, else `"Getting tighter"`. The explanation adds the scenario: `cushion.scenario(h, price, META_MW)` over the last 365 days, "would go from {hours_below_zero_today} to {hours_headroom_below_zero} hours a year with no new supply". Chart: daily minimum headroom, last 90 local days (line). Changes-if text: "would change if tight hours rise above last year's pace."
- **Bills.** Headline: mean pool price over the last 365 days vs the 365 before that, as `"$X/MWh, up/down Y% on the year before"`. If `transmission_rr` is None, verdict is `"Can't verify yet"` and the explanation says the total transmission cost isn't in a public source we could check. Otherwise `share = 200e6 / transmission_rr`, verdict `"Plausible"` if `share >= 0.06`, `"Overstated"` if `share < 0.03`, else `"Partly true"`. The explanation states the share and that it's an upper bound because total transmission costs also grow. Chart: monthly mean pool price since 2020-01 (bar).
- **Emissions.** `f = impacts.footprint(META_MW)`. Headline `"{co2_mt:.1f} Mt CO₂ a year"`. Verdict by `share_of_ab_electricity_co2`: ≥ 0.10 `"Significant"`, ≥ 0.03 `"Noticeable"`, else `"Small"`. No chart.
- **Water.** Headline: cooling-tower range in billion L/yr. Verdict `"Depends on the plant's cooling"`. The explanation contrasts it with the dry-cooling range and notes the government's golf-course claim (`goa_water`) is about the data centre, not its power plant. No chart.

- [ ] **Step 1: Write failing tests** in `tests/test_claims.py` using a synthetic hourly frame (UTC hourly index from 2024-01-01 to 2026-10-16, columns `pool_price`, `load_mw`, `dispatchable_ac`):
  - `test_scale_record_from_data`: record_mw equals the frame's max `load_mw`; meta/edmonton/requested equal 970/1400/19565.
  - `test_reliability_verdict_rises`: more headroom<0 hours in 2026 YTD than 2025 YTD → verdict `"Getting tighter"`, headline contains the 2026 count.
  - `test_reliability_verdict_zero_tight_hours`: headroom always positive → verdict `"Not so far"`, headline `"0 tight hours in 2026 so far"`, no exception, no `"nan"` or `"inf"` in any string field.
  - `test_reliability_card_on_stale_frame`: frame ends 2026-10-10, `now=2026-10-16` → `cards(df, now)["stale"] is True` and all four cards present.
  - `test_bills_card_without_denominator`: with `FACTS["transmission_rr"]["value"] = None` (monkeypatch) → verdict `"Can't verify yet"`.
  - `test_bills_verdict_thresholds`: denominators 2e9 / 5e9 / 1e10 → `"Plausible"` / `"Partly true"` / `"Overstated"`.
  - `test_emissions_card_matches_footprint`: headline contains `f"{impacts.footprint(970)['co2_mt']:.1f}"`; verdict `"Significant"` (share ≈ 0.16).
  - `test_every_card_has_sources_and_how`: each card has non-empty `sources` and `how`, and every source key exists in `rag/sources.csv`.
- [ ] **Step 2:** Run `pytest tests/test_claims.py -v`. Expected: FAIL (`ModuleNotFoundError: gridwatch.claims`).
- [ ] **Step 3:** Implement `src/gridwatch/claims.py` with the interfaces and rules above. Local-time spans use `features.TZ`.
- [ ] **Step 4:** Run `pytest tests/test_claims.py -v`. Expected: all PASS. Then `ruff check .` is clean.
- [ ] **Step 5:** Commit: `git commit -m "Claims page: card data and verdict rules"`

### Task 3: `claims_page.py`: render the page

**Files:**
- Create: `src/gridwatch/claims_page.py`
- Test: `tests/test_claims_page.py`

**Interfaces:**
- Consumes: the `cards(df, now)` dict from Task 2; `sources: dict[str, dict]` mapping key → `{"title", "publisher", "url"}` (rows of `rag/sources.csv`).
- Produces: `render(data: dict, sources: dict[str, dict]) -> str`, one complete HTML document.

Layout: `<title>Meta in Alberta: claims vs data</title>`; header with one-line purpose ("checks the worries and the promises against grid data"); scale strip; four `<article>` cards (question `<h2>`, headline, verdict badge, explanation, optional `<canvas>`, `<details><summary>How we know</summary>…</details>`, source list as `<a href>` showing publisher and title); footer per Global Constraints. Colours are CSS custom properties on `:root`, overridden under `@media (prefers-color-scheme: dark)`. Chart data goes in as JSON with `</` escaped, the same as `page.py`.

- [ ] **Step 1: Write failing tests:**
  - `test_page_has_all_cards`: output contains each card's `question` and verdict, and four `<article`.
  - `test_every_source_is_linked`: for each source key used by any card, `sources[key]["url"]` appears in an `href`.
  - `test_page_escapes_text`: a card question `"<b>x</b> & y"` and a source title with `|` and `"` render escaped (`&lt;b&gt;`, `&amp;`), and no raw `<b>x</b>`.
  - `test_page_shows_stale_warning`: `data["stale"] = True` → the page contains the warning text; False → it doesn't.
  - `test_page_links_health_and_terms`: contains `href="health.html"` and "non-commercial".
- [ ] **Step 2:** Run `pytest tests/test_claims_page.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement `render`, using `html.escape` on all text the same way `page.py` does.
- [ ] **Step 4:** Run `pytest tests/test_claims_page.py -v`. Expected: PASS. Render once from real data (`python -c` with `db.hourly_frame`), open the file in a browser at 375px and 1280px width, light and dark. Expected: no horizontal scroll, charts visible.
- [ ] **Step 5:** Commit: `git commit -m "Claims page: HTML renderer"`

### Task 4: `build_site.py`: write the site and snapshot

**Files:**
- Create: `scripts/build_site.py`
- Modify: `.gitignore` (add `site/`)
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: `db.connect`, `db.hourly_frame`, `claims.cards`, `claims_page.render`, `api.load_summary()`, `page.render`.
- Produces: `build(conn, out: Path, snapshots: Path, now: pd.Timestamp) -> dict`. It writes `out/index.html`, `out/health.html`, `out/data.json` (the `cards` dict with charts) and `snapshots/YYYY-MM-DD.json` (local date: `scale`, plus per card `id, headline, verdict`; no chart series), and returns the cards dict. The script's `__main__` calls it with `site/`, `snapshots/` and `pd.Timestamp.now(tz="UTC")`.

- [ ] **Step 1: Write failing test** `test_build_writes_all_files` using the temp-table `conn` fixture pattern from `tests/test_ingest.py` (skip without Postgres): insert ~400 days of synthetic hours, call `build`, assert the three site files plus one snapshot exist, `data.json` loads with 4 cards, and the snapshot has no `chart` key.
- [ ] **Step 2:** Run `pytest tests/test_build_site.py -v`. Expected: FAIL (`build` missing).
- [ ] **Step 3:** Implement `build`. Make `api.load_summary` reusable without a second connection by having it accept an optional `conn`. Keep the existing `/api/health` behaviour (`tests/test_api.py` must still pass).
- [ ] **Step 4:** Run `pytest -q`. Expected: all PASS. Then run `python scripts/build_site.py` against local Postgres. Expected: `site/index.html` opens and shows today's numbers.
- [ ] **Step 5:** Commit: `git commit -m "Claims page: site build and daily snapshot"`

### Task 5: Daily workflow with DST-safe guard

**Files:**
- Create: `src/gridwatch/schedule.py`
- Create: `.github/workflows/daily.yml`
- Modify: `docs/superpowers/specs/2026-10-17-claims-page-design.md` (guard wording, per the Global Constraints refinement)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Produces: `should_run(now_utc: pd.Timestamp, issued_today: bool, manual: bool) -> bool`. Returns True if `manual`, else `local(now) >= 10:00 and not issued_today`, where local is `features.TZ`. Also `scripts/should_run.py`, which queries `SELECT 1 FROM forecasts WHERE source='live' AND issue_date = <local today>` and prints `run=true|false` to `$GITHUB_OUTPUT`.

Workflow `daily.yml`:
- `on`: `schedule` crons `5 16 * * *` and `5 17 * * *`, plus `workflow_dispatch`.
- `permissions`: `contents: write`, `pages: write`, `id-token: write`.
- `concurrency: daily` (no overlapping runs).
- Steps: checkout → setup-python 3.12 with pip cache → `pip install .` → guard (`scripts/should_run.py`, manual = `github.event_name == 'workflow_dispatch'`) → if run: `python scripts/daily.py` (continue on error) → `python scripts/build_site.py` (`if: always()` within the guarded block) → commit `snapshots/` as `github-actions[bot]` with message `snapshot YYYY-MM-DD` (skip if no change) → `actions/upload-pages-artifact` (`path: site`) → `actions/deploy-pages`.
- Secrets: `AESO_API_KEY`, `DATABASE_URL`.

- [ ] **Step 1: Write failing tests:**
  - `test_should_run_summer_first_cron`: 2026-07-01 16:05 UTC (10:05 MDT), not issued → True.
  - `test_should_run_summer_second_cron_skips`: 2026-07-01 17:05 UTC, issued → False.
  - `test_should_run_winter_first_cron_too_early`: 2026-12-01 16:05 UTC (09:05 MST) → False.
  - `test_should_run_winter_second_cron`: 2026-12-01 17:05 UTC, not issued → True.
  - `test_should_run_late_cron_still_runs`: 2026-07-01 17:50 UTC (11:50 MDT), not issued → True.
  - `test_should_run_manual_always`: 03:00 local, issued → True when `manual=True`.
- [ ] **Step 2:** Run `pytest tests/test_schedule.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `should_run`, `scripts/should_run.py`, and `daily.yml`. Update the spec's guard line.
- [ ] **Step 4:** Run `pytest -q` and `ruff check .`. Expected: all PASS. Validate the workflow syntax with `gh workflow view` after the push in Task 6, or with `actionlint` if available.
- [ ] **Step 5:** Commit: `git commit -m "Claims page: daily GitHub Actions workflow"`

### Task 6: Go live (with the user)

**Files:**
- Modify: `README.md` (live URL at the top, "How it runs" note, architecture sketch from the spec)
- Modify: `PROGRESS.md` (phase status, retire-the-task note)

Needs the user for account steps. Do not push until the user approves.

- [ ] **Step 1:** With the user: create the Supabase project, enable the `vector` extension, and copy the connection string. Use the session pooler string if the direct one is IPv6-only.
- [ ] **Step 2:** From the PC: `DATABASE_URL=<supabase> python scripts/ingest.py --start 2020-01-01` (~16 min), then `scripts/backtest.py`, `scripts/rag_ingest.py`, `scripts/build_site.py`. Expected: no errors, and `site/index.html` matches the local build.
- [ ] **Step 3:** With the user: add the `AESO_API_KEY` and `DATABASE_URL` repo secrets, and set Pages source to "GitHub Actions".
- [ ] **Step 4:** Push (user approves first). Run the workflow manually (`gh workflow run daily.yml`). Expected: a green run, the page live at `https://tuguzbay.github.io/alberta-grid-watch/`, and a snapshot commit in the repo.
- [ ] **Step 5:** Check the live URL on phone and laptop. Reread each verdict against its sources.
- [ ] **Step 6:** After three clean scheduled runs: `Unregister-ScheduledTask AlbertaGridWatchDaily`. Update README/PROGRESS, then commit and push.
