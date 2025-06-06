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

    def fake_set_theme(theme, root=None):
        calls["set_theme"] = (theme, root)

    monkeypatch.setattr("race_gui.sv_ttk", types.SimpleNamespace(set_theme=fake_set_theme))

    root = DummyRoot()
    gui = types.SimpleNamespace(root=root)

    RaceLoggerGUI.setup_style(gui)

    assert gui.bg == "#23272e"
    assert calls["root_configure"].get("bg") == "#23272e"
    assert calls["set_theme"] == ("dark", root)


def test_view_pitstops_uses_toplevel(monkeypatch, tmp_path):
    calls = {}

    class DummyTop:
        def __init__(self, root):
            calls["root"] = root

        def title(self, t):
            calls["title"] = t

    class DummyWidget:
        def __init__(self, *a, **k):
            pass

        def grid(self, *a, **k):
            pass

        def pack(self, *a, **k):
            pass

        def rowconfigure(self, *a, **k):
            pass

        def columnconfigure(self, *a, **k):
            pass

        def configure(self, *a, **k):
            pass

        def heading(self, *a, **k):
            pass

        def column(self, *a, **k):
            return {"width": 100}

        def bind(self, *a, **k):
            pass

        def yview(self, *a, **k):
            pass

        def set(self, *a, **k):
            pass

    class DummyTree(DummyWidget):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.opts = {}

        def delete(self, *a, **k):
            pass

        def get_children(self, *a, **k):
            return []

        def __setitem__(self, k, v):
            self.opts[k] = v

        def __getitem__(self, k):
            return self.opts.get(k)

        def insert(self, *a, **k):
            pass

    monkeypatch.setattr("race_gui.tk.Toplevel", DummyTop)
    monkeypatch.setattr("race_gui.ttk.Frame", DummyWidget)
    monkeypatch.setattr("race_gui.ttk.Treeview", DummyTree)
    monkeypatch.setattr("race_gui.ttk.Scrollbar", DummyWidget)
    monkeypatch.setattr("race_gui.ttk.Button", DummyWidget)
    monkeypatch.setattr("race_gui.messagebox", types.SimpleNamespace(showinfo=lambda *a, **k: None, showerror=lambda *a, **k: None))

    gui = types.SimpleNamespace(root=object())
    RaceLoggerGUI.view_pitstops(gui)

    assert calls.get("title") == "Pit Stops"


def test_view_series_standings_uses_toplevel(monkeypatch, tmp_path):
    calls = {}

    csv_file = tmp_path / "series_standings.csv"
    csv_file.write_text("Team,Points\nA,10\n")

    class DummyTop:
        def __init__(self, root):
            calls["root"] = root

        def title(self, t):
            calls["title"] = t

        def rowconfigure(self, *a, **k):
            pass

        def columnconfigure(self, *a, **k):
            pass

    class DummyWidget:
        def __init__(self, *a, **k):
            pass

        def grid(self, *a, **k):
            pass

        def pack(self, *a, **k):
            pass

        def rowconfigure(self, *a, **k):
            pass

        def columnconfigure(self, *a, **k):
            pass

        def configure(self, *a, **k):
            pass

        def heading(self, *a, **k):
            pass

        def column(self, *a, **k):
            return {"width": 100}

        def bind(self, *a, **k):
            pass

        def yview(self, *a, **k):
            pass

        def set(self, *a, **k):
            pass

    class DummyTree(DummyWidget):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.opts = {}

        def delete(self, *a, **k):
            pass

        def get_children(self, *a, **k):
            return []

        def __setitem__(self, k, v):
            self.opts[k] = v

        def __getitem__(self, k):
            return self.opts.get(k)

        def insert(self, *a, **k):
            pass

    def fake_find_log_file(name: str):
        if name == "series_standings.csv":
            return csv_file
        return Path(name)

    monkeypatch.setattr("race_gui.find_log_file", fake_find_log_file)
    monkeypatch.setattr("race_gui.tk.Toplevel", DummyTop)
    monkeypatch.setattr("race_gui.ttk.Treeview", DummyTree)
    monkeypatch.setattr("race_gui.ttk.Scrollbar", DummyWidget)
    monkeypatch.setattr("race_gui.ttk.Button", DummyWidget)
    monkeypatch.setattr(
        "race_gui.messagebox",
        types.SimpleNamespace(showinfo=lambda *a, **k: None, showerror=lambda *a, **k: None),
    )

    gui = types.SimpleNamespace(root=object())
    RaceLoggerGUI.view_series_standings(gui)

    assert calls.get("title") == "Series Standings"

