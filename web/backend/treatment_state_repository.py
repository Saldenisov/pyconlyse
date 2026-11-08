"""Durable, per-browser treatment session and queue snapshots."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock


class TreatmentStateRepository:
    def __init__(self, path):
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise ValueError("Treatment state database path must be absolute")
        self.path = candidate.resolve()
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS treatment_session (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS treatment_queue (
                    session_id TEXT PRIMARY KEY,
                    jobs_json TEXT NOT NULL,
                    discarded_terminal_jobs INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS treatment_setting (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _encode(value):
        def convert(item):
            if isinstance(item, Path):
                return str(item)
            if hasattr(item, "tolist"):
                return item.tolist()
            if hasattr(item, "item"):
                return item.item()
            raise TypeError(f"Unsupported treatment state value: {type(item).__name__}")

        return json.dumps(value, ensure_ascii=False, allow_nan=False, default=convert)

    def load_sessions(self):
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT session_id, state_json FROM treatment_session"
            ).fetchall()
        return {session_id: json.loads(payload) for session_id, payload in rows}

    def save_session(self, session_id, state):
        payload = self._encode(state)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO treatment_session (session_id, state_json) VALUES (?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json",
                (session_id, payload),
            )

    def delete_session(self, session_id=None):
        with self._lock, self._connect() as connection:
            if session_id is None:
                connection.execute("DELETE FROM treatment_session")
            else:
                connection.execute(
                    "DELETE FROM treatment_session WHERE session_id=?", (session_id,)
                )

    def load_queues(self):
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT session_id, jobs_json, discarded_terminal_jobs FROM treatment_queue"
            ).fetchall()
        return {
            session_id: (json.loads(payload), int(discarded))
            for session_id, payload, discarded in rows
        }

    def save_queue(self, session_id, jobs, discarded_terminal_jobs=0):
        payload = self._encode(jobs)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO treatment_queue (session_id, jobs_json, discarded_terminal_jobs) "
                "VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET "
                "jobs_json=excluded.jobs_json, "
                "discarded_terminal_jobs=excluded.discarded_terminal_jobs",
                (session_id, payload, int(discarded_terminal_jobs)),
            )

    def get_setting(self, name):
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM treatment_setting WHERE name=?", (name,)
            ).fetchone()
        return row[0] if row else None

    def save_setting(self, name, value):
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO treatment_setting (name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (name, value),
            )
