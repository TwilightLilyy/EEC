import types
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import race_gui


def test_check_dependencies_installs_sv_ttk(monkeypatch):
    installed = {}

    def fake_ensure(pkg):
        installed['pkg'] = pkg

    monkeypatch.setattr(race_gui, 'SVTTK_IMPORT_ERROR', ImportError())
    monkeypatch.setattr(race_gui, 'sv_ttk', None)
    monkeypatch.setattr(race_gui, 'ensure_package', fake_ensure)
    monkeypatch.setattr(
        race_gui,
        'importlib',
        types.SimpleNamespace(import_module=lambda n: 'dummy')
    )

    logger = race_gui.logging.getLogger('test')
    race_gui.check_dependencies(logger)
    assert installed.get('pkg') == 'sv_ttk'
    assert race_gui.sv_ttk == 'dummy'
