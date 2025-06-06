import sqlite3
from pathlib import Path
from typing import Iterable, Any

__all__ = ["init_db", "insert", "connect"]


def connect(path: str | Path) -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    return sqlite3.connect(str(path))


def init_db(path: str | Path) -> sqlite3.Connection:
    """Initialise the SQLite database and return the connection."""
    conn = connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS standings (
            time TEXT,
            car_idx INTEGER,
            team TEXT,
            driver TEXT,
            class_id TEXT,
            position INTEGER,
            class_position INTEGER,
            lap INTEGER,
            best_lap REAL,
            last_lap REAL,
            on_pit INTEGER,
            pit_count INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pitstops (
            car_idx INTEGER,
            class TEXT,
            team TEXT,
            driver TEXT,
            start_ts TEXT,
            end_ts TEXT,
            start_sess REAL,
            end_sess REAL,
            start_lap INTEGER,
            end_lap INTEGER,
            duration_sec REAL,
            duration TEXT,
            duration_laps INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_swaps (
            timestamp TEXT,
            car_idx INTEGER,
            team TEXT,
            driver_out TEXT,
            driver_in TEXT,
            lap INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_totals (
            team TEXT,
            driver TEXT,
            total_time REAL,
            total_laps INTEGER,
            best_lap REAL
        )
        """
    )
    conn.commit()
    return conn


def insert(conn: sqlite3.Connection, table: str, row: Iterable[Any]) -> None:
    """Insert a row tuple into the given table."""
    placeholders = ",".join(["?"] * len(row))
    conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", tuple(row))
    conn.commit()

