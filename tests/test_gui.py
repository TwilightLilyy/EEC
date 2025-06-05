import sys
from pathlib import Path
import signal
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from race_gui import RaceLoggerGUI, filter_rows

class DummyProc:
    def __init__(self):
        self.signals = []
        self.waits = 0
        self.terminated = False
    def send_signal(self, sig):
        self.signals.append(sig)
    def wait(self, timeout=None):
        self.waits += 1
    def terminate(self):
        self.terminated = True
    def kill(self):
        self.killed = True

class DummyButton:
    def config(self, **kwargs):
        pass

def test_stop_logging_sends_sigint():
    gui = types.SimpleNamespace(
        proc=DummyProc(),
        output_thread=object(),
        start_btn=DummyButton(),
        stop_btn=DummyButton()
    )
    p = gui.proc
    RaceLoggerGUI.stop_logging(gui)
    assert signal.SIGINT in p.signals
    assert p.waits == 1
    assert p.terminated is False
    assert gui.output_thread is None


def test_filter_rows_removes_hidden_entries():
    rows = [
        {"Team": "T1", "Driver": "DriverA", "Pos": "1", "Laps": "5"},
        {"Team": "Pace Car", "Driver": "Pace Car", "Pos": "1", "Laps": "5"},
        {"Team": "TeamB", "Driver": "DriverB", "Pos": "0", "Laps": "2"},
        {"Team": "TeamC", "Driver": "DriverC", "Pos": "3", "Laps": "0"},
        {"Team": "Any", "Driver": "Lily Bowling", "Pos": "2", "Laps": "3"},
        {"Team": "Lily Bowling", "Driver": "Someone", "Pos": "2", "Laps": "3"},
        {"Team": "Car 20", "Driver": "Car 20", "Pos": "5", "Laps": "10"},
    ]
    filtered = filter_rows(rows)
    assert len(filtered) == 1
    assert filtered[0]["Driver"] == "DriverA"

