"""Question answering over AESO / AUC / Government of Alberta data-centre documents.

Extractive only: an answer is the best-matching passages, each with its source, and no
generated text. If no passage scores at least SCORE_MIN, the question counts as not covered
by the documents and we abstain.
"""

import hashlib
import re
from datetime import date
from functools import cache
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import httpx
import psycopg
from pypdf import PdfReader

MODEL = "BAAI/bge-small-en-v1.5"  # 384-d, matches chunks.embedding
# BGE expects this on queries (not passages); fastembed 0.9 does not add it.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
SCORE_MIN = 0.70  # cosine; best total on rag/eval.jsonl (scripts/rag_eval.py), so tuned in-sample
CHUNK_WORDS, OVERLAP = 200, 40
UA = {"User-Agent": "Mozilla/5.0 (gridwatch document ingest; educational)"}


class _Text(HTMLParser):
    """Visible text of a page, taken from <main> when there is one."""

    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form", "button"}
    BLOCK = {"p", "div", "li", "tr", "br", "section", "article", "table",
             "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip, self.main = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "main":
            self.main = [len(self.parts), None]
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "main" and self.main:
            self.main[1] = len(self.parts)
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(re.sub(r"\s+", " ", data))  # source line breaks aren't text


def html_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    parts = p.parts[p.main[0]:p.main[1]] if p.main else p.parts
    lines = (re.sub(r"\s+", " ", line).strip() for line in "".join(parts).split("\n"))
    return "\n".join(line for line in lines if line)


def pages(content: bytes) -> list[tuple[int | None, str]]:
    """(page, text) pairs: one per PDF page, or a single (None, text) for a web page."""
    if content[:5] == b"%PDF-":
        reader = PdfReader(BytesIO(content))
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
    return [(None, html_text(content.decode("utf-8", "replace")))]


def chunk(pages: list[tuple[int | None, str]]) -> list[tuple[int | None, str]]:
    """Overlapping word windows within each page, so every chunk cites one page."""
    out = []
    for page, text in pages:
        words = text.split()
        for start in range(0, max(len(words) - OVERLAP, 1), CHUNK_WORDS - OVERLAP):
            if words:
                out.append((page, " ".join(words[start:start + CHUNK_WORDS])))
    return out


@cache
def _model():
    from fastembed import TextEmbedding  # slow import; only load when needed

    return TextEmbedding(MODEL)


def _vec(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


MAX_BYTES = 25_000_000  # well above any source PDF; stops a huge or endless response


def fetch(url: str) -> bytes:
    with httpx.stream("GET", url, headers=UA, follow_redirects=True, timeout=60) as r:
        r.raise_for_status()
        body = bytearray()
        for chunk in r.iter_bytes():
            body += chunk
            if len(body) > MAX_BYTES:
                raise ValueError(f"response over {MAX_BYTES:,} bytes")
    return bytes(body)


def text_sha(content: bytes) -> str:
    """Fingerprint of a document's visible text, ignoring markup and whitespace."""
    text = " ".join(" ".join(t.split()) for _, t in pages(content))
    return hashlib.sha256(text.encode()).hexdigest()


def store(conn: psycopg.Connection, src: dict, content: bytes, force: bool = False) -> int | None:
    """Replace one document and its chunks. Returns the chunk count, or None if unchanged.

    force re-chunks an unchanged file, for when chunking or the model changed."""
    sha, tsha = hashlib.sha256(content).hexdigest(), text_sha(content)
    row = conn.execute("SELECT sha256, changed_on, text_sha FROM documents WHERE key = %s",
                       (src["key"],)).fetchone()
    if row and sha == row[0] or row and tsha == row[2]:  # same file, or same visible text
        if row[2] is None:  # rows stored before text fingerprints: fill it in now
            conn.execute("UPDATE documents SET text_sha = %s WHERE key = %s", (tsha, src["key"]))
        if not force:
            return None
    # Only a different visible text, compared with a known earlier fingerprint, is a change.
    changed_on = date.today() if row and row[2] and row[2] != tsha else (row[1] if row else None)
    chunks = chunk(pages(content))
    vecs = list(_model().passage_embed([t for _, t in chunks]))
    with conn.transaction():
        conn.execute("DELETE FROM documents WHERE key = %s", (src["key"],))
        conn.execute(
            "INSERT INTO documents (key, publisher, title, published, url, retrieved_on, sha256,"
            " changed_on, text_sha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (src["key"], src["publisher"], src["title"], src["published"] or None, src["url"],
             date.today(), sha, changed_on, tsha))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (doc_key, ord, page, text, embedding)"
                " VALUES (%s, %s, %s, %s, %s::vector)",
                [(src["key"], i, p, t, _vec(v))
                 for i, ((p, t), v) in enumerate(zip(chunks, vecs, strict=True))])
    return len(chunks)


def ingest_all(conn: psycopg.Connection, sources: list[dict], raw_dir: Path,
               force: bool = False) -> list[str]:
    """Fetch and store every source; returns keys whose content changed (not first inserts).

    Documents no longer in `sources` are deleted. Raw files are kept in raw_dir."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    conn.execute("DELETE FROM documents WHERE key <> ALL(%s)", ([s["key"] for s in sources],))
    changed = []
    for src in sources:
        try:
            content = fetch(src["url"])
        except Exception as e:  # one dead link shouldn't stop the rest
            print(f"{src['key']:24} FETCH FAILED: {e}")
            continue
        (raw_dir / src["key"]).write_bytes(content)
        prev = conn.execute("SELECT text_sha FROM documents WHERE key = %s",
                            (src["key"],)).fetchone()
        n = store(conn, src, content, force=force)
        if prev and prev[0] and prev[0] != text_sha(content):
            changed.append(src["key"])
        words = sum(len(t.split()) for _, t in pages(content))
        status = "unchanged" if n is None else f"{n} chunks"
        # Few words usually means a JS-rendered page or a soft 404: check by hand.
        check = "  CHECK: little text" if words < 150 else ""
        print(f"{src['key']:24} {words:6} words  {status}{check}")
    return changed


def retrieve(conn: psycopg.Connection, question: str, k: int = 5) -> list[dict]:
    q = _vec(next(iter(_model().query_embed(QUERY_PREFIX + question))))
    cur = conn.execute(
        "SELECT c.doc_key, d.publisher, d.title, d.published, d.url, d.retrieved_on, c.page,"
        " c.text, 1 - (c.embedding <=> %s::vector) AS score"
        " FROM chunks c JOIN documents d ON d.key = c.doc_key"
        " ORDER BY c.embedding <=> %s::vector LIMIT %s", (q, q, k))
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def answer(hits: list[dict], score_min: float = SCORE_MIN, n: int = 3) -> dict:
    """The top passages that clear score_min, or an abstention if none do."""
    passages = [h for h in hits if h["score"] >= score_min][:n]
    return {"abstained": not passages, "passages": passages,
            "note": "Extracted passages, not advice. Check the cited source."
            if passages else "The indexed documents don't cover this question."}


def ask(conn: psycopg.Connection, question: str) -> dict:
    return answer(retrieve(conn, question))
