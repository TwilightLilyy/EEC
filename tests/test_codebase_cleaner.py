from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codebase_cleaner import analyze_project


def test_analyze_project_detects_dead_code(tmp_path: Path) -> None:
    project = tmp_path / "example_project"
    project.mkdir()

    (project / "main.py").write_text(
        "import utils\n\nutils.foo()\n",
        encoding="utf-8",
    )
    (project / "utils.py").write_text(
        "def foo():\n    pass\n\n\ndef unused_func():\n    pass\n",
        encoding="utf-8",
    )

    report = analyze_project(str(project))
    symbols = [d["symbol"] for d in report["dead_code"]]
    assert "utils.unused_func" in symbols
