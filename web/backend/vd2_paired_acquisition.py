"""VD2 paired measurement owns a single RemoteEx stream and its raw archive."""
from dataclasses import asdict, dataclass
import base64
import json
import math
from pathlib import Path
import threading
import time
from uuid import uuid4

import numpy as np

from vd2_measurement_protocol import Vd2MeasurementProtocol, _utc_now
from vd2_paired_analysis import DetectorROI, ERROR_CONFIRMATIONS, PairedAnalysis
from vd2_paired_storage import PairedRecording, load_dark_reference
from vd2_project_manifest import record_paired_project_run
from vd2_tango_optics import paired_capture_clock


MAX_PAIRS = 10_000
FRAME_TIMEOUT_S = 5
TRIGGER_SOURCES = {"internal": 0, "external_rising": 1, "external_falling": 2}


def target_error(value):
    if type(value) not in {int, float} or not math.isfinite(value) or not 0 < value <= 1000:
        raise ValueError("Target error must be above 0 and at most 1000 mOD")
    return float(value)


@dataclass(frozen=True)
class PairedRequest:
    output_root: str
    sample_name: str
    reuse_bruit: str
    mode: str
    first_map_with_electrons: bool
    pair_limit: int
    target_mod: float | None
    trigger_source: str
    roi: DetectorROI | None

    @classmethod
    def from_payload(cls, payload, allowed_root):
        mode = payload["mode"]
        if mode not in ("fixed", "precision"):
            raise ValueError("Choose fixed pairs or ROI precision")
        first = payload["first_map_with_electrons"]
        if type(first) is not bool:
            raise ValueError("Select whether the first frame has electrons")
        limit = payload["pair_limit"]
        if type(limit) is not int or not 1 <= limit <= MAX_PAIRS:
            raise ValueError(f"Pair limit must be an integer between 1 and {MAX_PAIRS}")
        source = payload["trigger_source"]
        if source not in tuple(TRIGGER_SOURCES):
            raise ValueError("Select a supported 5 Hz trigger source")
        if type(payload["output_root"]) is not str or type(payload["sample_name"]) is not str:
            raise ValueError("Select a project folder and sample name")
        root = allowed_root(payload["output_root"])
        run = Vd2MeasurementProtocol._build_request("ABSORPTION", 2 * limit, root, payload["sample_name"])
        folder = Path(run.output_root).resolve()
        if not folder.is_dir() or not (folder / run.run_name).resolve().is_relative_to(folder):
            raise ValueError("Sample path must be inside an existing project folder")
        noise = payload["reuse_bruit"]
        if noise not in ("latest", "none"):
            raise ValueError("Select a supported Noise Source")
        roi = DetectorROI.from_payload(payload["roi"]) if payload["roi"] is not None else None
        if mode == "precision" and roi is None:
            raise ValueError("Select a camera ROI before starting precision mode")
        threshold = target_error(payload["target_mod"]) if mode == "precision" else None
        return cls(str(folder), run.run_name, noise, mode, first, limit, threshold, source, roi)


def _validate_dark_settings(api, camera, dark):
    machine = api._machine_snapshot(camera)
    current = machine["streak_control"].get("values", {})
    old = (dark.artifact.get("machine_before") or {}).get("streak_control", {}).get("values", {})
    for name in ("time_range", "streak_mode", "gate_mode", "mcp_gain"):
        if old.get(name) in (None, "") or old[name] != current.get(name):
            raise ValueError(f"Bruit setting {name} differs from camera readback; record a new Bruit")
    if not old.get("acquire_exposure_time") or not api.equivalent(
        "acquire_exposure_time", old["acquire_exposure_time"], current.get("live_exposure_time")
    ):
        raise ValueError("Bruit exposure must match the camera Live exposure")
    for parameter in ("RecurFilter", "RecurFilter2"):
        if api._remoteex_readback(camera, f"CamParamGet(Live,{parameter})") != "0":
            raise ValueError("Turn off Live rolling average before paired acquisition")
    if str(current.get("streak_mode")).lower() != "operate":
        raise ValueError("Set the streak camera to Operate before paired acquisition")
    for shutter in ("streak_shutter", "spectrograph_shutter"):
        if str(current.get(shutter)).lower() != "open":
            raise ValueError(f"Verify {shutter} open before paired acquisition")
    return machine


def _raw_frame(payload, shape):
    width, height = payload["width"], payload["height"]
    size = payload["bytes_per_pixel"]
    if (width, height) != shape or size not in (1, 2, 4):
        raise ValueError("Camera data format or geometry differs from Bruit")
    raw = base64.b64decode(payload["pixels_b64"], validate=True)
    if len(raw) != width * height * size:
        raise ValueError("RemoteEx returned a truncated raw image")
    image = np.frombuffer(raw, dtype=f"<u{size}").reshape(height, width).T
    sequence, timestamp = payload.get("sequence"), payload.get("timestamp_ms")
    if type(sequence) is not int or not 0 <= sequence <= 2_147_483_647:
        sequence = -1
    if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
        timestamp = math.nan
    return image, sequence, timestamp


def _preview(image, sequence):
    low, high = np.percentile(image, (1, 99))
    display = np.clip((image.T.astype(np.float32) - low) * (255 / max(1, high - low)), 0, 255).astype("u1")
    return {"success": True, "frame_available": True, "stream_state": "acquiring",
            "width": image.shape[0], "height": image.shape[1], "frame_sequence": sequence,
            "pixels_b64": base64.b64encode(display.tobytes()).decode("ascii"),
            "received_at": _utc_now()}


class PairedAcquisition:
    def __init__(self, *, clock=paired_capture_clock, dark_reader=load_dark_reference, project_writer=record_paired_project_run):
        self._clock = clock
        self._dark_reader = dark_reader
        self._project_writer = project_writer
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = {"status": "idle", "active": False}
        self._preview = None

    def status(self):
        with self._lock:
            return self._state.copy()

    def preview(self):
        with self._lock:
            if not self._state["active"]:
                return None
            return self._preview or {"success": True, "frame_available": False,
                                     "stream_state": self._state["status"]}

    def _update(self, **fields):
        with self._lock:
            self._state.update(fields)

    def start(self, api, request):
        with self._lock:
            if self._state["active"]:
                raise ValueError("Paired acquisition already owns the camera")
            job = uuid4().hex
            self._stop = threading.Event()
            self._preview = None
            self._state = {
                "job_id": job, "status": "preparing", "active": True, "stage": "Checking Bruit and camera",
                "sample_name": request.sample_name, "mode": request.mode,
                "pair_limit": request.pair_limit, "first_map_with_electrons": request.first_map_with_electrons,
                "trigger_source": request.trigger_source,
                "target_mod": request.target_mod, "estimate_mod": None, "error_mod": None,
                "pairs_recorded": 0, "frames_recorded": 0, "roi_pairs": 0, "h5_path": None, "error": "",
            }
            self._thread = threading.Thread(target=self._run, args=(api, request, job),
                                            name="vd2-paired-acquisition", daemon=True)
            try:
                self._thread.start()
            except BaseException:
                self._state.update(status="failed", active=False)
                raise
            return self._state.copy()

    def wait(self, timeout):
        if self._thread:
            self._thread.join(timeout)

    def stop(self, job):
        with self._lock:
            self._assert_job(job)
            self._stop.set()
            return self._state.copy()

    def set_target(self, job, value):
        with self._lock:
            self._assert_job(job)
            if self._state["mode"] != "precision" or self._stop.is_set():
                raise ValueError("An active precision measurement is required")
            self._state["target_mod"] = target_error(value)
            return self._state.copy()

    def _assert_job(self, job):
        if self._state.get("job_id") != job or not self._state["active"]:
            raise ValueError("Paired measurement is no longer active")

    def _run(self, api, request, job):
        recording = analysis = None
        stop_reason = "operator_stop"
        errors = []
        try:
            root = Path(request.output_root)
            dark = self._dark_reader(root, request.sample_name, request.reuse_bruit, request.roi,
                                     request.mode == "precision", self._stop)
            if dark is None or self._stop.is_set():
                return
            camera = api._proxy()
            camera.set_timeout_millis(4000)
            api._assert_preparation_idle(camera, ignore_paired=True)
            for command in ("StartPairedLive", "ReadPairedLiveFrame", "StopPairedLive"):
                try:
                    camera.command_query(command)
                except Exception as exc:
                    raise RuntimeError(f"Paired camera command unavailable before warm-up: {command}") from exc
            machine = _validate_dark_settings(api, camera, dark)
            folder = (root / request.sample_name).resolve()
            if not folder.is_relative_to(root):
                raise ValueError("Sample path is outside the project folder")
            folder.mkdir(exist_ok=True)
            file = folder / f"PAIRED-{job}.h5"
            analysis = PairedAnalysis(dark.image, request.roi, dark.roi_blocks)
            recording = PairedRecording(file, dark, asdict(request), machine)
            self._update(h5_path=str(file), bruit_artifact_id=dark.identity, stage="Warming lamp at 10 Hz")
            attempted = False

            def arm():
                nonlocal attempted
                attempted = True
                camera.command_inout("StartPairedLive")

            try:
                if not self._stop.is_set():
                    with self._clock(api, camera, TRIGGER_SOURCES[request.trigger_source], self._stop, arm) as running:
                        if running:
                            self._update(status="acquiring", stage="Recording 10 Hz pairs")
                            stop_reason = self._read_pairs(camera, request, recording, analysis)
            except Exception as exc:
                errors.append(str(exc))
            finally:
                # The clock context has paused DG645 before returning the camera.
                if attempted:
                    try:
                        camera.command_inout("StopPairedLive")
                    except Exception as exc:
                        errors.append(f"Camera stop unverified: {exc}")
        except Exception as exc:
            errors.append(str(exc))
        finally:
            final = "failed" if errors else "stopped" if stop_reason == "operator_stop" else "completed"
            result = {"status": final, "stop_reason": "fault" if errors else stop_reason,
                      "completed_at": _utc_now(), "error": " | ".join(errors)}
            if recording:
                self._update(status="saving", stage="Finalizing paired H5")
                try:
                    summary = {**self.status(), **result, "active": False}
                    recording.finish(analysis, summary)
                except Exception as exc:
                    result.update(status="failed", stop_reason="fault",
                                  error=" | ".join(filter(None, (result["error"], f"H5 finalization failed: {exc}"))))
                else:
                    if summary["frames_recorded"]:
                        try:
                            result["manifest_path"] = self._project_writer(root, request.sample_name, file, summary)
                        except (OSError, ValueError, KeyError) as exc:
                            result["manifest_warning"] = f"Paired H5 saved; project history unavailable: {exc}"
            self._update(**result, active=False, stage="")

    def _read_pairs(self, camera, request, recording, analysis):
        previous_sequence = None
        previous_time = None
        first_image = None
        count = 0
        next_preview = 0
        confirmations = 0
        target = request.target_mod
        deadline = time.monotonic() + FRAME_TIMEOUT_S
        while not self._stop.is_set():
            sequence_request = -1 if previous_sequence is None else previous_sequence + 1
            data = camera.command_inout("ReadPairedLiveFrame", sequence_request)
            if not data:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Timed out waiting for the next 10 Hz camera frame")
                self._stop.wait(0.025)
                continue
            image, sequence, timestamp = _raw_frame(json.loads(data), analysis.background.shape)
            is_contiguous = sequence >= 0 and math.isfinite(timestamp) and (
                previous_sequence is None
                or (sequence == previous_sequence + 1 and abs(timestamp - previous_time - 100.0) <= 5.0)
            )
            is_first = recording.frame_count % 2 == 0
            role = int(request.first_map_with_electrons == is_first) if is_contiguous else -1
            recording.append(image, sequence, timestamp, role)
            self._update(frames_recorded=recording.frame_count)
            if not is_contiguous:
                raise ValueError("10 Hz frame sequence interrupted; data retained, confirm the first frame again")
            previous_sequence, previous_time = sequence, timestamp
            current = time.monotonic()
            deadline = current + FRAME_TIMEOUT_S
            if current >= next_preview:
                preview = _preview(image, sequence)
                with self._lock:
                    self._preview = preview
                next_preview = current + 0.4

            if is_first:
                first_image = image
                continue
            absorption, base = (first_image, image) if request.first_map_with_electrons else (image, first_image)
            block_done = analysis.add(absorption, base)
            count += 1
            self._update(pairs_recorded=count, estimate_mod=analysis.estimate_mod,
                         error_mod=analysis.error_mod, roi_pairs=analysis.roi_pair_count)
            if request.mode == "precision":
                current_target = self.status()["target_mod"]
                if target != current_target or analysis.error_mod is None:
                    target, confirmations = current_target, 0
                if block_done:
                    confirmations = confirmations + 1 if analysis.error_mod is not None and analysis.error_mod <= target else 0
                    if confirmations >= ERROR_CONFIRMATIONS:
                        return "precision_reached"
            if count >= request.pair_limit:
                return "pair_limit" if request.mode == "precision" else "pair_count_reached"
        return "operator_stop"
