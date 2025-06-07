import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import codebase_cleaner


class DummyResp:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        pass

def test_unsupported_version_exit(monkeypatch):
    monkeypatch.setattr(
        codebase_cleaner.urllib.request,
        "urlopen",
        lambda *a, **k: DummyResp({"latest": "2", "min_supported": "1.5"}),
    )
    monkeypatch.setattr(codebase_cleaner.messagebox, "showerror", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exc:
        codebase_cleaner.check_latest_version("1")
    assert exc.value.code == 20


def test_update_available_returns_false(monkeypatch):
    monkeypatch.setattr(
        codebase_cleaner.urllib.request,
        "urlopen",
        lambda *a, **k: DummyResp({"latest": "2", "min_supported": "1"}),
    )
    monkeypatch.setattr(codebase_cleaner.messagebox, "showinfo", lambda *a, **k: None)
    assert codebase_cleaner.check_latest_version("1.5") is False


def test_network_error_returns_true(monkeypatch):
    def boom(*a, **k):
        raise codebase_cleaner.urllib.error.URLError("fail")
    monkeypatch.setattr(codebase_cleaner.urllib.request, "urlopen", boom)
    assert codebase_cleaner.check_latest_version("1") is True


def test_single_instance(monkeypatch, tmp_path):
    env = os.environ.copy()
    env["EEC_DUMMY_TK"] = "1"
    env["LOCALAPPDATA"] = str(tmp_path)
    script = Path(__file__).resolve().parents[1] / "race_gui.py"
    p1 = subprocess.Popen([sys.executable, str(script)], env=env)
    time.sleep(0.5)
    p2 = subprocess.Popen([sys.executable, str(script)], env=env)
    time.sleep(0.5)
    running = sum(p.poll() is None for p in (p1, p2))
    for p in (p1, p2):
        if p.poll() is None:
            p.terminate()
            p.wait()
    assert running == 1
