"""iRacing AI standings logger.

This script periodically records standings information from iRacing to a
CSV file.  The output path and polling interval can be configured via
command line arguments.
"""

import argparse
import csv
import time
from datetime import datetime

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


def log_standings(csv_path: str, interval: int) -> None:
    """Main logging loop."""
    ir = irsdk.IRSDK()
    ir.startup()

    print("Waiting for iRacing session…")
    while not (ir.is_initialized and ir.is_connected):
        print("Not connected… waiting.")
        time.sleep(2)
    print("Connected to iRacing!")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(HEADER)

    pit_count: dict[int, int] = {}
    last_pit_state: dict[int, bool] = {}

    try:
        while True:
            ts = datetime.now().isoformat(timespec="seconds")
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
    args, _ = parser.parse_known_args()
    return args


def main() -> None:
    args = parse_args()
    log_standings(args.output, args.interval)


if __name__ == "__main__":
    main()
