from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from gridwatch import watch

TODAY = date(2026, 10, 18)
TEXT = ("Pembina says the campus could add up to $460 a year to household bills by 2030. "
        "The minister disagreed and said bills would fall because Meta pays transmission fees.")


def cand(url, days_ago=1, title="t"):
    return watch.Candidate(url=url, title=title, outlet="CBC",
                           published=TODAY - timedelta(days=days_ago))


def test_quote_exact_match():
    assert watch.quote_in_text("the campus could add up to $460 a year to household bills", TEXT)


def test_quote_ignores_curly_quotes_and_spacing():
    text = "It will cost “$460 a year”  more, the report says today"
    assert watch.quote_in_text('It will cost "$460 a year" more, the report says today', text)


def test_quote_rejects_paraphrase():
    assert not watch.quote_in_text(
        "the campus might raise household bills by about $460 every year", TEXT)


def test_quote_rejects_two_sentence_splice():
    assert not watch.quote_in_text(
        "Pembina says the campus could add up to $460 a year because Meta pays transmission fees",
        TEXT)


def test_quote_rejects_short_and_empty():
    assert not watch.quote_in_text("could add up to $460 a year to", TEXT)  # 8 words
    assert not watch.quote_in_text("", TEXT)


def test_canonical_url_drops_tracking():
    assert (watch.canonical_url("https://CBC.ca/news/x/?utm_source=a&id=3&fbclid=z#c")
            == "https://cbc.ca/news/x?id=3")
    assert watch.canonical_url("ftp://x.org/a") is None
    assert watch.canonical_url("javascript:alert(1)") is None


def test_filter_drops_bad_candidates():
    seen = {"https://seen.ca/a"}
    cands = [cand("https://ok.ca/1"), cand("https://ok.ca/1?utm_medium=x"),  # in-batch dup
             cand("https://future.ca/a", days_ago=-2), cand("https://old.ca/a", days_ago=20),
             cand("javascript:alert(1)"), cand("https://seen.ca/a/")]
    out = watch.filter_candidates(cands, seen, since=TODAY - timedelta(days=14), today=TODAY)
    assert [c.url for c in out] == ["https://ok.ca/1"]

    many = [cand(f"https://ok.ca/{i}", days_ago=i % 10) for i in range(50)]
    out = watch.filter_candidates(many, set(), since=TODAY - timedelta(days=14), today=TODAY)
    assert len(out) == watch.MAX_ARTICLES == 8
    assert [c.published for c in out] == sorted((c.published for c in out), reverse=True)


def test_filter_respects_last_run():
    cands = [cand("https://ok.ca/new", days_ago=1), cand("https://ok.ca/older", days_ago=5)]
    out = watch.filter_candidates(cands, set(), since=TODAY - timedelta(days=2), today=TODAY)
    assert [c.url for c in out] == ["https://ok.ca/new"]


def test_claim_id_stable():
    a = watch.claim_id("https://ok.ca/1", "some quote")
    assert a == watch.claim_id("https://ok.ca/1", "some quote") and len(a) == 16
    assert a != watch.claim_id("https://ok.ca/1", "another quote")


def test_extraction_schema_rejects_unknown_topic():
    with pytest.raises(ValidationError):
        watch.Extraction.model_validate({"claims": [
            {"claim": "c", "speaker": "s", "quote": "q", "topic": "crypto", "numbers": []}]})
