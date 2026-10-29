"""Append-only, hash-chained audit journal for authenticated web mutations."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from flask import current_app, g, request
from flask_jwt_extended import get_jwt, get_jwt_identity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_event (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL,
    subject TEXT NOT NULL,
    roles_json TEXT NOT NULL,
    source_ip TEXT,
    method TEXT NOT NULL,
    route_id TEXT,
    path TEXT NOT NULL,
    request_json TEXT,
    status_code INTEGER NOT NULL,
    completed_at TEXT,
    duration_ms REAL,
    outcome TEXT,
    response_json TEXT,
    error_json TEXT,
    device TEXT,
    command TEXT,
    entry_version INTEGER NOT NULL DEFAULT 2,
    previous_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS audit_event_recorded_at_idx
    ON audit_event(recorded_at);
CREATE INDEX IF NOT EXISTS audit_event_subject_idx
    ON audit_event(subject);
"""

_REDACTED_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "credential",
    "credentials",
}
_MAX_TEXT = 32_768
_HEARTBEAT_COMMANDS = frozenset(
    {"heartbeat", "heart_beat", "keepalive", "keep_alive", "ping"}
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            name = str(key)
            result[name] = (
                "[REDACTED]" if name.lower() in _REDACTED_KEYS else _json_safe(item)
            )
        return result
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _bounded_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    encoded = _canonical(_json_safe(value))
    if len(encoded) > _MAX_TEXT:
        return encoded[:_MAX_TEXT] + "...[TRUNCATED]"
    return encoded


def _is_heartbeat_command(command: Any) -> bool:
    return str(command or "").strip().lower() in _HEARTBEAT_COMMANDS


class AuditJournal:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def append(self, event: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT entry_hash FROM audit_event ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = row[0] if row else "0" * 64
            payload = dict(event)
            payload.setdefault("entry_version", 2)
            payload["previous_hash"] = previous_hash
            entry_hash = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO audit_event (
                    event_id, recorded_at, subject, roles_json, source_ip,
                    method, route_id, path, request_json, status_code,
                    completed_at, duration_ms, outcome, response_json,
                    error_json, device, command, entry_version,
                    previous_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload["recorded_at"],
                    payload["subject"],
                    _canonical(payload["roles"]),
                    payload.get("source_ip"),
                    payload["method"],
                    payload.get("route_id"),
                    payload["path"],
                    payload.get("request_json"),
                    payload["status_code"],
                    payload.get("completed_at"),
                    payload.get("duration_ms"),
                    payload.get("outcome"),
                    payload.get("response_json"),
                    payload.get("error_json"),
                    payload.get("device"),
                    payload.get("command"),
                    payload["entry_version"],
                    previous_hash,
                    entry_hash,
                ),
            )


def _configured_journal() -> Optional[AuditJournal]:
    path = os.environ.get("PYCONLYSE_AUDIT_DB_PATH", "").strip()
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        raise RuntimeError("PYCONLYSE_AUDIT_DB_PATH must be absolute")
    return AuditJournal(candidate)


def install_audit_log(app) -> None:
    """Install response-time mutation logging for authenticated API requests."""
    app.extensions["pyconlyse_audit_journal"] = _configured_journal()

    @app.after_request
    def write_authenticated_mutation_audit(response):
        context = getattr(g, "pyconlyse_audit", None)
        journal = current_app.extensions.get("pyconlyse_audit_journal")
        if context is None or journal is None:
            return response
        event = dict(context)
        event["status_code"] = int(response.status_code)
        event["completed_at"] = datetime.now(timezone.utc).isoformat()
        started = getattr(g, "pyconlyse_audit_started_monotonic", None)
        event["duration_ms"] = (
            round((time.monotonic() - started) * 1000.0, 3)
            if isinstance(started, (int, float))
            else None
        )
        response_payload = response.get_json(silent=True) if response.is_json else None
        event["response_json"] = _bounded_json(response_payload)
        event["error_json"] = (
            event["response_json"] if response.status_code >= 400 else None
        )
        event["outcome"] = "success" if response.status_code < 400 else "error"
        try:
            journal.append(event)
        except Exception:
            current_app.logger.exception("Unable to append audit event")
        return response


def mark_authenticated_mutation() -> None:
    """Capture immutable request details after JWT and CSRF verification."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    payload = request.get_json(silent=True)
    request_json = _bounded_json(payload)
    roles = get_jwt().get("roles", [])
    if not isinstance(roles, list):
        roles = []
    g.pyconlyse_audit = {
        "event_id": str(uuid.uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "subject": str(get_jwt_identity()),
        "roles": [str(role) for role in roles],
        "source_ip": request.remote_addr,
        "method": request.method,
        "route_id": request.endpoint,
        "path": request.path,
        "request_json": request_json,
        "device": str(payload.get("device")) if isinstance(payload, dict) and payload.get("device") is not None else None,
        "command": str(payload.get("command")) if isinstance(payload, dict) and payload.get("command") is not None else None,
    }
    g.pyconlyse_audit_started_monotonic = time.monotonic()


def record_websocket_mutation(
    *,
    subject: str,
    roles,
    device: str,
    command: str,
    args: Any,
    status_code: int,
    result: Any = None,
    error: Any = None,
    started_monotonic: Optional[float] = None,
) -> None:
    """Append the outcome of one authenticated WebSocket hardware command."""
    if _is_heartbeat_command(command):
        return
    journal = current_app.extensions.get("pyconlyse_audit_journal")
    if journal is None or not subject:
        return
    payload = _bounded_json({"device": device, "command": command, "args": args})
    completed_at = datetime.now(timezone.utc).isoformat()
    try:
        journal.append(
            {
                "event_id": str(uuid.uuid4()),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "subject": str(subject),
                "roles": (
                    [str(role) for role in roles] if isinstance(roles, list) else []
                ),
                "source_ip": request.remote_addr,
                "method": "WEBSOCKET",
                "route_id": "websocket.execute_command",
                "path": f"{device}/{command}",
                "request_json": payload,
                "status_code": int(status_code),
                "completed_at": completed_at,
                "duration_ms": (
                    round((time.monotonic() - started_monotonic) * 1000.0, 3)
                    if isinstance(started_monotonic, (int, float))
                    else None
                ),
                "outcome": "success" if int(status_code) < 400 else "error",
                "response_json": _bounded_json(result),
                "error_json": _bounded_json(error),
                "device": str(device),
                "command": str(command),
            }
        )
    except Exception:
        current_app.logger.exception("Unable to append WebSocket audit event")
