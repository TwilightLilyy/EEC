import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import race_gui


def test_main_success(monkeypatch, tmp_path, capsys):
    log_path = tmp_path / 'race_gui.log'
    monkeypatch.setattr(race_gui, 'LOG_PATH', log_path)
    logger = race_gui.logging.getLogger('race_gui')
    for h in list(logger.handlers):
        logger.removeHandler(h)

    class DummyRoot:
        def mainloop(self):
            pass

        def after(self, _delay, func):
            func()

    def make_root():
        root = DummyRoot()
        race_gui.tk._default_root = root
        return root

    monkeypatch.setattr(race_gui.tk, '_default_root', None)
    monkeypatch.setattr(race_gui.tk, 'Tk', make_root)
    monkeypatch.setattr(race_gui, 'RaceLoggerGUI', lambda _root: None)

    code = race_gui.main([])
    captured = capsys.readouterr()
    assert 'Race GUI started successfully' in captured.out
    assert code == 0


def test_main_failure(monkeypatch, tmp_path, capsys):
    log_path = tmp_path / 'race_gui.log'
    monkeypatch.setattr(race_gui, 'LOG_PATH', log_path)
    logger = race_gui.logging.getLogger('race_gui')
    for h in list(logger.handlers):
        logger.removeHandler(h)

    def boom():
        raise RuntimeError('boom')

    monkeypatch.setattr(race_gui.tk, '_default_root', None)
    monkeypatch.setattr(race_gui.tk, 'Tk', boom)

    with pytest.raises(RuntimeError):
        race_gui.main([])
    assert log_path.exists()
