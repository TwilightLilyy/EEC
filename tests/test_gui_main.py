import sys
from pathlib import Path

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

    monkeypatch.setattr(race_gui.tk, 'Tk', lambda: DummyRoot())
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

    monkeypatch.setattr(race_gui.tk, 'Tk', boom)
    monkeypatch.setattr(race_gui, 'open_log_file', lambda *_: None)

    code = race_gui.main([])
    captured = capsys.readouterr()
    assert code == 1
    assert 'Race GUI failed to start' in captured.err
    assert log_path.exists()
