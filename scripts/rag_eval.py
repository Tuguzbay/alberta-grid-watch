"""Score retrieval on rag/eval.jsonl and sweep the abstention threshold.

Run: python scripts/rag_eval.py   (needs DATABASE_URL and an ingested corpus).
A question with sources [] must be abstained on. Otherwise it's a hit when at least one
returned passage comes from an expected source.
"""

import json
from pathlib import Path

from gridwatch import db, rag

evals = [json.loads(line) for line in open(Path(__file__).parents[1] / "rag" / "eval.jsonl")]
with db.connect() as conn:
    hits = [rag.retrieve(conn, e["q"]) for e in evals]


def score(t: float) -> tuple[int, int, int, int]:
    hit = abstain_ok = n_ans = n_abs = 0
    for e, h in zip(evals, hits, strict=True):
        a = rag.answer(h, t)
        if e["sources"]:
            n_ans += 1
            hit += any(p["doc_key"] in e["sources"] for p in a["passages"])
        else:
            n_abs += 1
            abstain_ok += a["abstained"]
    return hit, n_ans, abstain_ok, n_abs


print("threshold  answered-correctly  abstained-correctly")
for t in [x / 100 for x in range(60, 86, 2)]:
    h, na, a, nb = score(t)
    mark = "  <- SCORE_MIN" if abs(t - rag.SCORE_MIN) < 1e-9 else ""
    print(f"{t:9.2f}  {h:8}/{na} ({h / na:4.0%})  {a:8}/{nb} ({a / nb:4.0%}){mark}")

print(f"\nper question at SCORE_MIN={rag.SCORE_MIN} (top score, top source, expected):")
for e, h in zip(evals, hits, strict=True):
    a = rag.answer(h)
    got = [p["doc_key"] for p in a["passages"]]
    ok = (not e["sources"] and a["abstained"]) or bool(set(got) & set(e["sources"]))
    print(f"{'ok ' if ok else 'BAD'} {h[0]['score']:.3f} {h[0]['doc_key']:22} "
          f"{','.join(e['sources']) or '(abstain)':30.30} {e['q'][:60]}")
