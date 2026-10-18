"""Claim watch: find new articles and changed official documents about Meta's Alberta data
centre, extract their claims with Claude Haiku, and keep only claims whose quote appears
word for word in the source.

Haiku extracts and categorises; it never judges whether a claim is true.
"""

import hashlib
import re
import unicodedata
from datetime import date, timedelta
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel

MAX_SEARCHES, MAX_ARTICLES, MAX_DOC_CHANGES = 3, 8, 3
MAX_CHARS, MIN_WORDS, WINDOW_DAYS = 60_000, 150, 14
MIN_QUOTE_WORDS = 9  # quotes of 8 words or fewer are too short to mean anything
TOPICS = ("bills", "reliability", "emissions", "water", "land_community", "jobs_economy",
          "other")
CARD_FOR_TOPIC = {"bills": "bills", "reliability": "reliability", "emissions": "emissions",
                  "water": "water"}
Topic = Literal["bills", "reliability", "emissions", "water", "land_community",
                "jobs_economy", "other"]


class Candidate(BaseModel):
    url: str
    title: str
    outlet: str
    published: date


class Discovery(BaseModel):
    articles: list[Candidate]


class ExtractedClaim(BaseModel):
    claim: str
    speaker: str
    quote: str
    topic: Topic
    numbers: list[str]


class Extraction(BaseModel):
    claims: list[ExtractedClaim]


_PUNCT = str.maketrans({c: "'" for c in "‘’‚‛"}
                       | {c: '"' for c in "“”„‟"}
                       | {c: "-" for c in "‐‑‒–—―−"})


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_PUNCT)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str) -> bool:
    q = normalize(quote)
    return len(q.split()) >= MIN_QUOTE_WORDS and q in normalize(text)


_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid)$")


def canonical_url(url: str) -> str | None:
    p = urlsplit(url.strip())
    if p.scheme.lower() not in ("http", "https") or not p.netloc:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if not _TRACKING.match(k)])
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), query, ""))


def filter_candidates(cands: list[Candidate], seen: set[str], since: date, today: date,
                      limit: int = MAX_ARTICLES) -> list[Candidate]:
    """New, in-window candidates with canonical URLs, newest first, at most `limit`."""
    lo = max(since, today - timedelta(days=WINDOW_DAYS))
    out, taken = [], set(seen)
    for c in sorted(cands, key=lambda c: c.published, reverse=True):
        url = canonical_url(c.url)
        if url and url not in taken and lo <= c.published <= today:
            taken.add(url)
            out.append(c.model_copy(update={"url": url}))
    return out[:limit]


def claim_id(url: str, quote: str) -> str:
    return hashlib.sha256(f"{url}\n{quote}".encode()).hexdigest()[:16]
