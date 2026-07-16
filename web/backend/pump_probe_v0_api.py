import ast
import math
import os
import random
import json
import shutil
import threading
import time
import zlib
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from flask import Blueprint, jsonify, request

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
    REQUIRED_NETIO_OUTPUTS,
    SIGNAL_RANDOM_COUNTS,
    SPECTROMETER_BURST,
    SPECTROMETER_HZ,
    STAGE_MAX_MM,
    STAGE_MIN_MM,
    STAGE_SPEED_MM_PER_SEC,
)
from pump_probe_v0_data import parse_dat_payload, parse_h5_payload, parse_zip_payload
from pump_probe_v0_storage import RAW_GROUPS, V0EmulatorRunWriter

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


def _starter_for_server(server_name):
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


def _restart_server_for_device(device_name):
    server_name = _server_name_for_device(device_name)
    starter_name, starter, running, _stopped = _starter_for_server(server_name)
    if server_name in running:
        try:
            starter.command_inout("DevStop", server_name)
            time.sleep(2)
        except Exception:
            try:
                starter.command_inout("HardKillServer", server_name)
                time.sleep(2)
            except Exception:
                pass
    try:
        starter.command_inout("DevStart", server_name)
    except Exception as exc:
        text = str(exc).lower()
        if "already_running" not in text and "already running" not in text:
            raise
    time.sleep(2)
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
            kinetics = 0.18 * (1 - math.exp(-(delay + 30) / 42))
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
        frame_count = payload_rows.shape[0] // track_count
        if frame_count < 1:
            raise ValueError("Andor order contains no spectra")
        tracks = payload_rows[: frame_count * track_count].reshape(frame_count, track_count, width)
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

    def _start_emulator_run_locked(self, payload):
        output_dir = str(payload.get("save_path") or "").strip()
        if not output_dir:
            raise ValueError("Choose a data folder before starting an emulator run")
        output_dir = _normalize_data_path(output_dir)
        if not _is_data_path_allowed(output_dir):
            raise ValueError("Run output path is outside pump-probe data root")

        self._reset_locked()
        self._run_output_dir = output_dir
        self._run_sample_name = str(payload.get("sample_name") or "").strip()
        positions = [self._delay_to_mm(delay) for delay in self._delays]
        run_config = {
            "experiment": "V0 DirectLine pump-probe",
            "mode": "emulator",
            "sample_name": self._run_sample_name,
            "settings": dict(self._settings),
            "hardware_config": dict(self._hardware_config),
            "raw_groups": list(RAW_GROUPS),
            "spectrometer": {"rate_hz": SPECTROMETER_HZ, "burst": SPECTROMETER_BURST},
            "accelerator_hz": ACCELERATOR_HZ,
        }
        self._run_writer = V0EmulatorRunWriter(
            self._wavelengths,
            self._delays,
            positions,
            self._settings["pulses_per_point"],
            run_config,
        )
        self._run_status = "running"
        self._run_error = ""
        self._run_artifacts = {}
        self._running = True
        self._real_time = False
        self._last_pulse_update = time.monotonic()

    def _finalize_run_locked(self, status, error=""):
        writer = self._run_writer
        self._running = False
        if writer is None:
            self._run_status = status
            self._run_error = str(error)
            return
        try:
            staged = writer.finalize(status=status, error=error)
            self._run_artifacts = {
                "run_id": staged["run_id"],
                "h5": _publish_data_file(self._run_output_dir, staged["h5_path"]),
                "dat": _publish_data_file(self._run_output_dir, staged["dat_path"]),
                "manifest": _publish_data_file(self._run_output_dir, staged["manifest_path"]),
                "frame_counts": staged["frame_counts"],
            }
            self._run_status = status
            self._run_error = str(error)
        except Exception as exc:
            self._run_status = "fault"
            self._run_error = f"Run storage failed: {exc}"
        finally:
            self._run_writer = None

    def _apply_pulse_locked(self):
        if not self._running and not self._real_time:
            return

        if self._running and self._run_writer is not None:
            if abs(self._set_position_mm - self._position_mm) > 0.0005:
                return
            try:
                frames = self._emulator_raw_cycle_locked(self._current_index)
                self._total_pulses += 1
                self._spectrometer_frames += len(frames)
                self._live_od = self._run_writer.record_cycle(
                    self._current_index,
                    frames,
                    self._set_position_mm,
                    self._position_mm,
                )
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
            self._set_position_mm = self._delay_to_mm(self._delays[self._current_index])
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
            self._sync_locked()
            self._sync_sample_stage_locked()
            if self._running and self._run_writer is not None:
                raise RuntimeError("Stop the active run before changing scan settings")
            self._configure_hardware_locked(payload)
            if "delay_points_ps" in payload:
                raw_delays = payload["delay_points_ps"]
                if raw_delays:
                    delays = [float(value) for value in raw_delays]
                    delays = delays[:400]
                    self._settings["delay_points_ps"] = delays
                    self._settings["point_count"] = len(delays)
                    self._settings["scan_start_ps"] = delays[0]
                    if len(delays) > 1:
                        self._settings["delay_step_ps"] = delays[1] - delays[0]
                        self._settings["scan_span_ps"] = delays[-1] - delays[0]
                else:
                    self._settings["delay_points_ps"] = None
            for key in ("point_count", "scan_start_ps", "delay_step_ps", "scan_span_ps", "pulses_per_point", "real_zero_ps"):
                if key not in payload:
                    continue
                if key in ("point_count", "pulses_per_point"):
                    self._settings[key] = max(1, int(payload[key]))
                else:
                    self._settings[key] = float(payload[key])
                if key in ("point_count", "scan_start_ps", "delay_step_ps"):
                    self._settings["delay_points_ps"] = None
            self._settings["point_count"] = _clamp(self._settings["point_count"], 2, 400)
            self._settings["pulses_per_point"] = _clamp(self._settings["pulses_per_point"], 1, 200)
            if not self._settings.get("delay_points_ps"):
                self._settings["scan_span_ps"] = (int(self._settings["point_count"]) - 1) * float(self._settings["delay_step_ps"])
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

    def set_running(self, running, payload=None):
        with self._lock:
            self._sync_locked()
            next_running = bool(running)
            payload = payload or {}
            if not next_running and self._run_writer is not None:
                self._finalize_run_locked("stopped")
                return self.state()
            if next_running and self._control_mode_locked() == "emulator":
                if self._run_writer is None:
                    self._start_emulator_run_locked(payload)
                return self.state()
            if next_running and self._control_mode_locked() == "tango":
                self._preflight_dg645_locked()
            self._running = next_running
            if next_running:
                self._real_time = False
            self._last_pulse_update = time.monotonic()
            return self.state()

    def set_real_time(self, enabled):
        with self._lock:
            self._sync_locked()
            self._real_time = bool(enabled)
            self._last_pulse_update = time.monotonic()
            return self.state()

    def set_faraday(self, closed):
        with self._lock:
            self._sync_locked()
            self._faraday_closed = bool(closed)
            return self.state()

    def move_stage(self, payload):
        with self._lock:
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
            self._sync_locked()
            if self._control_mode_locked() == "tango":
                self._stop_owis_axis_locked(self._hardware_config["delay_line_axis"])
            self._set_position_mm = self._position_mm
            return self.state()

    def move_sample_stage(self, payload):
        with self._lock:
            self._sync_sample_stage_locked()
            position = _clamp(float(payload.get("position_mm", self._sample_set_position_mm)), 0.0, 150.0)
            if self._control_mode_locked() == "tango":
                self._move_owis_axis_locked(self._hardware_config["sample_stage_axis"], position)
            self._sample_set_position_mm = position
            return self.state()

    def stop_sample_stage(self):
        with self._lock:
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

    def _check_device(self, label, device_name, fix=False):
        try:
            server_name = _server_name_for_device(device_name)
            proxy = _tango_proxy(device_name, timeout_ms=5000)
            state = str(proxy.state())
            ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
            if not ok and fix:
                repair = _restart_server_for_device(device_name)
                proxy = _tango_proxy(device_name, timeout_ms=5000)
                state = str(proxy.state())
                ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
                return (_json_ok if ok else _json_fail)(
                    label,
                    f"state={state}",
                    device=device_name,
                    server=server_name,
                    repair=repair,
                )
            return (_json_ok if ok else _json_fail)(label, f"state={state}", device=device_name, server=server_name)
        except Exception as exc:
            repair = None
            if fix:
                try:
                    repair = _restart_server_for_device(device_name)
                    proxy = _tango_proxy(device_name, timeout_ms=5000)
                    state = str(proxy.state())
                    ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
                    return (_json_ok if ok else _json_fail)(
                        label,
                        f"state={state}",
                        device=device_name,
                        repair=repair,
                    )
                except Exception as repair_exc:
                    return _json_fail(label, repair_exc, device=device_name, repair=repair)
            return _json_fail(label, exc, device=device_name)

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
            index = ids.index(output_id) if output_id in ids else output_id - 1
            state = int(states[index]) if 0 <= index < len(states) else 0
            name = names[index] if 0 <= index < len(names) else f"Output {output_id}"
            if state != 1 and fix:
                next_states = list(states)
                while len(next_states) <= index:
                    next_states.append(0)
                next_states[index] = 1
                proxy.command_inout("set_channels_states", next_states)
                time.sleep(0.5)
                _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
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

    def _check_owis_axes(self, fix=False):
        checks = []
        aggregator = self._hardware_config["owis_aggregator_device"]
        backend = self._hardware_config["owis_backend_device"]
        axes = [
            ("Sample holder V0 axis", int(self._hardware_config["sample_stage_axis"])),
            ("Delay line long axis", int(self._hardware_config["delay_line_axis"])),
        ]
        checks.append(self._check_device("OWIS aggregator", aggregator, fix=fix))
        checks.append(self._check_device("OWIS backend", backend, fix=fix))
        for label, axis in axes:
            try:
                proxy = _tango_proxy(backend, timeout_ms=5000)
                state = str(proxy.command_inout("get_status_axis", axis))
                position = float(proxy.command_inout("read_position_axis", axis))
                ok = "FAULT" not in state.upper() and "ERROR" not in state.upper()
                if not ok and fix:
                    try:
                        proxy.command_inout("turn_on_axis", axis)
                        time.sleep(0.5)
                        state = str(proxy.command_inout("get_status_axis", axis))
                        ok = "FAULT" not in state.upper() and "ERROR" not in state.upper()
                    except Exception:
                        pass
                checks.append((_json_ok if ok else _json_fail)(label, f"axis {axis}: {state}, {position:.4f} mm", axis=axis))
            except Exception as exc:
                checks.append(_json_fail(label, exc, axis=axis))
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

    def hardware_preflight(self, fix=False):
        with self._lock:
            self._sync_locked()
            checks = []
            checks.extend(self._check_owis_axes(fix=fix))
            checks.append(self._check_device("Andor UV-visible detector", self._hardware_config["andor_device"], fix=fix))
            checks.append(self._check_device("DAQmx card", self._hardware_config["daqmx_device"], fix=fix))
            checks.append(self._check_device("DG645 Tango server", self._hardware_config["dg645_device"], fix=fix))
            for item in REQUIRED_NETIO_OUTPUTS:
                checks.append(self._check_netio_output(item, fix=fix))
            checks.append(self._check_dg645_recall(apply_recall=fix))
            checks.append(self._check_counter_activity())
            ok = all(check.get("ok") for check in checks)
            return {
                "success": ok,
                "fixed": bool(fix),
                "message": "Hardware initialized" if ok else "Hardware initialization failed",
                "recommendation": "" if ok else "Use auto-fix once. If this still fails, restart the Windows/Tango computer.",
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
            if self._run_writer is not None:
                self._finalize_run_locked("aborted", "Reset requested")
            self._reset_locked()
            self._run_status = "idle"
            self._run_error = ""
            return self.state()

    def state(self):
        with self._lock:
            self._sync_locked()
            self._sync_sample_stage_locked()
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
                "daq_counter": self._counter_status_locked() if self._control_mode_locked() == "tango" else {
                    "value": None,
                    "rate_hz": 0.0,
                    "active": False,
                    "error": "",
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
                    "raw_groups": list(RAW_GROUPS),
                },
                "wavelengths": self._wavelengths,
                "delays": self._delays,
                "heatmap": self._heatmap,
                "live_od": self._live_od,
                "spectra": self._last_spectra,
            }
            return self._read_tango_motion_state_locked(state)


_emulator = PumpProbeV0Controller()


@pump_probe_v0_api.route("/state", methods=["GET"])
def pump_probe_state():
    return jsonify(_emulator.state())


@pump_probe_v0_api.route("/config", methods=["POST"])
def pump_probe_configure():
    return jsonify(_emulator.configure(request.get_json(silent=True) or {}))


@pump_probe_v0_api.route("/hardware-config", methods=["GET", "POST"])
def pump_probe_hardware_config():
    if request.method == "POST":
        return jsonify(_emulator.configure(request.get_json(silent=True) or {}))
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
        return jsonify(_emulator.hardware_preflight(fix=True))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/run", methods=["POST"])
def pump_probe_run():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(_emulator.set_running(payload.get("running", True), payload))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/realtime", methods=["POST"])
def pump_probe_realtime():
    payload = request.get_json(silent=True) or {}
    return jsonify(_emulator.set_real_time(payload.get("enabled", True)))


@pump_probe_v0_api.route("/faraday", methods=["POST"])
def pump_probe_faraday():
    payload = request.get_json(silent=True) or {}
    return jsonify(_emulator.set_faraday(payload.get("closed", True)))


@pump_probe_v0_api.route("/stage/move", methods=["POST"])
def pump_probe_stage_move():
    try:
        return jsonify(_emulator.move_stage(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/stage/stop", methods=["POST"])
def pump_probe_stage_stop():
    try:
        return jsonify(_emulator.stop_stage())
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/sample-stage/move", methods=["POST"])
def pump_probe_sample_stage_move():
    try:
        return jsonify(_emulator.move_sample_stage(request.get_json(silent=True) or {}))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_v0_api.route("/sample-stage/stop", methods=["POST"])
def pump_probe_sample_stage_stop():
    try:
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
        suffix = _data_file_suffix(normalized)
        if suffix == ".dat":
            return jsonify(parse_dat_payload(normalized, file_payload))
        if suffix == ".zip":
            return jsonify(parse_zip_payload(normalized, file_payload))
        if suffix in {".h5", ".hdf5"}:
            return jsonify(parse_h5_payload(normalized, file_payload))
        raise ValueError("Only .dat, .zip, and V0 .h5 files can be loaded")
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
