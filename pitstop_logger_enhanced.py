import irsdk, csv, time, pandas as pd
from datetime import datetime

CSV_FILE     = "pitstop_log.csv"
OVERLAY_FILE = "live_standings_overlay.html"

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

def write_overlay(csv_path, html_path=OVERLAY_FILE):
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

# ── initialise CSV ────────────────────────────────────────────
try:
    open(CSV_FILE, "x", newline="").write(",".join(HEADERS) + "\n")
except FileExistsError:
    pass

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
