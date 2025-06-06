import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from race_data_runner import ensure_watchfiles


def test_ensure_watchfiles_installed(tmp_path, monkeypatch):
    pkg = tmp_path / "watchfiles"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("def watch(*a, **k):\n    return []\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    watch = ensure_watchfiles()
    assert callable(watch)


def test_runner_missing_watchfiles(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    proc = subprocess.run([sys.executable, "-S", "race_data_runner.py"], capture_output=True, text=True, env=env)
    assert proc.returncode == 1
    assert "watchfiles' package is not installed" in proc.stdout
