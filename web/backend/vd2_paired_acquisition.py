"""VD2 paired measurement owns a single RemoteEx stream and its raw archive."""
from dataclasses import asdict, dataclass, replace
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
from vd2_paired_kinetics import KineticAnalysis, METHODS, SpectralBand
from vd2_paired_sequence import frames, native_capture, sequence_header
from vd2_paired_storage import BruitRequired, PairedRecording, load_dark_reference
from vd2_spectral_calibration import camera_geometry, verified_wavelengths
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
    band: SpectralBand | None = None
    method: str = "mean_pair_od"
    sam_surface_percent: float = 3.0
    native_sequence: bool = False

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
        band = SpectralBand.from_payload(payload["band"]) if payload.get("band") is not None else None
        method = payload.get("method", "mean_pair_od")
        if method not in METHODS or (band is None and method != "mean_pair_od"):
            raise ValueError("Choose an OD method and a calibrated spectral band")
        surface = payload.get("sam_surface_percent", 3.0)
        if type(surface) not in (int, float) or not math.isfinite(surface) or not 0 < surface <= 100:
            raise ValueError("SAM surface threshold must be above 0 and at most 100%")
        if mode == "precision" and roi is None and band is None:
            raise ValueError("Select a calibrated spectral band or a camera ROI")
        threshold = target_error(payload["target_mod"]) if mode == "precision" else None
        return cls(str(folder), run.run_name, noise, mode, first, limit, threshold, source, roi,
                   band, method, float(surface), mode == "fixed")


def _dark_matches(api, current, artifact, native):
    old = (artifact.get("machine_before") or {}).get("streak_control", {}).get("values", {})
    for name in ("time_range", "streak_mode", "gate_mode", "mcp_gain"):
        if old.get(name) in (None, "") or old[name] != current.get(name):
            return False
    exposure = "acquire_exposure_time" if native else "live_exposure_time"
    return bool(old.get("acquire_exposure_time") and api.equivalent(
        "acquire_exposure_time", old["acquire_exposure_time"], current.get(exposure)
    ))


def _validate_illuminated_settings(api, camera, current, native):
    if not native:
        for parameter in ("RecurFilter", "RecurFilter2"):
            if api._remoteex_readback(camera, f"CamParamGet(Live,{parameter})") != "0":
                raise ValueError("Turn off Live rolling average before paired acquisition")
    if str(current.get("streak_mode")).lower() != "operate":
        raise ValueError("Set the streak camera to Operate before paired acquisition")
    for shutter in ("streak_shutter", "spectrograph_shutter"):
        if str(current.get(shutter)).lower() != "open":
            raise ValueError(f"Verify {shutter} open before paired acquisition")


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
                "trigger_source": request.trigger_source, "method": request.method,
                "band": asdict(request.band) if request.band else None,
                "capture": "sequence" if request.native_sequence else "stream", "time_scale": "",
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
        recording = analysis = kinetics = None
        bruit_required = False
        stop_reason = "operator_stop"
        errors = []
        try:
            root = Path(request.output_root)
            camera = api._proxy()
            camera.set_timeout_millis(4000)
            api._assert_preparation_idle(camera, ignore_paired=True)
            machine = api._machine_snapshot(camera)
            current = machine["streak_control"].get("values", {})
            if request.band and not request.native_sequence and not api.equivalent(
                "acquire_exposure_time", current.get("acquire_exposure_time"), current.get("live_exposure_time")
            ):
                raise ValueError("Set Live exposure to the Acquire exposure before precision Measurement")
            def compatible(artifact):
                return _dark_matches(api, current, artifact, request.native_sequence)
            dark_options = {"compatible": compatible} if self._dark_reader is load_dark_reference else {}
            dark = self._dark_reader(root, request.sample_name, request.reuse_bruit,
                                     None if request.band else request.roi,
                                     request.mode == "precision" or bool(request.band), self._stop,
                                     **dark_options)
            if dark is None or self._stop.is_set():
                return
            if not compatible(dark.artifact):
                raise BruitRequired("Record Bruit with the selected acquisition exposure and camera settings")
            _validate_illuminated_settings(api, camera, current, request.native_sequence)
            commands = ("StartSequence", "SaveCurrentSequence", "StopSequence") if request.native_sequence else (
                "StartPairedLive", "ReadPairedLiveFrame", "StopPairedLive")
            for command in commands:
                try:
                    camera.command_query(command)
                except Exception as exc:
                    raise RuntimeError(f"Paired camera command unavailable before warm-up: {command}") from exc
            if request.band:
                axis, calibration_id = verified_wavelengths(dark.description, machine, api.KYMERA_DEVICE)
                dark = replace(dark, wavelengths=np.asarray(axis))
                machine["spectral_calibration_id"] = calibration_id
                kinetics = KineticAnalysis(dark.image, dark.wavelengths, dark.timedelays, request.band,
                                           request.method, request.sam_surface_percent, dark.roi_blocks)
            folder = (root / request.sample_name).resolve()
            if not folder.is_relative_to(root):
                raise ValueError("Sample path is outside the project folder")
            folder.mkdir(exist_ok=True)
            file = folder / f"PAIRED-{job}.h5"
            analysis = PairedAnalysis(dark.image, None if request.band else request.roi, dark.roi_blocks)
            recording = PairedRecording(file, dark, asdict(request), machine)
            self._update(h5_path=str(file), bruit_artifact_id=dark.identity, time_scale=dark.time_scale,
                         stage="Warming lamp at 10 Hz")
            if request.native_sequence:
                source = file.with_suffix(".his")
                self._update(his_path=str(source))
                completed = native_capture(api, camera, self._clock, TRIGGER_SOURCES[request.trigger_source],
                                           self._stop, 2 * request.pair_limit, source, self._update)
                if completed:
                    self._archive_sequence(source, request, dark, recording, analysis, kinetics)
                    stop_reason = "pair_count_reached"
                return
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
                            stop_reason = self._read_pairs(camera, request, recording, analysis, kinetics)
            except Exception as exc:
                errors.append(str(exc))
            finally:
                # The clock context has paused DG645 before returning the camera.
                if attempted:
                    try:
                        camera.command_inout("StopPairedLive")
                    except Exception as exc:
                        errors.append(f"Camera stop unverified: {exc}")
        except BruitRequired as exc:
            bruit_required = True
            errors.append(str(exc))
        except Exception as exc:
            errors.append(str(exc))
        finally:
            if kinetics is not None and recording is not None:
                try:
                    kinetics.calculate()
                    self._publish_kinetics(kinetics)
                except Exception as exc:
                    errors.append(f"Kinetics calculation failed: {exc}")
            final = "bruit_required" if bruit_required else "failed" if errors else "stopped" if stop_reason == "operator_stop" else "completed"
            result = {"status": final, "stop_reason": "fault" if errors else stop_reason,
                      "completed_at": _utc_now(), "error": " | ".join(errors)}
            if recording:
                self._update(status="saving", stage="Finalizing paired H5")
                try:
                    summary = {**self.status(), **result, "active": False}
                    recording.finish(analysis, summary, kinetics)
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

    def _publish_kinetics(self, kinetics):
        preview = None
        if kinetics.values is not None:
            index = np.linspace(0, len(kinetics.time) - 1, min(256, len(kinetics.time)), dtype=int)
            preview = {"time": kinetics.time[index].tolist(), "od_mod": kinetics.values[index].tolist()}
        self._update(estimate_mod=kinetics.estimate_mod, error_mod=kinetics.error_mod,
                     roi_pairs=kinetics.pairs_used, kinetics=preview)

    def _archive_sequence(self, path, request, dark, recording, analysis, kinetics):
        expected = 2 * request.pair_limit
        count, description = sequence_header(path)
        if count != expected:
            raise ValueError(f"HIS contains {count} frames, expected {expected}; raw HIS retained")
        if dark.description and camera_geometry(description) != camera_geometry(dark.description):
            raise ValueError("Sequence detector crop differs from Bruit; raw HIS retained")
        previous = first_image = None
        for image, sequence, timestamp in frames(path, count, dark.image.shape):
            valid = math.isfinite(timestamp) and (previous is None or abs(timestamp - previous - 100) <= 5)
            first = sequence % 2 == 0
            role = int(request.first_map_with_electrons == first) if valid else -1
            recording.append(image, sequence, timestamp, role)
            self._update(frames_recorded=recording.frame_count)
            if not valid:
                raise ValueError("10 Hz HIS sequence interrupted; raw HIS retained")
            previous = timestamp
            if first:
                first_image = image
            else:
                pair = (first_image, image) if request.first_map_with_electrons else (image, first_image)
                analysis.add(*pair)
                if kinetics is not None:
                    kinetics.add(*pair)
                self._update(pairs_recorded=(sequence + 1) // 2)

    def _read_pairs(self, camera, request, recording, analysis, kinetics=None):
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
            estimate = analysis
            used = analysis.roi_pair_count
            if kinetics is not None:
                block_done = kinetics.add(absorption, base)
                if block_done:
                    kinetics.calculate()
                    self._publish_kinetics(kinetics)
                estimate = kinetics
                used = kinetics.pairs_used
            count += 1
            self._update(pairs_recorded=count, estimate_mod=estimate.estimate_mod,
                         error_mod=estimate.error_mod, roi_pairs=used)
            if request.mode == "precision":
                current_target = self.status()["target_mod"]
                if target != current_target or estimate.error_mod is None:
                    target, confirmations = current_target, 0
                if block_done:
                    confirmations = confirmations + 1 if estimate.error_mod is not None and estimate.error_mod <= target else 0
                    if confirmations >= ERROR_CONFIRMATIONS:
                        return "precision_reached"
            if count >= request.pair_limit:
                return "pair_limit" if request.mode == "precision" else "pair_count_reached"
        return "operator_stop"
