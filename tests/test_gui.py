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


def test_filter_rows_removes_pace_and_zero_lap_entries():
    rows = [
        {"Driver": "DriverA", "Pos": "1", "Laps": "5"},
        {"Driver": "Pace Car", "Pos": "1", "Laps": "5"},
        {"Driver": "DriverB", "Pos": "0", "Laps": "2"},
        {"Driver": "DriverC", "Pos": "3", "Laps": "0"},
    ]
    filtered = filter_rows(rows)
    assert len(filtered) == 1
    assert filtered[0]["Driver"] == "DriverA"


def test_setup_style_applies_dark_theme(monkeypatch):
    calls = {}

    class DummyRoot:
        def configure(self, **kwargs):
            calls["root_configure"] = kwargs

        def option_add(self, opt, value):
            calls["option_add"] = (opt, value)

    class DummyStyle:
        def __init__(self, root):
            calls["style_root"] = root

        def theme_use(self, theme):
            calls["theme_use"] = theme

        def configure(self, *_args, **_kwargs):
            pass

        def map(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("race_gui.ttk.Style", DummyStyle)

    root = DummyRoot()
    gui = types.SimpleNamespace(root=root)

    RaceLoggerGUI.setup_style(gui)

    assert gui.bg == "#23272e"
    assert calls["root_configure"].get("bg") == "#23272e"
    assert calls["theme_use"] == "clam"

