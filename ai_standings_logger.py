import irsdk
import time
import csv
from datetime import datetime

ir = irsdk.IRSDK()
ir.startup()

csv_path = "standings_log.csv"
header = [
    "Time", "CarIdx",               # session snapshot
    "TeamName", "UserName",         # NEW: team + driver
    "CarClassID",
    "Position", "ClassPosition",
    "Lap", "BestLapTime", "LastLapTime",
    "OnPitRoad", "PitCount"
]

print("Waiting for iRacing session…")
while not (ir.is_initialized and ir.is_connected):
    print("Not connected… waiting.")
    time.sleep(2)
print("Connected to iRacing!")

# Write header once
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerow(header)

pit_count = {}          # carIdx → int
last_pit_state = {}     # carIdx → bool

while True:
    try:
        ts = datetime.now().isoformat(timespec="seconds")
        laps = ir["CarIdxLap"]
        pos  = ir["CarIdxPosition"]
        cpos = ir["CarIdxClassPosition"]
        best = ir["CarIdxBestLapTime"]
        last = ir["CarIdxLastLapTime"]
        pit  = ir["CarIdxOnPitRoad"]
        drvs = ir["DriverInfo"]["Drivers"]

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            for d in drvs:
                idx       = d.get("CarIdx")
                team_name = d.get("TeamName", "")
                user_name = d.get("UserName", "")
                cls_id    = d.get("CarClassID", "")

                def safe(arr):
                    return arr[int(idx)] if arr is not None and idx is not None and int(idx) < len(arr) else ""

                in_pit           = safe(pit)
                prev             = last_pit_state.get(idx, False)
                pit_count[idx]   = pit_count.get(idx, 0) + (1 if (not prev and in_pit) else 0)
                last_pit_state[idx] = in_pit

                wr.writerow([
                    ts, idx,
                    team_name, user_name,          # NEW
                    cls_id, safe(pos), safe(cpos), safe(laps),
                    safe(best), safe(last),
                    in_pit, pit_count[idx]
                ])
        print(f"[{ts}] Logged {len(drvs)} cars.")
        time.sleep(5)
    except KeyboardInterrupt:
        print("Stopped by user.")
        break
    except Exception as e:
        print("Error logging:", e)
        time.sleep(5)
