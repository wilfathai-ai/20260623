"""SQLite による議事録の永続化"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "meetings.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                client_name TEXT,
                meeting_date TEXT,
                raw_text TEXT,
                analysis_json TEXT
            )
            """
        )
        conn.commit()


def save_meeting(client_name: str, meeting_date: str, raw_text: str, analysis_json: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO meetings (created_at, client_name, meeting_date, raw_text, analysis_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (datetime.now().isoformat(timespec="seconds"), client_name, meeting_date, raw_text, analysis_json),
        )
        conn.commit()
        return cursor.lastrowid


def list_meetings() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, client_name, meeting_date, analysis_json
            FROM meetings
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_meeting(meeting_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        return dict(row) if row else None


def delete_meeting(meeting_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        conn.commit()
        return cursor.rowcount > 0
