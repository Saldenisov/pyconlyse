import ast
import math
import os
import random
import json
import hashlib
import shutil
import threading
import time
import zlib
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from flask import Blueprint, Response, jsonify, request

from mutation_auth import install_mutation_auth
from hardware_authorization import authorization_required, require_http_hardware
from experiment_readiness import EXPERIMENT_MUTATION_LOCK, recover_device, start_managed_server
from experiment_lifecycle import ExperimentLifecycle
from v0_experiment_shutdown import (
    CAMERA as V0_SHUTDOWN_CAMERA, OUTPUT_PLAN as V0_SHUTDOWN_OUTPUT_PLAN,
    STAGE as V0_SHUTDOWN_STAGE, STAGE_BACKEND as V0_SHUTDOWN_STAGE_BACKEND,
    STAGE_AXIS as V0_SHUTDOWN_STAGE_AXIS, STAGE_TOLERANCE_MM as V0_SHUTDOWN_STAGE_TOLERANCE,
    STAGE_TIMEOUT_S as V0_SHUTDOWN_STAGE_TIMEOUT, execute_shutdown as execute_v0_shutdown,
)
from pump_probe_v0_config import (
    ACCELERATOR_HZ,
    BACKGROUND_RANDOM_COUNTS,
    DARK_DRIFT_COUNTS,
    DEFAULT_DATA_ROOT,
    DEFAULT_DG645_RECALL_CONFIG,
    DEFAULT_HARDWARE_CONFIG,
    LAMP_DRIFT_FRACTION,
    MM_PER_PS,
    OD_COMMON_OSCILLATION,
    OD_NOISE_SCALE,
    PIXELS,
    READ_NOISE_COUNTS,
    REFERENCE_RANDOM_COUNTS,
    REQUIRED_NETIO_OUTPUTS as REQUIRED_NETIO_OUTPUTS,
    SIGNAL_RANDOM_COUNTS,
    SPECTROMETER_BURST,
    SPECTROMETER_HZ,
    STAGE_MAX_MM,
    STAGE_MIN_MM,
    STAGE_SPEED_MM_PER_SEC,
    V0_CAMERA_DEVICES,
    V0_LASER_POINTING_DEVICES,
    V0_PDU_DEVICES,
    V0_STANDA_DEVICES,
    V0_STARTER_DEVICE,
    V0_STANDA_STARTER_DEVICE,
    V0_PREPARATION_NETIO_OUTPUTS,
    V0_PREPARATION_PDU_DEVICES,
    V0_PREPARATION_READ_ONLY,
)
from pump_probe_v0_dataset import (
    derive_dataset, export_dat, load_payload, treat_dataset, treat_derived_dataset,
)
from pump_probe_v0_delays import preview_kinetics, resolve_scan_settings
from pump_probe_v0_storage import RAW_GROUPS, V0EmulatorRunWriter, V0TangoRunWriter
from pump_probe_v0_scanplan import build_scan_plan
from pump_probe_v0_processing import TRANCON_GROUPS, TRANCON_FLOAT_LAYOUT as TRANCON_FLOAT_LAYOUT
from pump_probe_v0_tango import AcquisitionCancelled, RejectedCycle as RejectedCycle, TangoPacketError, TangoRawAdapter
from pump_probe_v0_tango_plan import build_tango_plan, load_profile
from pump_probe_v0_detector_filters import apply_detector_filters

from treatment_network_path import (
    is_smb_path,
    normalize_smb_path,
    smb_is_within,
    smb_join,
    smb_listdir,
    smb_parent,
    smb_to_unc,
    split_smb_path,
)


pump_probe_v0_api = Blueprint("pump_probe_v0_api", __name__, url_prefix="/api/pump-probe-v0")
install_mutation_auth(pump_probe_v0_api)


class TangoProfileNotCommissioned(ValueError):
    pass


def _clamp(value, low, high):
    return max(low, min(high, value))


def _clean_control_mode(value):
    mode = str(value or "emulator").strip().lower()
    return mode if mode in {"emulator", "tango"} else "emulator"


def _parse_tango_dict(value):
    import ast

    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = ast.literal_eval(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _tango_proxy(device_name, timeout_ms=3000):
    import tango

    proxy = tango.DeviceProxy(str(device_name))
    proxy.set_timeout_millis(int(timeout_ms))
    return proxy


def _numeric_list(value):
    try:
        return [float(part.strip()) for part in str(value).split(",")]
    except ValueError:
        return None


def _values_match(expected, actual, tolerance=1e-9):
    expected_numbers = _numeric_list(expected)
    actual_numbers = _numeric_list(actual)
    if expected_numbers is not None and actual_numbers is not None:
        if len(expected_numbers) != len(actual_numbers):
            return False
        return all(abs(left - right) <= tolerance for left, right in zip(expected_numbers, actual_numbers))
    return str(expected).strip() == str(actual).strip()


def _axis_is_ready(state, position):
    """Tango get_status_axis returns numeric DevState, not an error string."""
    if not math.isfinite(position):
        return False
    text = str(state).strip().upper()
    if "DEVSTATE." in text:
        text = text.rsplit(".", 1)[-1]
    # DevState.ON=0, MOVING=6, RUNNING=10. In particular OFF=1 and FAULT=8
    # must not pass merely because their string lacks the word 'FAULT'.
    return text in {"0", "6", "10", "ON", "MOVING", "RUNNING"}


def _load_dg645_recall_config(config_path):
    path = Path(str(config_path or DEFAULT_DG645_RECALL_CONFIG)).expanduser()
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_ok(label, detail=None, **extra):
    return {"label": label, "ok": True, "detail": detail or "OK", **extra}


def _json_fail(label, detail, **extra):
    return {"label": label, "ok": False, "detail": str(detail), **extra}


def _server_name_for_device(device_name):
    import tango

    db = tango.Database()
    info = db.get_device_info(str(device_name))
    server_name = getattr(info, "ds_full_name", None) or getattr(info, "server", None)
    if not server_name:
        raise RuntimeError(f"Could not resolve server for {device_name}")
    return str(server_name)


def _starter_devices():
    import tango

    db = tango.Database()
    return [str(name) for name in db.get_device_exported("*") if str(name).startswith("tango/admin/")]


def _starter_for_server(server_name, preferred_starter=None):
    if preferred_starter:
        starter = _tango_proxy(preferred_starter, timeout_ms=5000)
        running = set(starter.command_inout("DevGetRunningServers", False))
        stopped = set(starter.command_inout("DevGetStopServers", False))
        return preferred_starter, starter, running, stopped

    for starter_name in _starter_devices():
        try:
            starter = _tango_proxy(starter_name, timeout_ms=5000)
            running = set(starter.command_inout("DevGetRunningServers", False))
            stopped = set(starter.command_inout("DevGetStopServers", False))
            if server_name in running or server_name in stopped:
                return starter_name, starter, running, stopped
        except Exception:
            continue
    raise RuntimeError(f"No Starter manages server {server_name}")


def _restart_server_for_device(device_name, preferred_starter=None):
    server_name = _server_name_for_device(device_name)
    if server_name.lower().startswith("ds_standa_motor/"):
        raise RuntimeError("V0 preparation never starts or restarts STANDA servers; check Elysium2")
    starter_name, starter, running, _stopped = _starter_for_server(
        server_name,
        preferred_starter=preferred_starter,
    )

    def wait_exported():
        deadline = time.monotonic() + 25.0
        last_error = None
        while time.monotonic() < deadline:
            try:
                proxy = _tango_proxy(device_name, timeout_ms=3000)
                proxy.state()
                return proxy
            except Exception as exc:
                last_error = exc
                time.sleep(0.5)
        raise RuntimeError(f"{device_name} did not become available: {last_error}")

    start_managed_server(starter, server_name, wait_exported, restart_existing=False)
    return {"server": server_name, "starter": starter_name}


def _linspace(start, stop, count):
    if count <= 1:
        return [float(start)]
    step = (stop - start) / (count - 1)
    return [float(start + index * step) for index in range(count)]


def _gaussian(x_value, center, width):
    scaled = (x_value - center) / width
    return math.exp(-0.5 * scaled * scaled)


def _data_root():
    return os.environ.get("PYCONLYSE_PUMP_PROBE_DATA_ROOT", DEFAULT_DATA_ROOT)


def _normalize_data_path(path):
    raw_path = str(path or "").strip() or _data_root()
    if is_smb_path(raw_path):
        return normalize_smb_path(raw_path)
    return os.path.abspath(os.path.expanduser(raw_path))


def _is_data_path_allowed(path):
    root = _normalize_data_path(_data_root())
    normalized = _normalize_data_path(path)
    if is_smb_path(root) or is_smb_path(normalized):
        return is_smb_path(root) and is_smb_path(normalized) and smb_is_within(normalized, root)
    try:
        return os.path.commonpath([normalized, root]) == root
    except ValueError:
        return False


def _local_listdir(folder):
    entries = []
    with os.scandir(folder) as iterator:
        for entry in iterator:
            is_file = entry.is_file()
            entries.append({
                "name": entry.name,
                "path": entry.path,
                "is_dir": entry.is_dir(),
                "is_file": is_file,
                "size_bytes": int(entry.stat().st_size) if is_file else 0,
            })
    return entries


def _list_data_path(path):
    normalized = _normalize_data_path(path)
    if not _is_data_path_allowed(normalized):
        raise ValueError("Data path is outside pump-probe data root")
    if is_smb_path(normalized):
        return smb_listdir(normalized)
    return _local_listdir(normalized)


def _parent_data_path(path):
    root = _normalize_data_path(_data_root())
    normalized = _normalize_data_path(path)
    if normalized == root:
        return root
    if is_smb_path(normalized):
        parent = smb_parent(normalized)
        return parent if _is_data_path_allowed(parent) else root
    parent = os.path.dirname(normalized)
    return parent if _is_data_path_allowed(parent) else root


def _safe_folder_name(name):
    text = str(name or "").strip()
    cleaned = "".join(char if char.isalnum() or char in " ._-+()" else "_" for char in text)
    cleaned = cleaned.strip(" .")
    if not cleaned:
        raise ValueError("Folder name is empty")
    return cleaned[:120]


def _mkdir_data_path(parent, name):
    parent_path = _normalize_data_path(parent)
    if not _is_data_path_allowed(parent_path):
        raise ValueError("Parent path is outside pump-probe data root")
    folder_name = _safe_folder_name(name)
    if is_smb_path(parent_path):
        import smbclient

        server, _share, _remote_path = split_smb_path(parent_path)
        from treatment_network_path import _register_session

        _register_session(server)
        next_path = smb_join(parent_path, folder_name)
        smbclient.makedirs(smb_to_unc(next_path), exist_ok=True)
        return next_path
    next_path = os.path.join(parent_path, folder_name)
    Path(next_path).mkdir(parents=True, exist_ok=True)
    return next_path


def _read_data_file(path):
    normalized = _normalize_data_path(path)
    if not _is_data_path_allowed(normalized):
        raise ValueError("Data file is outside pump-probe data root")
    if is_smb_path(normalized):
        import smbclient

        server, _share, _remote_path = split_smb_path(normalized)
        from treatment_network_path import _register_session

        _register_session(server)
        with smbclient.open_file(smb_to_unc(normalized), mode="rb") as handle:
            return normalized, handle.read()
    with open(normalized, "rb") as handle:
        return normalized, handle.read()


def _publish_data_file(directory, source_path):
    """Copy a staged run artifact to the selected local or SMB data folder."""
    target_directory = _normalize_data_path(directory)
    if not _is_data_path_allowed(target_directory):
        raise ValueError("Run output path is outside pump-probe data root")

    source = Path(source_path)
    target_name = source.name
    if is_smb_path(target_directory):
        import smbclient

        server, _share, _remote_path = split_smb_path(target_directory)
        from treatment_network_path import _register_session

        _register_session(server)
        target = smb_join(target_directory, target_name)
        with open(source, "rb") as input_handle:
            with smbclient.open_file(smb_to_unc(target), mode="wb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle)
        return target

    Path(target_directory).mkdir(parents=True, exist_ok=True)
    target = Path(target_directory) / target_name
    shutil.copy2(source, target)
    return str(target)


def _data_file_name(path):
    if is_smb_path(path):
        return unquote(path.rstrip("/").split("/")[-1])
    return Path(path).name


def _data_file_suffix(path):
    return Path(_data_file_name(path)).suffix.lower()


class PumpProbeV0Controller:
    def __init__(self):
        self._lock = threading.RLock()
        self._hardware_config = dict(DEFAULT_HARDWARE_CONFIG)
        self._sample_position_mm = 0.0
        self._sample_set_position_mm = 0.0
        self._sample_last_motion_update = time.monotonic()
        self._counter_last_value = None
        self._counter_last_time = None
        self._counter_rate_hz = 0.0
        self._andor_order = None
        self._andor_error = ""
        self._run_writer = None
        self._run_status = "idle"
        self._run_error = ""
        self._run_artifacts = {}
        self._run_output_dir = ""
        self._run_sample_name = ""
        self._run_thread = None
        self._scan_plan = None
        self._resume_source = None
        self._tango_run_plan = None
        self._tango_stop_event = None
        self._tango_done_event = threading.Event()
        self._tango_done_event.set()
        self._tango_stop_status = "stopped"
        self._tango_order_id = None
        self._tango_rejected_cycles = 0
        self._tango_cleanup_errors = []
        self._tango_camera_fingerprint = None
        self._tango_reset_requested = False
        self._run_raw_groups = tuple(RAW_GROUPS)
        self._settings = {
            "point_count": 100,
            "scan_start_ps": -25.0,
            "delay_step_ps": 1.0,
            "scan_span_ps": 99.0,
            "pulses_per_point": 10,
            "real_zero_ps": 465.0,
            "delay_points_ps": None,
        }
        self._wavelengths = _linspace(253.2375, 826.3287, PIXELS)
        self._rng = random.Random()
        self._reset_locked()

    def _control_mode_locked(self):
        return _clean_control_mode(self._hardware_config.get("control_mode"))

    def _configure_hardware_locked(self, payload):
        raw_config = payload.get("hardware_config") or {}
        if "control_mode" in payload:
            raw_config = {**raw_config, "control_mode": payload.get("control_mode")}
        if raw_config:
            next_config = {**self._hardware_config}
            for key, value in raw_config.items():
                if key not in DEFAULT_HARDWARE_CONFIG:
                    continue
                if key in ("delay_line_axis", "sample_stage_axis"):
                    next_config[key] = int(value)
                elif key == "control_mode":
                    next_config[key] = _clean_control_mode(value)
                else:
                    next_config[key] = str(value)
            self._hardware_config = next_config

    def _reset_locked(self):
        self._running = False
        self._real_time = False
        self._andor_order = None
        self._faraday_closed = True
        self._crystal_position = 0
        self._current_index = 0
        self._pulses_at_point = 0
        self._total_pulses = 0
        self._spectrometer_frames = 0
        now = time.monotonic()
        self._last_pulse_update = now
        self._last_motion_update = now
        self._delays = self._make_delays_locked()
        self._position_mm = self._delay_to_mm(self._delays[0])
        self._set_position_mm = self._position_mm
        self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
        if self._control_mode_locked() == "tango":
            self._live_od = [None for _ in self._wavelengths]
            self._last_spectra = {
                key: [None for _ in self._wavelengths]
                for key in ("reference", "signal", "background")
            }
            self._last_spectra["background_available"] = False
        else:
            self._live_od = self._make_od_row_locked(0, include_signal=False)
            self._last_spectra = self._make_spectra_locked(0, False)

    def _make_delays_locked(self):
        custom_delays = self._settings.get("delay_points_ps")
        if custom_delays:
            return [float(value) for value in custom_delays]
        start = float(self._settings["scan_start_ps"])
        step = float(self._settings["delay_step_ps"])
        count = int(self._settings["point_count"])
        return [float(start + index * step) for index in range(count)]

    def _delay_to_mm(self, delay_ps):
        real_zero_ps = float(self._settings["real_zero_ps"])
        return _clamp(-(delay_ps + real_zero_ps) * MM_PER_PS, STAGE_MIN_MM, STAGE_MAX_MM)

    def _make_od_row_locked(self, index, include_signal=True, signal_progress=1.0):
        delay = self._delays[index]
        shot_phase = self._total_pulses * 1.37
        phase = index * 0.31 + shot_phase
        drift = (
            0.00045 * math.sin(self._total_pulses / 17.0 + index / 11.0)
            + OD_COMMON_OSCILLATION * math.sin(shot_phase)
            + 0.00035 * math.sin(shot_phase * 0.43 + index * 0.17)
        )
        signal_progress = _clamp(signal_progress, 0.0, 1.0)
        row = []
        for pixel, wavelength in enumerate(self._wavelengths):
            band_a = _gaussian(wavelength, 445, 42)
            band_b = _gaussian(wavelength, 650, 68)
            kinetics = preview_kinetics(delay)
            ripple = 0.012 * math.sin(pixel / 13 + index / 7)
            signal = kinetics * band_a - 0.07 * band_b + ripple
            signal_factor = signal_progress if include_signal and not self._faraday_closed else 0.0
            random_od = self._rng.uniform(-0.00045, 0.00045)
            od_noise = OD_NOISE_SCALE * (
                0.55 * math.sin(pixel * 0.37 + phase * 1.7)
                + 0.30 * math.sin(pixel * 1.91 + phase * 0.91)
                + 0.15 * math.cos(pixel * 0.11 + shot_phase * 2.3)
            )
            row.append(round(signal_factor * signal + drift + od_noise + random_od, 5))
        return row

    def _make_spectra_locked(self, index, electron_on):
        phase = index * 0.31 + self._total_pulses * 0.73
        electron_scale = 0.92 if electron_on else 1.0
        lamp_drift = 1.0 + LAMP_DRIFT_FRACTION * (
            0.6 * math.sin(self._total_pulses / 19.0)
            + 0.4 * math.sin(self._total_pulses * 1.11)
        )
        dark_drift = (
            DARK_DRIFT_COUNTS * math.sin(self._total_pulses / 23.0)
            + 0.7 * math.sin(self._total_pulses * 1.43)
            + 0.3 * math.sin(self._total_pulses * 2.17)
        )
        signal = []
        reference = []
        background = []
        for pixel, wavelength in enumerate(self._wavelengths):
            pixel_dark = 1.4 * math.sin(pixel / 41.0 + phase * 0.19)
            read_signal = READ_NOISE_COUNTS * math.sin(pixel * 0.73 + phase * 2.1)
            read_reference = READ_NOISE_COUNTS * math.cos(pixel * 0.67 + phase * 1.8)
            read_background = 1.8 * math.sin(pixel * 0.91 + phase * 2.7)
            signal_random = self._rng.randint(-SIGNAL_RANDOM_COUNTS, SIGNAL_RANDOM_COUNTS)
            reference_random = self._rng.randint(-REFERENCE_RANDOM_COUNTS, REFERENCE_RANDOM_COUNTS)
            background_random = self._rng.randint(-BACKGROUND_RANDOM_COUNTS, BACKGROUND_RANDOM_COUNTS)

            lamp_signal = (22000 * _gaussian(wavelength, 525, 230) + 4200) * lamp_drift
            absorbance_depth = 0.11 if electron_on else 0.0
            absorbance = 1 - absorbance_depth * _gaussian(wavelength, 458 + 6 * math.sin(phase), 38)
            signal.append(round(lamp_signal * absorbance * electron_scale + read_signal + signal_random))

            lamp_reference = (21000 * _gaussian(wavelength, 535, 250) + 4600) * lamp_drift
            reference.append(round(lamp_reference + read_reference + reference_random))

            bg = 520 + dark_drift + pixel_dark + 2.5 * math.sin(pixel / 17 + phase) + read_background + background_random
            background.append(round(bg))
        return {
            "signal": signal,
            "reference": reference,
            "background": background,
        }

    def _sync_locked(self):
        if self._control_mode_locked() == "tango":
            if self._tango_stop_event is not None:
                # Full acquisition is owned by the authorized worker.
                return
            # Passive idle reads must not begin an order.  Only an already
            # authorized run/realtime operation may advance Tango acquisition.
            if self._running or self._real_time:
                self._sync_andor_spectra_locked()
            return

        now = time.monotonic()
        motion_elapsed = max(0.0, now - self._last_motion_update)
        self._last_motion_update = now
        distance = self._set_position_mm - self._position_mm
        max_step = STAGE_SPEED_MM_PER_SEC * motion_elapsed
        if abs(distance) <= max_step:
            self._position_mm = self._set_position_mm
        elif distance > 0:
            self._position_mm += max_step
        else:
            self._position_mm -= max_step

        elapsed = now - self._last_pulse_update
        pulse_count = int(elapsed * ACCELERATOR_HZ)
        if pulse_count <= 0:
            return
        self._last_pulse_update += pulse_count / ACCELERATOR_HZ
        for _ in range(pulse_count):
            self._apply_pulse_locked()

    def _decode_andor_order_locked(self, payload, width):
        raw = zlib.decompress(ast.literal_eval(str(payload)))
        data = np.frombuffer(raw, dtype=np.float32)
        if width <= 0 or data.size < width * 3 or data.size % width:
            raise ValueError(f"Invalid Andor order shape: {data.size} values, width={width}")

        rows = data.reshape(-1, width)
        wavelengths = rows[0]
        payload_rows = rows[1:]
        track_count = 2
        if payload_rows.shape[0] % track_count:
            raise ValueError("Andor order contains an incomplete signal/reference pair")
        frame_count = payload_rows.shape[0] // track_count
        if frame_count < 1:
            raise ValueError("Andor order contains no spectra")
        tracks = payload_rows.reshape(frame_count, track_count, width)
        return wavelengths, tracks

    def _sync_andor_spectra_locked(self):
        """Pull completed three-shot Andor orders without fabricating spectra."""
        try:
            camera = _tango_proxy(self._hardware_config["andor_device"], timeout_ms=5000)
            if "FAULT" in str(camera.state()).upper() or "OFF" in str(camera.state()).upper():
                raise RuntimeError(f"Andor state is {camera.state()}")

            if self._andor_order is None:
                camera.command_inout("start_grabbing")
                self._andor_order = camera.command_inout("register_order", [SPECTROMETER_BURST])
                self._andor_error = ""
                return

            if not camera.command_inout("is_order_ready", self._andor_order):
                return

            axis = np.asarray(camera.read_attribute("wavelengths_axis").value, dtype=np.float32)
            wavelengths, frames = self._decode_andor_order_locked(
                camera.command_inout("give_order", self._andor_order), axis.size
            )
            self._andor_order = None
            if self._wavelengths != wavelengths.tolist():
                self._wavelengths = [float(value) for value in wavelengths]
                self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
                self._live_od = [None for _ in self._wavelengths]

            averaged = np.mean(frames, axis=0)
            self._last_spectra = {
                "reference": [float(value) for value in averaged[0]],
                "signal": [float(value) for value in averaged[1]],
                # Dark/background has to be acquired separately; do not emulate it in Tango mode.
                "background": [0.0 for _ in self._wavelengths],
                "background_available": False,
            }
            self._spectrometer_frames += int(frames.shape[0])
            self._andor_error = ""
        except Exception as exc:
            self._andor_error = str(exc)

    def _sync_sample_stage_locked(self):
        now = time.monotonic()
        elapsed = max(0.0, now - self._sample_last_motion_update)
        self._sample_last_motion_update = now
        distance = self._sample_set_position_mm - self._sample_position_mm
        max_step = STAGE_SPEED_MM_PER_SEC * elapsed
        if abs(distance) <= max_step:
            self._sample_position_mm = self._sample_set_position_mm
        elif distance > 0:
            self._sample_position_mm += max_step
        else:
            self._sample_position_mm -= max_step

    def _emulator_raw_cycle_locked(self, delay_index):
        """Generate one unaveraged frame for each legacy V0 raw group."""
        off = self._make_spectra_locked(delay_index, electron_on=False)
        on = self._make_spectra_locked(delay_index, electron_on=True)
        return [
            off["background"],
            off["reference"],
            off["signal"],
            on["background"],
            on["reference"],
            on["signal"],
        ]

    def _current_scan_plan_locked(self):
        return build_scan_plan(self._settings, MM_PER_PS, STAGE_MIN_MM, STAGE_MAX_MM)

    def _resume_available_locked(self):
        source = self._resume_source
        if source is None:
            return False
        if self._tango_stop_event is not None:
            return False
        try:
            matches = (source["plan"].fingerprint == self._current_scan_plan_locked().fingerprint
                    and source["wavelengths"] == tuple(self._wavelengths)
                    and source["hardware_config"] == self._hardware_config)
            if not matches:
                return False
            if self._control_mode_locked() == "tango":
                profile = self._load_tango_profile_locked()
                timing = _load_dg645_recall_config(self._hardware_config["dg645_recall_config"])
                timing_sha = hashlib.sha256(json.dumps(timing, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
                return (source.get("mode") == "tango"
                        and source.get("dg645_sha256") == timing_sha
                        and source.get("profile_fingerprint") == V0TangoRunWriter.profile_fingerprint({"tango_profile": profile}))
            return source.get("mode", "emulator") == "emulator"
        except (ValueError, OSError):
            return False

    def _load_tango_profile_locked(self):
        path = os.environ.get("PYCONLYSE_V0_TANGO_PROFILE") or str(
            Path(__file__).resolve().parents[1] / "pump_probe" / "config" / "v0_tango_raw_profile.json")
        return load_profile(path)

    def prepare_tango_run(self, payload, *, require_commissioned=True):
        """Compute exact approval content without constructing any device proxy."""
        with self._lock:
            if self._run_writer is not None or not self._tango_done_event.is_set():
                raise RuntimeError("Wait for the active run and its device cleanup to finish")
            if self._tango_cleanup_errors:
                raise RuntimeError("Previous Tango cleanup is unresolved; recover retained RAW/device state before restarting acquisition")
            if self._control_mode_locked() != "tango":
                raise ValueError("Select Tango mode before preparing a Tango run")
            action = payload.get("run_action", "new")
            if action not in {"new", "continue", "overwrite"}:
                raise ValueError("Tango start action must be new, continue, or overwrite")
            profile = self._load_tango_profile_locked()
            if require_commissioned and profile.get("commissioned") is not True:
                raise TangoProfileNotCommissioned("Tango RAW profile is not commissioned: verify BG_level for the Andor ROI/readout and set commissioned=true in the server profile")
            checkpoint = None
            if action == "continue":
                if not self._resume_available_locked():
                    raise ValueError("No stopped Tango run matches the current profile and scan plan")
                source = self._resume_source
                checkpoint = {"run_id": source["run_id"], "source_sha256": hashlib.sha256(Path(source["h5_path"]).read_bytes()).hexdigest(),
                              "frame_counts": list(source["frame_counts"]),
                              "next_point_index": source["next_point_index"],
                              "next_shot_index": source["next_shot_index"],
                              "camera_config_fingerprint": source["camera_config_fingerprint"]}
            recall = _load_dg645_recall_config(self._hardware_config["dg645_recall_config"])
            output = str(payload.get("save_path") or (self._run_output_dir if action == "continue" else "")).strip()
            if not output:
                raise ValueError("Choose a data folder before preparing a Tango run")
            output = _normalize_data_path(output)
            if not _is_data_path_allowed(output):
                raise ValueError("Run output path is outside pump-probe data root")
            output_context = {"output_dir": output,
                              "sample_name": str(payload.get("sample_name") or self._run_sample_name or "").strip()}
            return build_tango_plan(self._current_scan_plan_locked(), dict(self._hardware_config), profile, recall,
                                    run_action=action, checkpoint=checkpoint, output_context=output_context)

    def _start_tango_run_locked(self, payload, plan):
        if self.prepare_tango_run(payload).fingerprint != plan.fingerprint:
            raise ValueError("Tango run configuration changed after plan authorization")
        continuing = payload.get("run_action", "new") == "continue"
        output = str(payload.get("save_path") or (self._run_output_dir if continuing else "")).strip()
        if not output:
            raise ValueError("Choose a data folder before starting a Tango run")
        output = _normalize_data_path(output)
        if not _is_data_path_allowed(output):
            raise ValueError("Run output path is outside pump-probe data root")
        self._run_output_dir = output
        self._run_sample_name = str(payload.get("sample_name") or self._run_sample_name or "").strip()
        self._tango_run_plan = plan
        self._scan_plan = plan.scan_plan
        self._tango_stop_event = threading.Event()
        self._tango_done_event.clear()
        self._tango_stop_status = "stopped"
        self._tango_order_id = None
        self._tango_rejected_cycles = 0
        self._tango_cleanup_errors = []
        self._tango_camera_fingerprint = None
        self._tango_reset_requested = False
        self._run_raw_groups = TRANCON_GROUPS
        self._run_status = "preparing"
        self._run_error = ""
        self._run_artifacts = {}
        self._running = True
        self._real_time = False
        self._andor_order = None
        if not continuing:
            self._resume_source = None
            self._delays = list(plan.scan_plan.delays)
            self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
            self._live_od = [None for _ in self._wavelengths]
            self._current_index = self._pulses_at_point = self._total_pulses = self._spectrometer_frames = 0
        context = {
            "id": uuid.uuid4().hex, "plan": plan, "stop": self._tango_stop_event,
            "checkpoint": dict(self._resume_source) if continuing else None,
            "settings": json.loads(json.dumps(self._settings)), "sample_name": self._run_sample_name,
            "done": self._tango_done_event,
        }
        self._tango_context_id = context["id"]
        self._run_thread = threading.Thread(target=self._run_tango_loop, args=(context,),
                                            name="v0-tango-" + context["id"], daemon=True)
        self._run_thread.start()

    def _request_tango_stop_locked(self, status="stopped"):
        self._running = False
        self._real_time = False
        self._andor_order = None
        if status == "aborted" or self._tango_stop_status != "aborted":
            self._tango_stop_status = status
        self._run_status = "stopping"
        self._tango_stop_event.set()

    def wait_for_tango_cleanup(self, timeout=15.0):
        if not self._tango_done_event.wait(timeout):
            raise RuntimeError("Tango acquisition has not stopped; device power must remain on")
        if self._tango_cleanup_errors:
            raise RuntimeError("Tango acquisition cleanup failed: " + "; ".join(self._tango_cleanup_errors))

    def _run_tango_loop(self, context):
        plan, stop = context["plan"], context["stop"]
        identity = context["id"]
        writer = None
        status, error = "completed", ""

        def current():
            return self._tango_context_id == identity and self._tango_stop_event is stop

        def on_motion(position, target, moving):
            with self._lock:
                if current():
                    self._position_mm, self._set_position_mm = position, target

        def on_order(order):
            with self._lock:
                if current():
                    self._tango_order_id = order

        adapter = TangoRawAdapter(plan, _tango_proxy, stop, on_motion=on_motion, on_order=on_order)
        try:
            checkpoint = context["checkpoint"]
            if checkpoint:
                expected_hash = plan.to_dict()["checkpoint"]["source_sha256"]
                if hashlib.sha256(Path(checkpoint["h5_path"]).read_bytes()).hexdigest() != expected_hash:
                    raise ValueError("Stopped RAW checkpoint changed after authorization")
            wavelengths = adapter.open()
            if checkpoint and adapter.capabilities["config_fingerprint"] != plan.to_dict()["checkpoint"]["camera_config_fingerprint"]:
                raise ValueError("Andor readout configuration differs from the stopped RAW checkpoint")
            with self._lock:
                if current():
                    self._tango_camera_fingerprint = adapter.capabilities["config_fingerprint"]
            if stop.is_set():
                raise AcquisitionCancelled("Acquisition cancelled during preparation")
            config = {"experiment": "V0 DirectLine pump-probe", "mode": "tango",
                      "settings": context["settings"], "sample_name": context["sample_name"],
                      "hardware_config": plan.hardware_config, "tango_profile": plan.profile,
                      "tango_run_plan": plan.to_dict(), "raw_groups": list(TRANCON_GROUPS)}
            if checkpoint:
                writer = V0TangoRunWriter.resume_from(checkpoint["h5_path"], config,
                         expected_plan=plan.scan_plan, expected_wavelengths=wavelengths)
            else:
                writer = V0TangoRunWriter(wavelengths, plan.scan_plan.delays, plan.scan_plan.positions,
                                         plan.scan_plan.shots_per_point, config, plan=plan.scan_plan)
            with self._lock:
                if not current() or stop.is_set():
                    raise AcquisitionCancelled("Acquisition cancelled before the first point")
                self._run_writer = writer
                self._resume_source = None
                self._wavelengths = wavelengths.tolist()
                self._delays = list(plan.scan_plan.delays)
                counts = writer.artifacts()["frame_counts"]
                self._heatmap = [[float(v) if np.isfinite(v) else None for v in writer.od_for_delay(i)] for i in range(len(counts))]
                self._total_pulses = sum(counts)
                self._spectrometer_frames = 3 * sum(counts)
                self._run_status = "running"
            for point, target in enumerate(plan.scan_plan.positions):
                acquired = writer.artifacts()["frame_counts"][point]
                if acquired == plan.scan_plan.shots_per_point:
                    continue
                with self._lock:
                    if not current() or stop.is_set():
                        raise AcquisitionCancelled("Acquisition cancelled before point motion")
                    self._current_index, self._pulses_at_point = point, acquired
                readback = adapter.move_to(point)
                rejected = 0
                while acquired < plan.scan_plan.shots_per_point:
                    # Similarity uses the minimum over the supplied batch. The
                    # source requests all remaining cycles, not singleton shots.
                    batch = adapter.acquire_batch(writer.run_id, point, plan.scan_plan.shots_per_point - acquired)
                    for exc in batch.rejected:
                        writer.record_rejected_transport(exc.packet, exc.metadata, str(exc))
                        rejected += 1
                    if batch.cycles:
                        admission = apply_detector_filters(np.stack([c.frames for c in batch.cycles]), plan.profile)
                        selected = set(admission["accepted_indices"])
                        for index, cycle in enumerate(batch.cycles):
                            metadata = {**cycle.metadata, "detector_filters": admission["details"],
                                        "filter_source_index": index, "filter_reasons": admission["reasons"][index]}
                            if index not in selected:
                                writer.record_rejected_transport(cycle.packet, metadata,
                                                                 "; ".join(admission["reasons"][index]))
                                rejected += 1
                                continue
                            with self._lock:
                                cancelled = not current() or stop.is_set()
                                if cancelled:
                                    writer.record_rejected_transport(batch.packet,
                                        {"source_envelope": batch.envelope, "source_order_id": batch.envelope["order_id"],
                                         "first_uncommitted_cycle": cycle.metadata["packet_cycle_index"]},
                                        "Cancelled before remaining RAW commits; entire source packet retained")
                                else:
                                    row = writer.record_tango_cycle(point, cycle.frames, target, readback,
                                                                   cycle.packet, metadata)
                                    acquired += 1
                                    self._pulses_at_point = acquired
                                    self._total_pulses += 1
                                    self._spectrometer_frames += 3
                                    self._live_od, self._heatmap[point] = row, row
                                    self._last_spectra = {"background": cycle.frames[1].tolist(),
                                                          "signal": cycle.frames[3].tolist(), "reference": cycle.frames[5].tolist(),
                                                          "background_available": True}
                            if cancelled:
                                writer.flush_transport()
                                adapter.acknowledge_cycle()
                                raise AcquisitionCancelled("Acquisition cancelled before RAW commit")
                    # Camera release follows durable RAW/journal flushes.
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
                    with self._lock:
                        if current():
                            self._tango_rejected_cycles += len(batch.rejected) + (len(admission["rejected_indices"]) if batch.cycles else 0)
                    if rejected > plan.profile["max_rejected_cycles"]:
                        raise RuntimeError("Detector rejection budget exceeded; check background and detector filter profile")
                    if stop.is_set():
                        raise AcquisitionCancelled("Acquisition cancelled after RAW commit")
        except AcquisitionCancelled:
            status = self._tango_stop_status
        except TangoPacketError as exc:
            status, error = "fault", str(exc)
            if writer is not None:
                try:
                    writer.record_rejected_transport(exc.packet, exc.metadata, str(exc))
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
                except Exception as journal_error:
                    error += "; RAW journal: " + str(journal_error)
        except Exception as exc:
            status, error = "fault", str(exc)
        finally:
            try:
                partial = adapter.close()
                if partial is not None:
                    if writer is None:
                        raise RuntimeError("Unjournaled camera packet retained in device server")
                    writer.record_rejected_transport(*partial, "Incomplete order retained during cleanup")
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
            except Exception as cleanup_error:
                adapter.cleanup_errors.append("RAW cleanup/journal: " + str(cleanup_error))
            try:
                if adapter.cleanup_errors:
                    status = "fault"
                    error = "; ".join(filter(None, [error, *adapter.cleanup_errors]))
                with self._lock:
                    if current():
                        self._tango_cleanup_errors = list(adapter.cleanup_errors)
                        if writer is not None:
                            self._run_writer = writer
                            self._finalize_run_locked(status, error)
                        else:
                            self._running = False
                            self._run_status, self._run_error = status, error
                        if self._tango_reset_requested and status != "fault" and self._run_status != "fault":
                            self._reset_locked()
                            self._run_status, self._run_error = "idle", ""
                            self._resume_source = None
                            self._scan_plan = None
                        self._tango_stop_event = None
                        self._tango_order_id = adapter.pending_order
                    elif writer is not None and not writer._closed:
                        writer.finalize("aborted", "Run context was replaced")
            finally:
                context["done"].set()

    def _start_emulator_run_locked(self, payload):
        # Validate the entire positional schedule before replacing any displayed
        # data or opening a writer. A clamp would merge distinct delay points.
        plan = self._current_scan_plan_locked()
        continuing = payload.get("run_action", "new") == "continue"
        if continuing and not self._resume_available_locked():
            raise ValueError("No stopped run matches the current scan plan; restore its settings or start a new run")
        output_dir = str(payload.get("save_path") or "").strip()
        if continuing and not output_dir:
            output_dir = self._run_output_dir
        if not output_dir:
            raise ValueError("Choose a data folder before starting an emulator run")
        output_dir = _normalize_data_path(output_dir)
        if not _is_data_path_allowed(output_dir):
            raise ValueError("Run output path is outside pump-probe data root")

        sample_name = str(payload.get("sample_name", self._run_sample_name if continuing else "") or "").strip()
        run_config = {
            "experiment": "V0 DirectLine pump-probe",
            "mode": "emulator",
            "sample_name": sample_name,
            "settings": dict(self._settings),
            "hardware_config": dict(self._hardware_config),
            "raw_groups": list(RAW_GROUPS),
            "spectrometer": {"rate_hz": SPECTROMETER_HZ, "burst": SPECTROMETER_BURST},
            "accelerator_hz": ACCELERATOR_HZ,
        }
        if continuing:
            writer = V0EmulatorRunWriter.resume_from(
                self._resume_source["h5_path"], run_config, expected_plan=plan,
                expected_wavelengths=self._wavelengths,
            )
        else:
            writer = V0EmulatorRunWriter(
                self._wavelengths, plan.delays, plan.positions,
                plan.shots_per_point, run_config, plan=plan,
            )
        previous_position = self._position_mm
        previous_faraday = self._faraday_closed
        self._reset_locked()
        self._position_mm = previous_position
        self._faraday_closed = previous_faraday
        self._run_writer = writer
        self._scan_plan = plan
        self._tango_run_plan = None
        self._run_raw_groups = tuple(RAW_GROUPS)
        self._resume_source = None
        self._run_output_dir = output_dir
        self._run_sample_name = sample_name
        checkpoint = writer.artifacts()
        counts = checkpoint["frame_counts"]
        next_index = checkpoint.get("next_point_index")
        self._current_index = int(next_index if next_index is not None else 0)
        self._pulses_at_point = int(counts[self._current_index])
        self._total_pulses = sum(counts)
        self._spectrometer_frames = self._total_pulses * len(RAW_GROUPS)
        self._set_position_mm = plan.positions[self._current_index]
        if continuing:
            for index, count in enumerate(counts):
                if count:
                    values = writer.od_for_delay(index)
                    self._heatmap[index] = [float(value) if np.isfinite(value) else None for value in values]
            if counts[self._current_index]:
                self._live_od = self._heatmap[self._current_index]
        self._run_status = "running"
        self._run_error = ""
        self._run_artifacts = {}
        self._running = True
        self._real_time = False
        self._last_pulse_update = time.monotonic()
        self._run_thread = threading.Thread(
            target=self._run_emulator_loop,
            args=(writer.run_id,),
            name=f"pump-probe-v0-{self._run_writer.run_id}",
            daemon=True,
        )
        self._run_thread.start()

    def _run_emulator_loop(self, run_id):
        """Advance a scan independently from HTTP state polling."""
        while True:
            with self._lock:
                if (not self._running or self._run_writer is None
                        or self._run_writer.run_id != run_id):
                    return
                self._sync_locked()
            time.sleep(0.02)

    def _finalize_run_locked(self, status, error=""):
        writer = self._run_writer
        self._running = False
        if writer is None:
            self._run_status = status
            self._run_error = str(error)
            return
        try:
            staged = writer.finalize(status=status, error=error)
            # Continue creates a new acquisition file from acquired RAW slots;
            # the stopped run remains an immutable parent artifact.
            self._resume_source = ({
                "h5_path": staged["h5_path"], "plan": self._scan_plan,
                "wavelengths": tuple(self._wavelengths),
                "hardware_config": dict(self._hardware_config),
                "mode": self._control_mode_locked(), "run_id": staged["run_id"],
                "frame_counts": list(staged["frame_counts"]),
                "next_point_index": staged.get("next_point_index"),
                "next_shot_index": staged.get("next_shot_index"),
                "profile_fingerprint": staged.get("tango_profile_fingerprint"),
                "camera_config_fingerprint": self._tango_camera_fingerprint,
                "dg645_sha256": self._tango_run_plan.to_dict()["dg645"]["source_sha256"] if self._tango_run_plan is not None and self._control_mode_locked() == "tango" else None,
            } if status == "stopped" and staged.get("next_point_index") is not None else None)
            self._run_artifacts = {
                "run_id": staged["run_id"],
                "h5": _publish_data_file(self._run_output_dir, staged["h5_path"]),
                "dat": _publish_data_file(self._run_output_dir, staged["dat_path"]),
                "manifest": _publish_data_file(self._run_output_dir, staged["manifest_path"]),
                "frame_counts": staged["frame_counts"],
                "parent_run_id": staged.get("parent_run_id"),
                "next_point_index": staged.get("next_point_index"),
                "next_shot_index": staged.get("next_shot_index"),
                "scan_plan_fingerprint": staged.get("scan_plan_fingerprint"),
                "raw_layout": staged.get("raw_layout"),
                "tango_profile_fingerprint": staged.get("tango_profile_fingerprint"),
            }
            self._run_status = status
            self._run_error = str(error)
        except Exception as exc:
            self._resume_source = None
            self._run_status = "fault"
            self._run_error = f"Run storage failed: {exc}"
        finally:
            self._run_writer = None

    def _apply_pulse_locked(self):
        if not self._running and not self._real_time:
            return

        if self._running and self._run_writer is not None:
            if (self._scan_plan is None
                    or self._set_position_mm != self._scan_plan.positions[self._current_index]):
                self._finalize_run_locked("fault", "Delay target no longer matches the immutable scan plan")
                return
            if abs(self._set_position_mm - self._position_mm) > 0.0005:
                return
            try:
                frames = self._emulator_raw_cycle_locked(self._current_index)
                self._live_od = self._run_writer.record_cycle(
                    self._current_index,
                    frames,
                    self._set_position_mm,
                    self._position_mm,
                )
                self._total_pulses += 1
                self._spectrometer_frames += len(frames)
                self._last_spectra = {
                    "background": frames[0],
                    "reference": frames[1],
                    "signal": frames[2],
                    "background_available": True,
                }
                self._heatmap[self._current_index] = self._live_od
                self._pulses_at_point += 1
            except Exception as exc:
                self._finalize_run_locked("fault", str(exc))
                return

            if self._pulses_at_point < int(self._settings["pulses_per_point"]):
                return
            self._pulses_at_point = 0
            if self._current_index + 1 >= len(self._delays):
                self._finalize_run_locked("completed")
                return
            self._current_index += 1
            self._set_position_mm = self._scan_plan.positions[self._current_index]
            return

        self._total_pulses += 1
        self._spectrometer_frames += SPECTROMETER_BURST
        electron_on = not self._faraday_closed
        self._last_spectra = self._make_spectra_locked(self._current_index, electron_on)
        pulses_per_point = int(self._settings["pulses_per_point"])
        signal_progress = min(1.0, (self._pulses_at_point + 1) / pulses_per_point)
        self._live_od = self._make_od_row_locked(
            self._current_index,
            include_signal=self._running,
            signal_progress=signal_progress,
        )

        if not self._running:
            return

        self._heatmap[self._current_index] = self._live_od
        self._pulses_at_point += 1
        if self._pulses_at_point < pulses_per_point:
            return

        self._live_od = self._make_od_row_locked(self._current_index, signal_progress=1.0)
        self._heatmap[self._current_index] = self._live_od
        self._pulses_at_point = 0
        if self._current_index + 1 >= len(self._delays):
            self._running = False
            return
        self._current_index += 1
        self._set_position_mm = self._delay_to_mm(self._delays[self._current_index])

    def configure(self, payload):
        with self._lock:
            if self._run_writer is not None or self._tango_stop_event is not None:
                raise RuntimeError("Stop the active run before changing scan settings")
            next_settings = resolve_scan_settings(self._settings, payload)
            if self._control_mode_locked() != "tango":
                self._sync_locked()
                self._sync_sample_stage_locked()
            self._configure_hardware_locked(payload)
            self._settings = next_settings
            old_running = self._running
            old_real_time = self._real_time
            old_faraday = self._faraday_closed
            self._reset_locked()
            self._running = old_running
            self._real_time = old_real_time
            self._faraday_closed = old_faraday
            return self.state()

    def hardware_config(self):
        with self._lock:
            return dict(self._hardware_config)

    def set_running(self, running, payload=None, *, tango_plan=None):
        with self._lock:
            next_running = bool(running)
            payload = payload or {}
            action = payload.get("run_action", "new")
            if action not in {"new", "continue", "overwrite", "cancel"}:
                raise ValueError("run_action must be new, continue, overwrite, or cancel")
            if self._tango_stop_event is not None:
                if action == "cancel" or not next_running:
                    self._request_tango_stop_locked("aborted" if action == "cancel" else "stopped")
                    return self.state()
                raise RuntimeError("Stop the active Tango run and wait for cleanup before starting another")
            if action == "cancel":
                if self._run_writer is not None:
                    self._finalize_run_locked("aborted", "Cancelled by operator")
                self._running = False
                self._real_time = False
                self._andor_order = None
                self._resume_source = None
                if self._run_status == "stopped":
                    self._run_status = "aborted"
                return self.state()
            if next_running and action in {"continue", "overwrite"} and self._running:
                raise ValueError("Stop the active run before continuing or replacing it")
            if not next_running:
                # Clearing the authorized active flag must precede any state
                # refresh: stopping an active sequence never polls or advances
                # another camera order.
                if self._run_writer is not None:
                    self._finalize_run_locked("stopped")
                self._running = False
                self._real_time = False
                self._andor_order = None
                self._last_pulse_update = time.monotonic()
                return self.state()
            if next_running and self._control_mode_locked() == "emulator":
                if self._run_writer is None:
                    self._start_emulator_run_locked(payload)
                return self.state()
            if next_running and self._control_mode_locked() == "tango":
                if tango_plan is None:
                    raise ValueError("A precomputed authorized Tango RAW plan is required")
                self._start_tango_run_locked(payload, tango_plan)
                return self.state()
            self._running = next_running
            if next_running:
                self._real_time = False
                if self._control_mode_locked() == "tango":
                    self._sync_locked()
            else:
                self._real_time = False
            self._last_pulse_update = time.monotonic()
            return self.state()

    def set_real_time(self, enabled):
        with self._lock:
            if self._tango_stop_event is not None:
                if enabled:
                    raise RuntimeError("Stop the Tango RAW run before enabling realtime spectra")
                self._real_time = False
                return self.state()
            if not enabled and self._control_mode_locked() == "tango":
                self._real_time = False
                self._andor_order = None
                self._last_pulse_update = time.monotonic()
                return self.state()
            self._sync_locked()
            self._real_time = bool(enabled)
            if self._real_time and self._control_mode_locked() == "tango":
                self._sync_locked()
            self._last_pulse_update = time.monotonic()
            return self.state()

    def set_faraday(self, closed):
        with self._lock:
            self._sync_locked()
            self._faraday_closed = bool(closed)
            return self.state()

    def move_stage(self, payload):
        with self._lock:
            if self._running or self._tango_stop_event is not None:
                raise RuntimeError("Stop the active run before moving the delay stage")
            self._sync_locked()
            if self._control_mode_locked() == "tango":
                position = float(payload.get("position_mm", self._set_position_mm))
                self._move_owis_axis_locked(self._hardware_config["delay_line_axis"], position)
                self._set_position_mm = _clamp(position, STAGE_MIN_MM, STAGE_MAX_MM)
            elif "position_mm" in payload:
                self._set_position_mm = _clamp(float(payload["position_mm"]), STAGE_MIN_MM, STAGE_MAX_MM)
            elif "delta_ps" in payload:
                self._set_position_mm = _clamp(
                    self._set_position_mm - float(payload["delta_ps"]) * MM_PER_PS,
                    STAGE_MIN_MM,
                    STAGE_MAX_MM,
                )
            elif "delta_mm" in payload:
                self._set_position_mm = _clamp(
                    self._set_position_mm + float(payload["delta_mm"]),
                    STAGE_MIN_MM,
                    STAGE_MAX_MM,
                )
            return self.state()

    def stop_stage(self):
        with self._lock:
            if self._tango_stop_event is not None:
                self._request_tango_stop_locked()
                return self.state()
            if self._run_writer is not None:
                self._finalize_run_locked("stopped")
            self._running = False
            self._real_time = False
            self._andor_order = None
            self._sync_locked()
            if self._control_mode_locked() == "tango":
                self._stop_owis_axis_locked(self._hardware_config["delay_line_axis"])
            self._set_position_mm = self._position_mm
            return self.state()

    def move_sample_stage(self, payload):
        with self._lock:
            if self._tango_stop_event is not None:
                raise RuntimeError("Wait for the Tango RAW run and device cleanup before manual sample motion")
            self._sync_sample_stage_locked()
            position = _clamp(float(payload.get("position_mm", self._sample_set_position_mm)), 0.0, 150.0)
            if self._control_mode_locked() == "tango":
                self._move_owis_axis_locked(self._hardware_config["sample_stage_axis"], position)
            self._sample_set_position_mm = position
            return self.state()

    def stop_sample_stage(self):
        with self._lock:
            if (self._tango_stop_event is not None
                    and self._hardware_config["sample_stage_axis"] == self._hardware_config["delay_line_axis"]):
                self._request_tango_stop_locked()
                return self.state()
            self._sync_sample_stage_locked()
            if self._control_mode_locked() == "tango":
                self._stop_owis_axis_locked(self._hardware_config["sample_stage_axis"])
            self._sample_set_position_mm = self._sample_position_mm
            return self.state()

    def _owis_aggregator_locked(self):
        return _tango_proxy(self._hardware_config["owis_aggregator_device"])

    def _move_owis_axis_locked(self, axis, position):
        proxy = self._owis_aggregator_locked()
        proxy.command_inout("move_axis", [float(axis), float(position)])

    def _stop_owis_axis_locked(self, axis):
        proxy = self._owis_aggregator_locked()
        proxy.command_inout("stop_axis", int(axis))

    def _preflight_dg645_locked(self):
        policy = str(self._hardware_config.get("dg645_preflight_policy") or "apply_recall_then_verify").strip().lower()
        if policy in {"off", "skip", "disabled"}:
            return

        config = _load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
        dg645 = _tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
        recall_slot = int(config.get("recall_slot", 8))

        if policy in {"apply_recall_then_verify", "recall_then_verify", "apply"}:
            dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
            time.sleep(1.0)
            try:
                dg645.command_inout("scpi_query", "*OPC?")
            except Exception:
                pass
        elif policy not in {"verify", "verify_only"}:
            raise ValueError(f"Unsupported DG645 preflight policy: {policy}")

        expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
        expected_queries.pop("*IDN?", None)
        mismatches = []
        for command, expected in expected_queries.items():
            actual = str(dg645.command_inout("scpi_query", command)).strip()
            if not _values_match(expected, actual):
                mismatches.append(f"{command} expected {expected!r} got {actual!r}")

        if mismatches:
            preview = "; ".join(mismatches[:5])
            suffix = f"; +{len(mismatches) - 5} more" if len(mismatches) > 5 else ""
            raise ValueError(f"DG645 recall {recall_slot} preflight failed: {preview}{suffix}")

    def _check_device(
        self,
        label,
        device_name,
        fix=False,
        starter_name=None,
        starter_running=None,
        on_progress=None,
    ):
        repair = None
        errors = []
        server_name = None

        def ready(proxy):
            state = str(proxy.state()).upper().rsplit(".", 1)[-1]
            if state not in {"ON", "RUNNING", "MOVING"}:
                return False
            if device_name == self._hardware_config["dg645_device"]:
                return bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
            if device_name in V0_PDU_DEVICES:
                return bool(list(proxy.read_attribute("ids").value))
            return True

        try:
            server_name = _server_name_for_device(device_name)
            # A composite or a rewired configuration must not indirectly repair
            # a STANDA axis. Only its Elysium2 owner may initialise it.
            if server_name.lower().startswith("ds_standa_motor/"):
                fix = False
                if starter_name != V0_STANDA_STARTER_DEVICE:
                    starter_name = V0_STANDA_STARTER_DEVICE
                    starter = _tango_proxy(starter_name, timeout_ms=2500)
                    starter_running = set(starter.command_inout("DevGetRunningServers", True))
            stopped = (
                starter_running is not None and server_name not in starter_running
            )
            if stopped and not fix:
                raise RuntimeError(f"{server_name} is not running on {starter_name}")
            # An initially stopped shared server may already have been started
            # for another device in this preparation pass.
            if stopped and fix:
                starter = _tango_proxy(starter_name, timeout_ms=5000)
                stopped = server_name not in set(starter.command_inout("DevGetRunningServers", False))
            if stopped:
                if on_progress:
                    on_progress(f"Starting missing server {server_name} on {starter_name}")
                repair = _restart_server_for_device(device_name, preferred_starter=starter_name)
                starter_running.add(server_name)
            try:
                proxy = _tango_proxy(device_name, timeout_ms=5000)
                ok = ready(proxy)
                if not ok:
                    errors.append(f"Initial state={proxy.state()}")
            except Exception as exc:
                proxy = None
                ok = False
                errors.append(str(exc))
            if not ok and fix and proxy is not None:
                ok, recovery_errors = recover_device(
                    proxy, ready, ("recover", "turn_on", "Init", "turn_on"),
                    on_progress=on_progress,
                )
                errors.extend(recovery_errors)
                if ok:
                    repair = repair or {"action": "reinitialized"}
            # Never stop an existing SDK process or replay a timed-out Init.
            # Report this branch and continue checking independent equipment.
            state = str(proxy.state()) if proxy is not None else "UNREACHABLE"
            detail = f"state={state}; hardware verified" if ok else (
                f"state={state}; {'; '.join(errors)}. Check power and connection, then press Prepare again."
            )
            return (_json_ok if ok else _json_fail)(
                label, detail, device=device_name, server=server_name,
                starter=starter_name, repair=repair,
            )
        except Exception as exc:
            return _json_fail(
                label, f"{exc}; {'; '.join(errors)}", device=device_name,
                server=server_name, starter=starter_name, repair=repair,
            )

    def _netio_outputs_for_device(self, device_name):
        proxy = _tango_proxy(device_name, timeout_ms=5000)
        ids = [int(value) for value in list(proxy.read_attribute("ids").value)]
        names = [str(value) for value in list(proxy.read_attribute("names").value)]
        states = [int(value) for value in list(proxy.read_attribute("states").value)]
        return proxy, ids, names, states

    def _check_netio_output(self, item, fix=False):
        try:
            proxy, ids, names, states = self._netio_outputs_for_device(item["device"])
            output_id = int(item["output_id"])
            if output_id not in ids or len(ids) != len(states):
                raise RuntimeError(f"PDU output {output_id} is missing or its state readback is invalid")
            index = ids.index(output_id)
            state = int(states[index]) if 0 <= index < len(states) else 0
            name = names[index] if 0 <= index < len(names) else f"Output {output_id}"
            if state != 1 and fix:
                # NETIO Action 5 means No Change. Do not rewrite stale states
                # of unrelated outlets (in particular the streak-camera supply).
                next_states = [5] * len(states)
                next_states[index] = 1
                proxy.command_inout("set_channels_states", next_states)
                time.sleep(max(0.5, float(item.get("settle_seconds", 0.5))))
                _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
                if output_id not in _ids or len(_ids) != len(states):
                    raise RuntimeError(f"PDU output {output_id} readback is unavailable")
                index = _ids.index(output_id)
                state = int(states[index]) if 0 <= index < len(states) else 0
            ok = state == 1
            return (_json_ok if ok else _json_fail)(
                item["label"],
                f"{name} output {output_id} is {'ON' if ok else 'OFF'}",
                device=item["device"],
                output_id=output_id,
                state=state,
            )
        except Exception as exc:
            return _json_fail(item["label"], exc, device=item["device"], output_id=item["output_id"])

    def _check_owis_axes(self, fix=False, starter_running=None, on_progress=None):
        checks = []
        aggregator = self._hardware_config["owis_aggregator_device"]
        backend = self._hardware_config["owis_backend_device"]
        legacy = self._hardware_config["owis_legacy_device"]
        axes = [
            (
                "Sample holder V0 axis",
                backend,
                int(self._hardware_config["sample_stage_axis"]),
            ),
            (
                "Delay line long axis",
                backend,
                int(self._hardware_config["delay_line_axis"]),
            ),
            ("OWIS legacy axis 4", legacy, 4),
        ]
        for label, device in (
            ("OWIS Ethernet backend", backend),
            ("OWIS legacy backend", legacy),
            ("OWIS aggregator", aggregator),
        ):
            if on_progress:
                on_progress(f"Checking {label}")
            checks.append(self._check_device(
                label, device, fix=fix, starter_name=V0_STARTER_DEVICE,
                starter_running=starter_running,
                on_progress=on_progress,
            ))
        for label, axis_device, axis in axes:
            try:
                proxy = _tango_proxy(axis_device, timeout_ms=5000)
                state = str(proxy.command_inout("get_status_axis", axis))
                position = float(proxy.command_inout("read_position_axis", axis))
                ok = _axis_is_ready(state, position)
                if not ok and fix:
                    try:
                        if on_progress:
                            on_progress(f"Enabling {label} axis {axis}; no move or home command")
                        proxy.command_inout("turn_on_axis", axis)
                        time.sleep(0.5)
                        state = str(proxy.command_inout("get_status_axis", axis))
                        position = float(proxy.command_inout("read_position_axis", axis))
                        ok = _axis_is_ready(state, position)
                    except Exception:
                        pass
                checks.append(
                    (_json_ok if ok else _json_fail)(
                        label,
                        f"axis {axis}: {state}, {position:.4f} mm",
                        device=axis_device,
                        axis=axis,
                    )
                )
            except Exception as exc:
                checks.append(
                    _json_fail(label, exc, device=axis_device, axis=axis)
                )
        return checks

    def _check_camera_stream(self, device_name, fix=False):
        label = f"Camera stream {device_name}"
        try:
            proxy = _tango_proxy(device_name, timeout_ms=2500)
            grabbing = bool(proxy.read_attribute("isgrabbing").value)
            if not grabbing and fix:
                proxy.command_inout("start_grabbing")
            deadline = time.monotonic() + (3.0 if fix else 0.0)
            while True:
                grabbing = bool(proxy.read_attribute("isgrabbing").value)
                if grabbing:
                    image = np.asarray(proxy.read_attribute("image").value)
                    if image.ndim >= 2 and image.size and np.isfinite(image).all():
                        return _json_ok(label, f"Image stream available: {image.shape}; no alignment or motion started", device=device_name)
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.2)
            return _json_fail(label, "Camera has no verified image stream", device=device_name)
        except Exception as exc:
            return _json_fail(label, exc, device=device_name)

    def _check_laser_pointing(self, device_name, fix=False, starter_running=None,
                              remote_running=None, on_progress=None):
        label = f"Laser Pointing {V0_LASER_POINTING_DEVICES.index(device_name) + 1}"
        checks = [self._check_device(label, device_name, fix=fix,
                  starter_name=V0_STARTER_DEVICE, starter_running=starter_running,
                  on_progress=on_progress)]
        try:
            proxy = _tango_proxy(device_name, timeout_ms=2500)
            raw = list(proxy.get_property(["ds_dict"]).get("ds_dict", []))
            dependencies = _parse_tango_dict(raw[0] if raw else None)
            actuators = [role for role in dependencies if str(role).startswith("Actuator")]
            if not dependencies.get("Camera") or len(actuators) < 4:
                raise RuntimeError("Camera or four mirror actuator dependencies are missing from ds_dict")
            for role, target in dependencies.items():
                axes = ()
                if isinstance(target, (list, tuple)) and len(target) == 2:
                    target, axes = target
                if not isinstance(target, str) or not target.strip():
                    raise RuntimeError(f"Invalid dependency for {role}")
                child_label = f"{label}: {role}"
                # Dependencies are always passive, including mirror motors,
                # diaphragms and shutters. Never call a composite motion command.
                server = _server_name_for_device(target)
                is_standa = server.lower().startswith("ds_standa_motor/")
                result = self._check_device(child_label, target, fix=False,
                    starter_name=V0_STANDA_STARTER_DEVICE if is_standa else None,
                    starter_running=remote_running if is_standa else None)
                if result.get("ok") and axes:
                    child = _tango_proxy(target, timeout_ms=2500)
                    for axis in axes:
                        state = str(child.command_inout("get_status_axis", int(axis)))
                        position = float(child.command_inout("read_position_axis", int(axis)))
                        if not _axis_is_ready(state, position):
                            raise RuntimeError(f"{child_label}: axis {axis} is not ready")
                checks.append(result)
        except Exception as exc:
            checks.append(_json_fail(f"{label} dependencies", exc, device=device_name))
        ready = all(check.get("ok") for check in checks)
        checks.append((_json_ok if ready else _json_fail)(
            f"{label} functional readiness",
            "Controller and all configured dependencies are available" if ready else
            "A camera/actuator dependency is unavailable; no alignment or motor initialisation was attempted",
            device=device_name))
        return checks

    def _read_daq_counter(self, timeout_ms=5000):
        proxy = _tango_proxy(self._hardware_config["daqmx_device"], timeout_ms=timeout_ms)
        return int(float(proxy.command_inout("read_counter", self._hardware_config["daqmx_counter_channel"])))

    def _counter_status_locked(self):
        try:
            value = self._read_daq_counter(timeout_ms=700)
            now = time.monotonic()
            rate = self._counter_rate_hz
            active = False
            if self._counter_last_value is not None and self._counter_last_time is not None:
                dt = max(1e-6, now - self._counter_last_time)
                delta = value - self._counter_last_value
                rate = max(0.0, delta / dt)
                self._counter_rate_hz = 0.65 * self._counter_rate_hz + 0.35 * rate
                active = delta > 0
            self._counter_last_value = value
            self._counter_last_time = now
            return {
                "value": value,
                "rate_hz": round(self._counter_rate_hz if rate is not None else 0.0, 3),
                "active": active or self._counter_rate_hz > 1.0,
                "error": "",
            }
        except Exception as exc:
            return {"value": None, "rate_hz": 0.0, "active": False, "error": str(exc)}

    def _check_counter_activity(self, seconds=1.25):
        try:
            first = self._read_daq_counter(timeout_ms=5000)
            time.sleep(max(0.5, float(seconds)))
            second = self._read_daq_counter(timeout_ms=5000)
            rate = (second - first) / max(0.5, float(seconds))
            ok = second > first and rate >= 1.0
            return (_json_ok if ok else _json_fail)(
                "ELYSE pulse counter",
                f"{first} -> {second}, {rate:.2f} Hz",
                value=second,
                rate_hz=round(rate, 3),
            )
        except Exception as exc:
            return _json_fail("ELYSE pulse counter", exc)

    def _check_dg645_recall(self, apply_recall=False):
        try:
            config = _load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
            dg645 = _tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
            recall_slot = int(config.get("recall_slot", 8))
            if apply_recall:
                dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
                time.sleep(1.0)
                try:
                    dg645.command_inout("scpi_query", "*OPC?")
                except Exception:
                    pass
            expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
            expected_queries.pop("*IDN?", None)
            mismatches = []
            for command, expected in expected_queries.items():
                actual = str(dg645.command_inout("scpi_query", command)).strip()
                if not _values_match(expected, actual):
                    mismatches.append(f"{command}: expected {expected!r}, got {actual!r}")
            if mismatches:
                preview = "; ".join(mismatches[:5])
                return _json_fail("DG645 recall 8", preview, mismatch_count=len(mismatches))
            return _json_ok("DG645 recall 8", "Recall 8 matches V0 DirectLine preset", recall_slot=recall_slot)
        except Exception as exc:
            return _json_fail("DG645 recall 8", exc)

    def _starter_server_snapshot(self, starter_name):
        try:
            starter = _tango_proxy(starter_name, timeout_ms=2500)
            running = set(starter.command_inout("DevGetRunningServers", True))
            stopped = set(starter.command_inout("DevGetStopServers", False))
            return (
                _json_ok(
                    f"Tango Starter {starter_name}",
                    f"{len(running)} server(s) running; {len(stopped)} stopped",
                    device=starter_name,
                    running_count=len(running),
                    stopped_count=len(stopped),
                ),
                running,
            )
        except Exception as exc:
            return (
                _json_fail(
                    f"Tango Starter {starter_name}",
                    exc,
                    device=starter_name,
                ),
                set(),
            )

    def _everest_server_snapshot(self):
        return self._starter_server_snapshot(V0_STARTER_DEVICE)

    def _v0_preparation_checks(self, fix=False, progress=None):
        if fix and V0_PREPARATION_READ_ONLY:
            raise ValueError("Prepare V0 is read-only: no server start, recovery, initialization, power or DG645 recall is allowed")
        starter_check, running_servers = self._everest_server_snapshot()
        checks = []

        def record(result):
            checks.append(result)
            if progress is not None:
                progress.append({**result, "step": result["label"],
                                 "status": "verified" if result.get("ok") else "failed"})
            return result

        def phase(message, stage=1):
            if progress is not None:
                progress.phase(message, stage=stage)

        record(starter_check)
        if not starter_check.get("ok"):
            # Existing exported devices can still be checked without Starter.
            # A missing Starter must not stop independent power branches.
            running_servers = None

        power_checks = {}

        def check_device(label, device_name, power_keys=()):
            phase(f"Checking {label}", stage=0 if device_name in V0_PREPARATION_PDU_DEVICES else 1)
            failed_power = [key for key in power_keys if not power_checks[key].get("ok")]
            if failed_power:
                result = _json_fail(
                    label, "Blocked by unconfirmed power: " + ", ".join(
                        power_checks[key]["label"] for key in failed_power
                    ), device=device_name, blocked=True,
                )
            else:
                result = self._check_device(
                    label, device_name, fix=fix, starter_name=V0_STARTER_DEVICE,
                    starter_running=running_servers,
                    on_progress=phase,
                )
            return record(result)

        phase("Checking PDU servers before enabling the explicit V0 supplies", stage=0)
        pdu_checks = {
            device_name: check_device(f"PDU server {device_name}", device_name)
            for device_name in V0_PREPARATION_PDU_DEVICES
        }
        for item in V0_PREPARATION_NETIO_OUTPUTS:
            phase(f"{'Confirming/enabling' if fix else 'Checking'} power: {item['label']}", stage=0)
            result = (
                self._check_netio_output(item, fix=fix)
                if pdu_checks[item["device"]].get("ok")
                else _json_fail(item["label"], "PDU is unavailable; power cannot be verified", blocked=True)
            )
            power_checks[item["key"]] = result
            record(result)

        # Power-dependent device servers are checked only after their outputs.
        dg645_check = check_device(
            "DG645 Tango server", self._hardware_config["dg645_device"], ("dg645",)
        )
        daq_check = check_device("DAQmx DS", self._hardware_config["daqmx_device"])

        for index, device_name in enumerate(V0_CAMERA_DEVICES, start=1):
            camera_check = check_device(f"V0 camera {index}", device_name)
            record(self._check_camera_stream(device_name, fix=fix) if camera_check.get("ok") else
                   _json_fail(f"Camera stream {device_name}", "Camera is unavailable", device=device_name, blocked=True))
        remote_check, remote_running = self._starter_server_snapshot(V0_STANDA_STARTER_DEVICE)
        record(remote_check)
        phase("Checking STANDA on Elysium2 only; no STANDA start, Init, recovery or motion")
        for device_name in V0_STANDA_DEVICES:
            label = f"STANDA {device_name.rsplit('/', 1)[-1]} (Elysium2)"
            if not remote_check.get("ok") or not power_checks["v0_standa"].get("ok"):
                record(_json_fail(label, "Remote Elysium2 server or STANDA power unavailable; no local start attempted",
                                         device=device_name, starter=V0_STANDA_STARTER_DEVICE, blocked=True))
            else:
                record(self._check_device(label, device_name, fix=False,
                                                 starter_name=V0_STANDA_STARTER_DEVICE, starter_running=remote_running))

        if power_checks["v0_owis"].get("ok"):
            phase("Verifying OWIS backends, routing and V0 axes without motion")
            for result in self._check_owis_axes(fix=fix, starter_running=running_servers, on_progress=phase):
                record(result)
        else:
            record(_json_fail("OWIS controllers and axes", "Blocked by unconfirmed OWIS power", blocked=True))
        for device_name in V0_LASER_POINTING_DEVICES:
            phase(f"Verifying {device_name} and its actual camera/actuator dependencies")
            for result in self._check_laser_pointing(device_name, fix=fix,
                    starter_running=running_servers, remote_running=remote_running if remote_check.get("ok") else set(),
                    on_progress=phase):
                record(result)
        phase("Checking DG645 timing and the pulse counter; DG645 settings are retained", stage=2)
        record(
            self._check_dg645_recall(apply_recall=False)
            if dg645_check.get("ok")
            else _json_fail("DG645 recall 8", "DG645 is unavailable; preset was not applied", blocked=True)
        )
        record(
            self._check_counter_activity()
            if daq_check.get("ok")
            else _json_fail("DAQ counter", "DAQmx is unavailable", blocked=True)
        )
        return checks

    def hardware_preflight(self, fix=False, progress=None):
        if fix and V0_PREPARATION_READ_ONLY:
            raise ValueError("V0 automatic initialization is disabled; use passive preflight only")
        with self._lock:
            if not fix:
                # Passive diagnostics may read state/attributes and approved
                # query commands, but never repair, move, power, recall, or
                # start/register a camera order.
                checks = self._v0_preparation_checks(fix=False)
                ok = all(check.get("ok") for check in checks)
                return {
                    "success": ok,
                    "fixed": False,
                    "read_only": True,
                    "excluded_devices": [self._hardware_config["andor_device"], self._hardware_config["spectrograph_device"]],
                    "message": "Passive hardware preflight" if ok else "Passive hardware preflight found unavailable hardware",
                    "recommendation": "Press Prepare to confirm/enable the required V0 supplies and prepare local controls. STANDA is check-only on Elysium2; DG645 timing remains unchanged. Andor CCD / UV-vis are excluded.",
                    "checks": checks,
                    "counter": self._counter_status_locked(),
                }
            checks = self._v0_preparation_checks(fix=fix, progress=progress)
            ok = all(check.get("ok") for check in checks)
            return {
                "success": ok,
                "fixed": bool(fix),
                "read_only": False,
                "dg645_timing_read_only": True,
                "standa_read_only": True,
                "message": "V0 laser-setup preparation completed; DG645 timing retained; acquisition not started" if ok else "V0 preparation incomplete; independent checks continued and DG645 timing was retained",
                "recommendation": "" if ok else (
                    "Correct power or connection for: "
                    + ", ".join(check["label"] for check in checks if not check.get("ok"))
                    + ". Then press Prepare again to repeat all checks."
                ),
                "checks": checks,
                "counter": self._counter_status_locked(),
            }

    def _read_tango_motion_state_locked(self, state):
        if self._control_mode_locked() != "tango":
            return state
        try:
            proxy = self._owis_aggregator_locked()
            positions = _parse_tango_dict(proxy.read_attribute("positions").value)
            states = _parse_tango_dict(proxy.read_attribute("states").value)
            delay_axis = int(self._hardware_config["delay_line_axis"])
            sample_axis = int(self._hardware_config["sample_stage_axis"])
            delay_pos = positions.get(delay_axis, positions.get(str(delay_axis)))
            sample_pos = positions.get(sample_axis, positions.get(str(sample_axis)))
            delay_state = states.get(delay_axis, states.get(str(delay_axis)))
            sample_state = states.get(sample_axis, states.get(str(sample_axis)))
            if delay_pos is not None:
                self._position_mm = float(delay_pos)
                state["position_mm"] = round(self._position_mm, 5)
            if sample_pos is not None:
                self._sample_position_mm = float(sample_pos)
            state["sample_position_mm"] = round(self._sample_position_mm, 5)
            state["sample_set_position_mm"] = round(self._sample_set_position_mm, 5)
            state["stage_moving"] = abs(self._set_position_mm - self._position_mm) > 0.0005
            state["sample_stage_moving"] = abs(self._sample_set_position_mm - self._sample_position_mm) > 0.0005
            state["tango_motion"] = {
                "delay_line_axis": delay_axis,
                "delay_line_state": str(delay_state),
                "sample_stage_axis": sample_axis,
                "sample_stage_state": str(sample_state),
            }
            state["hardware_error"] = ""
        except Exception as exc:
            state["hardware_error"] = str(exc)
        return state

    def move_crystal(self):
        with self._lock:
            self._sync_locked()
            self._crystal_position = (self._crystal_position + 1) % 8
            return self.state()

    def reset(self):
        with self._lock:
            if self._tango_stop_event is not None:
                self._tango_reset_requested = True
                self._request_tango_stop_locked("aborted")
                return self.state()
            if self._run_writer is not None:
                self._finalize_run_locked("aborted", "Reset requested")
            self._reset_locked()
            self._run_status = "idle"
            self._run_error = ""
            self._resume_source = None
            self._scan_plan = None
            return self.state()

    def state(self, advance_active=False):
        with self._lock:
            tango_mode = self._control_mode_locked() == "tango"
            if not tango_mode:
                self._sync_locked()
                self._sync_sample_stage_locked()
            elif advance_active and (self._running or self._real_time):
                self._sync_locked()
            state = {
                "accelerator_hz": ACCELERATOR_HZ,
                "spectrometer_hz": SPECTROMETER_HZ,
                "spectrometer_burst": SPECTROMETER_BURST,
                "stage_speed_mm_per_sec": STAGE_SPEED_MM_PER_SEC,
                "running": self._running,
                "real_time": self._real_time,
                "faraday_closed": self._faraday_closed,
                "electron_state": "OFF" if self._faraday_closed else "ON",
                "current_index": self._current_index,
                "pulses_at_point": self._pulses_at_point,
                "total_pulses": self._total_pulses,
                "spectrometer_frames": self._spectrometer_frames,
                "andor_error": self._andor_error,
                # Dashboard state is deliberately cached/no-probe in both
                # modes: GET state must never create a Tango proxy or command.
                "daq_counter": {
                    "value": None,
                    "rate_hz": 0.0,
                    "active": False,
                    "error": "not probed",
                },
                "position_mm": round(self._position_mm, 5),
                "set_position_mm": round(self._set_position_mm, 5),
                "stage_moving": abs(self._set_position_mm - self._position_mm) > 0.0005,
                "crystal_position": self._crystal_position,
                "control_mode": self._control_mode_locked(),
                "hardware_config": dict(self._hardware_config),
                "sample_position_mm": round(self._sample_position_mm, 5),
                "sample_set_position_mm": round(self._sample_set_position_mm, 5),
                "sample_stage_moving": abs(self._sample_set_position_mm - self._sample_position_mm) > 0.0005,
                "settings": dict(self._settings),
                "run": {
                    "id": self._run_writer.run_id if self._run_writer is not None else self._run_artifacts.get("run_id"),
                    "status": self._run_status,
                    "error": self._run_error,
                    "sample_name": self._run_sample_name,
                    "output_dir": self._run_output_dir,
                    "artifacts": dict(self._run_artifacts),
                    "raw_groups": list(self._run_raw_groups),
                    "acquisition_contract": "andor-v0-raw-order-v1" if self._tango_run_plan is not None and tango_mode else "andor-two-track-spectra-v1" if tango_mode else "v0-raw6-scan-v1",
                    "tango_run_plan_fingerprint": self._tango_run_plan.fingerprint if self._tango_run_plan is not None else None,
                    "tango_pending_order": self._tango_order_id,
                    "rejected_cycles": self._tango_rejected_cycles,
                    "cleanup_errors": list(self._tango_cleanup_errors),
                    "scan_plan": self._scan_plan.to_dict() if self._scan_plan is not None else None,
                    "resume_available": self._resume_available_locked(),
                },
                "wavelengths": self._wavelengths,
                "delays": self._delays,
                "heatmap": self._heatmap,
                "live_od": self._live_od,
                "spectra": self._last_spectra,
            }
            # RAW orders advance only in the worker. Once cleanup has ended,
            # preserve the existing passive OWIS readback for manual controls.
            return (state if self._tango_stop_event is not None or not self._tango_done_event.is_set()
                    else self._read_tango_motion_state_locked(state))


_emulator = PumpProbeV0Controller()
_v0_lifecycle_instance = None
_v0_lifecycle_factory_lock = threading.Lock()


def _v0_lifecycle():
    global _v0_lifecycle_instance
    with _v0_lifecycle_factory_lock:
        if _v0_lifecycle_instance is None:
            path = os.environ.get("PYCONLYSE_V0_EXPERIMENT_STATE_DB") or str(Path.home() / ".pyconlyse" / "experiment_preparation_v0.sqlite3")
            _v0_lifecycle_instance = ExperimentLifecycle(path, experiment="V0")
        return _v0_lifecycle_instance


class V0PreparationFailure(RuntimeError):
    code = "v0_preparation_incomplete"

    def __init__(self, result):
        self.checks = list(result.get("checks", []))
        self.steps = [{**check, "step": check["label"],
                       "status": "verified" if check.get("ok") else "failed"}
                      for check in self.checks]
        super().__init__(result.get("recommendation") or result.get("message") or "V0 preparation incomplete")


def _prepare_v0_experiment(steps=None):
    # Do not initialise shared controls while a live experiment owns them.
    import pump_probe_vd2_api as vd2
    with _emulator._lock:
        if _emulator._running or _emulator._real_time or vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"}:
            raise RuntimeError("Acquisition is active; V0 preparation did not change hardware")
    result = _emulator.hardware_preflight(fix=True, progress=steps)
    if not result["success"]:
        raise V0PreparationFailure(result)
    return {**result, "steps": list(steps) if steps is not None else [
        {**check, "step": check["label"], "status": "verified"} for check in result["checks"]]}


def _serialized_v0_mutation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
            return jsonify({"success": False, "error": "Experiment preparation/shutdown is in progress; hardware commands are locked"}), 409
        try:
            return function(*args, **kwargs)
        finally:
            EXPERIMENT_MUTATION_LOCK.release()
    return wrapped


def _v0_shutdown_vd2_status():
    import pump_probe_vd2_api as vd2
    streak = _tango_proxy(vd2.STREAK_DEVICE, timeout_ms=2500)
    return {"application_running": bool(streak.read_attribute("application_running").value),
            "connected": bool(streak.read_attribute("connected").value),
            "protocol_active": vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"},
            "lifecycle_active": vd2._lifecycle().snapshot().get("status") == "running"}


def _stop_v0_web_sequence():
    _emulator.set_running(False)
    _emulator.wait_for_tango_cleanup()
    _emulator.set_real_time(False)


def _v0_shutdown_authorization():
    targets = [{"device": V0_SHUTDOWN_CAMERA, "command": command}
               for command in ("BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup")]
    targets.extend({"device": device, "command": "set_channels_states"}
                   for device in dict.fromkeys(item[0] for item in V0_SHUTDOWN_OUTPUT_PLAN))
    targets.extend({"device": V0_SHUTDOWN_STAGE, "command": command}
                   for command in ("move_axis", "stop_axis"))
    return targets, {"pdu_output_states": [{"device": device, "output_id": output, "state": 0}
                                           for device, output, _label in V0_SHUTDOWN_OUTPUT_PLAN],
                     "translation_stage_return": {"device": V0_SHUTDOWN_STAGE, "backend": V0_SHUTDOWN_STAGE_BACKEND,
                                                  "axis": V0_SHUTDOWN_STAGE_AXIS, "position_mm": 0.0,
                                                  "tolerance_mm": V0_SHUTDOWN_STAGE_TOLERANCE,
                                                  "timeout_s": V0_SHUTDOWN_STAGE_TIMEOUT,
                                                  "home_or_redefine": False},
                     "camera_warmup_minimum_c": 0, "camera_warmup_timeout_s": 900,
                     "preserve": "Elysium2/STANDA, shared OWIS power and other axes, all VD2 outlets, Xe cooling",
                     "block_if_vd2_active": True, "server_start_or_restart": False}


def _v0_hardware_config(payload=None):
    config = _emulator.hardware_config()
    payload = payload or {}
    requested = payload.get("hardware_config") if isinstance(payload, dict) else None
    if isinstance(requested, dict):
        config = {**config, **{key: value for key, value in requested.items() if key in DEFAULT_HARDWARE_CONFIG}}
    if isinstance(payload, dict) and "control_mode" in payload:
        config["control_mode"] = payload["control_mode"]
    return config


def _v0_reject_runtime_hardware_rewire(payload):
    """Production/local-auth policy owns physical V0 topology, not requests."""
    if not authorization_required() or not isinstance(payload, dict):
        return None
    raw_config = payload.get("hardware_config")
    if raw_config is None:
        return None
    if not isinstance(raw_config, dict) or set(raw_config) - {"control_mode"}:
        return jsonify({
            "success": False,
            "error": "Hardware configuration rewiring is not authorized",
            "code": "hardware_not_authorized",
        }), 403
    return None


def _v0_tango_active(payload=None):
    current = _clean_control_mode(_emulator.hardware_config().get("control_mode"))
    requested = _clean_control_mode(_v0_hardware_config(payload).get("control_mode"))
    return current == "tango" or requested == "tango"


def _v0_reject_unbound_tango_sequence():
    """Fail closed until V0 can bind its complete runtime plan to approval."""
    return jsonify({
        "success": False,
        "error": "A precomputed exact hardware plan is required",
        "code": "hardware_not_authorized",
    }), 403


def _v0_targets(config, action):
    aggregator = str(config["owis_aggregator_device"])
    backend = str(config["owis_backend_device"])
    andor = str(config["andor_device"])
    dg645 = str(config["dg645_device"])
    daqmx = str(config["daqmx_device"])
    if action == "v0.initialize":
        targets = [
            {"device": backend, "command": "get_status_axis"},
            {"device": backend, "command": "read_position_axis"},
            {"device": backend, "command": "turn_on_axis"},
            {"device": dg645, "command": "scpi_query"},
            {"device": daqmx, "command": "read_counter"},
        ]
        for output in V0_PREPARATION_NETIO_OUTPUTS:
            targets.append({"device": str(output["device"]), "command": "set_channels_states"})
        preparation_devices = (
            *V0_PREPARATION_PDU_DEVICES, *V0_CAMERA_DEVICES, *V0_LASER_POINTING_DEVICES,
            aggregator, backend, str(config["owis_legacy_device"]),
            dg645, daqmx,
        )
        for device in preparation_devices:
            targets.extend(
                {"device": device, "command": command}
                for command in ("recover", "turn_on", "Init")
            )
        targets.extend(
            {"device": V0_STARTER_DEVICE, "command": command}
            for command in ("DevStart",)
        )
        targets.extend({"device": camera, "command": "start_grabbing"}
                       for camera in V0_CAMERA_DEVICES)
        return targets
    if action in {"v0.stage-move", "v0.sample-stage-move"}:
        return [{"device": aggregator, "command": "move_axis"}]
    if action in {"v0.stage-stop", "v0.sample-stage-stop"}:
        return [{"device": aggregator, "command": "stop_axis"}]
    if action == "v0.run":
        return [
            {"device": dg645, "command": "scpi_write"},
            {"device": dg645, "command": "scpi_query"},
            {"device": andor, "command": "start_grabbing"},
            {"device": andor, "command": "register_order"},
            {"device": andor, "command": "is_order_ready"},
            {"device": andor, "command": "give_order"},
        ]
    if action == "v0.realtime":
        return [
            {"device": andor, "command": "start_grabbing"},
            {"device": andor, "command": "register_order"},
            {"device": andor, "command": "is_order_ready"},
            {"device": andor, "command": "give_order"},
        ]
    raise ValueError(f"Unsupported V0 hardware action: {action}")


def _guard_v0_hardware(action, payload):
    config = _v0_hardware_config(payload)
    return require_http_hardware(action, _v0_targets(config, action), payload, route_id=action)


def _v0_stage_move_args(payload, *, sample_stage=False):
    with _emulator._lock:
        config = _emulator.hardware_config()
        if sample_stage:
            position = _clamp(float(payload.get("position_mm", _emulator._sample_set_position_mm)), 0.0, 150.0)
            axis = int(config["sample_stage_axis"])
        else:
            position = _emulator._set_position_mm
            if "position_mm" in payload:
                position = float(payload["position_mm"])
            elif "delta_ps" in payload:
                position -= float(payload["delta_ps"]) * MM_PER_PS
            elif "delta_mm" in payload:
                position += float(payload["delta_mm"])
            position = _clamp(position, STAGE_MIN_MM, STAGE_MAX_MM)
            axis = int(config["delay_line_axis"])
    return {"axis": axis, "position_mm": float(position)}


def _v0_stage_stop_args(*, sample_stage=False):
    config = _emulator.hardware_config()
    axis_name = "sample_stage_axis" if sample_stage else "delay_line_axis"
    return {"axis": int(config[axis_name])}


def _v0_sequence_args(payload, *, realtime=False):
    config = _v0_hardware_config(payload)
    recall = _load_dg645_recall_config(config.get("dg645_recall_config"))
    args = {
        "spectrometer_burst": int(SPECTROMETER_BURST),
        "order_token": "device_generated",
    }
    if not realtime:
        args.update({
            "dg645_preflight_policy": str(config.get("dg645_preflight_policy") or "apply_recall_then_verify").strip().lower(),
            "dg645_recall_slot": int(recall.get("recall_slot", 8)),
        })
    return args


@pump_probe_v0_api.route("/state", methods=["GET"])
def pump_probe_state():
    return jsonify(_emulator.state(advance_active=True))


@pump_probe_v0_api.route("/config", methods=["POST"])
def pump_probe_configure():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "Scan configuration must be a JSON object"}), 400
    rejected = _v0_reject_runtime_hardware_rewire(payload)
    if rejected is not None:
        return rejected
    try:
        return jsonify(_emulator.configure(payload))
    except (ValueError, RuntimeError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/hardware-config", methods=["GET", "POST"])
def pump_probe_hardware_config():
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "Scan configuration must be a JSON object"}), 400
        rejected = _v0_reject_runtime_hardware_rewire(payload)
        if rejected is not None:
            return rejected
        try:
            return jsonify(_emulator.configure(payload))
        except (ValueError, RuntimeError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({
        "success": True,
        "hardware_config": _emulator.hardware_config(),
    })


@pump_probe_v0_api.route("/hardware/preflight", methods=["GET", "POST"])
def pump_probe_hardware_preflight():
    try:
        return jsonify(_emulator.hardware_preflight(fix=False))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/hardware/initialize", methods=["POST"])
def pump_probe_hardware_initialize():
    try:
        if V0_PREPARATION_READ_ONLY:
            return jsonify({"success": False, "code": "v0_prepare_read_only", "read_only": True,
                            "error": "Prepare V0 is check-only; automatic server startup, recovery and power-on are disabled. Use /hardware/preflight."}), 409
        payload = request.get_json(silent=True)
        if payload is None and not request.get_data():
            payload = {}
        if not isinstance(payload, dict) or payload:
            return jsonify({"success": False, "error": "V0 preparation accepts no per-request hardware settings"}), 400
        if authorization_required():
            return jsonify({
                "success": False,
                "error": "Hardware action is not authorized",
                "code": "hardware_not_authorized",
            }), 403
        blocked = _guard_v0_hardware("v0.initialize", payload)
        if blocked is not None:
            return blocked
        lifecycle = _v0_lifecycle()
        if not EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
            job = lifecycle.snapshot()
            if job.get("status") == "running" and job.get("operation") == "prepare":
                return jsonify({"success": True, "job": job, "attached": True}), 202
            return jsonify({"success": False, "error": "Another experiment operation is active; shared equipment retained"}), 409
        if request.args.get("background") == "1":
            try:
                job = lifecycle.start("prepare", _prepare_v0_experiment, EXPERIMENT_MUTATION_LOCK.release)
                return jsonify({"success": True, "job": job}), 202
            except Exception:
                EXPERIMENT_MUTATION_LOCK.release()
                raise
        try:
            return jsonify(_prepare_v0_experiment())
        finally:
            EXPERIMENT_MUTATION_LOCK.release()
    except V0PreparationFailure as exc:
        return jsonify({"success": False, "error": str(exc), "checks": exc.checks, "steps": exc.steps}), 503
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/lifecycle", methods=["GET"])
def v0_lifecycle_state():
    return jsonify({"success": True, "job": _v0_lifecycle().snapshot()})


@pump_probe_v0_api.route("/lifecycle/log", methods=["GET"])
def v0_lifecycle_log():
    try:
        before = request.args.get("before", type=int)
        if before is not None and before < 1:
            raise ValueError("Invalid log cursor")
        return jsonify({"success": True, "events": _v0_lifecycle().events(before=before)})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/deinitialize", methods=["POST"])
def v0_deinitialize():
    targets, args = _v0_shutdown_authorization()
    blocked = require_http_hardware("deinitialize", targets, args, route_id="v0.deinitialize", wrapper_fields=set())
    if blocked is not None:
        return blocked
    lifecycle = _v0_lifecycle()
    if not EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
        job = lifecycle.snapshot()
        if job.get("status") == "running" and job.get("operation") == "shutdown":
            return jsonify({"success": True, "job": job, "attached": True}), 202
        return jsonify({"success": False, "error": "Another experiment operation is active; shared power retained"}), 409
    try:
        job = lifecycle.start("shutdown", lambda steps: execute_v0_shutdown(
            _tango_proxy, steps, _stop_v0_web_sequence, _v0_shutdown_vd2_status), EXPERIMENT_MUTATION_LOCK.release)
        return jsonify({"success": True, "job": job}), 202
    except Exception as exc:
        EXPERIMENT_MUTATION_LOCK.release()
        return jsonify({"success": False, "error": str(exc)}), 503


@pump_probe_v0_api.route("/run/plan", methods=["POST"])
def pump_probe_tango_plan():
    payload = request.get_json(silent=True) or {}
    try:
        if not isinstance(payload, dict):
            raise ValueError("Run request must be an object")
        plan = _emulator.prepare_tango_run(payload, require_commissioned=False)
        return jsonify({"success": True, "plan": plan.to_dict(), "fingerprint": plan.fingerprint,
                        "commissioned": plan.profile["commissioned"],
                        "authorization": {"route_id": "v0.run", "action": "v0.run", "method": "POST",
                                          "targets": plan.authorization_targets(), "args": plan.authorization_args()}})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/commissioning/andor-snapshot", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_andor_snapshot():
    """One authorized readback, with no acquisition/parameter/axis commands."""
    payload = request.get_json(silent=True)
    if (request.get_data(cache=True).strip() and not isinstance(payload, dict)) or (payload is not None and payload != {}):
        return jsonify({"success": False, "error": "Snapshot request must be an empty object"}), 400
    with _emulator._lock:
        if (_emulator._running or _emulator._real_time or _emulator._run_writer is not None
                or _emulator._tango_stop_event is not None or not _emulator._tango_done_event.is_set()):
            return jsonify({"success": False, "error": "Wait for V0 acquisition and cleanup before sampling its configuration"}), 409
        config = _emulator.hardware_config()
        if config["control_mode"] != "tango":
            return jsonify({"success": False, "error": "Select Tango mode before reading Andor configuration"}), 400
        device = config["andor_device"]
        args = {"andor_device": device, "readback": "V0Capabilities", "purpose": "BG_level_and_sampling_fingerprint"}
        blocked = require_http_hardware("v0.andor-snapshot", [{"device": device, "command": "V0Capabilities"}], args,
                                        route_id="v0.andor-snapshot", wrapper_fields=set())
        if blocked is not None:
            return blocked
        try:
            response = _tango_proxy(device, timeout_ms=2500).command_inout("V0Capabilities")
            def reject_constant(_value):
                raise ValueError("Andor capability JSON must be finite")
            caps = json.loads(response, parse_constant=reject_constant)
            if not isinstance(caps, dict) or caps.get("schema") != "andor-v0-raw-order-v1":
                raise ValueError("Andor does not expose the V0 RAW capability contract")
            snapshot = {"schema": "v0-andor-capability-snapshot-v1", "device": device,
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "capabilities": caps}
            return jsonify({"success": True, "snapshot": snapshot})
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 503


@pump_probe_v0_api.route("/run", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_run():
    payload = request.get_json(silent=True) or {}
    try:
        if not isinstance(payload, dict):
            raise ValueError("Run request must be an object")
        starting = payload.get("run_action") != "cancel" and bool(payload.get("running", True))
        if _v0_tango_active(payload) and starting:
            fields = {"running", "run_action", "save_path", "sample_name", "plan_fingerprint"}
            if set(payload) - fields:
                raise ValueError("Unknown Tango run request field")
            with _emulator._lock:
                plan = _emulator.prepare_tango_run(payload)
                if payload.get("plan_fingerprint", plan.fingerprint) != plan.fingerprint:
                    return jsonify({"success": False, "error": "Tango run plan changed; refresh its preview",
                                    "code": "v0_run_plan_stale"}), 409
                blocked = require_http_hardware("v0.run", plan.authorization_targets(), plan.authorization_args(),
                                                route_id="v0.run", wrapper_fields=fields)
                if blocked is not None:
                    return blocked
                return jsonify(_emulator.set_running(True, payload, tango_plan=plan))
        return jsonify(_emulator.set_running(payload.get("running", True), payload))
    except TangoProfileNotCommissioned as exc:
        return jsonify({"success": False, "error": str(exc), "code": "hardware_not_authorized"}), (403 if authorization_required() else 409)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/realtime", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_realtime():
    payload = request.get_json(silent=True) or {}
    if _v0_tango_active(payload) and bool(payload.get("enabled", True)):
        if authorization_required():
            return _v0_reject_unbound_tango_sequence()
        blocked = _guard_v0_hardware("v0.realtime", _v0_sequence_args(payload, realtime=True))
        if blocked is not None:
            return blocked
    return jsonify(_emulator.set_real_time(payload.get("enabled", True)))


@pump_probe_v0_api.route("/faraday", methods=["POST"])
def pump_probe_faraday():
    payload = request.get_json(silent=True) or {}
    return jsonify(_emulator.set_faraday(payload.get("closed", True)))


@pump_probe_v0_api.route("/stage/move", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_stage_move():
    try:
        payload = request.get_json(silent=True) or {}
        if _v0_tango_active(payload):
            normalized = _v0_stage_move_args(payload)
            blocked = _guard_v0_hardware("v0.stage-move", normalized)
            if blocked is not None:
                return blocked
            return jsonify(_emulator.move_stage({"position_mm": normalized["position_mm"]}))
        return jsonify(_emulator.move_stage(payload))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/stage/stop", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_stage_stop():
    try:
        if _v0_tango_active():
            blocked = _guard_v0_hardware("v0.stage-stop", _v0_stage_stop_args())
            if blocked is not None:
                return blocked
        return jsonify(_emulator.stop_stage())
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/sample-stage/move", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_sample_stage_move():
    try:
        payload = request.get_json(silent=True) or {}
        if _v0_tango_active(payload):
            normalized = _v0_stage_move_args(payload, sample_stage=True)
            blocked = _guard_v0_hardware("v0.sample-stage-move", normalized)
            if blocked is not None:
                return blocked
            return jsonify(_emulator.move_sample_stage({"position_mm": normalized["position_mm"]}))
        return jsonify(_emulator.move_sample_stage(payload))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/sample-stage/stop", methods=["POST"])
@_serialized_v0_mutation
def pump_probe_sample_stage_stop():
    try:
        if _v0_tango_active():
            blocked = _guard_v0_hardware("v0.sample-stage-stop", _v0_stage_stop_args(sample_stage=True))
            if blocked is not None:
                return blocked
        return jsonify(_emulator.stop_sample_stage())
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/crystal/move", methods=["POST"])
def pump_probe_crystal_move():
    return jsonify(_emulator.move_crystal())


@pump_probe_v0_api.route("/reset", methods=["POST"])
def pump_probe_reset():
    return jsonify(_emulator.reset())


@pump_probe_v0_api.route("/data/list", methods=["GET"])
def pump_probe_data_list():
    try:
        root = _normalize_data_path(_data_root())
        path = _normalize_data_path(request.args.get("path") or root)
        entries = _list_data_path(path)
        entries = sorted(
            entries,
            key=lambda item: (not item.get("is_dir"), str(item.get("name", "")).lower()),
        )
        return jsonify({
            "success": True,
            "root": root,
            "path": path,
            "parent": _parent_data_path(path),
            "entries": entries,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/data/folder", methods=["POST"])
def pump_probe_data_create_folder():
    try:
        payload = request.get_json(silent=True) or {}
        parent = payload.get("parent") or _data_root()
        name = payload.get("name") or ""
        path = _mkdir_data_path(parent, name)
        return jsonify({
            "success": True,
            "root": _normalize_data_path(_data_root()),
            "path": path,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/data/load", methods=["POST"])
def pump_probe_data_load():
    try:
        payload = request.get_json(silent=True) or {}
        path = payload.get("path") or ""
        normalized, file_payload = _read_data_file(path)
        return jsonify(load_payload(normalized, file_payload))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/data/treat", methods=["POST"])
def pump_probe_data_treat():
    """Replay a correction recipe from source; never write acquisition files."""
    try:
        payload = request.get_json(silent=True) or {}
        if payload.get("source_spec") is not None:
            spec = payload["source_spec"]
            sources = _derived_sources(spec)
            dataset, preview = treat_derived_dataset(
                sources, spec["method"], payload.get("operations", []), payload.get("source_sha256"),
            )
            if payload.get("path") != preview["path"]:
                raise ValueError("Derived source identity changed; recreate the dataset")
        else:
            normalized, file_payload = _read_data_file(payload.get("path") or "")
            dataset, preview = treat_dataset(
                normalized, file_payload, payload.get("operations", []), payload.get("source_sha256"),
            )
        return _treatment_response(dataset, preview, payload.get("format"))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


def _derived_sources(spec):
    """Resolve every original file within the data root and verify its bytes."""
    if (not isinstance(spec, dict) or set(spec) != {"kind", "method", "sources"}
            or spec["kind"] != "derived" or spec["method"] not in {"average", "merge"}):
        raise ValueError("Invalid derived source specification")
    entries = spec["sources"]
    if not isinstance(entries, list) or not 2 <= len(entries) <= 32:
        raise ValueError("Select 2..32 source datasets")
    sources = []
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {"path", "source_sha256"}
                or not isinstance(entry["path"], str) or not isinstance(entry["source_sha256"], str)):
            raise ValueError("Each source requires a path and source_sha256")
        normalized, file_payload = _read_data_file(entry["path"])
        if hashlib.sha256(file_payload).hexdigest() != entry["source_sha256"]:
            raise ValueError("Source file changed; reload before deriving or applying corrections")
        sources.append((normalized, file_payload))
    return sources


def _treatment_response(dataset, preview, output_format):
    if output_format == "dat":
        response = Response(export_dat(dataset), mimetype="text/tab-separated-values")
        response.headers["Content-Disposition"] = 'attachment; filename="v0-corrected.dat"'
        return response
    if output_format not in {None, "json"}:
        raise ValueError("Unsupported correction output format")
    return jsonify(preview)


@pump_probe_v0_api.route("/data/derive", methods=["POST"])
def pump_probe_data_derive():
    """Build an explicitly selected multi-file OD dataset without changing RAW."""
    try:
        payload = request.get_json(silent=True) or {}
        spec = {"kind": "derived", "method": payload.get("method"), "sources": payload.get("sources")}
        sources = _derived_sources(spec)
        dataset, preview = derive_dataset(sources, spec["method"])
        operations = payload.get("operations", [])
        if not isinstance(operations, list):
            raise ValueError("Recipe must be a list with at most 32 operations")
        if operations:
            dataset, preview = treat_derived_dataset(
                sources, spec["method"], operations, preview["source_sha256"],
            )
        return _treatment_response(dataset, preview, payload.get("format"))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
