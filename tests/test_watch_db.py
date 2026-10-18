from datetime import UTC, date, datetime, timedelta

from gridwatch import watch

CLAIM = watch.ExtractedClaim(
    claim="Bills could rise $460 a year", speaker="Pembina Institute",
    quote="the campus could add up to $460 a year to household bills", topic="bills",
    numbers=["$460 a year"])
URL = "https://pembina.org/a"


def save(conn, url=URL, published=date(2026, 10, 17)):
    watch.save_article(conn, url, "Title <b>", "Pembina", published, "ok", "news")


def test_save_and_reload_claims(conn):
    save(conn)
    assert watch.save_claims(conn, URL, [CLAIM]) == 1
    rows = watch.recent_claims(conn, datetime(2026, 10, 1, tzinfo=UTC), hidden=set())
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == watch.claim_id(URL, CLAIM.quote) and r["quote"] == CLAIM.quote
    assert r["numbers"] == ["$460 a year"] and r["outlet"] == "Pembina"
    assert r["published"] == "2026-10-17" and r["source_kind"] == "news"
    assert watch.seen_urls(conn) == {URL}


def test_save_is_idempotent(conn):
    save(conn)
    save(conn)
    assert watch.save_claims(conn, URL, [CLAIM]) == 1
    assert watch.save_claims(conn, URL, [CLAIM]) == 0
    assert len(watch.recent_claims(conn, datetime(2026, 1, 1, tzinfo=UTC), set())) == 1


def test_recent_claims_excludes_hidden_and_old(conn):
    save(conn)
    watch.save_claims(conn, URL, [CLAIM])
    hidden = {watch.claim_id(URL, CLAIM.quote)}
    assert watch.recent_claims(conn, datetime(2026, 1, 1, tzinfo=UTC), hidden) == []
    future = datetime.now(UTC) + timedelta(days=1)
    assert watch.recent_claims(conn, future, set()) == []


def test_last_run_none_when_empty(conn):
    assert watch.last_run(conn) is None
    save(conn)
    assert watch.last_run(conn) == datetime.now(UTC).date()
