from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eec_calendar import Race, Season


def test_available_logs(tmp_path):
    log_dir = tmp_path / "Race1"
    log_dir.mkdir()
    (log_dir / "foo.txt").write_text("data")
    race = Race(round=1, name="R1", date=date.today(), track="N/A", logs=log_dir)
    files = race.available_logs()
    assert "foo.txt" in files
    assert files["foo.txt"].is_file()


def test_season_structure():
    race = Race(round=1, name="R1", date=date.today(), track="N/A")
    season = Season(year=2025, races=[race])
    assert season.year == 2025
    assert season.races[0] is race
