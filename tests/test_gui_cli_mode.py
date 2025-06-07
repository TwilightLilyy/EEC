import os
import sys
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'race_gui.py'

def test_cli_debug(monkeypatch):
    env = os.environ.copy()
    env['EEC_DUMMY_TK'] = '1'
    proc = subprocess.run([sys.executable, str(SCRIPT), '--debug'], capture_output=True, text=True, env=env)
    assert proc.returncode == 0
    assert 'Race GUI started successfully' in proc.stdout
