# "Meta in Alberta: claims vs data": design

_2026-10-17. Status: approved in conversation, awaiting written-spec review._

## Purpose

A public, self-updating web page that checks common worries about Meta's Sturgeon County data centre, and the government's promises about it, against Alberta grid data. It's a resume project: a stranger should understand each worry, what the data says and how sure we are within a minute. A technical reader should be able to reach the method and code in one click.

**Tone:** it tests claims in both directions. It doesn't defend or attack the project. A verdict can be "Not so far," "Partly true," "Too early to tell" and so on, and each one states what would change it.

**Audience:** plain language first. Every card has a "How we know" expander with the method, caveats and links to the code.

## Page content (`site/index.html`)

### Scale strip, "How big is it?"
- Meta's grid draw: ~970 MW (`goa_bills`, `goa_grid`)
- City of Edmonton load: ~1,400 MW (`aeso_factsheet`)
- Alberta record hourly load: computed from `hourly` (currently 12,785 MW, 2025-12-11 17:00 MT)
- Data-centre load requested: ~19,565 MW as of 2026-07-30 (`goa_grid`)

### Cards
Each card shows: the worry as a question, one headline number, a verdict label, a two-sentence explanation, one chart, a "How we know" expander, and source links.

| Card | Live part (rebuilt daily) | Fixed part | Caveats shown on the card |
|---|---|---|---|
| **Will it cause blackouts?** | Daily minimum headroom over the last 90 days (chart); count of hours with headroom < 0 so far this year vs the same period last year | `cushion.scenario` with +970 MW and no new supply; government quote "homes come first" (`goa_grid`, `goa_bills`) | Headroom ignores wind, solar and imports; Meta's adjacent gas plant is meant to cover its load; it's a correlation, not a forecast |
| **Will my power bill go up?** | Monthly mean pool price since 2020 (chart) | Check of "~$200M/yr in transmission fees cuts household transmission costs by up to 6%" (`goa_bills`): $200M ÷ AESO's annual transmission revenue requirement | Most households are on fixed-rate contracts, so pool price isn't the bill; the 6% applies only to the transmission line item |
| **Is it bad for emissions?** | none | `impacts.footprint(970)`: CO₂ Mt/yr on new combined-cycle gas, as a share of Alberta power-sector CO₂ (2023) | Flat load is an upper bound on energy; the best-gas factor is a lower bound on emissions |
| **Will it drain our water?** | none | `impacts.footprint(970)`: gas-plant cooling water, cooling tower vs dry cooling; the government's "closed loop, less than a golf course" claim (`goa_water`) | That claim is about the data centre, not its power plant |

Verdict text is written by hand in `claims.py`, picked by rules over the computed numbers (for example, the blackouts verdict depends on whether tight hours rose year over year). It never comes from a model. If the denominator for the 6% check can't be sourced, the bills verdict for that claim is "Can't verify yet," with the reason.

### Footer
Link to `health.html` (forecast track record), the GitHub repo, the data-terms note (AESO data is for non-commercial/educational use) and a "data as of …" timestamp.

### Out of scope
Document search on the page, the bill simulator (old Phase 5), and a before/after view for Meta (AESO data doesn't break out sites, and the connection date isn't known).

## Architecture

```
GitHub Actions (daily.yml, cron 16:05 + 17:05 UTC, guard: on/after 10:00 America/Edmonton
                and no live forecast issued today, or a manual run)
  1. scripts/daily.py          ingest + forecast → Supabase (unchanged)
  2. scripts/build_site.py     Supabase → site/index.html, site/health.html, site/data.json
  3. commit snapshots/YYYY-MM-DD.json   (card numbers; keeps the repo active)
  4. actions/deploy-pages      site/ → https://tuguzbay.github.io/alberta-grid-watch/
```

### New units
- `src/gridwatch/claims.py`: pure functions over the `hourly` DataFrame, which return one dict per card (numbers, chart series, verdict key). It reuses `cushion.headroom`, `cushion.scenario` and `impacts.footprint`. The fixed facts are a constant dict, each entry carrying a `rag/sources.csv` key so the page can link the document.
- `src/gridwatch/claims_page.py`: `render(cards: dict) -> str`, one self-contained HTML document. It uses the same pattern as `page.py` (escaped values, JSON embedded for Chart.js 4.4.1 from cdnjs) and works at phone width.
- `scripts/build_site.py`: connects, builds the cards, writes the three files. It also writes `health.html` with the existing `health.summary` + `page.render`.
- `.github/workflows/daily.yml`: the schedule, the guard step, the steps above. Secrets: `AESO_API_KEY`, `DATABASE_URL`.

### Failure handling
- If step 1 fails, steps 2–4 still run (`if: always()`) on the last good data. The page shows the existing >36 h stale warning, and GitHub emails the repo owner about the failed run.
- If step 2 fails, nothing is deployed and the previous page stays live.

### One-time setup
1. Create a Supabase project and enable `vector`. Run the backfill from the PC (`scripts/ingest.py --start 2020-01-01`, ~16 min).
2. Add the two repository secrets and enable Pages (source: GitHub Actions).
3. After three clean scheduled runs, unregister `AlbertaGridWatchDaily` on the PC.

## Testing
- `tests/test_claims.py`: card numbers on a small synthetic hourly frame; a frame with zero tight hours (verdict still reads correctly); a frame ending several days ago (stale flag set).
- `tests/test_claims_page.py`: every card renders, every fixed fact has a source link, and HTML is escaped.
- Timing guard: correct run/skip decision for both UTC cron times in summer (MDT) and winter (MST).
- `build_site.py`: writes all three files against a test database (skipped if Postgres isn't up, like the existing DB tests).
- Manual: the live URL works on phone and laptop; three clean scheduled runs; each verdict reread against its sources.

## Open research (do first)
1. AESO annual transmission revenue requirement (an AESO ISO tariff application or AUC decision), with year and source URL, for the 6% check.
2. Supabase free tier: confirm the inactivity-pause rule and that daily database writes keep the project active.
3. GitHub: confirm that scheduled workflows stay enabled when the workflow itself commits daily, under the 60-day inactivity rule.

## Research results (2026-10-18)
1. **Transmission revenue requirement:** the AESO 2026 ISO Tariff Update Application (2025-11-07, p. 6) gives a 2026 total revenue requirement forecast of **$2,636.9 million** (wires $2,049.0M ≈ 77.7%; the rest is ancillary services, losses, and administration). Source key `aeso_tariff_rr`. The bills card uses the total, since all of it is recovered through the transmission tariff. $200M ÷ $2,636.9M ≈ 7.6%. The $200M itself is the government's figure (`goa_bills`); we don't verify it independently.
2. **Supabase pausing** ([docs](https://supabase.com/docs/guides/platform/free-project-pausing)): a Free project pauses without "sufficient user database activity over the past week"; "a few user requests to the database each day" is enough. Paused projects can be restored within 1 year. The daily job's queries should qualify. If it is paused anyway, the page shows the stale warning and the project is restored from the dashboard.
3. **GitHub 60-day rule** ([docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)): "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." The docs don't define activity. The daily snapshot commit is the standard keep-alive. If GitHub disables the workflow anyway, it's re-enabled with one click (GitHub emails a warning first).
