import pathlib
import re

README = pathlib.Path(__file__).resolve().parents[2] / "README.md"


def replace_section(name: str, body: str) -> None:
    """Rewrite the text between <!-- name:start --> and <!-- name:end --> in README.md."""
    text = README.read_text(encoding="utf-8")
    pat = rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)"
    assert re.search(pat, text, flags=re.S), f"README has no {name} markers"
    README.write_text(re.sub(pat, lambda g: g[1] + body + g[2], text, flags=re.S),
                      encoding="utf-8")
