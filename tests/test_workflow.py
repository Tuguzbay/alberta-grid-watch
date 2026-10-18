from importlib.metadata import requires
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_tzdata_is_a_dependency_on_every_platform():
    # Workflows set PYTHONTZPATH="", so Linux needs the tzdata package too.
    assert any(r.split(";")[0].strip().startswith("tzdata") and ";" not in r
               for r in requires("gridwatch"))


def test_daily_workflow_uploads_before_best_effort_steps():
    steps = yaml.safe_load(open(ROOT / ".github/workflows/daily.yml"))["jobs"]["build"]["steps"]
    names = [s.get("uses", "") + s.get("name", "") for s in steps]
    upload = next(i for i, n in enumerate(names) if "upload-pages-artifact" in n)
    commit = next(i for i, n in enumerate(names) if "Commit snapshot" in n)
    assert upload < commit
    for s in steps[upload + 1:]:
        assert s.get("continue-on-error") is True, s.get("name")
    assert "pull --rebase" in steps[commit]["run"]
