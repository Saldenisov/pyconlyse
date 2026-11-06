"""One-phase HIS acquisition protocol for the VD2 streak-camera experiment."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PureWindowsPath
from typing import Any, Callable, Mapping
from uuid import uuid4


PHASES: Mapping[str, dict[str, str]] = {
    "BRUIT": {"label": "Bruit", "file_stem": "BRUIT"},
    "BASE": {"label": "Base", "file_stem": "BASE"},
    "ABSORPTION": {"label": "Absorption", "file_stem": "ABS"},
}
DEFAULT_OUTPUT_ROOT = r"E:\DATA_VD2"


class Vd2ProtocolError(RuntimeError):
    """A protocol request cannot be performed safely."""


@dataclass(frozen=True)
class PhaseRequest:
    phase: str
    frames_per_his: int
    output_root: str
    run_name: str
    his_path: str
    sample_description: str = ""
    reuse_bruit: str = "latest"
    replaces_artifact: str | None = None
    repeat_of: str | None = None
    repeat_series: str | None = None
    reserve_directory: bool = False


class Vd2MeasurementProtocol:
    """Serializes one prepared Bruit/Base/Absorption HIS acquisition at a time."""

    def __init__(
        self,
        proxy_factory: Callable[[], Any],
        *,
        sequence_processor: Callable[[PhaseRequest], Mapping[str, Any]] | None = None,
        processing_worker: Callable | None = None,
        artifact_preflight: Callable[[PhaseRequest], None] | None = None,
        wait_for_idle: Callable[[Any], None] | None = None,
        artifact_journal=None,
        snapshot_reader=None,
        artifact_finalizer=None,
        point_recorder=None,
        max_pending_processing=8,
    ):
        if type(max_pending_processing) is not int or max_pending_processing < 1:
            raise ValueError("Processing queue capacity must be a positive integer")
        self._proxy_factory = proxy_factory
        self._sequence_processor = sequence_processor
        self._processing_worker = processing_worker
        self._artifact_preflight = artifact_preflight
        self._wait_for_idle = wait_for_idle
        self._artifact_journal = artifact_journal
        self._snapshot_reader = snapshot_reader
        self._artifact_finalizer = artifact_finalizer
        self._point_recorder = point_recorder
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._processing_thread = None
        self._pending = deque()
        self._jobs = {}
        self._latest_id = None
        self._acquisition_id = None
        self._max_pending_processing = max_pending_processing
        self._state: dict[str, Any] = {
            "status": "idle",
            "phase": None,
            "frames_per_his": None,
            "his_path": None,
            "h5_path": None,
            "frame_count": None,
            "started_at": None,
            "completed_at": None,
            "error": "",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            selected = self._acquisition_id or self._latest_id
            primary = self._jobs[selected] if selected else self._state
            fields = ("job_id", "phase", "phase_label", "sample_name", "status", "his_path", "h5_path", "frame_count", "error", "completed_at", "process_percent")
            processing = [{key: job.get(key) for key in fields} for job in self._jobs.values() if job.get("postprocessing")]
            pending = sum(job["status"] in {"preparing", "acquiring", "saving", "queued", "processing"} for job in self._jobs.values())
            return {**primary, "acquisition_active": self._acquisition_id is not None,
                    "acquisition_phase": self._jobs[self._acquisition_id]["status"] if self._acquisition_id else "idle",
                    "processing_jobs": processing, "queue_full": pending >= self._max_pending_processing,
                    "processing_capacity": self._max_pending_processing}

    def start(
        self,
        *,
        phase: str,
        frames_per_his: object,
        output_root: object = DEFAULT_OUTPUT_ROOT,
        run_name: object,
        sample_description: object = "",
        reuse_bruit: object = "latest",
    ) -> dict[str, Any]:
        request = self._build_request(phase, frames_per_his, output_root, run_name, sample_description, reuse_bruit)
        return self.start_request(request)

    def start_request(self, request: PhaseRequest) -> dict[str, Any]:
        """Start one internally validated destination, preserving its exact path."""
        if not isinstance(request, PhaseRequest):
            raise Vd2ProtocolError("A validated VD2 phase request is required")
        if not self._start_lock.acquire(blocking=False):
            raise Vd2ProtocolError("A VD2 HIS acquisition is already starting")
        job_id = uuid4().hex
        previous_latest = None
        try:
            with self._lock:
                if self._acquisition_id is not None:
                    raise Vd2ProtocolError("A VD2 HIS acquisition is already running")
                pending = sum(job["status"] in {"queued", "processing"} for job in self._jobs.values())
                if pending >= self._max_pending_processing:
                    raise Vd2ProtocolError("H5 conversion queue is full; wait for a conversion to finish")
                self._acquisition_id = job_id
                previous_latest = self._latest_id
                self._jobs[job_id] = {**self._state, "job_id": job_id, "status": "preparing", "phase": request.phase,
                                      "sample_name": request.run_name, "postprocessing": False}
                self._latest_id = job_id
            # Never hold the status/camera lock while validating files or
            # writing provenance. A slow disk cannot block status requests.
            if self._artifact_preflight is not None:
                self._artifact_preflight(request)
            provenance = self._artifact_journal.prepare(request) if self._artifact_journal else {}
            state = {
                "job_id": job_id,
                "status": "acquiring",
                "phase": request.phase,
                "phase_label": PHASES[request.phase]["label"],
                "frames_per_his": request.frames_per_his,
                "his_path": request.his_path,
                "sample_name": request.run_name,
                "sample_folder": str(PureWindowsPath(request.output_root) / request.run_name),
                "is_replacement": request.reserve_directory and not request.repeat_of,
                "h5_path": None, "frame_count": None, "started_at": _utc_now(), "completed_at": None,
                "error": "", "postprocessing": False, **provenance,
            }
            with self._lock:
                self._jobs[job_id] = state
                self._thread = threading.Thread(target=self._acquire, args=(request, provenance, job_id),
                                                daemon=True, name=f"vd2-{request.phase.lower()}-his")
                self._thread.start()
                accepted = {**state, "acquisition_active": True, "acquisition_phase": "acquiring"}
            return accepted
        except Exception as exc:
            with self._changed:
                if self._acquisition_id == job_id:
                    self._acquisition_id = None
                if job_id in self._jobs:
                    if self._jobs[job_id]["status"] == "preparing":
                        del self._jobs[job_id]
                        self._latest_id = previous_latest
                    else:
                        self._jobs[job_id].update(status="failed", error=str(exc), completed_at=_utc_now())
                self._changed.notify_all()
            raise
        finally:
            self._start_lock.release()

    def wait(self, timeout: float | None = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._changed:
            while any(job["status"] in {"preparing", "acquiring", "saving", "queued", "processing"} for job in self._jobs.values()):
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return
                self._changed.wait(remaining)

    def _acquire(self, request: PhaseRequest, provenance, job_id) -> None:
        identity = (provenance or {}).get("artifact_id")
        def record(status, **details):
            if self._artifact_journal:
                self._artifact_journal.record(request, identity, status, **details)
        try:
            proxy = self._proxy_factory()
            proxy.set_timeout_millis(300_000)
            if not bool(proxy.read_attribute("connected").value):
                raise Vd2ProtocolError("Hamamatsu Tango device is not connected")
            if not bool(proxy.read_attribute("application_running").value):
                raise Vd2ProtocolError("HPD-TA is not running")

            proxy.write_attribute("sequence_loops", str(request.frames_per_his))
            machine_before = self._snapshot_reader(proxy) if self._snapshot_reader else None
            if self._artifact_journal and request.reuse_bruit not in {"latest", "none", ""}:
                self._artifact_journal.verify_bruit_settings(request, machine_before)
            record("acquiring", machine_before=machine_before)
            proxy.command_inout("StartSequence")
            dg645 = (machine_before or {}).get("devices", {}).get("manip/sync/DG645", {}).get("values", {})
            rate = None
            if dg645.get("trigger_source") == 0 and dg645.get("burst_enabled") == 0:
                rate = dg645.get("trigger_rate_hz")
            self._update(job_id, capture_started_at=_utc_now(), capture_rate=rate)
            if self._wait_for_idle is None:
                proxy.command_inout("WaitForIdle")
            else:
                self._wait_for_idle(proxy)
            self._update(job_id, status="saving")
            proxy.command_inout("SaveCurrentSequence", request.his_path)
            # Capture machine state while this job still owns the camera.
            # The file worker receives plain data, never a Tango proxy.
            machine_after = self._snapshot_reader(proxy) if self._snapshot_reader else None
            record("saved", machine_after=machine_after)
            with self._changed:
                self._jobs[job_id].update(status="queued", postprocessing=True)
                self._pending.append((request, provenance, job_id, machine_after))
                self._acquisition_id = None
                if self._processing_thread is None or not self._processing_thread.is_alive():
                    self._processing_thread = threading.Thread(target=self._drain_processing, daemon=True, name="vd2-h5-conversion")
                    self._processing_thread.start()
                self._changed.notify_all()
        except Exception as exc:
            self._fail(request, provenance, job_id, exc)

    def _drain_processing(self):
        while True:
            with self._lock:
                if not self._pending:
                    self._processing_thread = None
                    return
                task = self._pending.popleft()
                if self._jobs.get(task[2], {}).get("status") != "queued":
                    continue
            self._process(*task)

    def _process(self, request, provenance, job_id, machine_after):
        identity = (provenance or {}).get("artifact_id")
        def record(status, **details):
            if self._artifact_journal:
                self._artifact_journal.record(request, identity, status, **details)
        try:
            result = {}
            if self._sequence_processor is not None or self._processing_worker is not None:
                self._update(job_id, status="processing", process_percent=0)
                record("processing")
                if self._processing_worker is not None:
                    result = self._processing_worker(request, lambda value: self._update(job_id, process_percent=value))
                else:
                    result = self._sequence_processor(request)
                self._update(job_id, **result)
            record("completed", machine_after=machine_after)
            if self._artifact_finalizer is not None:
                try:
                    cleanup = self._artifact_finalizer(request, result)
                except Exception:
                    self._update(job_id, lossless_verified=False, source_his_retained=True, source_his_cleanup_pending=False)
                    raise
                self._update(job_id, **cleanup)
                if self._artifact_journal is not None:
                    try:
                        self._artifact_journal.record_retention(request, identity, cleanup)
                    except Exception as journal_error:
                        self._update(job_id, cleanup_warning=f"HIS cleanup finished; manifest cleanup status was not updated: {journal_error}")
            if self._point_recorder is not None:
                try:
                    self._point_recorder(request, machine_after)
                except Exception as exc:
                    self._update(job_id, recovery_warning=f"Measurement completed; camera return point was not saved: {exc}")
            self._finish(job_id, "completed")
        except Exception as exc:
            self._fail(request, provenance, job_id, exc)

    def _fail(self, request, provenance, job_id, exc):
        error = str(exc)
        try:
            if self._artifact_journal:
                self._artifact_journal.record(request, (provenance or {}).get("artifact_id"), "failed", error=error)
        except Exception as journal_error:
            error += f"; manifest write failed: {journal_error}"
        self._finish(job_id, "failed", error)

    def _update(self, job_id, **values: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(values)

    def _finish(self, job_id, status: str, error: str = "") -> None:
        with self._changed:
            self._jobs[job_id].update(status=status, error=error, completed_at=_utc_now())
            if self._acquisition_id == job_id:
                self._acquisition_id = None
            for identity in list(self._jobs):
                if len(self._jobs) <= 32:
                    break
                if identity != self._latest_id and self._jobs[identity]["status"] in {"completed", "failed"}:
                    del self._jobs[identity]
            self._changed.notify_all()

    @staticmethod
    def _build_request(
        phase: object,
        frames_per_his: object,
        output_root: object,
        run_name: object,
        sample_description: object = "",
        reuse_bruit: object = "latest",
    ) -> PhaseRequest:
        phase_name = str(phase).strip().upper()
        # Keep the early UI spelling accepted for clients not yet upgraded.
        if phase_name == "BREW":
            phase_name = "BRUIT"
        if phase_name not in PHASES:
            raise Vd2ProtocolError(f"Unsupported VD2 phase: {phase}")
        try:
            frames = int(frames_per_his)
        except (TypeError, ValueError) as exc:
            raise Vd2ProtocolError("HIS frames must be an integer") from exc
        if not 1 <= frames <= 100_000:
            raise Vd2ProtocolError("HIS frames must be between 1 and 100000")

        name = str(run_name).strip()
        if (not name or len(name) > 120 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or name in {".", ".."} or name.endswith((".", " "))
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", name)):
            raise Vd2ProtocolError("Run name must be a valid sample folder name (maximum 120 characters)")
        description = str(sample_description or "").strip()
        if len(description) > 4000:
            raise Vd2ProtocolError("Sample description must be at most 4000 characters")

        root = PureWindowsPath(str(output_root).strip() or DEFAULT_OUTPUT_ROOT)
        if not root.is_absolute() or any(part == ".." for part in root.parts):
            raise Vd2ProtocolError("Output folder must be an absolute Windows path")
        his_path = root / name / f"{PHASES[phase_name]['file_stem']}.his"
        return PhaseRequest(
            phase=phase_name,
            frames_per_his=frames,
            output_root=str(root),
            run_name=name,
            his_path=str(his_path),
            sample_description=description,
            reuse_bruit=str(reuse_bruit or "latest"),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
