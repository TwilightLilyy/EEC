from datetime import datetime
__version__     = "2025.06.07.0"         # auto-bump in CI
__build_time__  = "2025-06-07T15:42:00Z" # auto-fill in CI
__commit_hash__ = "abc1234"              # git rev-parse --short HEAD

import sys

if getattr(sys, "frozen", False):
    try:
        setattr(sys, "_MEIPASS_VERSION", __version__)
        setattr(sys, "_MEIPASS_BUILD", __build_time__)
        setattr(sys, "_MEIPASS_COMMIT", __commit_hash__)
        if __spec__ is not None:
            __spec__.origin = f"{__spec__.origin}|{__version__}"
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText
import subprocess
import signal
import threading
import time
import os
import shutil
from pathlib import Path
from queue import Queue, Empty
from collections import deque

VERSION_DONE = threading.Event()
VERSION_OK = False

def _run_version_check() -> None:
    global VERSION_OK
    VERSION_OK = check_latest_version(__version__)
    VERSION_DONE.set()
import csv
import re
import json
from datetime import datetime, timedelta
from typing import Any
import argparse
import logging
import atexit
import platform
import traceback
from codebase_cleaner import (
    check_latest_version,
    acquire_single_instance_lock,
    focus_running_window,
)

# Acquire the single instance lock as soon as possible so additional
# processes launched during the heavy import phase fail fast on Windows
# where imports can be slow.
_EARLY_LOCK = None
if __name__ == "__main__":  # pragma: no cover - exercised via subprocess tests
    _EARLY_LOCK = acquire_single_instance_lock()
    if _EARLY_LOCK is None:
        focus_running_window()
        sys.exit(0)

import eec_teams
import importlib

try:
    from ensure_dependencies import ensure_package
except Exception:
    ensure_package = None

try:
    import irsdk
except ImportError:
    irsdk = None
OPENAI_IMPORT_ERROR: Exception | None = None
try:
    import openai
except Exception as exc:
    OPENAI_IMPORT_ERROR = exc
    openai = None

SVTTK_IMPORT_ERROR: Exception | None = None
try:
    import sv_ttk
except Exception as exc:
    SVTTK_IMPORT_ERROR = exc
    sv_ttk = None

OPENAI_ENABLED = True

LOG_PATH = Path(__file__).with_name("race_gui.log")

# Timestamp of the last "pit-window duration" warning. Used to throttle
# repeated messages when the expected stint duration is missing.
LAST_PIT_WARNING: datetime | None = None
PIT_WARNING_INTERVAL = timedelta(minutes=10)

LOG_FILES = [
    "pitstop_log.csv",
    "standings_log.csv",
    "sorted_standings.csv",
    "driver_swaps.csv",
    "driver_times.csv",
]

# Map ANSI colour codes (foreground) to Tkinter tag names
ANSI_COLOUR_MAP = {
    "30": "black",
    "90": "black",
    "31": "red",
    "91": "red",
    "32": "green",
    "92": "green",
    "33": "yellow",
    "93": "yellow",
    "34": "blue",
    "94": "blue",
    "35": "magenta",
    "95": "magenta",
    "36": "cyan",
    "96": "cyan",
    "37": "white",
    "97": "white",
}

EVENT_TYPES = {
    "overtake": {"label": "Overtakes", "colour": "blue"},
    "pitstop": {"label": "Pit Stops", "colour": "green"},
    "driver_swap": {"label": "Driver Swaps", "colour": "cyan"},
    "fastest_lap": {"label": "Fastest Laps", "colour": "magenta"},
    "penalty": {"label": "Penalties", "colour": "red"},
    "yellow": {"label": "Yellow / SC", "colour": "yellow"},
}


def filter_rows(rows):
    """Filter out non-racing entries from standings rows."""
    filtered = []
    car_re = re.compile(r"car\s*\d+$", re.IGNORECASE)
    for r in rows:
        driver = r.get("Driver", r.get("DriverName", ""))
        team = r.get("Team", r.get("TeamName", ""))
        try:
            pos = int(r.get("Pos", 0))
        except Exception:
            pos = 0
        try:
            laps = float(r.get("Laps", 0))
        except Exception:
            laps = 0.0
        if driver in {"Pace Car", "Lily Bowling"}:
            continue
        if team == "Lily Bowling":
            continue
        d = driver.strip().lower()
        t = team.strip().lower()
        if d == t and car_re.match(d):
            continue
        if pos <= 0 or laps <= 0:
            continue
        filtered.append(r)
    return filtered


def find_log_file(name: str) -> Path:
    """Return the first existing path for a log file."""
    path = Path(name)
    if path.exists():
        return path
    base = Path(sys.argv[0]).resolve().parent
    for p in (
        Path.cwd() / name,
        Path.cwd() / "RaceLogs" / name,
        base / name,
        base.parent / name,
    ):
        if p.exists():
            return p
    return path


def read_csv_file(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return field names and rows from a CSV file safely."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        data = f.read()
    lines = data.splitlines()
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        return [], []
    return reader.fieldnames, list(reader)


def _parse_time(val: str) -> float:
    """Return seconds represented by ``val`` which may be ``H:M:S`` or ``M:S``."""
    parts = val.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid time: {val}") from exc
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h = 0.0
        m, s = nums
    elif len(nums) == 1:
        h = 0.0
        m = 0.0
        s = nums[0]
    else:
        raise argparse.ArgumentTypeError(f"invalid time: {val}")
    return h * 3600 + m * 60 + s


def estimate_remaining_pits(
    race_end: datetime,
    now: datetime,
    expected: float | int,
    *,
    fallback: float = 1800,
) -> int:
    """Estimate remaining pit stops using historical stint duration.

    Parameters
    ----------
    race_end : datetime
        Timestamp when the race ends.
    now : datetime
        Current timestamp.
    expected : float | int
        Expected stint duration in seconds. Values ``<= 0`` trigger ``fallback``.
    fallback : float, optional
        Duration to use when ``expected`` is invalid, by default ``1800``.

    Returns
    -------
    int
        Estimated number of pit stops left.
    """

    global LAST_PIT_WARNING

    if expected is None or expected <= 0:
        if LAST_PIT_WARNING is None or now - LAST_PIT_WARNING >= PIT_WARNING_INTERVAL:
            logging.warning(
                "expected pit-window duration missing; using default %d s",
                int(fallback),
            )
            LAST_PIT_WARNING = now
        expected = fallback

    secs_left = max(0.0, (race_end - now).total_seconds())
    if expected == float("inf"):
        return 0
    return max(0, int(secs_left / expected))


def _find_python() -> str:
    """Return the preferred Python executable for launching child scripts."""
    exe = sys.executable

    # In development mode ``sys.executable`` is already the right interpreter
    if not getattr(sys, "frozen", False):
        return exe

    name = "python.exe" if os.name == "nt" else "python"

    # PyInstaller distributions may bundle an interpreter next to the GUI
    candidate = Path(exe).with_name(name)
    if candidate.exists():
        return str(candidate)

    # Some builds unpack the interpreter inside ``sys._MEIPASS``
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / name
        if candidate.exists():
            return str(candidate)

    # Fall back to an interpreter from the PATH
    for alt in ("python", "python3"):
        found = shutil.which(alt)
        if found:
            return found

    # As a last resort return ``sys.executable`` even though it may point back
    # to the frozen executable itself
    return exe


class RaceLoggerGUI:
    def __init__(self, root: tk.Tk, *, classic_theme: bool = False, time_left: float | None = None):
        self.root = root
        self.root.title(f"EEC Logger • v{__version__} • {__commit_hash__}")
        # Ensure the window is large enough when it first appears
        self.root.minsize(800, 600)
        if hasattr(self.root, "geometry"):
            self.root.geometry("1100x800")

        self.theme = self.setup_style(classic_theme)
        icon_path = Path(__file__).resolve().parent / "Logos" / "App" / "EECApp.png"
        if icon_path.exists():
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
            except Exception:
                pass
        self.race_end_override = (
            datetime.now() + timedelta(seconds=time_left)
            if time_left is not None
            else None
        )
        self.proc = None
        self.log_queue: Queue[str] = Queue()
        self.output_thread = None
        self.teams_file = Path(eec_teams.__file__).resolve()
        self.team_drivers = self.load_team_drivers()
        self.db_path = Path("eec_log.db")

        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Quit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self.auto_scroll = tk.BooleanVar(value=True)
        self.wrap_logs = tk.BooleanVar(value=True)
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(
            label="Auto Scroll Logs",
            variable=self.auto_scroll,
        )
        options_menu.add_checkbutton(
            label="Wrap Log Text",
            variable=self.wrap_logs,
            command=self.update_wrap,
        )
        options_menu.add_command(
            label="Set Time Left…",
            command=self.ask_time_left,
        )
        menubar.add_cascade(label="Options", menu=options_menu)
        root.config(menu=menubar)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        root.update_idletasks()

        frm = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frm, text="Logger")

        self.status_lbl = ttk.Label(frm, text="iRacing: ?")
        self.status_lbl.grid(column=0, row=0, sticky="w")
        self.log_status_frame = ttk.Frame(frm)
        self.log_status_frame.grid(column=1, row=0, sticky="w")
        self.log_status_lbls: dict[str, ttk.Label] = {}
        for i, f in enumerate(LOG_FILES):
            lbl = ttk.Label(self.log_status_frame, text=f"{f}: ?")
            lbl.grid(column=0, row=i, sticky="w")
            self.log_status_lbls[f] = lbl
        self.start_btn = ttk.Button(
            frm, text="Start Logging", command=self.start_logging
        )
        self.start_btn.grid(column=0, row=1, pady=5, sticky="ew")
        if not VERSION_DONE.is_set() or not VERSION_OK:
            self.start_btn.config(state="disabled")
            self.root.after(200, self._check_version_ready)
        self.stop_btn = ttk.Button(
            frm, text="Stop Logging", command=self.stop_logging, state="disabled"
        )
        self.stop_btn.grid(column=1, row=1, pady=5, sticky="ew")

        ttk.Button(frm, text="Reset Logs", command=self.reset_logs).grid(
            column=0, row=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="Save Logs…", command=self.save_logs).grid(
            column=1, row=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Pit Stops…", command=self.view_pitstops).grid(
            column=0, row=3, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Standings…", command=self.view_standings).grid(
            column=0, row=4, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Drive Times…", command=self.view_driver_times).grid(
            column=0, row=5, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(frm, text="View Stint Tracker…", command=self.view_stint_tracker).grid(
            column=0, row=6, columnspan=2, pady=5, sticky="ew"
        )
        ttk.Button(
            frm,
            text="View Series Standings…",
            command=self.view_series_standings,
        ).grid(column=0, row=7, columnspan=2, pady=5, sticky="ew")
        ttk.Button(frm, text="Export to ChatGPT", command=self.export_logs).grid(
            column=0, row=8, columnspan=2, pady=5, sticky="ew"
        )

        self.log_box = ScrolledText(
            frm,
            width=80,
            height=20,
            state="disabled",
            background=self.log_box_bg,
            foreground=self.fg,
            insertbackground="white",
        )
        self.log_box.grid(column=0, row=9, columnspan=2, pady=5)
        self.update_wrap()

        # Additional tabs for CSV logs
        try:
            self.create_csv_tab("driver_swaps.csv", "Driver Swaps")
            print("[TAB-OK] driver_swaps")
        except Exception as exc:
            print(f"[TAB-ERROR] driver_swaps_tab \u2192 {exc}", file=sys.stderr)

        # Auto-refresh the standings log viewer so it stays in sync with the
        # running logger.
        try:
            self.create_standings_log_tab(
                "standings_log.csv", "Standings Log", auto_refresh=True
            )
            print("[TAB-OK] standings_log")
        except Exception as exc:
            print(f"[TAB-ERROR] standings_log_tab \u2192 {exc}", file=sys.stderr)

        # New tabs for pit stop log and stint tracker
        try:
            self.create_pitstop_tab("pitstop_log.csv", "Pit Stops", auto_refresh=True)
            print("[TAB-OK] pitstop")
        except Exception as exc:
            print(f"[TAB-ERROR] pitstop_tab \u2192 {exc}", file=sys.stderr)

        try:
            self.create_stint_tab()
            print("[TAB-OK] stint")
        except Exception as exc:
            print(f"[TAB-ERROR] stint_tab \u2192 {exc}", file=sys.stderr)

        try:
            self.create_team_editor_tab()
            print("[TAB-OK] team_editor")
        except Exception as exc:
            print(f"[TAB-ERROR] team_editor_tab \u2192 {exc}", file=sys.stderr)

        # Start stint tracker update loop
        self.update_stint_table()

        # Live race feed data
        self.event_buffers = {k: deque(maxlen=3) for k in EVENT_TYPES}
        self.feed_window = None
        self.feed_text = None
        self.feed_paused = tk.BooleanVar(value=False)

        ttk.Button(frm, text="View Live Feed…", command=self.open_feed_window).grid(
            column=0, row=3, columnspan=2, pady=5, sticky="ew"
        )


        # ── ANSI colour setup for log output ────────────────────
        self._ansi_re = re.compile(r"\x1b\[([0-9;]+)m")
        self._current_tags: list[str] = []
        _colours = {
            "black": "black",
            "red": "red",
            "green": "green",
            "yellow": "#cccc00",
            "blue": "blue",
            "magenta": "magenta",
            "cyan": "cyan",
            "white": "white",
        }
        for name, colour in _colours.items():
            self.log_box.tag_config(f"fg-{name}", foreground=colour)
        self.log_box.tag_config("bold", font=("TkDefaultFont", 9, "bold"))

        self.update_status_once()
        self.root.after(100, self.update_log_box)
        self.root.after(3000, self.update_feed)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.monitor_logging_once()

    def open_feed_window(self) -> None:
        if self.feed_window is not None and self.feed_window.winfo_exists():
            self.feed_window.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Live Race Feed")
        self.feed_window = win

        self.feed_text = ScrolledText(
            win,
            width=80,
            height=20,
            state="disabled",
            background=self.log_box_bg,
            foreground=self.fg,
            insertbackground="white",
        )
        self.feed_text.pack(fill="both", expand=True)

        controls = ttk.Frame(win)
        controls.pack(pady=5)
        ttk.Checkbutton(
            controls, text="Pause Updates", variable=self.feed_paused
        ).pack(side="left", padx=5)
        ttk.Button(controls, text="Clear Feed", command=self.clear_feed).pack(
            side="left", padx=5
        )

        for etype, cfg in EVENT_TYPES.items():
            self.feed_text.tag_config(etype, foreground=cfg["colour"])
            self.feed_text.tag_config(
                f"header-{etype}",
                foreground=cfg["colour"],
                font=("TkDefaultFont", 9, "bold"),
            )

        def on_close() -> None:
            self.feed_window = None
            self.feed_text = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def setup_style(self, classic: bool = False) -> str:
        """Configure ttk styles and return the applied theme name."""
        style = ttk.Style(self.root)
        theme = "default"
        if not classic and sv_ttk is not None:
            try:
                sv_ttk.set_theme("dark", self.root)
                if hasattr(style, "layout") and not style.layout("TButton"):
                    raise RuntimeError("sv_ttk theme resources missing")
                theme = style.theme_use()
            except Exception:
                try:
                    style.theme_use("clam")
                except Exception:
                    pass
                theme = "clam"
        else:
            try:
                style.theme_use("clam")
            except Exception:
                pass
            theme = "clam"
        self.bg = "#23272e"
        self.fg = "#e7e7ff"
        accent = "#3c445c"
        self.root.configure(bg=self.bg)
        # Escaped font family to avoid TclError when family name has spaces
        self.root.option_add("*Font", "{Segoe UI} 10")
        style.configure("TFrame", background=self.bg)
        style.configure("TLabel", background=self.bg, foreground=self.fg)
        style.configure("TButton", background="#2b3249", foreground=self.fg, padding=6)
        style.map("TButton", background=[("active", accent)])
        style.configure("TNotebook", background=self.bg)
        style.configure(
            "TNotebook.Tab", background="#2b3249", foreground=self.fg, padding=(10, 4)
        )
        style.map("TNotebook.Tab", background=[("selected", accent)])
        self.log_box_bg = "#111111"
        return theme

    # ── logging subprocess management ────────────────────────────
    def start_logging(self):
        if self.proc:
            messagebox.showinfo("Logger", "Already running")
            return

        logger = logging.getLogger("race_gui")
        runner: Path

        try:
            if getattr(sys, "frozen", False):
                base = Path(sys._MEIPASS)
                runner = base / "race_data_runner.py"
                if not runner.exists():
                    base = Path(__file__).resolve().parent
                    runner = base / "race_data_runner.py"
                    if not runner.exists():
                        runner = base.parent / "race_data_runner.py"
            else:
                import race_data_runner as _runner_mod
                runner = Path(_runner_mod.__file__).resolve()
        except Exception:
            logger.exception("Failed to locate race_data_runner.py")
            base = Path(__file__).resolve().parent
            runner = base / "race_data_runner.py"
            if not runner.exists():
                runner = base.parent / "race_data_runner.py"

        if not runner.exists():
            msg = f"race_data_runner.py not found: {runner}"
            logger.error(msg)
            messagebox.showerror("Logger", msg)
            self.proc = None
            return

        python = _find_python()
        cmd = [python, str(runner), "--db", str(self.db_path), "--auto-install"]
        print(f"[INFO] Launching {runner.name} --db {self.db_path}")

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            logger.exception("Failed to launch race_data_runner")
            messagebox.showerror("Logger", f"Failed to launch runner: {exc}")
            self.proc = None
            return

        self.output_thread = threading.Thread(target=self.read_output, daemon=True)
        self.output_thread.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def stop_logging(self):
        if not self.proc:
            return
        try:
            # Gracefully stop the runner so it can terminate child processes
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Fallback to force termination if it doesn't exit
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass
        self.proc = None
        self.output_thread = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def monitor_logging_once(self):
        logger = logging.getLogger("race_gui")
        if self.proc:
            ret = self.proc.poll()
            if ret is not None:
                logger.warning(
                    "Logger process exited with code %s, restarting", ret
                )
                self.proc = None
                self.output_thread = None
                self.start_logging()
        self.root.after(10000, self.monitor_logging_once)

    # ── connection status loop ──────────────────────────────────
    def update_status_once(self):
        status = "N/A"
        if irsdk:
            ir = irsdk.IRSDK()
            try:
                ir.startup()
                connected = ir.is_initialized and ir.is_connected
                status = "Connected" if connected else "Waiting"
            except Exception:
                status = "Error"
            finally:
                try:
                    ir.shutdown()
                except Exception:
                    pass
        self.status_lbl.config(text=f"iRacing: {status}")
        now = time.time()
        for name, lbl in self.log_status_lbls.items():
            path = find_log_file(name)
            if path.exists():
                age = now - path.stat().st_mtime
                running = self.proc is not None and age < 10
                state = "active" if running else "stale"
                lbl.config(text=f"{path.name}: {int(age)}s ({state})")
            else:
                lbl.config(text=f"{name}: missing")
        self.root.after(2000, self.update_status_once)

    # ── log management helpers ──────────────────────────────────
    def reset_logs(self):
        if not messagebox.askyesno("Confirm", "Delete existing log files?"):
            return
        for f in LOG_FILES:
            path = find_log_file(f)
            if path.exists():
                try:
                    path.open("w").close()
                except Exception:
                    pass
        messagebox.showinfo("Reset", "Logs cleared")

    def save_logs(self):
        target = filedialog.askdirectory(title="Select folder to save logs")
        if not target:
            return
        for f in LOG_FILES:
            if os.path.exists(f):
                shutil.copy(f, target)
        messagebox.showinfo("Saved", f"Logs copied to {target}")

    def _check_version_ready(self) -> None:
        if VERSION_DONE.is_set():
            if VERSION_OK:
                self.start_btn.config(state="normal")
            return
        self.root.after(200, self._check_version_ready)

    def update_wrap(self) -> None:
        wrap = tk.WORD if self.wrap_logs.get() else tk.NONE
        self.log_box.configure(wrap=wrap)

    def create_csv_tab(
        self,
        csv_path: str,
        title: str,
        *,
        auto_refresh: bool = False,
        refresh_ms: int = 5000,
    ) -> None:
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        def load() -> None:
            tree.delete(*tree.get_children())
            path = find_log_file(csv_path)
            if not path.exists():
                return
            # Some log files may contain characters that are not valid UTF-8.
            # Using errors="replace" avoids a crash when decoding such files by
            # substituting invalid bytes with the Unicode replacement character.
            fields, rows = read_csv_file(path)
            if not fields:
                return
            tree["columns"] = fields
            for c in fields:
                tree.heading(c, text=c)
                tree.column(c, anchor="center")
            for row in rows:
                tree.insert("", "end", values=[row.get(c, "") for c in fields])

        ttk.Button(frame, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )

        def refresh_loop() -> None:
            load()
            if auto_refresh:
                self.root.after(refresh_ms, refresh_loop)

        refresh_loop()

    def create_stint_tab(self) -> None:
        """Create a tab showing current stint information."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Stint Tracker")

        cols = [
            "Car",
            "Driver",
            "Team",
            "Class",
            "Stint Laps",
            "Since Last Pit",
            "Until Next Pit",
            "Pits Left",
        ]
        self.stint_tab_tree = ttk.Treeview(frame, columns=cols, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.stint_tab_tree.yview)
        self.stint_tab_tree.configure(yscrollcommand=vsb.set)
        self.stint_tab_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for c in cols:
            self.stint_tab_tree.heading(c, text=c)
            self.stint_tab_tree.column(c, anchor="center")

        ttk.Button(frame, text="Refresh", command=self.update_stint_table).grid(
            row=1, column=0, columnspan=2, pady=5
        )

        self.update_stint_table()

    def create_pitstop_tab(
        self,
        csv_path: str,
        title: str,
        *,
        auto_refresh: bool = False,
        refresh_ms: int = 5000,
    ) -> None:
        """Specialised CSV viewer for the pit stop log."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        width_file = Path("pitstop_view_widths.json")
        widths = {}
        if width_file.exists():
            try:
                with open(width_file, "r", encoding="utf-8") as wf:
                    widths = json.load(wf)
            except Exception:
                widths = {}

        col_map = {
            "Class": "Class",
            "TeamName": "Team",
            "DriverName": "Driver",
            "Stint Start Timestamp": "Start Time",
            "Stint End Timestamp": "End Time",
            "Stint Start SessionTime": "Start Session",
            "Stint End SessionTime": "End Session",
            "Stint Start Lap": "Start Lap",
            "Stint End Lap": "End Lap",
            "Stint Duration (min:sec)": "Duration",
            "Stint Duration (Laps)": "Stint Laps",
        }
        display_cols = list(col_map.keys())

        def fmt_iso(ts: str) -> str:
            try:
                dt = datetime.fromisoformat(ts)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return ts

        def fmt_num(val: str) -> str:
            try:
                num = float(val)
            except Exception:
                return val
            return f"{num:.3f}".rstrip("0").rstrip(".")

        def load() -> None:
            tree.delete(*tree.get_children())
            path = find_log_file(csv_path)
            if not path.exists():
                return
            fields, rows = read_csv_file(path)
            if not fields:
                return
            cols = [c for c in display_cols if c in fields]
            tree["columns"] = cols
            for c in cols:
                tree.heading(c, text=col_map[c])
                tree.column(c, anchor="center", width=widths.get(c, 100), stretch=True)
            for row in rows:
                vals = []
                for c in cols:
                    v = row.get(c, "")
                    if c in {"Stint Start Timestamp", "Stint End Timestamp"}:
                        v = fmt_iso(v)
                    elif c in {"Stint Start SessionTime", "Stint End SessionTime", "Stint Duration (sec)"}:
                        v = fmt_num(v)
                    vals.append(v)
                tree.insert("", "end", values=vals)

        def save_widths(_: Any = None) -> None:
            data = {c: tree.column(c)["width"] for c in tree["columns"]}
            try:
                with open(width_file, "w", encoding="utf-8") as wf:
                    json.dump(data, wf)
            except Exception:
                pass

        tree.bind("<ButtonRelease-1>", save_widths)

        ttk.Button(frame, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )

        def refresh_loop() -> None:
            load()
            if auto_refresh:
                self.root.after(refresh_ms, refresh_loop)

        refresh_loop()

    def create_standings_log_tab(
        self,
        csv_path: str,
        title: str,
        *,
        auto_refresh: bool = False,
        refresh_ms: int = 5000,
    ) -> None:
        """CSV viewer for the raw standings log with class sorting."""
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        CLASS_COLOURS = {
            1: "#f3e36b",
            2: "#174fa3",
            3: "#d9534f",
            4: "#24c080",
            5: "#d878d8",
        }

        def load() -> None:
            tree.delete(*tree.get_children())
            path = find_log_file(csv_path)
            if not path.exists():
                return
            fields, rows = read_csv_file(path)
            if not fields:
                return
            tree["columns"] = fields
            for c in fields:
                tree.heading(c, text=c)
                tree.column(c, anchor="center")

            rows = filter_rows(rows)

            class_leaders: dict[str, int] = {}
            for r in rows:
                cls = r.get("CarClassID", "")
                try:
                    pos = int(r.get("Position", 0))
                except Exception:
                    pos = 0
                if cls not in class_leaders or pos < class_leaders[cls]:
                    class_leaders[cls] = pos
            order = {
                c: i + 1 for i, c in enumerate(sorted(class_leaders, key=class_leaders.get))
            }

            rows.sort(
                key=lambda r: (
                    order.get(r.get("CarClassID", ""), len(order) + 1),
                    int(r.get("Position", 0)),
                )
            )

            for r in rows:
                vals = [r.get(c, "") for c in fields]
                cls_order = order.get(r.get("CarClassID", ""), 0)
                tag = f"class-{cls_order}"
                if tag not in tree.tag_names():
                    colour = CLASS_COLOURS.get(cls_order, "")
                    if colour:
                        tree.tag_configure(tag, background=colour)
                tree.insert("", "end", values=vals, tags=(tag,))

        ttk.Button(frame, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )

        def refresh_loop() -> None:
            load()
            if auto_refresh:
                self.root.after(refresh_ms, refresh_loop)

        refresh_loop()

    # ── Stint Tracker overlay ───────────────────────────────────
    def view_stint_tracker(self) -> None:
        if getattr(self, "stint_win", None) and self.stint_win.winfo_exists():
            self.stint_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Stint Tracker")
        self.stint_win = win

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        cols = [
            "Car",
            "Driver",
            "Team",
            "Class",
            "Stint Laps",
            "Since Last Pit",
            "Until Next Pit",
            "Pits Left",
        ]
        self.stint_tree = ttk.Treeview(frame, columns=cols, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.stint_tree.yview)
        self.stint_tree.configure(yscrollcommand=vsb.set)
        self.stint_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for c in cols:
            self.stint_tree.heading(c, text=c, command=lambda c=c: self.sort_stint_tree(c))
            self.stint_tree.column(c, anchor="center")

        self.stint_sort_col = None
        self.stint_sort_reverse = False
        self.update_stint_table()

        ttk.Button(frame, text="Refresh", command=self.update_stint_table).grid(
            row=1, column=0, columnspan=2, pady=5
        )

        def on_close() -> None:
            self.stint_tree = None
            self.stint_win = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def view_logs(self):
        log_dir = Path("logs")
        file_map = {f.name: f for f in log_dir.glob("*.txt")}
        swap_file = Path("driver_swaps.csv")
        if swap_file.exists():
            file_map[swap_file.name] = swap_file
        files = list(file_map.keys())
        if not files:
            messagebox.showinfo("Logs", "No log files found")
            return

        win = tk.Toplevel(self.root)
        win.title("View Logs")

        sel = tk.StringVar(value=files[0])
        combo = ttk.Combobox(win, textvariable=sel, values=files, state="readonly")
        combo.pack(fill="x", padx=5, pady=5)

        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True, padx=5, pady=5)

        def load(event=None):
            path = file_map[sel.get()]
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception as e:
                content = f"Error reading {path}: {e}"
            txt.delete("1.0", tk.END)
            txt.insert(tk.END, content)
            txt.see(tk.END)

        ttk.Button(win, text="Refresh", command=load).pack(pady=5)
        combo.bind("<<ComboboxSelected>>", load)
        load()

    def view_standings(self):
        csv_path = find_log_file("sorted_standings.csv")
        if not csv_path.exists():
            messagebox.showinfo("Standings", "No standings file found")
            return

        win = tk.Toplevel(self.root)
        win.title("Standings")
        cols = [
            "Team",
            "Driver",
            "Class",
            "Pos",
            "Class Pos",
            "Laps",
            "Pits",
            "Avg Lap",
            "Best Lap",
            "Last Lap",
            "In Pit",
        ]
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        def load():
            tree.delete(*tree.get_children())
            try:
                _, rows = read_csv_file(csv_path)
                rows = filter_rows(rows)
                # determine order of classes based on their best overall position
                class_leaders = {}
                for r in rows:
                    try:
                        pos = int(r.get("Pos", 0))
                    except Exception:
                        pos = 0
                    cls = r.get("Class", "")
                    if cls not in class_leaders or pos < class_leaders[cls]:
                        class_leaders[cls] = pos
                order = {
                    c: i for i, c in enumerate(sorted(class_leaders, key=class_leaders.get))
                }
                rows.sort(
                    key=lambda r: (
                        order.get(r.get("Class", ""), len(order)),
                        int(r.get("Pos", 0)),
                    )
                )

                def fmt(val: str) -> str:
                    try:
                        num = float(val)
                    except Exception:
                        return val
                    return f"{num:.3f}".rstrip("0").rstrip(".")

                for r in rows:
                    vals = []
                    for c in cols:
                        v = r.get(c, "")
                        if c in {"Best Lap", "Last Lap"}:
                            v = fmt(v)
                        vals.append(v)
                    tree.insert("", "end", values=vals)
            except Exception as e:
                messagebox.showerror("Standings", f"Error reading {csv_path}: {e}")

        ttk.Button(win, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
        load()

    def view_series_standings(self) -> None:
        """Display the championship points table."""
        csv_path = find_log_file("series_standings.csv")
        if not csv_path.exists():
            messagebox.showinfo(
                "Series Standings", "No series standings file found"
            )
            return

        win = tk.Toplevel(self.root)
        win.title("Series Standings")

        tree = ttk.Treeview(win, show="headings")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        def load() -> None:
            tree.delete(*tree.get_children())
            try:
                fields, rows = read_csv_file(csv_path)
                if not fields:
                    return
                tree["columns"] = fields
                for c in fields:
                    tree.heading(c, text=c)
                    tree.column(c, anchor="center")
                for row in rows:
                    tree.insert("", "end", values=[row.get(c, "") for c in fields])
            except Exception as e:
                messagebox.showerror(
                    "Series Standings", f"Error reading {csv_path}: {e}"
                )

        ttk.Button(win, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
        load()

    def view_driver_times(self):
        csv_path = find_log_file("driver_times.csv")
        if not csv_path.exists():
            messagebox.showinfo("Driver Times", "No driver time file found")
            return

        win = tk.Toplevel(self.root)
        win.title("Driver Times")
        cols = ["Team", "Driver", "Total"]
        tree = ttk.Treeview(win, columns=cols, show="headings")
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        sort_col = None
        sort_reverse = False
        rows_cache = []

        def fmt(sec: str) -> str:
            try:
                val = float(sec)
            except Exception:
                return sec
            h = int(val // 3600)
            m = int((val % 3600) // 60)
            s = int(val % 60)
            return f"{h}:{m:02d}:{s:02d}"

        team_var = tk.StringVar(value="All")

        def refresh_tree() -> None:
            tree.delete(*tree.get_children())
            team = team_var.get()
            rows = rows_cache
            if team and team != "All":
                rows = [r for r in rows if r.get("TeamName", r.get("Team", "")) == team]
            if sort_col is not None:
                def key(r):
                    if sort_col == "Total":
                        try:
                            return float(r.get("Total Time (sec)", 0))
                        except Exception:
                            return 0.0
                    return r.get(sort_col + "Name", r.get(sort_col, "")).lower()
                rows = sorted(rows, key=key, reverse=sort_reverse)
            for r in rows:
                tree.insert(
                    "",
                    "end",
                    values=[
                        r.get("TeamName", r.get("Team", "")),
                        r.get("DriverName", r.get("Driver", "")),
                        r.get("Total Time (h:m:s)") or fmt(r.get("Total Time (sec)", "")),
                    ],
                )

        def load() -> None:
            nonlocal rows_cache
            try:
                _, rows_cache = read_csv_file(csv_path)
                teams = sorted({r.get("TeamName", r.get("Team", "")) for r in rows_cache})
                team_combo["values"] = ["All"] + teams
                if team_var.get() not in teams:
                    team_var.set("All")
                refresh_tree()
            except Exception as e:
                messagebox.showerror("Driver Times", f"Error reading {csv_path}: {e}")

        def sort_by(col: str) -> None:
            nonlocal sort_col, sort_reverse
            if sort_col == col:
                sort_reverse = not sort_reverse
            else:
                sort_col = col
                sort_reverse = False
            refresh_tree()

        for c in cols:
            tree.heading(c, text=c, command=lambda c=c: sort_by(c))
            tree.column(c, anchor="center")

        controls = ttk.Frame(win)
        controls.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        ttk.Label(controls, text="Team:").pack(side="left")
        team_combo = ttk.Combobox(controls, textvariable=team_var, state="readonly")
        team_combo.pack(side="left", padx=5)
        team_combo.bind("<<ComboboxSelected>>", lambda e: refresh_tree())
        ttk.Button(controls, text="Refresh", command=load).pack(side="left", padx=5)

        load()

    def view_pitstops(self):
        csv_path = find_log_file("pitstop_log.csv")

        win = tk.Toplevel(self.root)
        win.title("Pit Stops")
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        if not csv_path.exists():
            messagebox.showinfo("Pit Stops", "No pit stop file found")

        tree = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        width_file = Path("pitstop_view_widths.json")
        widths = {}
        if width_file.exists():
            try:
                with open(width_file, "r", encoding="utf-8") as wf:
                    widths = json.load(wf)
            except Exception:
                widths = {}

        col_map = {
            "Class": "Class",
            "TeamName": "Team",
            "DriverName": "Driver",
            "Stint Start Timestamp": "Start Time",
            "Stint End Timestamp": "End Time",
            "Stint Start SessionTime": "Start Session",
            "Stint End SessionTime": "End Session",
            "Stint Start Lap": "Start Lap",
            "Stint End Lap": "End Lap",
            "Stint Duration (min:sec)": "Duration",
            "Stint Duration (Laps)": "Stint Laps",
        }
        display_cols = list(col_map.keys())

        def fmt_iso(ts: str) -> str:
            try:
                dt = datetime.fromisoformat(ts)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return ts

        def fmt_num(val: str) -> str:
            try:
                num = float(val)
            except Exception:
                return val
            return f"{num:.3f}".rstrip("0").rstrip(".")

        def load() -> None:
            tree.delete(*tree.get_children())
            if not csv_path.exists():
                return
            try:
                fields, rows = read_csv_file(csv_path)
                if not fields:
                    return
                cols = [c for c in display_cols if c in fields]
                tree["columns"] = cols
                for c in cols:
                    tree.heading(c, text=col_map[c])
                    tree.column(c, anchor="center", width=widths.get(c, 100), stretch=True)
                for row in rows:
                    vals = []
                    for c in cols:
                        v = row.get(c, "")
                        if c in {"Stint Start Timestamp", "Stint End Timestamp"}:
                            v = fmt_iso(v)
                        elif c in {"Stint Start SessionTime", "Stint End SessionTime", "Stint Duration (sec)"}:
                            v = fmt_num(v)
                        vals.append(v)
                    tree.insert("", "end", values=vals)
            except Exception as e:
                messagebox.showerror("Pit Stops", f"Error reading {csv_path}: {e}")

        def save_widths(_: Any = None) -> None:
            data = {c: tree.column(c)["width"] for c in tree["columns"]}
            try:
                with open(width_file, "w", encoding="utf-8") as wf:
                    json.dump(data, wf)
            except Exception:
                pass

        tree.bind("<ButtonRelease-1>", save_widths)
        ttk.Button(frame, text="Refresh", command=load).grid(
            row=1, column=0, columnspan=2, pady=5
        )
        load()

    # ── Stint Tracker helpers ──────────────────────────────────
    def sort_stint_tree(self, col: str) -> None:
        if getattr(self, "stint_sort_col", None) == col:
            self.stint_sort_reverse = not self.stint_sort_reverse
        else:
            self.stint_sort_col = col
            self.stint_sort_reverse = False

        def conv(val: str) -> float:
            if val.count(":"):
                parts = [int(p) for p in val.split(":")]
                if len(parts) == 2:
                    return parts[0] * 60 + parts[1]
                if len(parts) == 3:
                    return parts[0] * 3600 + parts[1] * 60 + parts[2]
            try:
                return float(val)
            except Exception:
                return 0.0

        data = [
            (conv(self.stint_tree.set(k, col)), k)
            for k in self.stint_tree.get_children("")
        ]
        data.sort(reverse=self.stint_sort_reverse)
        for index, (_, k) in enumerate(data):
            self.stint_tree.move(k, "", index)

    def update_stint_table(self) -> None:
        trees = []
        t1 = getattr(self, "stint_tree", None)
        t2 = getattr(self, "stint_tab_tree", None)
        if t1 is not None:
            trees.append(t1)
        if t2 is not None and t2 is not t1:
            trees.append(t2)
        if not trees:
            return

        for t in trees:
            t.delete(*t.get_children())
        pit_path = find_log_file("pitstop_log.csv")
        stand_path = find_log_file("standings_log.csv")

        pit_rows = []
        if pit_path.exists():
            _, pit_rows = read_csv_file(pit_path)

        stand_rows = []
        if stand_path.exists():
            _, stand_rows = read_csv_file(stand_path)

        latest_stand: dict[str, dict[str, str]] = {}
        for r in stand_rows:
            car = r.get("CarIdx")
            if not car:
                continue
            if car not in latest_stand or r.get("Time", "") > latest_stand[car].get("Time", ""):
                latest_stand[car] = r

        last_pit: dict[str, dict[str, str]] = {}
        race_start = None
        for r in pit_rows:
            car = r.get("CarIdx")
            if not car:
                continue
            try:
                ts = datetime.fromisoformat(r.get("Stint End Timestamp"))
            except Exception:
                continue
            if race_start is None:
                try:
                    race_start = datetime.fromisoformat(r.get("Stint Start Timestamp"))
                except Exception:
                    pass
            if car not in last_pit or ts > datetime.fromisoformat(last_pit[car]["Stint End Timestamp"]):
                last_pit[car] = r

        if race_start is None:
            start_times = []
            for r in stand_rows:
                try:
                    start_times.append(datetime.fromisoformat(r.get("Time")))
                except Exception:
                    continue
            if start_times:
                race_start = min(start_times)

        if race_start is None:
            race_start = datetime.now()
        if getattr(self, "race_end_override", None) is not None:
            race_end = self.race_end_override  # type: ignore[assignment]
        else:
            race_end = race_start + timedelta(hours=24)

        avg_dur: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in pit_rows:
            car = r.get("CarIdx")
            try:
                d = float(r.get("Stint Duration (sec)", 0))
            except Exception:
                continue
            avg_dur[car] = avg_dur.get(car, 0.0) + d
            counts[car] = counts.get(car, 0) + 1
        for car in avg_dur:
            avg_dur[car] /= counts.get(car, 1)

        rows = []

        now = datetime.now()
        for car, info in latest_stand.items():
            driver = info.get("UserName", info.get("Driver", ""))
            team = info.get("TeamName", info.get("Team", ""))
            cls = info.get("CarClassID", info.get("Class", ""))
            try:
                cur_lap = int(info.get("Lap", 0))
            except Exception:
                cur_lap = 0

            lp = last_pit.get(car)
            last_lap = int(lp.get("Stint End Lap", 0)) if lp else cur_lap
            try:
                last_end = datetime.fromisoformat(lp.get("Stint End Timestamp")) if lp else race_start
            except Exception:
                last_end = race_start

            stint_laps = max(0, cur_lap - last_lap)
            since_sec = (now - last_end).total_seconds()

            expected_raw = avg_dur.get(car, 3600.0)
            sanitized = (
                expected_raw if expected_raw is not None and expected_raw > 0 else 1800
            )
            until_sec = max(0.0, sanitized - since_sec)
            pits_left = estimate_remaining_pits(
                race_end, now, expected_raw, fallback=1800
            )

            def fmt(sec: float) -> str:
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

            rows.append([
                car,
                driver,
                team,
                cls,
                stint_laps,
                fmt(since_sec),
                fmt(until_sec),
                pits_left,
            ])

        for t in trees:
            for vals in rows:
                t.insert("", "end", values=vals)

        self.root.after(3000, self.update_stint_table)

    def ask_time_left(self) -> None:
        """Prompt for the remaining race time and update estimates."""
        val = simpledialog.askstring(
            "Time Left", "Remaining race time (H:M:S)", parent=self.root
        )
        if not val:
            return
        try:
            secs = _parse_time(val)
        except Exception:
            messagebox.showerror("Time Left", "Invalid time format")
            return
        self.race_end_override = datetime.now() + timedelta(seconds=secs)
        self.update_stint_table()

    # ── Team editor helpers ─────────────────────────────────────
    def load_team_drivers(self) -> dict[str, list[str]]:
        """Load team roster from eec_teams module."""
        try:
            import importlib
            importlib.reload(eec_teams)
            return {k: list(v) for k, v in eec_teams.TEAM_DRIVERS.items()}
        except Exception:
            return {}

    def save_team_drivers(self) -> None:
        """Write the team roster back to eec_teams.py."""
        try:
            import pprint
            data = pprint.pformat(
                self.team_drivers,
                indent=4,
                width=120,
                sort_dicts=True,
            )
            with open(self.teams_file, "w", encoding="utf-8") as fh:
                fh.write('"""EEC team roster used for championship calculations."""\n\n')
                fh.write("TEAM_DRIVERS: dict[str, list[str]] = ")
                fh.write(data)
                fh.write("\n\n__all__ = [\"TEAM_DRIVERS\"]\n")
        except Exception as e:
            messagebox.showerror("Teams", f"Error saving teams: {e}")

    def create_team_editor_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text="Teams")

        self.team_list = tk.Listbox(frame, exportselection=False)
        self.team_list.grid(row=0, column=0, rowspan=4, sticky="nsew", padx=5, pady=5)
        self.driver_list = tk.Listbox(frame, exportselection=False)
        self.driver_list.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=5, pady=5)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        def refresh_drivers(_event=None) -> None:
            self.driver_list.delete(0, tk.END)
            sel = self.team_list.curselection()
            if not sel:
                return
            team = self.team_list.get(sel[0])
            for d in self.team_drivers.get(team, []):
                self.driver_list.insert(tk.END, d)

        def refresh() -> None:
            self.team_list.delete(0, tk.END)
            for t in sorted(self.team_drivers):
                self.team_list.insert(tk.END, t)
            refresh_drivers()

        def add_team() -> None:
            name = simpledialog.askstring("Add Team", "Team name:", parent=self.root)
            if not name:
                return
            if name in self.team_drivers:
                messagebox.showerror("Teams", "Team already exists")
                return
            self.team_drivers[name] = []
            self.save_team_drivers()
            refresh()

        def edit_team() -> None:
            sel = self.team_list.curselection()
            if not sel:
                return
            old = self.team_list.get(sel[0])
            name = simpledialog.askstring(
                "Edit Team", "Team name:", initialvalue=old, parent=self.root
            )
            if not name or name == old:
                return
            self.team_drivers[name] = self.team_drivers.pop(old)
            self.save_team_drivers()
            refresh()
            idx = list(sorted(self.team_drivers)).index(name)
            self.team_list.selection_set(idx)
            refresh_drivers()

        def del_team() -> None:
            sel = self.team_list.curselection()
            if not sel:
                return
            team = self.team_list.get(sel[0])
            if not messagebox.askyesno("Delete", f"Delete team '{team}'?"):
                return
            self.team_drivers.pop(team, None)
            self.save_team_drivers()
            refresh()

        def add_driver() -> None:
            sel = self.team_list.curselection()
            if not sel:
                messagebox.showinfo("Teams", "Select a team first")
                return
            team = self.team_list.get(sel[0])
            name = simpledialog.askstring("Add Driver", "Driver name:", parent=self.root)
            if not name:
                return
            self.team_drivers.setdefault(team, []).append(name)
            self.save_team_drivers()
            refresh_drivers()

        def edit_driver() -> None:
            sel_t = self.team_list.curselection()
            sel_d = self.driver_list.curselection()
            if not sel_t or not sel_d:
                return
            team = self.team_list.get(sel_t[0])
            old = self.driver_list.get(sel_d[0])
            name = simpledialog.askstring(
                "Edit Driver", "Driver name:", initialvalue=old, parent=self.root
            )
            if not name or name == old:
                return
            drivers = self.team_drivers.get(team, [])
            try:
                idx = drivers.index(old)
            except ValueError:
                return
            drivers[idx] = name
            self.save_team_drivers()
            refresh_drivers()

        def del_driver() -> None:
            sel_t = self.team_list.curselection()
            sel_d = self.driver_list.curselection()
            if not sel_t or not sel_d:
                return
            team = self.team_list.get(sel_t[0])
            drv = self.driver_list.get(sel_d[0])
            if not messagebox.askyesno("Delete", f"Delete driver '{drv}'?"):
                return
            try:
                self.team_drivers[team].remove(drv)
            except Exception:
                pass
            self.save_team_drivers()
            refresh_drivers()

        self.team_list.bind("<<ListboxSelect>>", refresh_drivers)

        ttk.Button(frame, text="Add Team", command=add_team).grid(row=4, column=0, sticky="ew", padx=5, pady=2)
        ttk.Button(frame, text="Edit Team", command=edit_team).grid(row=5, column=0, sticky="ew", padx=5, pady=2)
        ttk.Button(frame, text="Delete Team", command=del_team).grid(row=6, column=0, sticky="ew", padx=5, pady=2)
        ttk.Button(frame, text="Add Driver", command=add_driver).grid(row=4, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(frame, text="Edit Driver", command=edit_driver).grid(row=5, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(frame, text="Delete Driver", command=del_driver).grid(row=6, column=1, sticky="ew", padx=5, pady=2)

        refresh()

    # ── ChatGPT export ──────────────────────────────────────────
    def export_logs(self):
        if not OPENAI_ENABLED or openai is None:
            messagebox.showinfo("Export", "OpenAI features disabled")
            return
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            messagebox.showerror("Export", "OPENAI_API_KEY not set")
            return
        openai.api_key = api_key
        data = []
        for f in LOG_FILES:
            if os.path.exists(f):
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    data.append(f"## {f}\n" + fh.read())
        prompt = "\n".join(data)[:12000]  # limit size
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            res_text = resp["choices"][0]["message"]["content"]
            info = filedialog.asksaveasfilename(
                title="Save analysis", defaultextension=".txt"
            )
            if info:
                with open(info, "w", encoding="utf-8") as out:
                    out.write(res_text)
                messagebox.showinfo("Export", f"Analysis saved to {info}")
        except Exception as e:
            messagebox.showerror("Export", f"Error: {e}")

    # ── log output handling ─────────────────────────────────────
    def read_output(self):
        """Read subprocess stdout and stderr and push to the log queue."""
        if not self.proc:
            return

        def reader(stream):
            for line in iter(stream.readline, ""):
                if not line:
                    break
                if "Error:" in line or "Traceback" in line:
                    line = f"\x1b[31m{line.rstrip()}\x1b[0m\n"
                self.log_queue.put(line)

        threads = []
        if self.proc.stdout:
            threads.append(threading.Thread(target=reader, args=(self.proc.stdout,), daemon=True))
        if self.proc.stderr:
            threads.append(threading.Thread(target=reader, args=(self.proc.stderr,), daemon=True))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _apply_ansi_codes(self, codes: list[str]) -> None:
        for c in codes:
            if c == "0":
                self._current_tags.clear()
            elif c == "1":
                if "bold" not in self._current_tags:
                    self._current_tags.append("bold")
            else:
                colour = ANSI_COLOUR_MAP.get(c)
                if colour:
                    self._current_tags = [
                        t for t in self._current_tags if not t.startswith("fg-")
                    ]
                    self._current_tags.append(f"fg-{colour}")

    def insert_with_ansi(self, text: str) -> None:
        pos = 0
        for m in self._ansi_re.finditer(text):
            if m.start() > pos:
                self.log_box.insert(
                    "end", text[pos : m.start()], tuple(self._current_tags)
                )
            self._apply_ansi_codes(m.group(1).split(";"))
            pos = m.end()
        if pos < len(text):
            self.log_box.insert("end", text[pos:], tuple(self._current_tags))

    # ── live race feed handling ─────────────────────────────────
    def add_event(self, event_type: str, message: str) -> None:
        if event_type not in self.event_buffers:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.event_buffers[event_type].appendleft(f"{ts} - {message}")

    def parse_event(self, line: str) -> None:
        l = line.lower()
        if "overtook" in l:
            self.add_event("overtake", line.strip())
        if "pitted" in l or "pit -" in l or "pit \u2013" in l:
            # Tail logs emit lines like "PIT – Team / Driver" using an en dash.
            # Include both the plain hyphen and en dash variants so the feed
            # catches them regardless of terminal font or encoding.
            self.add_event("pitstop", line.strip())
        if "driver swap" in l or "swapped" in l:
            self.add_event("driver_swap", line.strip())
        if "fastest lap" in l:
            self.add_event("fastest_lap", line.strip())
        if "penalty" in l or "drive-through" in l:
            self.add_event("penalty", line.strip())
        if "yellow flag" in l or "safety car" in l:
            self.add_event("yellow", line.strip())

    def clear_feed(self) -> None:
        for buf in self.event_buffers.values():
            buf.clear()
        self.update_feed()

    def update_feed(self) -> None:
        if self.feed_text is None:
            self.root.after(3000, self.update_feed)
            return
        if self.feed_paused.get():
            self.root.after(3000, self.update_feed)
            return
        self.feed_text.configure(state="normal")
        self.feed_text.delete("1.0", tk.END)
        for etype, cfg in EVENT_TYPES.items():
            entries = list(self.event_buffers[etype])
            if not entries:
                continue
            self.feed_text.insert(tk.END, cfg["label"] + "\n", f"header-{etype}")
            for e in entries:
                self.feed_text.insert(tk.END, f"  {e}\n", etype)
            self.feed_text.insert(tk.END, "\n")
        self.feed_text.configure(state="disabled")
        self.feed_text.see("end")
        self.root.after(3000, self.update_feed)

    def update_log_box(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_box.configure(state="normal")
                self.insert_with_ansi(line)
                self.parse_event(line)
                if self.auto_scroll.get():
                    self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except Empty:
            pass
        self.root.after(100, self.update_log_box)

    def on_close(self):
        if self.proc:
            if messagebox.askyesno("Exit", "Stop logging and exit?"):
                self.stop_logging()
            else:
                return
        if self.feed_window is not None and self.feed_window.winfo_exists():
            self.feed_window.destroy()
        self.root.destroy()


_UNKNOWN_ARGS: list[str] = []


def parse_cli(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the GUI.

    Unknown or extra arguments are ignored and logged later.
    """

    parser = argparse.ArgumentParser(description="EEC Race Logger GUI")
    parser.add_argument("--debug", action="store_true", help="enable verbose logging")
    parser.add_argument(
        "--debug-shell",
        action="store_true",
        help="open an interactive shell before starting the GUI",
    )
    parser.add_argument(
        "--classic-theme",
        action="store_true",
        help="force the classic Tk theme even when sv_ttk is installed",
    )
    parser.add_argument(
        "--no-openai",
        action="store_true",
        help="disable all OpenAI features",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default="eec_log.db",
        help="SQLite database file",
    )
    parser.add_argument(
        "--time-left",
        metavar="TIME",
        type=_parse_time,
        help="remaining race time (H:M:S or seconds)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"EEC Logger v{__version__} (build {__build_time__}, git {__commit_hash__})",
    )

    args, unknown = parser.parse_known_args(argv)
    global _UNKNOWN_ARGS
    _UNKNOWN_ARGS = unknown
    return args


def setup_logging(debug: bool) -> logging.Logger:
    """Configure and return the logger used by the GUI."""
    logger = logging.getLogger("race_gui")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
    if debug:
        logger.addHandler(logging.StreamHandler())
    return logger


def setup_excepthook(logger: logging.Logger) -> None:
    """Redirect uncaught exceptions to the logger."""

    def handle(exc_type, exc, tb) -> None:
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        print(msg, file=sys.stderr)
        root = getattr(tk, "_default_root", None)
        if root is not None:
            try:
                messagebox.showerror("Error", str(exc))
            except Exception:
                pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = handle


def check_environment(logger: logging.Logger) -> None:
    """Log warnings for missing environment variables."""
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        logger.warning("DISPLAY environment variable is not set")
    if not os.environ.get("QT_QPA_PLATFORM"):
        logger.debug("QT_QPA_PLATFORM not set")
    if not os.environ.get("PYTHONPATH"):
        logger.debug("PYTHONPATH not set")


def check_dependencies(logger: logging.Logger) -> None:
    """Ensure optional dependencies are available and log warnings."""
    if OPENAI_IMPORT_ERROR is not None:
        logger.warning("module 'openai' not installed – OpenAI features disabled")
    if SVTTK_IMPORT_ERROR is not None and ensure_package is not None:
        logger.warning("module 'sv_ttk' not installed – attempting automatic installation")
        try:
            ensure_package("sv_ttk")
            globals()["sv_ttk"] = importlib.import_module("sv_ttk")
            logger.info("Installed 'sv_ttk' for modern theme")
        except Exception as exc:
            logger.error("Failed to install 'sv_ttk': %s", exc)
    elif SVTTK_IMPORT_ERROR is not None:
        logger.warning("module 'sv_ttk' not installed – falling back to default theme")
    if irsdk is None:
        logger.warning("module 'irsdk' not installed")


def start_heartbeat(start_event: threading.Event) -> None:
    """Print periodic heartbeat while the GUI event loop runs."""

    def beat() -> None:
        start_event.wait()
        # Print once immediately when the GUI enters the event loop to
        # avoid timing races in short-lived tests where the event is
        # cleared before the thread gets scheduled again.
        print("GUI_HEARTBEAT", flush=True)
        while start_event.is_set():
            # Delay between heartbeats to reduce log noise
            time.sleep(60)
            if not start_event.is_set():
                break
            print("GUI_HEARTBEAT", flush=True)

    threading.Thread(target=beat, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    """Application entry point."""
    start_time = time.monotonic()
    args = parse_cli(argv)
    logger = setup_logging(args.debug)
    setup_excepthook(logger)

    for arg in _UNKNOWN_ARGS:
        logger.warning("Ignoring unknown argument: %s", arg)

    atexit.register(
        lambda: logger.info(
            "Exited normally in %.2fs", time.monotonic() - start_time
        )
    )

    global OPENAI_ENABLED
    if args.no_openai:
        OPENAI_ENABLED = False
        logger.info("OpenAI disabled by flag")

    logger.debug("argv: %s", sys.argv)
    logger.debug("PID: %d", os.getpid())

    os.chdir(Path(__file__).resolve().parent)
    logger.debug("Checking environment")
    check_environment(logger)
    logger.debug("Checking dependencies")
    check_dependencies(logger)

    if os.environ.get("FORCE_GUI_IMPORT_ERROR"):
        raise RuntimeError("GUI never reached event loop")

    logger.debug("Creating GUI root")
    if os.environ.get("EEC_DUMMY_TK"):
        class DummyRoot:
            def after(self, _delay: int, func: Any) -> None:  # type: ignore[override]
                func()

            def mainloop(self) -> None:
                pass

        root = DummyRoot()
    else:
        prev_root = getattr(tk, "_default_root", None)
        root = tk.Tk()
        if hasattr(root, "geometry"):
            root.geometry("1100x800")
        if hasattr(root, "minsize"):
            root.minsize(800, 600)
        if hasattr(root, "rowconfigure"):
            root.rowconfigure(0, weight=1)
        if hasattr(root, "columnconfigure"):
            root.columnconfigure(0, weight=1)
        if prev_root is not None or tk._default_root is None:
            raise RuntimeError("Unexpected number of Tk root instances")
        if hasattr(root, "deiconify"):
            root.deiconify()
        if hasattr(root, "lift"):
            root.lift()
        if hasattr(root, "update_idletasks"):
            root.update_idletasks()
        mapped = getattr(root, "winfo_ismapped", lambda: True)
        updater = getattr(root, "update", lambda: None)
        start = time.time()
        while not mapped() and time.time() - start < 1:
            updater()
        if not mapped():
            raise RuntimeError("GUI failed to map")
    logger.debug("QApplication created")

    if os.environ.get("EEC_DUMMY_TK"):
        gui = None
        theme = "default"
    else:
        try:
            gui = RaceLoggerGUI(
                root, classic_theme=args.classic_theme, time_left=args.time_left
            )
        except TypeError:  # tests may monkeypatch RaceLoggerGUI
            gui = RaceLoggerGUI(root)  # type: ignore[arg-type]
        theme = getattr(gui, "theme", "default") if gui else "default"
        logger.debug("Window created")
    logger.info(
        "PID %d – theme %s – Python %s – Tk %s",
        os.getpid(),
        theme,
        platform.python_version(),
        root.tk.call("info", "patchlevel") if hasattr(root, "tk") else "0",
    )

    start_event = threading.Event()
    start_heartbeat(start_event)
    root.after(0, start_event.set)
    time.sleep(0.1)

    if args.debug_shell:
        import code

        code.interact(local={"root": root, "gui": gui})

    logger.debug("Starting event loop")
    print(f"Race GUI started successfully (PID {os.getpid()})")
    root.mainloop()
    if not start_event.is_set():
        raise RuntimeError("GUI never reached event loop")
    start_event.clear()
    return 0


if __name__ == "__main__":
    import threading
    threading.Thread(target=_run_version_check, daemon=True).start()
    lock = _EARLY_LOCK or acquire_single_instance_lock()
    if lock is None:
        focus_running_window()
        sys.exit(0)
    try:
        sys.exit(main())
    except RuntimeError as exc:  # pragma: no cover - early failures
        print("Race GUI failed – see race_gui.log", file=sys.stderr)
        print(exc)
        sys.exit(1)

