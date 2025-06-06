"""Tkinter UI to display EEC team rosters grouped by class."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import tkinter as tk
from tkinter import ttk

DRIVER_CLASSES = ["Hypercar", "P2", "GT3"]


def group_by_team(roster: List[Dict[str, str]]) -> Dict[str, Dict[str, List[str]]]:
    """Return roster data grouped by team and driver class."""
    teams: Dict[str, Dict[str, List[str]]] = {}
    for entry in roster:
        team = entry.get("team")
        driver_class = entry.get("driver_class")
        driver = entry.get("driver")
        if team is None or driver_class not in DRIVER_CLASSES or driver is None:
            continue
        team_data = teams.setdefault(team, {cls: [] for cls in DRIVER_CLASSES})
        team_data.setdefault(driver_class, []).append(driver)
    return teams


def load_roster(path: str | Path) -> List[Dict[str, str]]:
    """Load roster data from JSON or CSV file."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    rows: List[Dict[str, str]] = []
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append({"team": row.get("team", ""),
                         "driver_class": row.get("driver_class", ""),
                         "driver": row.get("driver", "")})
    return rows


def _format_driver_list(drivers: List[str]) -> str:
    if not drivers:
        return "\u2014"
    if len(drivers) == 1:
        return f"{drivers[0]}, \u2014"
    if len(drivers) == 2:
        return ", ".join(drivers)
    return f"{drivers[0]}, {drivers[1]} + {len(drivers) - 2} more"


class RosterView(tk.Tk):
    """Main application window for roster display."""

    def __init__(self, roster: List[Dict[str, str]]):
        super().__init__()
        self.title("EEC Team Rosters")
        self._roster = roster
        self._setup_ui()
        self.refresh()
        self.after(5000, self._auto_refresh)

    def _setup_ui(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.cards_frame = ttk.Frame(canvas)

        self.cards_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _auto_refresh(self) -> None:
        self.refresh()
        self.after(5000, self._auto_refresh)

    def update_roster(self, roster: List[Dict[str, str]]) -> None:
        self._roster = roster
        self.refresh()

    def refresh(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()

        teams = group_by_team(self._roster)
        for team, classes in sorted(teams.items()):
            card = ttk.Frame(self.cards_frame, relief="ridge", padding=5)
            card.pack(fill="x", padx=5, pady=5)

            ttk.Label(card, text=team, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
            for cls in DRIVER_CLASSES:
                drivers = classes.get(cls, [])
                text = _format_driver_list(drivers)
                ttk.Label(card, text=f"{cls}: {text}").pack(anchor="w")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="View EEC team rosters")
    parser.add_argument("file", help="Roster CSV or JSON file")
    args = parser.parse_args()

    roster_data = load_roster(args.file)
    RosterView(roster_data).mainloop()
