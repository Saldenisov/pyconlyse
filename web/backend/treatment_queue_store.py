"""Per-session treatment queues, job execution, and output reservations."""

import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Dict, List, Optional
from uuid import uuid4

from treatment_network_path import is_smb_path, normalize_smb_path, normalize_treatment_path


DEFAULT_TREATMENT_MAX_WORKERS = 6


def _treatment_worker_count(task_count: int) -> int:
    """Bound treatment work by task count, configured limit, and available CPUs."""
    try:
        configured = int(
            os.environ.get(
                "PYCONLYSE_TREATMENT_MAX_WORKERS",
                str(DEFAULT_TREATMENT_MAX_WORKERS),
            )
        )
    except ValueError:
        configured = DEFAULT_TREATMENT_MAX_WORKERS
    available_cpus = max(1, int(os.cpu_count() or 1))
    return max(
        1,
        min(
            max(1, int(task_count or 1)),
            max(1, configured),
            available_cpus,
        ),
    )


class TreatmentQueueStore:
    """In-memory, per-treatment-session sequential job runner.

    Queue jobs deliberately own an immutable recipe snapshot and a unique
    TreatmentDataService runtime id.  This prevents later interactive edits
    from changing a queued calculation or sharing its calculated OD result.
    """

    def __init__(self):
        self._lock = Lock()
        self._queues: Dict[str, List[Dict[str, object]]] = {}
        self._workers: Dict[str, Thread] = {}
        self._output_reservations: Dict[str, str] = {}
        self._discarded_terminal_jobs: Dict[str, int] = {}
        self._history_limit = 100

    @staticmethod
    def _public_job(job: Dict[str, object]) -> Dict[str, object]:
        return deepcopy(job)

    @staticmethod
    def _output_reservation_key(output_path: str) -> str:
        """Normalize aliases conservatively so queue jobs cannot overwrite each other."""
        raw_path = str(output_path or "").strip()
        if is_smb_path(raw_path):
            return f"smb:{normalize_smb_path(raw_path).rstrip('/').casefold()}"
        if re.match(r"^[A-Za-z]:[\\/]", raw_path):
            normalized_windows_path = raw_path.replace("\\", "/").rstrip("/")
            return f"windows:{normalized_windows_path.casefold()}"
        normalized = os.path.realpath(normalize_treatment_path(raw_path)).rstrip(os.sep)
        return f"local:{normalized.casefold()}"

    def _reserve_output_locked(self, output_path: str, owner: str) -> None:
        if not output_path:
            return
        key = self._output_reservation_key(output_path)
        existing_owner = self._output_reservations.get(key)
        if existing_owner and existing_owner != owner:
            raise ValueError("Output path is already reserved by an active queue or save operation")
        self._output_reservations[key] = owner

    def _release_output_locked(self, output_path: str, owner: str) -> None:
        if not output_path:
            return
        key = self._output_reservation_key(output_path)
        if self._output_reservations.get(key) == owner:
            self._output_reservations.pop(key, None)

    def reserve_immediate_output(self, output_path: str) -> Optional[str]:
        if not output_path:
            return None
        owner = f"immediate:{uuid4().hex}"
        with self._lock:
            self._reserve_output_locked(output_path, owner)
        return owner

    def release_immediate_output(self, output_path: str, owner: Optional[str]) -> None:
        if not owner:
            return
        with self._lock:
            self._release_output_locked(output_path, owner)

    def enqueue(self, session_id: str, recipe: Dict[str, object]) -> Dict[str, object]:
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "job_id": uuid4().hex,
            "status": "queued",
            "phase": "queued",
            "message": "Queued; processing has not started.",
            "queued_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "result": None,
            "saved": None,
            "recipe": deepcopy(recipe),
        }
        with self._lock:
            jobs = self._queues.setdefault(session_id, [])
            self._prune_terminal_jobs(session_id, jobs)
            output_path = str((recipe.get("output") or {}).get("path") or "")
            self._reserve_output_locked(output_path, f"queue:{job['job_id']}")
            jobs.append(job)
            return self._public_job(job)

    def snapshot(self, session_id: str) -> Dict[str, object]:
        with self._lock:
            jobs = self._queues.get(session_id, [])
            active_job = next((job for job in jobs if job["status"] == "running"), None)
            return {
                "running": session_id in self._workers,
                "persistence": "process_local",
                "restart_behavior": "Queued jobs are lost when the backend process restarts.",
                "active_job_id": active_job["job_id"] if active_job else None,
                "pending_count": sum(job["status"] == "queued" for job in jobs),
                "discarded_terminal_jobs": self._discarded_terminal_jobs.get(session_id, 0),
                "history_limit": self._history_limit,
                "jobs": [self._public_job(job) for job in jobs],
            }

    def remove_queued(self, session_id: str, job_id: str) -> Dict[str, object]:
        with self._lock:
            jobs = self._queues.get(session_id, [])
            for index, job in enumerate(jobs):
                if job["job_id"] != job_id:
                    continue
                if job["status"] != "queued":
                    raise RuntimeError("Only queued jobs can be removed")
                removed = jobs.pop(index)
                output_path = str(
                    (removed.get("recipe", {}).get("output") or {}).get("path") or ""
                )
                self._release_output_locked(output_path, f"queue:{removed['job_id']}")
                return self._public_job(removed)
        raise KeyError(job_id)

    def _prune_terminal_jobs(self, session_id: str, jobs: List[Dict[str, object]]) -> None:
        terminal = [job for job in jobs if job["status"] in {"completed", "failed"}]
        excess = len(terminal) - self._history_limit
        if excess <= 0:
            return
        stale_ids = {job["job_id"] for job in terminal[:excess]}
        jobs[:] = [job for job in jobs if job["job_id"] not in stale_ids]
        self._discarded_terminal_jobs[session_id] = (
            self._discarded_terminal_jobs.get(session_id, 0) + excess
        )

    def start(self, session_id: str, executor) -> bool:
        """Start one drain worker. Returns False when it is already draining."""
        with self._lock:
            if session_id in self._workers:
                return False
            worker = Thread(
                target=self._drain,
                args=(session_id, executor),
                daemon=True,
                name=f"treatment-queue-{session_id[:8]}",
            )
            self._workers[session_id] = worker
            worker.start()
            return True

    def update_job(self, job_id: str, **updates) -> None:
        with self._lock:
            for jobs in self._queues.values():
                for job in jobs:
                    if job["job_id"] == job_id:
                        job.update(deepcopy(updates))
                        return

    def _drain(self, session_id: str, executor) -> None:
        while True:
            with self._lock:
                jobs = self._queues.get(session_id, [])
                job = next((item for item in jobs if item["status"] == "queued"), None)
                if job is None:
                    self._workers.pop(session_id, None)
                    return
                job["status"] = "running"
                job["phase"] = "preparing"
                job["message"] = "Preparing immutable treatment recipe."
                job["started_at"] = datetime.now(timezone.utc).isoformat()
                job["error"] = None
                recipe = deepcopy(job["recipe"])
                job_id = str(job["job_id"])

            try:
                outcome = executor(job_id, recipe)
            except Exception as exc:  # Job failures must remain observable.
                with self._lock:
                    job["status"] = "failed"
                    job["phase"] = "error"
                    job["message"] = "Processing failed; inspect error."
                    job["error"] = str(exc)
                    job["completed_at"] = datetime.now(timezone.utc).isoformat()
                    output_path = str(
                        (job.get("recipe", {}).get("output") or {}).get("path") or ""
                    )
                    self._release_output_locked(output_path, f"queue:{job['job_id']}")
                    self._prune_terminal_jobs(session_id, self._queues.get(session_id, []))
            else:
                with self._lock:
                    job["status"] = "completed"
                    job["phase"] = "complete"
                    job["message"] = str(
                        outcome.get("message") or "Optical-density result saved."
                    )
                    job["result"] = deepcopy(outcome.get("result"))
                    job["saved"] = deepcopy(outcome.get("saved"))
                    job["preparation"] = deepcopy(outcome.get("preparation"))
                    job["completed_at"] = datetime.now(timezone.utc).isoformat()
                    output_path = str(
                        (job.get("recipe", {}).get("output") or {}).get("path") or ""
                    )
                    self._release_output_locked(output_path, f"queue:{job['job_id']}")
                    self._prune_terminal_jobs(session_id, self._queues.get(session_id, []))
