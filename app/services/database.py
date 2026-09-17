import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.config import get_settings

def _path() -> Path:
    p = Path(get_settings().database_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

@contextmanager
def connect():
    conn = sqlite3.connect(_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS appointments (
                booking_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                service TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS handoffs (
                handoff_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

def get_session(session_id: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["state"] = json.loads(data.pop("state_json"))
    return data

def save_session(session_id: str, customer_id: str, channel: str, state: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions(session_id, customer_id, channel, state_json)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                channel = excluded.channel,
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, customer_id, channel, json.dumps(state)),
        )

def create_appointment(record: dict[str, str]) -> dict[str, str]:
    with connect() as conn:
        existing = conn.execute(
            "SELECT * FROM appointments WHERE idempotency_key = ?",
            (record["idempotency_key"],),
        ).fetchone()
        if existing:
            return dict(existing)
        conn.execute(
            """
            INSERT INTO appointments(
                booking_id, customer_id, service, appointment_date,
                appointment_time, status, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["booking_id"], record["customer_id"], record["service"],
                record["appointment_date"], record["appointment_time"],
                record["status"], record["idempotency_key"],
            ),
        )
    return record

def get_appointment(booking_id: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE booking_id = ?",
            (booking_id.upper(),),
        ).fetchone()
    return dict(row) if row else None

def cancel_appointment(booking_id: str):
    with connect() as conn:
        conn.execute(
            """
            UPDATE appointments
            SET status='cancelled', updated_at=CURRENT_TIMESTAMP
            WHERE booking_id=?
            """,
            (booking_id.upper(),),
        )
    return get_appointment(booking_id)

def list_appointments():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY created_at DESC"
        ).fetchall()
    return [dict(x) for x in rows]

def create_handoff(record: dict[str, str]) -> dict[str, str]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO handoffs(handoff_id, session_id, customer_id, reason)
            VALUES (?, ?, ?, ?)
            """,
            (
                record["handoff_id"], record["session_id"],
                record["customer_id"], record["reason"],
            ),
        )
    return record

def list_handoffs():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM handoffs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(x) for x in rows]


def get_manager_summary():
    with connect() as conn:
        booking_total = conn.execute(
            "SELECT COUNT(*) AS n FROM appointments"
        ).fetchone()["n"]
        confirmed = conn.execute(
            "SELECT COUNT(*) AS n FROM appointments WHERE status = 'confirmed'"
        ).fetchone()["n"]
        cancelled = conn.execute(
            "SELECT COUNT(*) AS n FROM appointments WHERE status = 'cancelled'"
        ).fetchone()["n"]
        handoff_total = conn.execute(
            "SELECT COUNT(*) AS n FROM handoffs"
        ).fetchone()["n"]
        open_handoffs = conn.execute(
            "SELECT COUNT(*) AS n FROM handoffs WHERE status = 'open'"
        ).fetchone()["n"]

    return {
        "bookings_total": booking_total,
        "confirmed_bookings": confirmed,
        "cancelled_bookings": cancelled,
        "handoffs_total": handoff_total,
        "open_handoffs": open_handoffs,
    }
