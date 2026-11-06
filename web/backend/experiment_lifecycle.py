"""Durable, single-worker lifecycle progress; snapshots never replay hardware I/O."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4


class ProgressSteps(list):
    def __init__(self, lifecycle):
        super().__init__()
        self.lifecycle = lifecycle

    def append(self, item):
        super().append(item)
        self.lifecycle.update(steps=list(self), event={
            "kind": "error" if item.get("status") in {"failed", "skipped"}
                    else "warning" if item.get("status") == "unverified" else "check",
            "message": item.get("step", "Equipment check"),
            "detail": item.get("detail") or item.get("status", ""),
        })

    def phase(self, detail, stage=1, wait_until=None):
        self.lifecycle.update(phase=detail, stage=stage, wait_until=wait_until,
                              event={"kind": "progress", "message": detail})

    def power_intent(self):
        # Persist before the PDU write: an interrupted write has unknown outcome.
        self.lifecycle.put("camera_power_wait", {"pending": True, "deadline": None})

    def power_deadline(self, newly_enabled):
        previous = self.lifecycle.get("camera_power_wait") or {}
        deadline = previous.get("deadline")
        if newly_enabled or (previous.get("pending") and deadline is None):
            deadline = time.time() + 30.0
            self.lifecycle.put("camera_power_wait", {"pending": True, "deadline": deadline})
        return deadline

    def power_ready(self):
        self.lifecycle.put("camera_power_wait", {"pending": False, "deadline": None})


class ExperimentLifecycle:
    """One Flask worker owns execution; SQLite survives page and worker restarts."""

    def __init__(self, path, experiment="VD2"):
        self.path = Path(path).resolve()
        self.experiment = str(experiment)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, timestamp REAL NOT NULL, value TEXT NOT NULL)")
        previous = self.get("job")
        if previous and previous.get("status") == "running":
            previous.update(
                status="interrupted", wait_until=None, updated_at=time.time(),
                error="Web server restarted during the operation. Hardware state is not verified. Press Prepare to recheck; saved commands are never replayed automatically.",
                phase="Operation interrupted by web-server restart",
            )
            self.record(previous, {"kind": "interrupted", "message": previous["error"]})

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, key):
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, value):
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, json.dumps(value)))

    def snapshot(self):
        with self.lock:
            result = self.get("job") or {"status": "idle", "experiment": self.experiment, "steps": []}
        return {**result, "server_time": time.time(), "events": self.events()}

    def events(self, before=None, limit=100):
        limit = max(1, min(int(limit), 500))
        with self.connect() as connection:
            if before is None:
                rows = connection.execute("SELECT id, value FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = connection.execute("SELECT id, value FROM events WHERE id < ? ORDER BY id DESC LIMIT ?", (int(before), limit)).fetchall()
        return [{"id": row[0], **json.loads(row[1])} for row in reversed(rows)]

    def record(self, job, event):
        timestamp = time.time()
        entry = {"timestamp": timestamp, "job_id": job.get("job_id"),
                 "operation": job.get("operation"), **event}
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO state VALUES ('job', ?)", (json.dumps(job),))
            if job.get("job_id"):
                connection.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?)", (job["job_id"], json.dumps(job)))
            connection.execute("INSERT INTO events (job_id, timestamp, value) VALUES (?, ?, ?)",
                               (job.get("job_id"), timestamp, json.dumps(entry)))

    def update(self, event=None, **changes):
        with self.lock:
            job = self.get("job")
            job.update(changes, updated_at=time.time())
            if event:
                self.record(job, event)
            elif "status" in changes:
                self.record(job, {"kind": changes["status"], "message": job.get("error") or job.get("phase", ""),
                                  "code": job.get("code", "")})
            else:
                self.record(job, {"kind": "state", "message": "Operation state updated"})

    def start(self, operation, action, release, intent=None):
        now = time.time()
        job = {
            "job_id": str(uuid4()), "experiment": self.experiment, "operation": operation,
            "status": "running", "stage": 0, "steps": [], "error": "", "result": None,
            "phase": "Checking current equipment state" if operation == "prepare" else "Checking safe shutdown conditions",
            "wait_until": None, "created_at": now, "updated_at": now,
        }
        if intent is not None:
            job["intent"] = intent
        with self.lock:
            self.record(job, {"kind": "started", "message": job["phase"]})

        def run():
            steps = ProgressSteps(self)
            try:
                result = action(steps)
                self.update(status="completed", result=result, steps=result.get("steps", list(steps)),
                            phase=result.get("message", "Operation completed"), stage=2, wait_until=None)
            except Exception as exc:
                self.update(status="failed", error=str(exc), code=getattr(exc, "code", ""), steps=getattr(exc, "steps", list(steps)),
                            phase="Operation failed; correct the fault and retry", wait_until=None)
            finally:
                release()

        try:
            Thread(target=run, name=f"{self.experiment.lower()}-lifecycle", daemon=True).start()
        except Exception:
            self.update(status="failed", error="Could not start lifecycle worker", wait_until=None)
            raise
        return job
