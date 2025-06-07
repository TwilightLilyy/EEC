import sys
from pathlib import Path
import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import race_gui


def make_logger(tmp_path):
    log_path = tmp_path / 'race_gui.log'
    race_gui.LOG_PATH = log_path
    logger = race_gui.logging.getLogger('race_gui')
    for h in list(logger.handlers):
        logger.removeHandler(h)
    return logger, log_path


def test_visibility_watchdog(monkeypatch, tmp_path):
    logger, log_path = make_logger(tmp_path)

    class DummyRoot:
        def __init__(self):
            self.updates = 0
        def deiconify(self):
            pass
        def lift(self):
            pass
        def update_idletasks(self):
            pass
        def winfo_ismapped(self):
            return self.updates > 0
        def update(self):
            self.updates += 1
        def after(self, _delay, func):
            func()
        def mainloop(self):
            pass

    def make_root():
        root = DummyRoot()
        race_gui.tk._default_root = root
        return root

    monkeypatch.setattr(race_gui.tk, '_default_root', None)
    monkeypatch.setattr(race_gui.tk, 'Tk', make_root)
    monkeypatch.setattr(race_gui, 'RaceLoggerGUI', lambda *_a, **_k: types.SimpleNamespace(theme='default'))
    code = race_gui.main([])
    assert code == 0
    assert log_path.exists()


def test_theme_fallback(monkeypatch, tmp_path):
    logger, log_path = make_logger(tmp_path)

    class DummyRoot:
        def after(self, _delay, func):
            func()
        def mainloop(self):
            pass
        def deiconify(self):
            pass
        def lift(self):
            pass
        def update_idletasks(self):
            pass
        def winfo_ismapped(self):
            return True
        def update(self):
            pass

    def make_root():
        root = DummyRoot()
        race_gui.tk._default_root = root
        return root

    monkeypatch.setattr(race_gui.tk, '_default_root', None)
    monkeypatch.setattr(race_gui.tk, 'Tk', make_root)
    monkeypatch.setattr(race_gui, 'sv_ttk', None)
    monkeypatch.setattr(race_gui, 'RaceLoggerGUI', lambda *_a, **_k: types.SimpleNamespace(theme='default'))

    code = race_gui.main(['--classic-theme'])
    assert code == 0
    assert log_path.exists()
    assert 'theme default' in log_path.read_text()


