"""iRacing AI standings logger.

This script periodically records standings information from iRacing to a
CSV file.  The output path and polling interval can be configured via
command line arguments.
"""

from datetime import datetime
__version__     = "2025.06.07.0"
__build_time__  = "2025-06-07T15:42:00Z"
__commit_hash__ = "abc1234"

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

import argparse
import csv
import time
from pathlib import Path
from typing import Optional
import shutil
from codebase_cleaner import check_latest_version

import eec_db

import irsdk

HEADER = [
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

# keep backwards compatibility with tests
header = HEADER

DEFAULT_CSV_PATH = "standings_log.csv"
DEFAULT_INTERVAL = 5


def rollover_log(path: str) -> None:
    """Move the current log to ``RaceLogs`` with a timestamp and start fresh."""
    dest_dir = Path("RaceLogs")
    dest_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{Path(path).stem}_{timestamp}.csv"
    try:
        shutil.move(path, dest)
    except FileNotFoundError:
        pass
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADER)


def log_standings(csv_path: str, interval: int, db_path: Optional[str] = None) -> None:
    """Main logging loop."""
    ir = irsdk.IRSDK()
    ir.startup()

    conn = eec_db.init_db(db_path) if db_path else None

    print("Waiting for iRacing session…")
    while not (ir.is_initialized and ir.is_connected):
        print("Not connected… waiting.")
        time.sleep(2)
    print("Connected to iRacing!")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADER)

    pit_count: dict[int, int] = {}
    last_pit_state: dict[int, bool] = {}
    prev_session = ir["SessionNum"]

    try:
        while True:
            ts = datetime.now().isoformat(timespec="seconds")
            session_num = ir["SessionNum"]
            if session_num != prev_session:
                rollover_log(csv_path)
                pit_count.clear()
                last_pit_state.clear()
                prev_session = session_num

            laps = ir["CarIdxLap"]
            pos = ir["CarIdxPosition"]
            cpos = ir["CarIdxClassPosition"]
            best = ir["CarIdxBestLapTime"]
            last = ir["CarIdxLastLapTime"]
            pit = ir["CarIdxOnPitRoad"]
            drvs = ir["DriverInfo"]["Drivers"]

            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                wr = csv.writer(f)
                for d in drvs:
                    idx = d.get("CarIdx")
                    team_name = d.get("TeamName", "")
                    user_name = d.get("UserName", "")
                    cls_id = d.get("CarClassID", "")

                    def safe(arr):
                        return (
                            arr[int(idx)]
                            if arr is not None and idx is not None and int(idx) < len(arr)
                            else ""
                        )

                    in_pit = safe(pit)
                    prev = last_pit_state.get(idx, False)
                    pit_count[idx] = pit_count.get(idx, 0) + (1 if (not prev and in_pit) else 0)
                    last_pit_state[idx] = in_pit

                    wr.writerow(
                        [
                            ts,
                            idx,
                            team_name,
                            user_name,
                            cls_id,
                            safe(pos),
                            safe(cpos),
                            safe(laps),
                            safe(best),
                            safe(last),
                            in_pit,
                            pit_count[idx],
                        ]
                    )
                    if conn:
                        eec_db.insert(
                            conn,
                            "standings",
                            [
                                ts,
                                idx,
                                team_name,
                                user_name,
                                cls_id,
                                safe(pos),
                                safe(cpos),
                                safe(laps),
                                safe(best),
                                safe(last),
                                int(bool(in_pit)),
                                pit_count[idx],
                            ],
                        )
            print(f"[{ts}] Logged {len(drvs)} cars.")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped by user.")
    except Exception as e:  # pragma: no cover - unexpected runtime errors
        print("Error logging:", e)
    finally:
        try:
            ir.shutdown()
        except Exception:
            pass
        if conn:
            conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iRacing AI standings logger")
    parser.add_argument(
        "--output",
        default=DEFAULT_CSV_PATH,
        help=f"CSV output file (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--db",
        help="SQLite database path",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"EEC Logger v{__version__} (build {__build_time__}, git {__commit_hash__})",
    )
    args, _ = parser.parse_known_args()
    return args


def main() -> None:
    args = parse_args()
    log_standings(args.output, args.interval, args.db)


if __name__ == "__main__":
    import threading
    threading.Thread(target=check_latest_version, args=(__version__,), daemon=True).start()
    main()
