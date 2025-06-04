import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import standings_sorter


def test_sort_and_write(tmp_path, monkeypatch):
    inp = tmp_path / "standings_log.csv"
    out = tmp_path / "sorted_standings.csv"
    monkeypatch.setattr(standings_sorter, "INPUT", str(inp))
    monkeypatch.setattr(standings_sorter, "OUTPUT", str(out))

    header = [
        "Time",
        "CarIdx",
        "TeamName",
        "UserName",
        "CarClassID",
        "Position",
        "ClassPosition",
        "Lap",
        "BestLapTime",
        "LastLapTime",
        "OnPitRoad",
        "PitCount",
    ]
    rows = [
        ["2021-01-01T00:00:00", 0, "TeamA", "DriverA", "2708", 2, 1, 10, 60, 61, False, 1],
        ["2021-01-01T00:00:05", 1, "TeamB", "DriverB", "4074", 1, 1, 10, 55, 56, False, 0],
        ["2021-01-01T00:00:10", 0, "TeamA", "DriverA", "2708", 2, 1, 11, 60, 62, False, 1],
    ]
    with open(inp, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)

    standings_sorter.sort_and_write()

    with open(out, newline="") as f:
        out_rows = list(csv.DictReader(f))

    assert len(out_rows) == 2
    assert out_rows[0]["Team"] == "TeamB"
    assert out_rows[0]["Class"] == "Hypercar"
    assert out_rows[1]["Team"] == "TeamA"
    assert out_rows[1]["Class"] == "GT3"
    assert out_rows[1]["Avg Lap"] == "61.5"
