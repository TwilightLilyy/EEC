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
import irsdk, csv, time
import shutil
from pathlib import Path
from codebase_cleaner import check_latest_version

import eec_db
try:
    import pandas as pd
except Exception:
    pd = None

CSV_FILE     = "pitstop_log.csv"
OVERLAY_FILE = "live_standings_overlay.html"
DRIVER_TOTAL_FILE = "driver_times.csv"

DRIVER_HEADERS = [
    "TeamName",
    "DriverName",
    "Total Time (sec)",
    "Total Time (h:m:s)",
    "Total Laps",
    "Average Lap (sec)",
    "Best Lap (sec)",
]

HEADERS = [
    "CarIdx", "Class",               # NEW
    "TeamName", "DriverName",
    "Stint Start Timestamp", "Stint End Timestamp",
    "Stint Start SessionTime", "Stint End SessionTime",
    "Stint Start Lap", "Stint End Lap",
    "Stint Duration (sec)", "Stint Duration (min:sec)", "Stint Duration (Laps)"
]


def rollover_logs() -> dict:
    """Archive the current CSV files and return a fresh driver_total dict."""
    dest_dir = Path("RaceLogs")
    dest_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        shutil.move(CSV_FILE, dest_dir / f"{Path(CSV_FILE).stem}_{ts}.csv")
    except FileNotFoundError:
        pass
    try:
        shutil.move(DRIVER_TOTAL_FILE, dest_dir / f"{Path(DRIVER_TOTAL_FILE).stem}_{ts}.csv")
    except FileNotFoundError:
        pass
    open(CSV_FILE, "w", newline="").write(",".join(HEADERS) + "\n")
    open(DRIVER_TOTAL_FILE, "w", newline="").write(",".join(DRIVER_HEADERS) + "\n")
    return {}

def iso_now():
    return datetime.now().isoformat(timespec="seconds")

def minsec(sec):
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"

def hms(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"

def write_overlay(csv_path, html_path=OVERLAY_FILE):
    if pd is None:
        return
    df = pd.read_csv(csv_path)
    latest = (df.sort_values("Stint End Timestamp", ascending=False)
                .drop_duplicates("CarIdx")
                .sort_values("Stint End SessionTime", ascending=False))

    html = """
    <html><body style='background:rgba(20,20,20,.8);color:#f2f2f2;font-family:sans-serif;padding:14px;'>
    <h3 style='margin-top:0;font-size:26px;'>Live Standings</h3>
    <table border=0 style='font-size:18px;border-collapse:collapse;'>
      <tr style='border-bottom:1px solid #555;'>
        <th align='left'  style='padding:0 18px 0 0;'>Team</th>
        <th align='left'  style='padding:0 18px 0 0;'>Driver</th>
        <th align='center'style='padding:0 18px;'>Lap</th>
        <th align='center'style='padding:0 18px;'>Last Pit</th>
        <th align='center'style='padding:0 0 0 18px;'>Stint (min:sec)</th>
      </tr>"""

    for _, r in latest.iterrows():
        sess_to_hms = lambda s: f"{int(s//3600)}:{int((s%3600)//60):02d}:{int(s%60):02d}"
        html += (f"<tr><td align='left'  style='padding:0 18px 0 0;'>{r.TeamName}</td>"
                 f"<td align='left'  style='padding:0 18px 0 0;'>{r.DriverName}</td>"
                 f"<td align='center'style='padding:0 18px;'>{r['Stint End Lap']}</td>"
                 f"<td align='center'style='padding:0 18px;'>{sess_to_hms(r['Stint End SessionTime'])}</td>"
                 f"<td align='center'style='padding:0 0 0 18px;'>{r['Stint Duration (min:sec)']}</td></tr>")
    html += "</table></body></html>"
    open(html_path, "w", encoding="utf-8").write(html)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enhanced pit-stop logger")
    parser.add_argument("--output", default=CSV_FILE, help="CSV output file")
    parser.add_argument(
        "--driver-total", default=DRIVER_TOTAL_FILE, help="Driver totals CSV"
    )
    parser.add_argument("--db", help="SQLite database path")
    parser.add_argument(
        "--version",
        action="version",
        version=f"EEC Logger v{__version__} (build {__build_time__}, git {__commit_hash__})",
    )
    args, _ = parser.parse_known_args()
    return args


args = parse_args()
import threading
threading.Thread(target=check_latest_version, args=(__version__,), daemon=True).start()
CSV_FILE = args.output
DRIVER_TOTAL_FILE = args.driver_total
DB_PATH = args.db
conn = eec_db.init_db(DB_PATH) if DB_PATH else None

# ── initialise CSVs ───────────────────────────────────────────
try:
    open(CSV_FILE, "x", newline="").write(",".join(HEADERS) + "\n")
except FileExistsError:
    pass

try:
    with open(DRIVER_TOTAL_FILE, "r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        driver_total = {}
        for r in rdr:
            key = (r["TeamName"], r["DriverName"])
            driver_total[key] = {
                "time": float(r.get("Total Time (sec)", 0)),
                "laps": int(r.get("Total Laps", 0) or 0),
                "best": float(r.get("Best Lap (sec)", r.get("Best Lap Time (sec)", float("inf"))) or float("inf")),
            }
except FileNotFoundError:
    open(DRIVER_TOTAL_FILE, "w", newline="").write(",".join(DRIVER_HEADERS) + "\n")
    driver_total = {}

ir = irsdk.IRSDK(); ir.startup()
stint = {}                           # carIdx → dict
last_total_update = time.time()
prev_session = ir["SessionNum"]

print("Enhanced pit-stop logger running… Ctrl-C to stop.")
while True:
    try:
        if ir.is_initialized and ir.is_connected:
            ir.freeze_var_buffer_latest()
            session_num = ir["SessionNum"]
            if session_num != prev_session:
                driver_total = rollover_logs()
                stint.clear()
                prev_session = session_num
            sess  = ir["SessionTime"]
            onpit = ir["CarIdxOnPitRoad"]
            laps  = ir["CarIdxLap"]
            drvs  = ir["DriverInfo"]["Drivers"]

            for idx, pit in enumerate(onpit):
                team = drvs[idx]["TeamName"] if idx < len(drvs) else f"Car {idx}"
                drv  = drvs[idx]["UserName"] if idx < len(drvs) else f"Car {idx}"
                lap  = laps[idx] if idx < len(laps) else "?"
                cls  = drvs[idx]["CarClassShortName"] if idx < len(drvs) else "Unknown"

                # start stint
                if idx not in stint and not pit:
                    stint[idx] = {
                        "start_time": datetime.now(),
                        "start_sess": sess,
                        "start_lap": lap,
                        "team": team,
                        "driver": drv,
                        "on_pit": False,
                        "best_lap": ir["CarIdxBestLapTime"][idx],
                    }

                if idx in stint:
                    was = stint[idx]["on_pit"]
                    stint[idx]["on_pit"] = pit
                    stint[idx]["best_lap"] = min(stint[idx].get("best_lap", float("inf")), ir["CarIdxBestLapTime"][idx])

                    # pit entry  → end stint
                    if pit and not was:
                        end   = datetime.now()
                        dur_s = (end - stint[idx]["start_time"]).total_seconds()
                        row = [
                            idx, cls,               # NEW
                            team, drv,
                            stint[idx]["start_time"].isoformat(timespec="seconds"),
                            end.isoformat(timespec="seconds"),
                            stint[idx]["start_sess"], sess,
                            stint[idx]["start_lap"], lap,
                            dur_s, minsec(dur_s),
                            int(lap) - int(stint[idx]["start_lap"])
                        ]
                        with open(CSV_FILE, "a", newline="") as f:
                            csv.writer(f).writerow(row)
                        if conn:
                            eec_db.insert(conn, "pitstops", row)
                        print(f"[{iso_now()}] STINT END – "
                            f"{team} / {drv}: {row[-1]} laps, {row[-2]}.")

                        # update per-driver totals
                        key = (team, drv)
                        stats = driver_total.get(key, {"time": 0.0, "laps": 0, "best": float("inf")})
                        stats["time"] += dur_s
                        stats["laps"] += int(lap) - int(stint[idx]["start_lap"])
                        stats["best"] = min(stats["best"], stint[idx].get("best_lap", float("inf")))
                        driver_total[key] = stats
                        with open(DRIVER_TOTAL_FILE, "w", newline="", encoding="utf-8") as dt:
                            wr = csv.writer(dt)
                            wr.writerow(DRIVER_HEADERS)
                            for (t, d), s in driver_total.items():
                                avg = s["time"] / s["laps"] if s["laps"] else 0
                                wr.writerow([t, d, s["time"], hms(s["time"]), s["laps"], f"{avg:.3f}",
                                             f"{s['best']:.3f}" if s["best"] != float("inf") else ""])
                        if conn:
                            conn.execute("DELETE FROM driver_totals")
                            for (t, d), s in driver_total.items():
                                conn.execute(
                                    "INSERT INTO driver_totals VALUES (?,?,?,?,?)",
                                    (t, d, s["time"], s["laps"], s["best"]),
                                )
                            conn.commit()

                        if pd is not None:
                            write_overlay(CSV_FILE)
                        stint[idx] = {"on_pit": True}     # wait for exit

                    # pit exit → new stint
                    elif not pit and was:
                        stint[idx] = {
                            "start_time": datetime.now(),
                            "start_sess": sess,
                            "start_lap": lap,
                            "team": team,
                            "driver": drv,
                            "on_pit": False,
                            "best_lap": ir["CarIdxBestLapTime"][idx],
                        }

            # ── periodic update of driver times ──────────────────
            now = datetime.now()
            if time.time() - last_total_update >= 60:
                cur_totals = {k: dict(v) for k, v in driver_total.items()}
                for idx, s in stint.items():
                    if s.get("on_pit") is False and "start_time" in s:
                        team = drvs[idx]["TeamName"] if idx < len(drvs) else f"Car {idx}"
                        drv  = drvs[idx]["UserName"] if idx < len(drvs) else f"Car {idx}"
                        dur = (now - s["start_time"]).total_seconds()
                        laps_run = int(laps[idx]) - int(s["start_lap"])
                        best = min(s.get("best_lap", float("inf")), ir["CarIdxBestLapTime"][idx])
                        key = (team, drv)
                        stats = cur_totals.get(key, {"time": 0.0, "laps": 0, "best": float("inf")})
                        stats["time"] += dur
                        stats["laps"] += laps_run
                        stats["best"] = min(stats["best"], best)
                        cur_totals[key] = stats
                with open(DRIVER_TOTAL_FILE, "w", newline="", encoding="utf-8") as dt:
                    wr = csv.writer(dt)
                    wr.writerow(DRIVER_HEADERS)
                    for (t, d), s in cur_totals.items():
                        avg = s["time"] / s["laps"] if s["laps"] else 0
                        wr.writerow([t, d, s["time"], hms(s["time"]), s["laps"], f"{avg:.3f}",
                                     f"{s['best']:.3f}" if s["best"] != float("inf") else ""])
                if conn:
                    conn.execute("DELETE FROM driver_totals")
                    for (t, d), s in cur_totals.items():
                        conn.execute(
                            "INSERT INTO driver_totals VALUES (?,?,?,?,?)",
                            (t, d, s["time"], s["laps"], s["best"]),
                        )
                    conn.commit()
                last_total_update = time.time()
        time.sleep(0.5)
    except KeyboardInterrupt:
        now = datetime.now()
        for idx, info in list(stint.items()):
            if "start_time" in info:
                team = info.get("team", f"Car {idx}")
                drv = info.get("driver", f"Car {idx}")
                dur_s = (now - info["start_time"]).total_seconds()
                laps_run = int(ir["CarIdxLap"][idx]) - int(info.get("start_lap", 0))
                best = min(info.get("best_lap", float("inf")), ir["CarIdxBestLapTime"][idx])
                key = (team, drv)
                stats = driver_total.get(key, {"time": 0.0, "laps": 0, "best": float("inf")})
                stats["time"] += dur_s
                stats["laps"] += laps_run
                stats["best"] = min(stats["best"], best)
                driver_total[key] = stats
        with open(DRIVER_TOTAL_FILE, "w", newline="", encoding="utf-8") as dt:
            wr = csv.writer(dt)
            wr.writerow(DRIVER_HEADERS)
            for (t, d), s in driver_total.items():
                avg = s["time"] / s["laps"] if s["laps"] else 0
                wr.writerow([t, d, s["time"], hms(s["time"]), s["laps"], f"{avg:.3f}",
                             f"{s['best']:.3f}" if s["best"] != float("inf") else ""])
        if conn:
            conn.execute("DELETE FROM driver_totals")
            for (t, d), s in driver_total.items():
                conn.execute(
                    "INSERT INTO driver_totals VALUES (?,?,?,?,?)",
                    (t, d, s["time"], s["laps"], s["best"]),
                )
            conn.commit()
        print("\nLogger stopped.")
        break
    except Exception as e:
        print("Error:", e)
        time.sleep(1)
        if conn:
            conn.close()
        break
if conn:
    conn.close()

if __name__ == "__main__":
    import threading
    threading.Thread(target=check_latest_version, args=(__version__,), daemon=True).start()
