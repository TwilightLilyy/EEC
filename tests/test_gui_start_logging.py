import sys
import types
from pathlib import Path
import race_gui

class DummyButton:
    def config(self, **kwargs):
        pass


def test_start_logging_builds_command(monkeypatch, tmp_path, capsys):
    gui = types.SimpleNamespace(
        proc=None,
        db_path=tmp_path / "eec_log.db",
        start_btn=DummyButton(),
        stop_btn=DummyButton(),
        read_output=lambda: None,
    )

    called = {}

    def fake_thread(*a, **k):
        called['thread'] = True
        class T:
            def start(self):
                called['thread_started'] = True
        return T()

    def fake_popen(args, **kwargs):
        called['args'] = args
        class P:
            stdout=None
        return P()

    monkeypatch.setattr(race_gui.threading, 'Thread', fake_thread)
    monkeypatch.setattr(race_gui.subprocess, 'Popen', fake_popen)
    monkeypatch.setattr(race_gui, '_find_python', lambda: '/usr/bin/python')
    monkeypatch.setattr(race_gui, 'messagebox', types.SimpleNamespace(showinfo=lambda *a, **k: None))

    race_gui.RaceLoggerGUI.start_logging(gui)
    out = capsys.readouterr().out
    assert called['args'][0] == '/usr/bin/python'
    assert Path(called['args'][1]).name == 'race_data_runner.py'
    assert '--db' in called['args']
    assert 'Launching race_data_runner.py --db' in out
