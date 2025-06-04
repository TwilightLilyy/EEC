import irsdk, csv, time
try:
    import pandas as pd
except Exception:
    pd = None
from datetime import datetime

CSV_FILE     = "pitstop_log.csv"
OVERLAY_FILE = "live_standings_overlay.html"
DRIVER_TOTAL_FILE = "driver_times.csv"

DRIVER_HEADERS = [
    "TeamName", "DriverName",
    "Total Time (sec)", "Total Time (h:m:s)"
]

HEADERS = [
    "CarIdx", "Class",               # NEW
    "TeamName", "DriverName",
    "Stint Start Timestamp", "Stint End Timestamp",
    "Stint Start SessionTime", "Stint End SessionTime",
    "Stint Start Lap", "Stint End Lap",
    "Stint Duration (sec)", "Stint Duration (min:sec)", "Stint Duration (Laps)"
]

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

# ── initialise CSVs ───────────────────────────────────────────
try:
    open(CSV_FILE, "x", newline="").write(",".join(HEADERS) + "\n")
except FileExistsError:
    pass

try:
    with open(DRIVER_TOTAL_FILE, "r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        driver_total = {
            (r["TeamName"], r["DriverName"]): float(r["Total Time (sec)"])
            for r in rdr
        }
except FileNotFoundError:
    open(DRIVER_TOTAL_FILE, "w", newline="").write(",".join(DRIVER_HEADERS) + "\n")
    driver_total = {}

ir = irsdk.IRSDK(); ir.startup()
stint = {}                           # carIdx → dict

print("Enhanced pit-stop logger running… Ctrl-C to stop.")
while True:
    try:
        if ir.is_initialized and ir.is_connected:
            ir.freeze_var_buffer_latest()
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
                    stint[idx] = {"start_time": datetime.now(),
                                  "start_sess": sess, "start_lap": lap, "on_pit": False}

                if idx in stint:
                    was = stint[idx]["on_pit"]
                    stint[idx]["on_pit"] = pit

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
                        print(f"[{iso_now()}] STINT END – "
                            f"{team} / {drv}: {row[-1]} laps, {row[-2]}.")

                        # update per-driver totals
                        key = (team, drv)
                        driver_total[key] = driver_total.get(key, 0) + dur_s
                        with open(DRIVER_TOTAL_FILE, "w", newline="", encoding="utf-8") as dt:
                            wr = csv.writer(dt)
                            wr.writerow(DRIVER_HEADERS)
                            for (t, d), tot in driver_total.items():
                                wr.writerow([t, d, tot, hms(tot)])

                        if pd is not None:
                            write_overlay(CSV_FILE)
                        stint[idx] = {"on_pit": True}     # wait for exit

                    # pit exit → new stint
                    elif not pit and was:
                        stint[idx] = {"start_time": datetime.now(),
                                      "start_sess": sess, "start_lap": lap, "on_pit": False}
        time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nLogger stopped.")
        break
    except Exception as e:
        print("Error:", e)
        time.sleep(1)
