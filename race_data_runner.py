# race_data_runner.py
import subprocess, signal, sys, time, os, threading, shutil
import csv, itertools
from pathlib import Path
from datetime import datetime
from colorama import init as _init, Fore, Style
from collections import defaultdict
_init(autoreset=True)          # initialise colourama (harmless on *nix)

PITLOG = Path("pitstop_log.csv")   # same name the logger writes
STANDINGS_LOG = Path("standings_log.csv")   # the file ai_standings_logger writes
DRIVER_SWAP_CSV = Path("driver_swaps.csv")


# A finite palette of bright-ish colours (skip yellow – hard to read on white terminals)
_PALETTE = [
    Fore.MAGENTA, Fore.CYAN, Fore.GREEN,
    Fore.BLUE, Fore.RED, Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTCYAN_EX, Fore.LIGHTGREEN_EX, Fore.LIGHTBLUE_EX,
]
CLASS_COLOUR: dict[str, str] = {}          # filled on the fly

_SWAPS_COLOUR = Style.BRIGHT + Fore.YELLOW
_current_driver: dict[int, str] = defaultdict(str)

def colour_for(cls: str) -> str:
    """Return a consistent ANSI colour for each class name."""
    if cls not in CLASS_COLOUR:
        # Pop the next palette entry, or default to WHITE if we run out
        CLASS_COLOUR[cls] = _PALETTE[len(CLASS_COLOUR) % len(_PALETTE)]
    return CLASS_COLOUR[cls]


SCRIPTS = [
    ("AI Logger",        ["python", "ai_standings_logger.py"]),
    ("Pit Logger",       ["python", "pitstop_logger_enhanced.py"]),
    ("Standings Sorter", ["python", "standings_sorter.py"]),
    # add more here as needed
]

LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)

def stamp():
    """Return current local time in ISO-8601 to-the-second."""
    return datetime.now().isoformat(timespec="seconds")

def launch(name, cmd):
    logfile = LOG_DIR / f"{name.replace(' ', '_').lower()}.txt"
    return subprocess.Popen(
        cmd, stdout=open(logfile, "w"), stderr=subprocess.STDOUT, text=True
    )

procs = {name: launch(name, cmd) for name, cmd in SCRIPTS}
print(f"[{stamp()}] 🚀  Started {len(procs)} child processes.")

def stamp(): return datetime.now().strftime("%H:%M:%S")

def tail_pitlog(file: Path, sleep=0.5):
    while not (file.exists() and file.stat().st_size):
        time.sleep(1)

    with file.open("r", newline="", encoding="utf-8", errors="replace") as f:
        csv.reader(f).__next__()          # skip header
        f.seek(0, os.SEEK_END)            # move to EOF

        while True:
            line = f.readline()
            if not line:
                time.sleep(sleep)
                continue

            row = next(csv.reader([line]))
            if len(row) == 13:            # NEW schema
                (car, cls, team, driver,
                 *_,
                 dur_sec, dur_hms, dur_laps) = row
            elif len(row) == 12:          # OLD schema
                (car, team, driver,
                 *_,
                 dur_sec, dur_hms, dur_laps) = row
                cls = "Unknown"
            else:
                continue                  # malformed → skip

            colour = colour_for(cls)

            print(f"{colour}[{stamp()}] 🛠  PIT – {team.strip()} / {driver.strip()} "
                f"({dur_laps} laps in {dur_hms}) [{cls}]{Style.RESET_ALL}")

# ─────────────────────────────────────────────────────────────
def tail_driver_swaps(file: Path, sleep=0.5):
    """
    Tail standings_log.csv and emit a console line whenever CarIdx
    changes driver.  Also append that event to driver_swaps.csv.
    """
    # ▸ Ensure the swap-file has a header  ─────────────────────
    if not DRIVER_SWAP_CSV.exists():
        DRIVER_SWAP_CSV.write_text(
            "Timestamp,CarIdx,Team,DriverOut,DriverIn,Lap\n",
            encoding="utf-8"
        )

    while not (file.exists() and file.stat().st_size):
        time.sleep(1)

    with file.open("r", newline="", encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)        # skip header
        f.seek(0, os.SEEK_END)                      # jump to EOF

        while True:
            line = f.readline()
            if not line:
                time.sleep(sleep)
                continue

            row = next(csv.reader([line]))
            if len(row) < 8:                        # need at least Lap col
                continue

            ts, car, team, driver = row[:4]
            lap                   = row[7]          # Lap column in the log
            try:
                car = int(car)
            except ValueError:
                continue

            prev = _current_driver.get(car)
            if prev and driver and driver != prev:
                # ── 1) console shout ─────────────────────────
                colour = colour_for("swap")         # yellow by default
                print(f"{colour}[{stamp()}] 🔄  DRIVER SWAP – "
                      f"{team.strip()}  Car {car:>3}: "
                      f"{prev} → {driver} (Lap {lap}){Style.RESET_ALL}")

                # ── 2) CSV append ───────────────────────────
                with DRIVER_SWAP_CSV.open("a", newline="", encoding="utf-8") as w:
                    csv.writer(w).writerow([ts, car, team, prev, driver, lap])

            _current_driver[car] = driver

# ─────────────────────────────────────────────────────────────


def watchdog(seconds=600, directory=Path(".")):
    while True:
        for f in directory.glob("*.csv"):
            age = time.time() - f.stat().st_mtime
            if age > seconds:
                print(f"[{stamp()}] ⚠️  {f} stale ({age:.0f}s)")
        time.sleep(seconds)

# start the watchdog (no args needed – it defaults to current dir)
threading.Thread(target=watchdog,     daemon=True).start()
threading.Thread(target=tail_pitlog,  args=(PITLOG,), daemon=True).start()
threading.Thread(target=tail_driver_swaps, args=(STANDINGS_LOG,), daemon=True).start()

try:
    while True:
        dead = [n for n, p in procs.items() if p.poll() is not None]
        for n in dead:
            print(f"[{stamp()}] 🔁  Restarting {n} (exit {procs[n].returncode})")
            procs[n] = launch(n, dict(SCRIPTS)[n])
        time.sleep(2)
except KeyboardInterrupt:
    print(f"\n[{stamp()}] 🛑  Shutting down…")
    for p in procs.values():
        p.send_signal(signal.SIGINT)
    for p in procs.values():
        p.wait()
    sys.exit(0)
