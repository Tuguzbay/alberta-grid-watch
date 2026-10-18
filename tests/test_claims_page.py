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
    "scale": {"meta_mw": 970, "edmonton_mw": 1400, "requested_mw": 19565,
              "record_mw": 12785.0, "record_ts_local": "2025-12-11 17:00"},
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
