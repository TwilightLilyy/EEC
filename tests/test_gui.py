import sys
from pathlib import Path
import signal
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from race_gui import RaceLoggerGUI

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

