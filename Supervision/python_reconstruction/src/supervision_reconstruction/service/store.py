"""SQLite shadow-intent journal. Hash chaining detects accidental/mid-chain edits.

Not a signed audit authority: a fully privileged database editor can recompute
the chain or remove its tail. This journal never queues or replays hardware work.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from .shadow import canonical_json


class IdempotencyConflict(ValueError):
    pass


class AuditIntegrityError(RuntimeError):
    pass


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ShadowJournal:
    def __init__(self, path: str | Path):
        existing = str(path) != ":memory:" and Path(path).exists()
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        try:
            if existing and self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='shadow_intents'"
            ).fetchone() is None:
                raise AuditIntegrityError("Existing file is not a shadow journal; preserved without initialization")
            self._connection.execute("""CREATE TABLE IF NOT EXISTS shadow_intents (
                seq INTEGER PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                request_sha TEXT NOT NULL,
                record_json TEXT NOT NULL,
                previous_sha TEXT NOT NULL,
                record_sha TEXT NOT NULL
            )""")
            self._connection.commit()
            self.verify()
        except Exception:
            self._connection.close()
            raise

    def _verify_locked(self) -> list[dict]:
        previous = "0" * 64
        records = []
        for expected_seq, row in enumerate(self._connection.execute("SELECT * FROM shadow_intents ORDER BY seq"), 1):
            try:
                record = json.loads(row["record_json"])
                valid = (row["seq"] == expected_seq and row["previous_sha"] == previous
                         and row["record_sha"] == _sha(row["record_json"])
                         and canonical_json(record) == row["record_json"]
                         and record["seq"] == expected_seq and record["previous_sha"] == previous
                         and record["idempotency_key"] == row["idempotency_key"]
                         and record["request_sha"] == row["request_sha"]
                         and _sha(canonical_json(record["request"])) == row["request_sha"]
                         and record["result"]["execution_allowed"] is False
                         and record["result"]["physical_status"] == "NOT_EXECUTED")
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                raise AuditIntegrityError("Shadow journal integrity check failed; existing data preserved")
            record["record_sha"] = row["record_sha"]
            records.append(record)
            previous = row["record_sha"]
        return records

    @staticmethod
    def _status(records: list[dict]) -> dict:
        return {"valid": True, "count": len(records),
                "head_sha": records[-1]["record_sha"] if records else "0" * 64,
                "signed": False, "hardware_queue": False}

    def verify(self) -> dict:
        with self._lock:
            return self._status(self._verify_locked())

    def snapshot(self) -> tuple[dict, list[dict]]:
        """One coherent journal count/head/history view under concurrent previews."""
        with self._lock:
            records = self._verify_locked()
            return self._status(records), list(reversed(records[-20:]))

    def append(self, idempotency_key: str, request: dict, result: dict, *, now: datetime) -> tuple[dict, bool]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware journal time required")
        if result.get("execution_allowed") is not False or result.get("physical_status") != "NOT_EXECUTED":
            raise ValueError("Journal accepts only non-executable shadow results")
        request_json = canonical_json(request)
        request_sha = _sha(request_json)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                records = self._verify_locked()
                existing = next((item for item in records if item["idempotency_key"] == idempotency_key), None)
                if existing is not None:
                    if existing["request_sha"] != request_sha:
                        raise IdempotencyConflict("Idempotency key already belongs to a different intent")
                    self._connection.commit()
                    return existing, True
                record = {"seq": len(records) + 1, "command_id": str(uuid4()),
                          "idempotency_key": idempotency_key, "request_sha": request_sha,
                          "request": json.loads(request_json), "result": result,
                          "recorded_at": now.astimezone(timezone.utc).isoformat(),
                          "actor": "offline-local-analysis-not-an-authenticated-operator",
                          "previous_sha": records[-1]["record_sha"] if records else "0" * 64}
                record_json = canonical_json(record)
                record_sha = _sha(record_json)
                self._connection.execute("INSERT INTO shadow_intents VALUES (?, ?, ?, ?, ?, ?)",
                    (record["seq"], idempotency_key, request_sha, record_json, record["previous_sha"], record_sha))
                self._connection.commit()
                returned = json.loads(record_json)
                returned["record_sha"] = record_sha
                return returned, False
            except Exception:
                self._connection.rollback()
                raise

    def history(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100")
        with self._lock:
            return list(reversed(self._verify_locked()[-limit:]))

    def close(self) -> None:
        with self._lock:
            self._connection.close()
