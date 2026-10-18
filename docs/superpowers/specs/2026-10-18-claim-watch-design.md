# Claim watch: daily AI-extracted claims from news and official sources (design)

_2026-10-18. Status: approved in conversation, awaiting written-spec review._

## Purpose

Give the "Meta in Alberta: claims vs data" page a reason to come back to. Each day the site finds new news and analysis about Meta's Sturgeon County data centre and Alberta data-centre policy, re-checks the tracked official documents, extracts the claims they make, and publishes them, each with a word-for-word quote and a link.

**Decisions taken (by the user, 2026-10-18):**
- Extraction model: **Claude Haiku 4.5** (`claude-haiku-4-5`, $1 / $5 per MTok).
- Claims **auto-publish**, clearly labelled as AI-extracted and unreviewed. No approval queue.
- News is found with **Haiku's web search tool**. Our code then downloads each article itself (approach A, refined).

**Principles:**
- Haiku **extracts and categorises only**. It never decides whether a claim is true.
- Every published claim carries an exact quote that our code has **verified as a substring of the source text**. Claims failing that check are dropped and logged.
- Errors are visible and reversible: the page shows the AI label, every claim links to its source, and any claim can be hidden by ID.

## What visitors see

### "Spotted this week" (new section, after the front-page grid)
- Summary line: "N new claims from M sources this week", counting the last 7 days. Claims stay listed for 30 days.
- One card per claim:
  - plain-language claim
  - speaker (person or organisation)
  - outlet and date
  - exact quote in quotation marks
  - link to the source
  - topic tag
  - status chip "Not checked yet"
  - for topics matching a card: "Related data: see <card> ↓", linking to that card
- Topics (fixed enum): `bills`, `reliability`, `emissions`, `water`, `land_community`, `jobs_economy`, `other`. Mapping to cards: `bills` → bills, `reliability` → reliability, `emissions` → emissions, `water` → water.
- Section label: "Found and summarised automatically by AI (Claude Haiku) from public articles. Not reviewed by a person. Quotes are checked word-for-word against the source."
- Empty state: "No new claims this week."

### Inside each existing card
"Recent claims on this topic (N)": the newest 3 claims for that card's topic, each with its quote and link.

### Official sources changed
One line per tracked document whose content changed in the last 30 days, e.g. "Government of Alberta, Power Bills page, changed on 2026-10-20". Claims extracted from it appear in the feed with that document as the source.

### Out of scope
Automatic true/false verdicts on new claims, email or RSS alerts, a human review queue.

## Pipeline (`scripts/watch.py`, daily)

Runs in `.github/workflows/daily.yml` after `daily.py` and before `build_site.py`, with `continue-on-error`, in the same pattern as `daily.py`.

1. **Discover.** One Haiku request with the web search tool (`web_search_20250305`, `max_uses: 3`). Prompt: find news and analysis published since the last successful run (max 14 days back) about Meta's Sturgeon County / Alberta data centre or Alberta data-centre policy. Output: a list of `{url, title, outlet, published (date)}`. Code drops URLs already in `articles`, items older than 14 days and non-http(s) URLs, then keeps at most **8**.
2. **Read.** Download each URL with `rag.fetch` and extract the text with `rag.pages` / `rag.html_text`. Under 150 words, an HTTP error or a non-HTML/PDF response means `status = "unreadable"`, and the article is stored without claims. Text over 60,000 characters means `status = "too_long"`, stored without claims, never silently truncated.
3. **Extract.** One Haiku request per readable article with structured output (`client.messages.parse`, Pydantic schema). Fields per claim: `claim` (plain English, ≤ 30 words), `speaker`, `quote` (verbatim from the text), `topic` (enum above), `numbers` (list of strings as written, e.g. "$460 a year"). An article not about the subject returns an empty list. `max_tokens` 4000. On a `refusal` / `max_tokens` stop or a parse error, the article is marked `status = "extract_failed"` and logged.
4. **Verify.** `quote_in_text(quote, text)`: normalise both sides (Unicode NFKC, curly → straight quotes, dashes unified, whitespace collapsed, case-sensitive), then substring check. A quote of 8 words or fewer is rejected as too short to be meaningful. Failures are counted and logged, never published.
5. **Official documents.** `rag_ingest.py` also runs daily (it already skips unchanged files by hash). For up to **3** documents whose hash changed, the new text goes through steps 3–4, with the document as the source, and `documents.changed_on` is recorded.
6. **Store.** Tables `articles(url PK, title, outlet, published, fetched_at, status, source_kind 'news'|'official')` and `claims(id PK, article_url FK, claim, speaker, quote, topic, numbers jsonb, model, extracted_at)`. The claim `id` is a stable hash of (url, quote), so reruns are idempotent.
7. **Publish.** `claims.cards()` / `site.build` add `watch: {claims_30d, per_topic, changed_sources, counts}` to `data.json`. IDs listed in `rag/hidden_claims.txt` are excluded.

**Run summary** (printed to the log): candidates found, new articles, unreadable, claims extracted, claims rejected by the quote check, tokens in/out and estimated cost.

## Guardrails
- **Caps:** 3 searches, 8 articles and 3 changed documents per day. Worst case is about $0.10/day. The user also sets a monthly spend limit in the Anthropic Console.
- `ANTHROPIC_API_KEY` is a GitHub secret. A missing key means the step logs "skipped: no key" and the page builds as usual.
- All article-derived text is HTML-escaped on render, and URLs must be http(s).
- The prompt tells Haiku to treat article text as data, not instructions. The extraction request has no tools, so text in an article can't trigger actions.

## Testing
- **Offline unit tests** (Haiku responses faked):
  - `quote_in_text`: exact match, curly vs straight quotes, extra whitespace, a paraphrase rejected, a two-sentence splice rejected, too-short/empty rejected.
  - Discover filtering: dedupe, the 14-day window, caps holding when 50 candidates come back, bad URLs dropped.
  - Extraction handling: malformed output, an unknown topic, `refusal`, `max_tokens`. Each leads to skip + log, never a crash.
  - Page: claim cards escaped, every claim shows its quote and link, hidden IDs excluded, the AI label present, the empty state.
- **DB test** (temp tables): save and reload, a same-day rerun creates no duplicates.
- **Manual before done:** one real run with the user's key. Every produced claim is read against its article. The run summary numbers (extracted, rejected, cost) go into the PR.

## Open checks (Task 1 of the plan)
1. Whether `claude-haiku-4-5` accepts the web search tool together with structured output (`output_config.format`) in one request. If not: discovery asks for JSON in the text answer and validates it against the same Pydantic schema.
2. Current web search pricing per search.
3. The user creates an Anthropic API key, adds it as the `ANTHROPIC_API_KEY` secret and sets a Console spend limit.
