from fastapi.testclient import TestClient

from gridwatch import rag
from gridwatch.api import app


def test_html_text_keeps_main_drops_chrome():
    html = """<html><body><nav>Menu Home</nav><main><h1>Grid</h1><p>Homes come
    <b>first</b>.</p><script>var x = 1;</script><footer>Copyright</footer></main>
    <p>outside main</p></body></html>"""
    assert rag.html_text(html) == "Grid\nHomes come first."


def test_html_text_without_main_uses_whole_page():
    assert rag.html_text("<div>a</div><div>b</div>") == "a\nb"


def test_chunk_overlaps_and_keeps_page():
    words = [f"w{i}" for i in range(400)]
    chunks = rag.chunk([(3, " ".join(words)), (4, ""), (None, "short page")])
    step = rag.CHUNK_WORDS - rag.OVERLAP
    assert [p for p, _ in chunks] == [3, 3, 3, None]
    assert chunks[0][1].split() == words[:rag.CHUNK_WORDS]
    assert chunks[1][1].split()[0] == words[step]  # overlaps the previous chunk
    assert chunks[2][1].split()[-1] == "w399"  # nothing lost at the end
    assert chunks[3][1] == "short page"


def hit(key, score):
    return {"doc_key": key, "score": score}


def test_answer_abstains_below_threshold():
    a = rag.answer([hit("a", 0.71), hit("b", 0.5)], score_min=0.72)
    assert a["abstained"] and a["passages"] == []
    assert rag.answer([], score_min=0.72)["abstained"]


def test_answer_keeps_only_passages_over_threshold():
    a = rag.answer([hit("a", 0.9), hit("b", 0.8), hit("c", 0.7)], score_min=0.75)
    assert not a["abstained"]
    assert [p["doc_key"] for p in a["passages"]] == ["a", "b"]


def test_ask_rejects_bad_input():
    client = TestClient(app)
    assert client.post("/api/ask", json={"q": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"q": "x" * 501}).status_code == 422
