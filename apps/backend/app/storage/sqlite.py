"""SQLite storage for sessions and events (demo-grade)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from app.models import EventEnvelope, EventRecord, SessionState


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _dt_to_str(dt: datetime) -> str:
    # ISO 8601 with timezone
    return dt.isoformat()


def _str_to_dt(s: str) -> datetime:
    # Python 3.11: fromisoformat handles offset
    return datetime.fromisoformat(s)


@dataclass(frozen=True)
class SQLiteStore:
    db_path: Path

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  status TEXT NOT NULL,
                  state_json TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT NOT NULL,
                  ts TEXT NOT NULL,
                  type TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session_id_id ON events(session_id, id);"
            )
            conn.commit()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def create_session(self, session_id: str) -> SessionState:
        now = utc_now()
        state = SessionState(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            status="new",
            messages=[],
        )
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at, status, state_json) VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    _dt_to_str(state.created_at),
                    _dt_to_str(state.updated_at),
                    state.status,
                    state.model_dump_json(),
                ),
            )
            conn.commit()
        return state

    def get_session(self, session_id: str) -> SessionState:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"session not found: {session_id}")
        return SessionState.model_validate_json(row[0])

    def save_session(self, session: SessionState) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ?, status = ?, state_json = ? WHERE id = ?",
                (
                    _dt_to_str(session.updated_at),
                    session.status,
                    session.model_dump_json(),
                    session.session_id,
                ),
            )
            conn.commit()

    def append_event(
        self,
        session_id: str,
        *,
        type: str,
        payload: Optional[dict[str, Any]] = None,
        ts: Optional[datetime] = None,
    ) -> EventEnvelope:
        payload = payload or {}
        ts = ts or utc_now()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO events (session_id, ts, type, payload_json) VALUES (?, ?, ?, ?)",
                (session_id, _dt_to_str(ts), type, json.dumps(payload, ensure_ascii=False)),
            )
            event_id = int(cur.lastrowid)
            conn.commit()

        return EventEnvelope(id=event_id, type=type, ts=ts, payload=payload)

    def list_events(
        self,
        session_id: str,
        *,
        after_id: int = 0,
        limit: int = 200,
    ) -> list[EventRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, ts, type, payload_json
                FROM events
                WHERE session_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, after_id, limit),
            ).fetchall()

        out: list[EventRecord] = []
        for (eid, sid, ts_s, typ, payload_json) in rows:
            out.append(
                EventRecord(
                    id=int(eid),
                    session_id=str(sid),
                    ts=_str_to_dt(str(ts_s)),
                    type=typ,
                    payload=json.loads(payload_json) if payload_json else {},
                )
            )
        return out


