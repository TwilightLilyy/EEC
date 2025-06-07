"""Team roster editing UI for the EEC race manager."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image, ImageTk  # type: ignore
except Exception:  # pragma: no cover - Pillow is optional in tests
    Image = None
    ImageTk = None

__all__ = [
    "TeamModel",
    "DriverModel",
    "RosterDashboard",
    "TeamEditor",
    "DriverTile",
    "LogoUploader",
    "ValidationSidebar",
    "_validate_team",
]


@dataclass
class DriverModel:
    """Simple driver model used by the team editor."""

    id: int
    name: str


@dataclass
class TeamModel:
    """Represents a team with drivers grouped by class."""

    id: int
    name: str
    logo_path: Path
    drivers: Dict[str, List[int]]  # {"hypercar": [...], "p2": [...], "gt3": [...]}


class DriverTile(ttk.Frame):
    """Tile showing a driver's name or an add placeholder."""

    def __init__(self, master: tk.Widget, driver: DriverModel | None = None) -> None:
        super().__init__(master)
        self.driver = driver
        text = driver.name if driver else "Add Driver"
        ttk.Label(self, text=text).pack()


class LogoUploader(ttk.Frame):
    """Widget used to upload and display a team logo."""

    def __init__(self, master: tk.Widget, path: Path | None = None) -> None:
        super().__init__(master)
        self.path = path
        self.label = ttk.Label(self)
        self.label.pack()
        if path and path.exists():
            self._load_image(path)

    def _load_image(self, path: Path) -> None:
        if Image is None:
            return
        try:
            img = Image.open(path)
        except Exception as exc:  # pragma: no cover - error path
            messagebox.showerror("Logo", f"Error loading logo: {exc}")
            return
        img = img.resize((64, 64))
        self.photo = ImageTk.PhotoImage(img)
        self.label.configure(image=self.photo)


class ValidationSidebar(ttk.Frame):
    """Sidebar listing validation errors for a team."""

    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master)
        self.msg = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.msg, justify="left").pack(anchor="nw")

    def show(self, errors: Dict[str, Any]) -> None:
        lines = [f"{k}: {v}" for k, v in errors.items() if v]
        self.msg.set("\n".join(lines))


class TeamEditor(tk.Toplevel):
    """Modal window used to edit a team's data."""

    def __init__(self, master: tk.Widget, team: TeamModel) -> None:
        super().__init__(master)
        self.title("Edit Team")
        self.team = team
        ttk.Label(self, text="Team Name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=team.name)
        ttk.Entry(self, textvariable=self.name_var).grid(row=0, column=1, sticky="ew")
        self.logo = LogoUploader(self, team.logo_path)
        self.logo.grid(row=1, column=0, columnspan=2, pady=5)
        self.sidebar = ValidationSidebar(self)
        self.sidebar.grid(row=0, column=2, rowspan=2, sticky="nsw", padx=5)
        self.columnconfigure(1, weight=1)
        self.refresh_validation()

    def refresh_validation(self) -> None:
        errors = _validate_team(self.team)
        self.sidebar.show(errors)


class RosterDashboard(ttk.Frame):
    """Scrollable frame displaying roster cards for all teams."""

    def __init__(self, master: tk.Widget, teams: List[TeamModel] | None = None) -> None:
        super().__init__(master)
        canvas = tk.Canvas(self, borderwidth=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.cards = ttk.Frame(canvas)
        self.cards.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.cards, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.teams = teams or []
        self.refresh()

    def refresh(self) -> None:
        for child in self.cards.winfo_children():
            child.destroy()
        for team in self.teams:
            card = ttk.Frame(self.cards, relief="ridge", padding=5)
            card.pack(fill="x", pady=2, padx=2)
            ttk.Label(card, text=team.name).pack(side="left")


# ── validation helpers ────────────────────────────────────────────

def _validate_team(team: TeamModel) -> Dict[str, Any]:
    """Return a dictionary with validation results for ``team``."""

    results: Dict[str, Any] = {}
    name_len = len(team.name.strip())
    results["name_error"] = not (3 <= name_len <= 30)
    results["logo_missing"] = not team.logo_path or not team.logo_path.exists()
    for cls in ("hypercar", "p2", "gt3"):
        drivers = team.drivers.get(cls, [])
        missing_key = f"{cls}_missing"
        over_key = f"{cls}_over"
        count = len(drivers)
        results[missing_key] = max(0, 2 - count)
        results[over_key] = max(0, count - 2)
    return results
