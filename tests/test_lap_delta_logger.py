import csv
import runpy
import sys
import types
import time
from pathlib import Path


def test_lap_delta_logger(tmp_path, monkeypatch):
    """Ensure lap_delta_logger creates a CSV with lap deltas."""

    class DummyIR:
        def __init__(self):
            self.is_initialized = True
            self.is_connected = True
            self.idx = 0
            self.data = [
                {
                    "SessionTime": 0,
                    "SessionNum": 0,
                    "CarIdxLap": [0, 0],
                    "CarIdxPosition": [1, 2],
                    "DriverInfo": {"Drivers": [{}, {}]},
                },
                {
                    "SessionTime": 30,
                    "SessionNum": 0,
                    "CarIdxLap": [1, 0],
                    "CarIdxPosition": [1, 2],
                    "DriverInfo": {"Drivers": [{}, {}]},
                },
                {
                    "SessionTime": 32,
                    "SessionNum": 0,
                    "CarIdxLap": [1, 1],
                    "CarIdxPosition": [1, 2],
                    "DriverInfo": {"Drivers": [{}, {}]},
                },
                {
                    "SessionTime": 60,
                    "SessionNum": 0,
                    "CarIdxLap": [2, 1],
                    "CarIdxPosition": [1, 2],
                    "DriverInfo": {"Drivers": [{}, {}]},
                },
                {
                    "SessionTime": 66,
                    "SessionNum": 0,
                    "CarIdxLap": [2, 2],
                    "CarIdxPosition": [1, 2],
                    "DriverInfo": {"Drivers": [{}, {}]},
                },
            ]

        def startup(self):
            pass

        def step(self):
            if self.idx < len(self.data) - 1:
                self.idx += 1

        def __getitem__(self, key):
            return self.data[self.idx][key]

    dummy_ir = DummyIR()
    monkeypatch.setitem(sys.modules, "irsdk", types.SimpleNamespace(IRSDK=lambda: dummy_ir))

    sleep_calls = [0]
    def fake_sleep(_):
        sleep_calls[0] += 1
        dummy_ir.step()
        if sleep_calls[0] >= 6:
            raise KeyboardInterrupt

    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(sys, "argv", ["lap_delta_logger.py"])
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    runpy.run_module("lap_delta_logger", run_name="__main__")

    csv_path = tmp_path / "lap_delta_log.csv"
    rows = list(csv.reader(open(csv_path)))
    assert rows[0] == ["Time", "CarIdx", "Lap", "DeltaToLeader"]
    assert rows[1][2:] == ["1", "0.0"]
    assert rows[2][2:] == ["1", "2"]
    assert rows[3][2:] == ["2", "0.0"]
    assert rows[4][2:] == ["2", "6"]

