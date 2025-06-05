from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict


@dataclass
class Race:
    """Represent a single race in the Eorzean Endurance Championship."""

    round: int
    name: str
    date: date
    track: str
    logs: Optional[Path] = None

    def available_logs(self) -> Dict[str, Path]:
        """Return a mapping of log file names to paths if the log directory exists."""
        if not self.logs or not self.logs.exists():
            return {}
        return {p.name: p for p in self.logs.iterdir() if p.is_file()}


@dataclass
class Season:
    """Collection of races that make up a championship year."""

    year: int
    races: List[Race]


# Example calendar.  Additional rounds can be appended in the future.
EEC_2025 = Season(
    year=2025,
    races=[
        Race(
            round=1,
            name="Round 1",
            date=date(2025, 6, 4),
            track="Unknown",
            logs=Path("RaceLogs"),
        ),
    ],
)
