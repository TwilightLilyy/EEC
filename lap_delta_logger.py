"""Log lap-by-lap delta to the leader.

This script connects to iRacing via :mod:`irsdk` and writes a CSV file
``lap_delta_log.csv`` containing the time difference to the race leader
whenever a car completes a lap. The delta is calculated using the
``SessionTime`` at the moment a car's lap counter increments compared to
the leader's time for the same lap.
"""

from __future__ import annotations
from datetime import datetime
__version__     = "2025.06.07.0"
__build_time__  = "2025-06-07T15:42:00Z"
__commit_hash__ = "abc1234"

import sys
import argparse

if getattr(sys, "frozen", False):
    try:
        setattr(sys, "_MEIPASS_VERSION", __version__)
        setattr(sys, "_MEIPASS_BUILD", __build_time__)
        setattr(sys, "_MEIPASS_COMMIT", __commit_hash__)
        if __spec__ is not None:
            __spec__.origin = f"{__spec__.origin}|{__version__}"
    except Exception:
        pass

import csv
import time
from pathlib import Path
from typing import Optional

from codebase_cleaner import check_latest_version

import irsdk


CSV_PATH = "lap_delta_log.csv"

HEADER = ["Time", "CarIdx", "Lap", "DeltaToLeader"]


def iso_now() -> str:
    """Return current local time in ISO-8601 format."""

    return datetime.now().isoformat(timespec="seconds")


def rollover_log(path: str) -> None:
    """Move the current log to ``RaceLogs`` with a timestamp."""

    dest_dir = Path("RaceLogs")
    dest_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{Path(path).stem}_{ts}.csv"
    try:
        Path(path).rename(dest)
    except FileNotFoundError:
        pass
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADER)


def log_deltas(csv_path: str) -> None:
    """Main logging loop."""

    ir = irsdk.IRSDK()
    ir.startup()

    last_lap: dict[int, int] = {}
    leader_lap_time: dict[int, float] = {}
    prev_session = ir["SessionNum"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADER)

    try:
        while True:
            ts = iso_now()
            session_num = ir["SessionNum"]
            if session_num != prev_session:
                rollover_log(csv_path)
                last_lap.clear()
                leader_lap_time.clear()
                prev_session = session_num

            laps = ir["CarIdxLap"]
            pos = ir["CarIdxPosition"]
            sess_time = ir["SessionTime"]

            try:
                leader_idx = pos.index(1)
            except ValueError:
                leader_idx = None

            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                wr = csv.writer(f)
                for idx, lap in enumerate(laps):
                    if lap <= 0:
                        continue
                    prev = last_lap.get(idx)
                    if prev is not None and lap == prev:
                        continue
                    last_lap[idx] = lap

                    if idx == leader_idx:
                        leader_lap_time[lap] = sess_time
                        delta = 0.0
                    else:
                        leader_time = leader_lap_time.get(lap)
                        delta = sess_time - leader_time if leader_time is not None else ""

                    wr.writerow([ts, idx, lap, delta])

            time.sleep(1)
    except KeyboardInterrupt:
        print("Logger stopped by user.")
    finally:
        try:
            ir.shutdown()
        except Exception:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lap delta logger")
    parser.add_argument("--output", default=CSV_PATH, help="CSV output file")
    parser.add_argument(
        "--version",
        action="version",
        version=f"EEC Logger v{__version__} (build {__build_time__}, git {__commit_hash__})",
    )
    args, _ = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    csv_path = args.output
    log_deltas(csv_path)


if __name__ == "__main__":
    import threading
    threading.Thread(target=check_latest_version, args=(__version__,), daemon=True).start()
    main()

