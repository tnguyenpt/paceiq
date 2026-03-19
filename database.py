"""
SQLite database layer for PaceIQ.
Stores activities and weekly summaries in ~/.paceiq/activities.db
"""

import sqlite3
import pathlib
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import get_config


def _get_connection() -> sqlite3.Connection:
    """Open and return a database connection with row_factory set."""
    config = get_config()
    db_path = config["db_path"]
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS activities (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                strava_id           INTEGER UNIQUE,
                date                TEXT NOT NULL,
                name                TEXT,
                distance_miles      REAL,
                duration_seconds    INTEGER,
                avg_pace_per_mile   TEXT,
                avg_hr              REAL,
                max_hr              REAL,
                elevation_gain      REAL,
                run_type            TEXT,
                week_number         INTEGER,
                year                INTEGER,
                shoe_used           TEXT,
                created_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                week_number     INTEGER NOT NULL,
                year            INTEGER NOT NULL,
                total_miles     REAL,
                tempo_avg_pace  TEXT,
                long_run_miles  REAL,
                num_runs        INTEGER,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                UNIQUE(week_number, year)
            );

            CREATE INDEX IF NOT EXISTS idx_activities_date
                ON activities(date);
            CREATE INDEX IF NOT EXISTS idx_activities_week
                ON activities(week_number, year);
            CREATE INDEX IF NOT EXISTS idx_activities_strava_id
                ON activities(strava_id);
        """)
        conn.commit()
    finally:
        conn.close()


def save_activity(activity: Dict[str, Any]) -> int:
    """
    Insert or update an activity record.
    Returns the row id.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO activities
                (strava_id, date, name, distance_miles, duration_seconds,
                 avg_pace_per_mile, avg_hr, max_hr, elevation_gain,
                 run_type, week_number, year, shoe_used)
            VALUES
                (:strava_id, :date, :name, :distance_miles, :duration_seconds,
                 :avg_pace_per_mile, :avg_hr, :max_hr, :elevation_gain,
                 :run_type, :week_number, :year, :shoe_used)
            ON CONFLICT(strava_id) DO UPDATE SET
                date             = excluded.date,
                name             = excluded.name,
                distance_miles   = excluded.distance_miles,
                duration_seconds = excluded.duration_seconds,
                avg_pace_per_mile= excluded.avg_pace_per_mile,
                avg_hr           = excluded.avg_hr,
                max_hr           = excluded.max_hr,
                elevation_gain   = excluded.elevation_gain,
                run_type         = excluded.run_type,
                week_number      = excluded.week_number,
                year             = excluded.year,
                shoe_used        = excluded.shoe_used
            """,
            {
                "strava_id": activity.get("strava_id"),
                "date": activity.get("date", datetime.now().strftime("%Y-%m-%d")),
                "name": activity.get("name", "Run"),
                "distance_miles": activity.get("distance_miles", 0.0),
                "duration_seconds": activity.get("duration_seconds", 0),
                "avg_pace_per_mile": activity.get("avg_pace_per_mile", "0:00"),
                "avg_hr": activity.get("avg_hr"),
                "max_hr": activity.get("max_hr"),
                "elevation_gain": activity.get("elevation_gain", 0.0),
                "run_type": activity.get("run_type", "easy"),
                "week_number": activity.get("week_number"),
                "year": activity.get("year"),
                "shoe_used": activity.get("shoe_used"),
            },
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_activity_by_strava_id(strava_id: int) -> Optional[Dict[str, Any]]:
    """Return a single activity dict by Strava ID, or None."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM activities WHERE strava_id = ?", (strava_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_activities_by_week(week_number: int, year: int) -> List[Dict[str, Any]]:
    """Return all activities for a given ISO week number and year."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM activities
            WHERE week_number = ? AND year = ?
            ORDER BY date ASC
            """,
            (week_number, year),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_activities(n: int = 10) -> List[Dict[str, Any]]:
    """Return the n most recent activities."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM activities ORDER BY date DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_activities_since(date_str: str) -> List[Dict[str, Any]]:
    """Return all activities on or after date_str (YYYY-MM-DD)."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM activities WHERE date >= ? ORDER BY date ASC",
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_weekly_summary(summary: Dict[str, Any]) -> None:
    """Insert or replace a weekly summary record."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO weekly_summaries
                (week_number, year, total_miles, tempo_avg_pace,
                 long_run_miles, num_runs, notes)
            VALUES
                (:week_number, :year, :total_miles, :tempo_avg_pace,
                 :long_run_miles, :num_runs, :notes)
            ON CONFLICT(week_number, year) DO UPDATE SET
                total_miles    = excluded.total_miles,
                tempo_avg_pace = excluded.tempo_avg_pace,
                long_run_miles = excluded.long_run_miles,
                num_runs       = excluded.num_runs,
                notes          = excluded.notes
            """,
            {
                "week_number": summary.get("week_number"),
                "year": summary.get("year"),
                "total_miles": summary.get("total_miles", 0.0),
                "tempo_avg_pace": summary.get("tempo_avg_pace", ""),
                "long_run_miles": summary.get("long_run_miles", 0.0),
                "num_runs": summary.get("num_runs", 0),
                "notes": summary.get("notes", ""),
            },
        )
        conn.commit()
    finally:
        conn.close()


def get_weekly_summary(week_number: int, year: int) -> Optional[Dict[str, Any]]:
    """Return the weekly summary for a given week, or None."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM weekly_summaries WHERE week_number = ? AND year = ?",
            (week_number, year),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_activities_for_weeks(
    week_numbers: List[int], year: int
) -> List[Dict[str, Any]]:
    """Return activities for a list of week numbers in a given year."""
    if not week_numbers:
        return []
    placeholders = ",".join("?" * len(week_numbers))
    conn = _get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM activities
            WHERE week_number IN ({placeholders}) AND year = ?
            ORDER BY date ASC
            """,
            (*week_numbers, year),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
