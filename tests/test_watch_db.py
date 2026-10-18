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


# --- run() --------------------------------------------------------------------------------
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from gridwatch import rag  # noqa: E402

NOW = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)
WORDS = " ".join(f"word{i}" for i in range(200))
ARTICLE = (f"<html><body><main><p>{WORDS}</p><p>Pembina says the campus could add up to $460 a"
           f" year to household bills by 2030.</p></main></body></html>").encode()


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def fake_client(urls, claims):
    body = '{"articles": [%s]}' % ",".join(
        '{"url": "%s", "title": "T", "outlet": "CBC", "published": "2026-10-17"}' % u
        for u in urls)
    use = Obj(input_tokens=1000, output_tokens=100, server_tool_use=Obj(web_search_requests=1))
    create = Obj(content=[Obj(type="text", text=body)], stop_reason="end_turn", usage=use)
    parse = Obj(parsed_output=watch.Extraction(claims=claims), stop_reason="end_turn", usage=use)
    calls = []
    client = Obj(messages=Obj(create=lambda **kw: create,
                              parse=lambda **kw: calls.append(kw) or parse))
    return client, calls


def paraphrase():
    return CLAIM.model_copy(update={"quote": "Pembina thinks household bills will climb by $460 per"
                                             " year because of the campus"})


def test_run_keeps_only_verified_quotes(conn):
    client, _ = fake_client(["https://cbc.ca/a"], [CLAIM, paraphrase()])
    s = watch.run(conn, client, NOW, fetch=lambda url: ARTICLE)
    assert (s["claims_saved"], s["quotes_rejected"], s["new_articles"]) == (1, 1, 1)
    assert s["est_cost_usd"] > 0


def test_run_marks_short_and_long_articles(conn):
    short = b"<p>" + b"x " * 80 + b"</p>"
    long = b"<p>" + ("word " * 14_000).encode() + b"</p>"
    pages = {"https://cbc.ca/short": short, "https://cbc.ca/long": long}
    client, calls = fake_client(list(pages), [CLAIM])
    s = watch.run(conn, client, NOW, fetch=pages.__getitem__)
    assert (s["unreadable"], s["too_long"], calls) == (1, 1, [])


def test_run_survives_fetch_error(conn):
    def fetch(url):
        if url.endswith("/bad"):
            raise OSError("boom")
        return ARTICLE
    client, _ = fake_client(["https://cbc.ca/bad", "https://cbc.ca/good"], [CLAIM])
    s = watch.run(conn, client, NOW, fetch=fetch)
    assert (s["unreadable"], s["claims_saved"]) == (1, 1)


def test_run_respects_caps(conn):
    fetched = []
    client, _ = fake_client([f"https://cbc.ca/{i}" for i in range(30)], [])
    watch.run(conn, client, NOW, fetch=lambda url: fetched.append(url) or ARTICLE)
    assert len(fetched) == watch.MAX_ARTICLES


def test_run_without_key_skips():
    script = Path(__file__).parents[1] / "scripts" / "watch.py"
    env = {k: v for k, v in __import__("os").environ.items() if k != "ANTHROPIC_API_KEY"}
    out = subprocess.run([sys.executable, str(script)], env=env | {"ANTHROPIC_API_KEY": ""},
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "skipped: no key" in out.stdout


def test_store_sets_changed_on_only_on_change(conn, monkeypatch):
    monkeypatch.setattr(rag, "_model", lambda: Obj(
        passage_embed=lambda texts: [np.zeros(384) for _ in texts]))
    src = {"key": "k", "publisher": "P", "title": "T", "published": "", "url": "https://x.ca/k"}
    changed = lambda: conn.execute(  # noqa: E731
        "SELECT changed_on FROM documents WHERE key = 'k'").fetchone()[0]
    rag.store(conn, src, b"<p>one two three</p>")
    assert changed() is None
    rag.store(conn, src, b"<p>one two three</p>")
    assert changed() is None
    rag.store(conn, src, b"<p>one two four</p>")
    assert changed() == date.today()


def test_store_ignores_markup_only_changes(conn, monkeypatch):
    monkeypatch.setattr(rag, "_model", lambda: Obj(
        passage_embed=lambda texts: [np.zeros(384) for _ in texts]))
    src = {"key": "m", "publisher": "P", "title": "T", "published": "", "url": "https://x.ca/m"}
    page = '<html><head><meta name="csrf-token" content="{}"></head><body><p>same words</p></body>'
    rag.store(conn, src, page.format("aaa").encode())
    # Rows stored before text fingerprints existed must not all count as changed afterwards.
    conn.execute("UPDATE documents SET text_sha = NULL WHERE key = 'm'")
    rag.store(conn, src, page.format("bbb").encode())
    rag.store(conn, src, page.format("ccc").encode())
    assert conn.execute("SELECT changed_on FROM documents WHERE key = 'm'").fetchone()[0] is None
