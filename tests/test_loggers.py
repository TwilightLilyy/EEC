import runpy
import sys
import sqlite3
import types
import csv
import time
from pathlib import Path


def test_ai_standings_logger_writes_csv(tmp_path, monkeypatch):
    class DummyIR:
        def __init__(self):
            self.is_initialized = True
            self.is_connected = True
        def startup(self):
            pass
        def __getitem__(self, key):
            if key == "DriverInfo":
                return {
                    "Drivers": [
                        {
                            "CarIdx": 0,
                            "TeamName": "TeamA",
                            "UserName": "DriverA",
                            "CarClassID": "2708",
                        }
                    ]
                }
            if key == "SessionNum":
                return 0
            data = {
                "CarIdxLap": [1],
                "CarIdxPosition": [2],
                "CarIdxClassPosition": [1],
                "CarIdxBestLapTime": [1.1],
                "CarIdxLastLapTime": [1.2],
                "CarIdxOnPitRoad": [False],
            }
            return data[key]

    dummy_ir = DummyIR()
    monkeypatch.setitem(sys.modules, "irsdk", types.SimpleNamespace(IRSDK=lambda: dummy_ir))

    sleep_calls = [0]
    def fake_sleep(_):
        sleep_calls[0] += 1
        raise KeyboardInterrupt
    monkeypatch.setattr(time, "sleep", fake_sleep)

    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(sys, "argv", ["ai_standings_logger.py", "--db", str(db_path)])
    module = runpy.run_module("ai_standings_logger", run_name="__main__")

    csv_path = tmp_path / "standings_log.csv"
    rows = list(csv.reader(open(csv_path)))
    assert rows[0] == module["header"]
    assert len(rows) == 2
    assert rows[1][2] == "TeamA"
    assert rows[1][3] == "DriverA"
    conn = sqlite3.connect(db_path)
    db_rows = list(conn.execute("SELECT * FROM standings"))
    conn.close()
    assert len(db_rows) == 1


def test_pitstop_logger_writes_stint(tmp_path, monkeypatch):
    class DummyIR:
        def __init__(self):
            self.is_initialized = True
            self.is_connected = True
            self.iter = -1
            self.data = [
                {
                    "SessionTime": 0,
                    "SessionNum": 0,
                    "CarIdxOnPitRoad": [False],
                    "CarIdxLap": [1],
                    "CarIdxBestLapTime": [1.1],
                    "DriverInfo": {"Drivers": [{"TeamName": "TeamA", "UserName": "DriverA", "CarClassShortName": "GT3"}]},
                },
                {
                    "SessionTime": 60,
                    "SessionNum": 0,
                    "CarIdxOnPitRoad": [True],
                    "CarIdxLap": [2],
                    "CarIdxBestLapTime": [1.1],
                    "DriverInfo": {"Drivers": [{"TeamName": "TeamA", "UserName": "DriverA", "CarClassShortName": "GT3"}]},
                },
            ]
        def startup(self):
            pass
        def freeze_var_buffer_latest(self):
            self.iter += 1
            if self.iter >= len(self.data):
                self.iter = len(self.data) - 1
        def __getitem__(self, key):
            return self.data[self.iter][key]

    dummy_ir = DummyIR()
    monkeypatch.setitem(sys.modules, "irsdk", types.SimpleNamespace(IRSDK=lambda: dummy_ir))

    sleep_calls = [0]
    def fake_sleep(_):
        sleep_calls[0] += 1
        if sleep_calls[0] >= 2:
            raise KeyboardInterrupt
    monkeypatch.setattr(time, "sleep", fake_sleep)

    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    db_path = tmp_path / "test2.db"
    monkeypatch.setattr(sys, "argv", ["pitstop_logger_enhanced.py", "--db", str(db_path)])
    module = runpy.run_module("pitstop_logger_enhanced", run_name="__main__")

    csv_path = tmp_path / "pitstop_log.csv"
    rows = list(csv.reader(open(csv_path)))
    assert rows[0] == module["HEADERS"]
    assert len(rows) == 2
    # ensure the stint duration laps column is present
    assert rows[1][-1] == "1"
    conn = sqlite3.connect(db_path)
    db_rows = list(conn.execute("SELECT * FROM pitstops"))
    conn.close()
    assert len(db_rows) == 1
