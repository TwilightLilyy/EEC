import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eec_db import init_db, insert


def test_init_and_insert(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)

    for table in ("standings", "pitstops", "driver_swaps", "driver_totals"):
        cur = conn.execute(f"PRAGMA table_info({table})")
        assert cur.fetchall(), f"{table} table not created"

    row = (
        "2021-01-01T00:00:00",
        0,
        "TeamA",
        "DriverA",
        "2708",
        1,
        1,
        5,
        60.0,
        61.0,
        0,
        0,
    )
    insert(conn, "standings", row)
    stored = conn.execute("SELECT * FROM standings").fetchone()
    conn.close()
    assert stored == row
