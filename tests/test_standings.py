import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import standings_sorter


def test_class_order_sorting(tmp_path, monkeypatch):
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
        ["2021-01-01T00:00:00", 0, "GT3Team1", "DriverA", "2708", 2, 1, 5, 60, 61, False, 0],
        ["2021-01-01T00:00:00", 1, "HyperTeam1", "DriverB", "4074", 1, 1, 5, 55, 56, False, 0],
        ["2021-01-01T00:00:00", 2, "HyperTeam2", "DriverC", "4074", 3, 2, 5, 57, 58, False, 1],
        ["2021-01-01T00:00:00", 3, "GT3Team2", "DriverD", "2708", 4, 2, 5, 62, 63, False, 2],
    ]
    with open(inp, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)

    standings_sorter.sort_and_write()

    with open(out, newline="") as f:
        out_rows = list(csv.DictReader(f))

    teams = [r["Team"] for r in out_rows]
    assert teams == ["HyperTeam1", "HyperTeam2", "GT3Team1", "GT3Team2"]
    classes = [r["Class"] for r in out_rows]
    assert classes == ["Hypercar", "Hypercar", "GT3", "GT3"]
