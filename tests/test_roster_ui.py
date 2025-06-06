import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roster_ui import group_by_team


def test_group_by_team():
    sample = [
        {"team": "Warriors of Light", "driver_class": "Hypercar", "driver": "Celestia Astraethi"},
        {"team": "Warriors of Light", "driver_class": "Hypercar", "driver": "Iryq"},
        {"team": "Warriors of Light", "driver_class": "GT3", "driver": "Pele"},
        {"team": "Warriors of Light", "driver_class": "GT3", "driver": "Luna"},
    ]
    expected = {
        "Warriors of Light": {
            "Hypercar": ["Celestia Astraethi", "Iryq"],
            "P2": [],
            "GT3": ["Pele", "Luna"],
        }
    }
    assert group_by_team(sample) == expected
