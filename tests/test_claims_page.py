import copy

from gridwatch import claims_page

SOURCES = {
    "goa_bills": {"publisher": "Government of Alberta", "title": "Power Bills",
                  "url": "https://www.alberta.ca/datacentres/power-bills"},
    "aeso_byog": {"publisher": "AESO", "title": 'Phase 2A | BYOG "Process"',
                  "url": "https://aesoengage.aeso.ca/pre-engagement-phase-ii-large-load-integration"},
}


def card(i, **kw):
    c = {"id": f"c{i}", "question": f"Question {i}?", "headline": f"{i} things",
         "verdict": f"Verdict {i}", "explain": "Because.", "how": ["Method."],
         "chart": {"type": "line", "labels": ["2026-01-01"], "series": {"MW": [1.0]}},
         "sources": ["goa_bills"]}
    return {**c, **kw}


DATA = {
    "scale": {"meta_mw": 970, "meta_full_mw": 1800, "edmonton_mw": 1400, "requested_mw": 19565,
              "record_mw": 12785.0, "record_ts_local": "2025-12-11 17:00",
              "history_from": 2020},
    "cards": [card(1), card(2, chart=None, sources=["aeso_byog"]), card(3), card(4)],
    "as_of_utc": "2026-10-17T22:00:00+00:00",
    "stale": False,
}


def test_page_has_all_cards():
    html = claims_page.render(DATA, SOURCES)
    assert html.count("<article") == 4
    for c in DATA["cards"]:
        assert c["question"] in html and c["verdict"] in html


def test_every_source_is_linked():
    html = claims_page.render(DATA, SOURCES)
    for key in {k for c in DATA["cards"] for k in c["sources"]}:
        assert f'href="{SOURCES[key]["url"]}"' in html


def test_page_escapes_text():
    data = copy.deepcopy(DATA)
    data["cards"][0]["question"] = "<b>x</b> & y"
    html = claims_page.render(data, SOURCES)
    assert "&lt;b&gt;x&lt;/b&gt; &amp; y" in html and "<b>x</b>" not in html
    assert "BYOG &quot;Process&quot;" in html


def test_page_shows_stale_warning():
    assert "isn't up to date" not in claims_page.render(DATA, SOURCES)
    assert "isn't up to date" in claims_page.render({**DATA, "stale": True}, SOURCES)


def test_page_links_health_and_terms():
    html = claims_page.render(DATA, SOURCES)
    assert 'href="health.html"' in html and "non-commercial" in html


def test_page_checks_staleness_in_browser():
    # The build can't flag staleness if the daily job stops running, so the page checks too.
    html = claims_page.render(DATA, SOURCES)
    assert 'data-as-of="2026-10-17T22:00:00+00:00"' in html
    assert 'id="stale-live" hidden' in html


def test_record_tile_says_since_when():
    assert "Highest hour since 2020" in claims_page.render(DATA, SOURCES)


def test_at_a_glance_links_every_section():
    html = claims_page.render(DATA, SOURCES)
    for c in DATA["cards"]:
        assert f'href="#{c["id"]}"' in html and f'id="{c["id"]}"' in html


def test_scale_bars_are_drawn_to_scale():
    html = claims_page.render(DATA, SOURCES)
    assert "--w:100.0%" in html  # the largest value fills the bar
    assert f"--w:{970 / 19565:.1%}" in html


def test_page_says_it_is_independent():
    assert "not affiliated with Meta" in claims_page.render(DATA, SOURCES)


def test_short_answer_is_the_first_sentence():
    data = copy.deepcopy(DATA)
    data["cards"][0]["explain"] = "First point. Second point here."
    html = claims_page.render(data, SOURCES)
    assert '<p class="lead">First point.</p>' in html
    assert "Second point here." in html


def test_method_and_sources_share_one_panel():
    html = claims_page.render(DATA, SOURCES)
    assert html.count("<details") == len(DATA["cards"])
    assert html.count("How we know &amp; sources") == len(DATA["cards"])


def test_theme_switch_overrides_system_setting():
    html = claims_page.render(DATA, SOURCES)
    assert 'id="theme-toggle"' in html and 'aria-label="Switch to dark mode"' in html
    assert ':root[data-theme="dark"]' in html and ':root:not([data-theme="light"])' in html


def test_scroll_reveal_never_hides_content_without_js():
    # Sections only start hidden once the script has marked the page with the js class.
    html = claims_page.render(DATA, SOURCES)
    assert ".js .reveal" in html and "\n.reveal {" not in html


def test_uses_newsreader():
    assert "family=Newsreader" in claims_page.render(DATA, SOURCES)


def wclaim(i, topic="bills", **kw):
    c = {"id": f"id{i}", "claim": f"Claim {i}", "speaker": "Pembina Institute",
         "quote": f"quote number {i} with enough words to pass the check", "topic": topic,
         "numbers": [], "url": f"https://news.ca/{i}", "title": f"Story {i}", "outlet": "CBC",
         "published": "2026-10-17", "source_kind": "news"}
    return c | kw


def with_watch(claims, changed=()):
    per = {}
    for c in claims:
        per.setdefault(c["topic"], []).append(c)
    return {**DATA, "cards": [card(1, id="bills"), card(2), card(3), card(4)],
            "watch": {"claims": claims, "week_count": len(claims), "week_sources": 1,
                      "per_card": {k: v[:3] for k, v in per.items() if k == "bills"},
                      "changed_sources": list(changed)}}


def test_spotted_section_renders_claims():
    html = claims_page.render(with_watch([wclaim(1)]), SOURCES)
    assert 'id="spotted"' in html
    assert claims_page.AI_LABEL == (
        "Found and summarised automatically by AI (Claude Haiku) from public articles. "
        "Not reviewed by a person. Quotes are checked word-for-word against the source.")
    assert claims_page.AI_LABEL in html
    assert "<blockquote>quote number 1 with enough words to pass the check</blockquote>" in html
    assert 'href="https://news.ca/1#:~:text=' in html and "Not checked yet" in html
    assert 'href="#bills"' in html and 'href="#spotted"' in html


def test_spotted_empty_state():
    assert "No new claims this week." in claims_page.render(DATA, SOURCES)


def test_watch_cards_escape_article_text():
    bad = wclaim(1, speaker="<script>x</script>", quote='"><img src=x onerror=alert(1)>',
                 url="javascript:alert(1)")
    html = claims_page.render(with_watch([bad]), SOURCES)
    assert "<script>x" not in html and "&lt;script&gt;x" in html
    assert "<img src=x" not in html and 'href="javascript:' not in html


def test_recent_claims_inside_story():
    html = claims_page.render(with_watch([wclaim(1)]), SOURCES)
    story = html[html.index('<article id="bills"'):]
    story = story[:story.index("</article>")]
    assert "Recent claims on this topic (1)" in story and "quote number 1" in story


def test_changed_sources_listed():
    changed = [{"key": "goa_bills", "title": "Power Bills", "publisher": "Government of Alberta",
                "url": "https://www.alberta.ca/datacentres/power-bills",
                "changed_on": "2026-10-20"}]
    html = claims_page.render(with_watch([], changed), SOURCES)
    assert "changed on 2026-10-20" in html and "Power Bills" in html


def test_claim_shows_link_hostname():
    # Review finding: the outlet name comes from the AI; the hostname shows where the link goes.
    html = claims_page.render(with_watch([wclaim(1, outlet="CBC", url="https://evil.example/x")]),
                              SOURCES)
    assert '<span class="host">evil.example</span>' in html


def test_claim_link_jumps_to_quote():
    assert claims_page._at_quote("https://a.ca/x#top", "short - quote, here") == (
        "https://a.ca/x#:~:text=short%20%2D%20quote%2C%20here")
    long = "one two three four five six seven eight nine ten"
    assert claims_page._at_quote("https://a.ca/x", long).endswith(
        "#:~:text=one%20two%20three%20four,seven%20eight%20nine%20ten")
    # Quote marks and brackets break literal matching, so anchors skip those words.
    q = "The county imposed [pdf] 41 conditions on it"
    assert claims_page._at_quote("https://a.ca/x", q) == (
        "https://a.ca/x#:~:text=The%20county%20imposed,41%20conditions%20on%20it")
    assert claims_page._at_quote("https://a.ca/x", "The project's main plan here") == (
        "https://a.ca/x#:~:text=main%20plan%20here")
    assert claims_page._at_quote("https://a.ca/x", "\"Meta's\"") == "https://a.ca/x"
    html = claims_page.render(with_watch([wclaim(1)]), SOURCES)
    assert "#:~:text=" in html and 'class="claims scroller"' in html


def test_claim_card_puts_verified_quote_before_ai_summary():
    html = claims_page.render(with_watch([wclaim(1)]), SOURCES)
    card = html[html.index('<li class="claim">'):]
    assert card.index("<blockquote>") < card.index("AI summary")


def test_spotted_is_a_carousel_with_hidden_bar_until_script_runs():
    html = claims_page.render(with_watch([wclaim(1)]), SOURCES)
    assert '<div class="car-bar" hidden>' in html
    assert 'aria-label="Previous claims"' in html and 'aria-label="Next claims"' in html


def test_chip_tone_ignores_the_number_after_the_colon():
    assert 'class="chip warn"' in claims_page._chip("Big: up to 16% of Alberta's power emissions")
    assert 'class="chip neutral"' in claims_page._chip("Depends on the plant's cooling")
