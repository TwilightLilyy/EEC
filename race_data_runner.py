# race_data_runner.py
from datetime import datetime
__version__     = "2025.06.07.0"
__build_time__  = "2025-06-07T15:42:00Z"
__commit_hash__ = "abc1234"

import argparse
import subprocess
import signal
import sys
import time
import os
import threading
import csv
from pathlib import Path
from typing import Any
from codebase_cleaner import check_latest_version

if getattr(sys, "frozen", False):
    try:
        setattr(sys, "_MEIPASS_VERSION", __version__)
        setattr(sys, "_MEIPASS_BUILD", __build_time__)
        setattr(sys, "_MEIPASS_COMMIT", __commit_hash__)
        if __spec__ is not None:
            __spec__.origin = f"{__spec__.origin}|{__version__}"
    except Exception:
        pass

# Ensure all relative paths resolve to the project directory
if getattr(sys, "frozen", False):
    # Running inside a PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Race data runner")
    parser.add_argument("--db", default="eec_log.db", help="SQLite database file")
    parser.add_argument(
        "--auto-install",
        action="store_true",
        help="Automatically install missing dependencies",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"EEC Logger v{__version__} (build {__build_time__}, git {__commit_hash__})",
    )
    args, _ = parser.parse_known_args()
    return args


ARGS: argparse.Namespace
DB_PATH: Path
watch: Any


def ensure_watchfiles(auto_install: bool = False) -> Any:
    """Return the :func:`watch` function from the watchfiles package.

    Attempts installation when ``auto_install`` is ``True`` or the
    ``EEC_AUTO_INSTALL`` environment variable is set to ``"1"`` and the module
    is missing.

    >>> import types, sys
    >>> mod = types.SimpleNamespace(watch=lambda: None)
    >>> sys.modules['watchfiles'] = mod
    >>> ensure_watchfiles() is mod.watch
    True
    >>> del sys.modules['watchfiles']
    >>> try:
    ...     ensure_watchfiles()
    ... except SystemExit as exc:
    ...     assert exc.code == 1
    """
    env_auto = os.getenv("EEC_AUTO_INSTALL", "1") == "1"
    auto_install = auto_install or env_auto
    try:
        from watchfiles import watch as watch_func
        return watch_func
    except ModuleNotFoundError:
        if auto_install:
            print("Error: The 'watchfiles' package is not installed.", flush=True)
            print("Attempting automatic installation...", flush=True)
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "watchfiles>=0.21.0"]
            )
            if result.returncode == 0:
                try:
                    from watchfiles import watch as watch_func
                    return watch_func
                except ModuleNotFoundError:
                    pass
            sys.exit(1)
        print(
            "Error: The 'watchfiles' package is not installed.\n"
            "Run python -m pip install watchfiles or start with --auto-install.",
            flush=True,
        )
        sys.exit(1)

try:
    from colorama import init as _init, Fore, Style
    try:
        from colorama import just_fix_windows_console
        just_fix_windows_console()
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    _init(autoreset=True)
except Exception:  # colorama not installed
    class _Dummy:
        def __getattr__(self, _):
            return ""

    Fore = Style = _Dummy()

    def _init(*args, **kwargs):
        pass

from collections import defaultdict

PITLOG: Path = Path("pitstop_log.csv")   # same name the logger writes
STANDINGS_LOG: Path = Path("standings_log.csv")   # the file ai_standings_logger writes
DRIVER_SWAP_CSV: Path = Path("driver_swaps.csv")


# Ordered palette for class colours (fastest → slowest)
_PALETTE = [
    Style.BRIGHT + Fore.YELLOW,
    Fore.BLUE,
    Fore.RED,
    Fore.GREEN,
    Fore.MAGENTA,
]
CLASS_COLOUR: dict[str, str] = {}          # filled on the fly


_SWAPS_COLOUR = Style.BRIGHT + Fore.YELLOW
_current_driver: dict[int, str] = defaultdict(str)


def build_scripts(db_path: Path) -> list[tuple[str, list[str]]]:
    """Return the command list for child processes."""
    return [
        (
            "AI Logger",
            [sys.executable, str(BASE_DIR / "ai_standings_logger.py"), "--db", str(db_path)],
        ),
        (
            "Pit Logger",
            [sys.executable, str(BASE_DIR / "pitstop_logger_enhanced.py"), "--db", str(db_path)],
        ),
        ("Standings Sorter", [sys.executable, str(BASE_DIR / "standings_sorter.py")]),
        # add more here as needed
    ]

def colour_for(cls: str) -> str:
    """Return a consistent ANSI colour for each class name."""
    if cls not in CLASS_COLOUR:
        # Pop the next palette entry, or default to WHITE if we run out
        CLASS_COLOUR[cls] = _PALETTE[len(CLASS_COLOUR) % len(_PALETTE)]
    return CLASS_COLOUR[cls]


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def iso_stamp() -> str:
    """Return current local time in ISO-8601 to-the-second."""
    return datetime.now().isoformat(timespec="seconds")


def launch(name: str, cmd: list[str]) -> subprocess.Popen:
    logfile = LOG_DIR / f"{name.replace(' ', '_').lower()}.txt"
    return subprocess.Popen(
        cmd,
        stdout=open(logfile, "w"),
        stderr=subprocess.STDOUT,
        text=True,
    )


def start_processes(scripts: list[tuple[str, list[str]]]) -> dict[str, subprocess.Popen]:
    """Launch all child processes and return a mapping of names to processes."""
    procs = {name: launch(name, cmd) for name, cmd in scripts}
    print(f"[{iso_stamp()}] 🚀  Started {len(procs)} child processes.", flush=True)
    return procs

def stamp(): return datetime.now().strftime("%H:%M:%S")

def tail_pitlog(file: Path):
    """Watch pitstop_log.csv and print new pit entries as they appear."""
    pos = 0
    header_read = False
    while True:
        if not (file.exists() and file.stat().st_size):
            time.sleep(1)
            continue
        for _ in watch(str(file)):
            if not file.exists():
                pos = 0
                header_read = False
                continue
            try:
                size = file.stat().st_size
            except FileNotFoundError:
                pos = 0
                header_read = False
                continue
            if size < pos:
                pos = 0
                header_read = False
            with file.open("r", newline="", encoding="utf-8", errors="replace") as f:
                if not header_read:
                    csv.reader(f).__next__()  # skip header
                    header_read = True
                f.seek(pos)
                for line in f:
                    row = next(csv.reader([line]))
                    if len(row) == 13:  # NEW schema
                        (car, cls, team, driver, *_, dur_sec, dur_hms, dur_laps) = row
                    elif len(row) == 12:  # OLD schema
                        (car, team, driver, *_, dur_sec, dur_hms, dur_laps) = row
                        cls = "Unknown"
                    else:
                        continue

                    colour = colour_for(cls)
                    print(
                        f"{colour}[{stamp()}] 🛠  PIT – {team.strip()} / {driver.strip()} "
                        f"({dur_laps} laps in {dur_hms}) [{cls}]{Style.RESET_ALL}",
                        flush=True,
                    )
                pos = f.tell()


# ─────────────────────────────────────────────────────────────
def tail_driver_swaps(file: Path):
    """Watch standings_log.csv and emit a message whenever a driver swap occurs."""
    header = "Timestamp,CarIdx,Team,DriverOut,DriverIn,Lap\n"
    pos = 0
    header_read = False
    while True:
        if not DRIVER_SWAP_CSV.exists() or DRIVER_SWAP_CSV.stat().st_size == 0:
            DRIVER_SWAP_CSV.write_text(header, encoding="utf-8")

        if not (file.exists() and file.stat().st_size):
            time.sleep(1)
            continue
        for _ in watch(str(file)):
            if not file.exists():
                pos = 0
                header_read = False
                continue
            try:
                size = file.stat().st_size
            except FileNotFoundError:
                pos = 0
                header_read = False
                continue
            if size < pos:
                pos = 0
                header_read = False
            with file.open("r", newline="", encoding="utf-8", errors="replace") as f:
                if not header_read:
                    next(csv.reader(f), None)  # skip header
                    header_read = True
                f.seek(pos)
                for line in f:
                    row = next(csv.reader([line]))
                    if len(row) < 8:
                        continue
                    ts, car, team, driver = row[:4]
                    lap = row[7]
                    try:
                        car = int(car)
                    except ValueError:
                        continue

                    prev = _current_driver.get(car)
                    if prev and driver and driver != prev:
                        colour = colour_for("swap")
                        print(
                            f"{colour}[{stamp()}] 🔄  DRIVER SWAP – "
                            f"{team.strip()}  Car {car:>3}: "
                            f"{prev} → {driver} (Lap {lap}){Style.RESET_ALL}",
                            flush=True,
                        )
                        with DRIVER_SWAP_CSV.open("a", newline="", encoding="utf-8") as w:
                            csv.writer(w).writerow([ts, car, team, prev, driver, lap])

                    _current_driver[car] = driver
                pos = f.tell()

# ─────────────────────────────────────────────────────────────


def watchdog(seconds: int = 600, directory: Path = Path(".")) -> None:
    while True:
        for f in directory.glob("*.csv"):
            age = time.time() - f.stat().st_mtime
            if age > seconds:
                print(f"[{stamp()}] ⚠️  {f} stale ({age:.0f}s)", flush=True)
        time.sleep(seconds)


def main() -> int:
    """Entry point for the race data runner."""

    global ARGS, DB_PATH, watch
    ARGS = parse_args()
    DB_PATH = Path(ARGS.db)
    watch = ensure_watchfiles(ARGS.auto_install)

    scripts = build_scripts(DB_PATH)
    procs = start_processes(scripts)

    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=tail_pitlog, args=(PITLOG,), daemon=True).start()
    threading.Thread(target=tail_driver_swaps, args=(STANDINGS_LOG,), daemon=True).start()

    try:
        while True:
            dead = [n for n, p in procs.items() if p.poll() is not None]
            for n in dead:
                print(
                    f"[{stamp()}] 🔁  Restarting {n} (exit {procs[n].returncode})",
                    flush=True,
                )
                procs[n] = launch(n, dict(scripts)[n])
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n[{stamp()}] 🛑  Shutting down…", flush=True)
        for p in procs.values():
            p.send_signal(signal.SIGINT)
        for p in procs.values():
            p.wait()
    return 0


if __name__ == "__main__":
    import threading
    threading.Thread(target=check_latest_version, args=(__version__,), daemon=True).start()
    sys.exit(main())
