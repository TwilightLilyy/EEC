try:
    import pandas as pd
except Exception:
    pd = None
import time

INPUT = "standings_log.csv"
OUTPUT = "sorted_standings.csv"

CAR_CLASS_MAP = {  # extend as needed
    "2708": "GT3",
    "4074": "Hypercar",
}


def class_name(cid: str) -> str:
    return CAR_CLASS_MAP.get(str(cid), f"Class {cid}")


def sort_and_write():
    if pd is None:
        print("[ERR] pandas not installed – standings sorter disabled")
        return
    try:
        df = pd.read_csv(INPUT)

        # ⬇ new numeric conversions (unchanged)
        for col in ["Position", "ClassPosition", "Lap", "BestLapTime", "LastLapTime"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # limit lap time precision
        df["BestLapTime"] = df["BestLapTime"].round(3)
        df["LastLapTime"] = df["LastLapTime"].round(3)
        df["PitCount"] = (
            pd.to_numeric(df["PitCount"], errors="coerce").fillna(0).astype(int)
        )

        # keep latest row / car
        idx = df.groupby("CarIdx")["Time"].idxmax()
        latest = df.loc[idx].copy()
        latest["Class"] = latest["CarClassID"].apply(class_name)

        # —— NEW: keep readable team column ——
        latest.rename(
            columns={
                "TeamName": "Team",
                "UserName": "Driver",
                "Position": "Pos",
                "ClassPosition": "Class Pos",
                "Lap": "Laps",
                "PitCount": "Pits",
                "BestLapTime": "Best Lap",
                "LastLapTime": "Last Lap",
                "OnPitRoad": "In Pit",
            },
            inplace=True,
        )

        # optional per-car average (unchanged)
        def avg(car):
            v = df[(df.CarIdx == car) & (df.Lap > 0) & (df.LastLapTime > 0)][
                "LastLapTime"
            ]
            return round(v.mean(), 3) if not v.empty else ""

        latest["Avg Lap"] = latest["CarIdx"].apply(avg)

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

        # determine class order based on the best overall position per class
        class_leaders = latest.groupby("Class")["Pos"].min().sort_values()
        order_map = {c: i for i, c in enumerate(class_leaders.index)}
        latest["ClassOrder"] = latest["Class"].map(order_map)

        latest.sort_values(by=["ClassOrder", "Pos"]).to_csv(
            OUTPUT, columns=cols, index=False
        )
        print("[OK] standings written →", OUTPUT)
    except Exception as e:
        print("[ERR]", e)


if __name__ == "__main__":
    print("Standings sorter running. Ctrl-C to stop.")
    while True:
        sort_and_write()
        time.sleep(5)
