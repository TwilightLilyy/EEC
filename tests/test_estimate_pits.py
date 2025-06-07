import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from race_gui import estimate_remaining_pits


def test_normal_expected():
    race_end = dt.datetime(2025, 6, 7, 12, 0)
    now = dt.datetime(2025, 6, 7, 10, 0)
    assert estimate_remaining_pits(race_end, now, 1800) == 4


def test_zero_expected_uses_fallback(caplog):
    race_end = dt.datetime(2025, 6, 7, 12, 0)
    now = dt.datetime(2025, 6, 7, 10, 0)
    pits = estimate_remaining_pits(race_end, now, 0, fallback=1800)
    assert pits == 4
    assert "expected pit-window duration missing" in caplog.text


def test_negative_expected_uses_fallback():
    race_end = dt.datetime(2025, 6, 7, 12, 0)
    now = dt.datetime(2025, 6, 7, 10, 0)
    assert estimate_remaining_pits(race_end, now, -50, fallback=1800) == 4

