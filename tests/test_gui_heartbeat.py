import subprocess
import sys
import time
import pathlib
import shutil
import os


SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[1] / "race_gui.py"


def launch(tmp: pathlib.Path, extra: str = ""):
    shutil.copy2(SCRIPT_PATH, tmp / "race_gui.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPT_PATH.parent)
    env["EEC_DUMMY_TK"] = "1"
    return subprocess.Popen(
        [sys.executable, "race_gui.py", *extra.split()],
        cwd=tmp,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_heartbeat_success(tmp_path):
    p = launch(tmp_path, "--debug")
    start = time.time()
    output = ""
    while time.time() - start < 5:
        output += p.stdout.read(1)
        if "GUI_HEARTBEAT" in output:
            p.kill()
            break
    assert "GUI_HEARTBEAT" in output


def test_import_failure(tmp_path, monkeypatch):
    shutil.copy2(SCRIPT_PATH, tmp_path / "race_gui.py")
    monkeypatch.setenv("FORCE_GUI_IMPORT_ERROR", "1")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPT_PATH.parent)
    env["EEC_DUMMY_TK"] = "1"
    p = subprocess.run(
        [sys.executable, "race_gui.py"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert p.returncode != 0
    assert "GUI never reached event loop" in p.stdout
