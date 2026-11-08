"""Per-session treatment queues, job execution, and output reservations."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock, Thread, local
from time import monotonic
from typing import Dict, List, Optional
from uuid import uuid4

from treatment_network_path import is_smb_path, normalize_smb_path, normalize_treatment_path


DEFAULT_TREATMENT_MAX_WORKERS = 6
_treatment_thread_context = local()


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
    available_cpus = max(1, int(getattr(os, 'process_cpu_count', os.cpu_count)() or 1))
    return max(
        1,
        min(
            max(1, int(task_count or 1)),
            max(1, configured),
            available_cpus,
        ),
    )


class TreatmentQueueStore:
    """Session queues with independent manifest batches and durable snapshots.

    Queue jobs deliberately own an immutable recipe snapshot and a unique
    TreatmentDataService runtime id.  This prevents later interactive edits
    from changing a queued calculation or sharing its calculated OD result.
    """

    def __init__(self, repository=None):
        self._lock = Lock()
        self._repository = repository
        self._queues: Dict[str, List[Dict[str, object]]] = {}
        self._workers: Dict[str, Thread] = {}
        self._output_reservations: Dict[str, str] = {}
        self._discarded_terminal_jobs: Dict[str, int] = {}
        self._last_progress_persist_at: Dict[str, float] = {}
        self._history_limit = 100
        self._sample_slots = BoundedSemaphore(_treatment_worker_count(100))
        if repository:
            for session_id, (jobs, discarded) in repository.load_queues().items():
                self._queues[session_id] = jobs
                self._discarded_terminal_jobs[session_id] = discarded
                changed = False
                for job in jobs:
                    if job.get("status") == "running":
                        job.update({
                            "status": "interrupted",
                            "phase": "interrupted",
                            "message": "Server restarted during processing; this job was not retried.",
                            "error": "Server restarted before the job completed.",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        })
                        changed = True
                    elif job.get("status") == "queued":
                        output_path = str((job.get("recipe", {}).get("output") or {}).get("path") or "")
                        try:
                            self._reserve_output_locked(output_path, f"queue:{job['job_id']}")
                        except ValueError:
                            job.update({
                                "status": "interrupted",
                                "phase": "interrupted",
                                "message": "Queued output conflicts with another restored job.",
                                "error": "Output reservation conflict after restart.",
                            })
                            changed = True
                if changed:
                    self._persist_locked(session_id)

    def _persist_locked(self, session_id):
        if self._repository:
            self._repository.save_queue(
                session_id,
                self._queues.get(session_id, []),
                self._discarded_terminal_jobs.get(session_id, 0),
            )

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
        return self.enqueue_batch(session_id, [recipe])[0]

    def enqueue_batch(self, session_id, recipes):
        now = datetime.now(timezone.utc).isoformat()
        new_jobs = [{
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
        } for recipe in recipes]
        with self._lock:
            outputs = [str((job["recipe"].get("output") or {}).get("path") or "") for job in new_jobs]
            keys = [self._output_reservation_key(output) for output in outputs if output]
            if len(keys) != len(set(keys)) or any(key in self._output_reservations for key in keys):
                raise ValueError("Output path is already reserved by an active queue or save operation")
            jobs = self._queues.setdefault(session_id, [])
            self._prune_terminal_jobs(session_id, jobs)
            for job, output in zip(new_jobs, outputs):
                self._reserve_output_locked(output, f"queue:{job['job_id']}")
            jobs.extend(new_jobs)
            self._persist_locked(session_id)
            return [self._public_job(job) for job in new_jobs]

    def snapshot(self, session_id: str) -> Dict[str, object]:
        with self._lock:
            jobs = self._queues.get(session_id, [])
            active_job = next((job for job in jobs if job["status"] == "running"), None)
            return {
                "running": session_id in self._workers,
                "persistence": "sqlite" if self._repository else "process_local",
                "restart_behavior": (
                    "Jobs survive restart; running jobs become interrupted and queued jobs await Run."
                    if self._repository else
                    "Queued jobs are lost when the backend process restarts."
                ),
                "active_job_id": active_job["job_id"] if active_job else None,
                "active_job_ids": [job["job_id"] for job in jobs if job["status"] == "running"],
                "max_parallel_samples": _treatment_worker_count(100),
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
                self._persist_locked(session_id)
                return self._public_job(removed)
        raise KeyError(job_id)

    def _prune_terminal_jobs(self, session_id: str, jobs: List[Dict[str, object]]) -> None:
        terminal = [job for job in jobs if job["status"] in {"completed", "failed", "interrupted"}]
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
            for session_id, jobs in self._queues.items():
                for job in jobs:
                    if job["job_id"] == job_id:
                        job.update(deepcopy(updates))
                        now = monotonic()
                        critical = bool({"status", "error", "saved", "result", "completed_at"} & updates.keys())
                        if critical or now - self._last_progress_persist_at.get(session_id, 0.0) >= 1.0:
                            self._persist_locked(session_id)
                            self._last_progress_persist_at[session_id] = now
                        return

    def _drain(self, session_id: str, executor) -> None:
        while True:
            with self._lock:
                jobs = self._queues.get(session_id, [])
                pending = [item for item in jobs if item["status"] == "queued"]
                if not pending:
                    self._workers.pop(session_id, None)
                    return
                # Only manifest recipes have fully captured, independent noise
                # identities. Folder-set jobs inherit prior state and remain ordered.
                batch = []
                for item in pending:
                    if not (item["recipe"].get("provenance") or {}).get("vd2_project"):
                        break
                    batch.append(item)
                if not batch:
                    batch = pending[:1]
            if len(batch) > 1:
                with ThreadPoolExecutor(max_workers=_treatment_worker_count(len(batch)),
                                        thread_name_prefix="treatment-sample") as pool:
                    list(pool.map(lambda item: self._run_job(session_id, item, executor, True), batch))
            else:
                self._run_job(session_id, batch[0], executor, False)

    def _run_job(self, session_id, job, executor, parallel):
        with self._sample_slots if parallel else nullcontext():
            self._execute_job(session_id, job, executor, parallel)

    def _execute_job(self, session_id, job, executor, parallel):
        with self._lock:
            if job["status"] != "queued":
                return
            job["status"] = "running"
            job["phase"] = "preparing"
            job["message"] = "Preparing immutable treatment recipe."
            job["started_at"] = datetime.now(timezone.utc).isoformat()
            job["error"] = None
            recipe = deepcopy(job["recipe"])
            job_id = str(job["job_id"])
            self._persist_locked(session_id)

        try:
            _treatment_thread_context.parallel_sample = parallel
            try:
                outcome = executor(job_id, recipe)
            finally:
                _treatment_thread_context.parallel_sample = False
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
                self._persist_locked(session_id)
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
                self._persist_locked(session_id)
