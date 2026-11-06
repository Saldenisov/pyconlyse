"""Narrow control API for the VD2 streak-camera pump-probe experiment."""

from __future__ import annotations

import ast
import base64
import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Mapping

from flask import Blueprint, jsonify, request
from tango import DevState, DeviceProxy

from hardware_authorization import authorization_required, require_http_hardware
from mutation_auth import install_mutation_auth
from vd2_workspace_api import install_workspace_routes
from experiment_readiness import EXPERIMENT_MUTATION_LOCK, recover_device, start_managed_server, stop_managed_server as stop_managed_server
from experiment_lifecycle import ExperimentLifecycle
from vd2_measurement_protocol import PhaseRequest, Vd2MeasurementProtocol, Vd2ProtocolError
from vd2_sequence_processing import check_new_sequence, process_saved_sequence_in_worker, retire_source_his
from vd2_project_manifest import MANIFEST_NAME, Vd2ProjectManifest, inspect_project
from vd2_phase_destination import PhaseDestinations
from vd2_live_acquisition import SEQUENCE_TIMEOUT_S, SEQUENCE_WAIT_QUERY, camera_serialization_timeout, wait_for_sequence
from vd2_alignment import read_alignment_axes, image_alignment_settings, image_intensity_settings, alignment_calibration_key, alignment_measurement_key
from vd2_alignment_readout import AlignmentReadout, READOUT_VERSION, parse_selection
from vd2_dg645_timing import apply_timing, timing_for_range, verify_timing
from vd2_recovery import RecoverySnapshots, PARAMETERS as RECOVERY_PARAMETERS, settings_from_state, equivalent
from vd2_alignment_presets import (AlignmentSnapshots, CHANNELS as ALIGNMENT_CHANNELS,
                                  DEVICE as ALIGNMENT_DEVICE, SnapshotConflict,
                                  device_name as alignment_device_name, validate_intent)

pump_probe_vd2_api = Blueprint(
    "pump_probe_vd2_api", __name__, url_prefix="/api/pump-probe-vd2"
)
install_mutation_auth(pump_probe_vd2_api)
install_workspace_routes(pump_probe_vd2_api)
_preparation_lock = EXPERIMENT_MUTATION_LOCK
_lifecycle_factory_lock = Lock()
_lifecycle_instance = None


def _recovery_snapshots():
    path = os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or str(
        Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3")
    return RecoverySnapshots(path)


def _remember_camera(state, kind="previous", ui=None):
    try:
        job = _lifecycle_instance.get("job") if _lifecycle_instance is not None else None
        if job and job.get("operation") == "prepare" and job.get("status") in {"failed", "interrupted"}:
            raise ValueError("Preparation/restoration is incomplete; earlier return points are retained")
        settings = settings_from_state(state, _live_average_readback)
        return _recovery_snapshots().capture(settings, kind, ui)
    except Exception as exc:
        # Persistence cannot turn a valid camera read into a transport fault.
        # Keep the previous good record and expose the failed save separately.
        state["recovery_warning"] = f"Camera return point was not saved: {exc}"
        return None


def _remember_measurement_point(measurement, machine_after):
    state = (machine_after or {}).get("streak_control", {})
    settings = settings_from_state(state, (machine_after or {}).get("live_rolling_average"))
    ui = {"tab": "acquisition", "form": {
        "outputRoot": measurement.output_root, "runName": measurement.run_name,
        "framesPerHis": str(measurement.frames_per_his), "sampleDescription": measurement.sample_description,
        "reuseBruit": "none" if measurement.reuse_bruit == "none" else "latest"}}
    return _recovery_snapshots().capture(settings, "point", ui)


def _alignment_snapshots():
    # Share the durable application DB without constructing ExperimentLifecycle,
    # whose startup recovery must not run during a snapshot request.
    path = (os.environ.get("PYCONLYSE_ALIGNMENT_STATE_DB") or
            os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or
            str(Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3"))
    return AlignmentSnapshots(path)


def _alignment_current_snapshot():
    proxy = DeviceProxy(ALIGNMENT_DEVICE)
    proxy.set_timeout_millis(5000)
    attributes = ("names", "ids", "states", "currents_setpoint", "currents_meas", "current_limits")
    values = {}
    for name, attribute in zip(attributes, proxy.read_attributes(list(attributes))):
        failed = getattr(attribute, "has_failed", False)
        if failed() if callable(failed) else failed:
            raise RuntimeError(f"iTest {name} read failed; settings were not saved")
        values[name] = list(attribute.value)
    def canonical(name):
        return "".join(char for char in str(name).lower() if char.isalnum())
    result = []
    for name in ALIGNMENT_CHANNELS:
        matches = [index for index, label in enumerate(values["names"]) if canonical(label) == canonical(name)]
        if len(matches) != 1:
            raise RuntimeError(f"Cannot uniquely identify {name}")
        index = matches[0]
        def scalar(key, offset=index):
            value = values[key][offset]
            return value.item() if hasattr(value, "item") else value
        result.append({"id": scalar("ids"), "name": name, "state": scalar("states"),
                       "value": scalar("currents_setpoint"), "measured": scalar("currents_meas"),
                       "min": scalar("current_limits", index * 2), "max": scalar("current_limits", index * 2 + 1)})
    return result


@pump_probe_vd2_api.route("/alignment/snapshots", methods=["GET", "POST"])
def alignment_snapshots():
    if request.method == "GET":
        try:
            device = alignment_device_name(request.args.get("device", ALIGNMENT_DEVICE))
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400
        try:
            return jsonify(success=True, **_alignment_snapshots().history(device))
        except Exception as exc:
            return jsonify(success=False, error=f"Alignment database unavailable: {exc}"), 503
    if (request.content_length or 0) > 32768:
        return jsonify(success=False, error="Alignment snapshot request is too large"), 413
    try:
        payload = json.loads(request.get_data(cache=True, as_text=True),
                             object_pairs_hook=_reject_duplicate_json_keys,
                             parse_constant=_reject_nonfinite_json)
        intent = validate_intent(payload)
    except (TypeError, ValueError) as exc:
        return jsonify(success=False, error=str(exc)), 400
    try:
        repository = _alignment_snapshots()
        existing = repository.preflight(intent)
        if existing:
            return jsonify(success=True, snapshot=existing)
        # Only attribute reads. Saving cannot set currents or enable outputs.
        snapshot = repository.capture(intent, _alignment_current_snapshot())
        return jsonify(success=True, snapshot=snapshot), 201
    except SnapshotConflict as exc:
        return jsonify(success=False, error=str(exc)), 409
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 409
    except Exception as exc:
        return jsonify(success=False, error=f"Settings were not saved: {exc}"), 503


def _lifecycle():
    global _lifecycle_instance
    with _lifecycle_factory_lock:
        if _lifecycle_instance is None:
            path = os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or str(
                Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3"
            )
            _lifecycle_instance = ExperimentLifecycle(path)
        return _lifecycle_instance


def _progress(steps, detail, stage=1, wait_until=None):
    publish = getattr(steps, "phase", None)
    if publish:
        publish(detail, stage=stage, wait_until=wait_until)


def _start_lifecycle(operation, action, intent=None):
    lifecycle = _lifecycle()
    if not _preparation_lock.acquire(blocking=False):
        job = lifecycle.snapshot()
        if job["status"] == "running" and job.get("operation") == operation:
            if intent is not None and job.get("intent") != intent:
                return jsonify(success=False, error="Prepare is already running with another return point; follow its current progress", job=job), 409
            return jsonify({"success": True, "job": job, "attached": True}), 202
        return jsonify({"success": False, "error": _vd2_busy_message(job), "job": job}), 409
    try:
        def execute(steps):
            try:
                return action(steps)
            except AlreadyPrepared as exc:
                # Synchronous POST retains its 409 contract. A durable Prepare
                # that verified every dependency has completed successfully.
                return {**exc.result, "already_ready": True,
                        "message": exc.result.get("message") or str(exc)}
            except Exception as exc:
                raise PreparationFailure(_control_error(exc), getattr(exc, "steps", steps)) from exc
        if intent is None:
            job = lifecycle.start(operation, execute, _preparation_lock.release)
        else:
            job = lifecycle.start(operation, execute, _preparation_lock.release, intent=intent)
        return jsonify({"success": True, "job": job}), 202
    except Exception as exc:
        _preparation_lock.release()
        return jsonify({"success": False, "error": _control_error(exc)}), 503


def _vd2_busy_message(job=None):
    job = job if job is not None else (_lifecycle_instance.snapshot() if _lifecycle_instance else {})
    return ("VD2 preparation/shutdown is already in progress" if job.get("status") == "running"
            else "VD2 control is busy with another camera read or command; wait for it to finish")


def _serialized_vd2_mutation(function):
    """Prevent a new acquisition/parameter write from racing power-down."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not _preparation_lock.acquire(blocking=False):
            return jsonify(success=False, code="VD2_CONTROL_LOCKED", error=_vd2_busy_message()), 409
        try:
            return function(*args, **kwargs)
        finally:
            _preparation_lock.release()
    return wrapped

STREAK_DEVICE = "manip/camera/hamamatsu_streak_main"
DG645_DEVICE = "manip/sync/DG645"
DG645_POWER_UP_TIMEOUT_S = 180.0
VD2_PDU_DEVICE = "manip/SD2/PDU_SD2"
ZABER_PDU_DEVICE = "manip/VD2/PDU_VD2"
ZABER_STAGE_DEVICE = "manip/VD2/Zaber"
ZABER_FLASH_LAMP_MM = 0.0
ZABER_PRESET_TOLERANCE_MM = 0.05
OWIS_SAMPLE_DEVICE = "manip/general/DS_OWIS_PS90_IP"
OWIS_SAMPLE_AXIS = 2
OWIS_CONTROLLER_DEVICE = "manip/general/DS_OWIS_PS90_IP"
OWIS_LEGACY_DEVICE = "manip/general/DS_OWIS_PS90"
OWIS_PDU_DEVICE = "manip/V0/PDU_VO"
OWIS_DEVICES = frozenset({OWIS_CONTROLLER_DEVICE, OWIS_LEGACY_DEVICE, OWIS_SAMPLE_DEVICE})
VD2_DG645_RECALL_SLOT = 9
KYMERA_DEVICE = "manip/CR/ANDOR_KYMERA1"
RETAINED_INSTRUMENT_SERVERS = OWIS_DEVICES | {DG645_DEVICE, KYMERA_DEVICE}
ASTOR_DEVICE = "tango/admin/everest"
ELYSIUM_ASTOR_DEVICE = "tango/admin/elysium2"

VD2_SERVERS = {
    VD2_PDU_DEVICE: "DS_Netio_pdu/4_SD2",
    ZABER_PDU_DEVICE: "DS_Netio_pdu/2_VD2",
    OWIS_PDU_DEVICE: "DS_Netio_pdu/1_V0",
    OWIS_CONTROLLER_DEVICE: "DS_OWIS_PS90/2_IP",
    OWIS_LEGACY_DEVICE: "DS_OWIS_PS90/1",
    ZABER_STAGE_DEVICE: "DS_Zaber/1_Zaber",
    DG645_DEVICE: "DS_DG645/1_DG645",
    STREAK_DEVICE: "DS_HAMAMATSU_STREAK/1_hamamatsu_streak_main",
    KYMERA_DEVICE: "DS_ANDOR_SPECTROGRAPH/2_ANDOR_KYMERA1",
}
SD2_REQUIRED_PDU_OUTPUTS = {
    1: "Streak camera / spectrograph",
    2: "DG645",
    3: "Power control",
}
# Shutdown retains the control supply; preparation must always verify it is ON.
VD2_SHUTDOWN_PDU_OUTPUTS = {1: "Streak camera / spectrograph", 2: "DG645"}
VD2_REQUIRED_PDU_OUTPUTS = {
    1: "Flash Lamp",
    2: "Xe-lamp-CW",
    3: "Zaber",
}
# Xe outlet powers cooling, not a safe remote lamp-off control. The lamp must
# be switched off physically; Unprepare must never remove its cooling power.
VD2_LAMP_SHUTDOWN_OUTPUTS = {1: "Flash Lamp"}
VD2_RETAINED_PDU_OUTPUTS = {2: "Xe lamp cooling supply", 3: "Zaber always-on supply"}
OWIS_REQUIRED_PDU_OUTPUTS = {2: "OWIS controller (VD2 sample axis 2)"}

READ_ATTRIBUTES = {
    "connected": "connected",
    "application_running": "application_running",
    "remoteex_status": "remoteex_status",
    "time_range": "time_range",
    "streak_mode": "streak_mode",
    "gate_mode": "gate_mode",
    "mcp_gain": "mcp_gain_text",
    "streak_shutter": "streak_shutter",
    "streak_trigger_mode": "streak_trig_mode",
    "streak_trigger_status": "streak_trigger_status",
    "focus_time_over": "focus_time_over",
    "wavelength_nm": "wavelength_nm",
    "grating": "grating",
    "blaze": "blaze",
    "ruling": "ruling",
    "exit_mirror": "exit_mirror",
    "turret": "turret",
    "slit_width_um": "slit_width_um",
    "spectrograph_shutter": "spectrograph_shutter",
    "focus_mirror": "focus_mirror",
    "side_entry_iris": "side_entry_iris",
    "delay_trigger_mode": "delay_trig_mode",
    "delay_repetition_rate": "delay_repetition_rate",
    "delay_setting": "delay_setting",
    "delay_a": "delay_a",
    "delay_b": "delay_b",
    "delay_c": "delay_c",
    "delay_d": "delay_d",
    "delay_e": "delay_e",
    "delay_f": "delay_f",
    "delay_g": "delay_g",
    "delay_h": "delay_h",
    "delay_ss_trigger": "delay_ss_trigger",
    "delay_burst_mode": "delay_burst_mode",
    "delay_manual_control": "delay_manual_control",
    "live_exposure_time": "live_exposure_time",
    "acquire_exposure_time": "acquire_exposure_time",
    "analog_integration_count": "analog_integration_count",
    "sequence_loops": "sequence_loops",
}


def _string(value: Any) -> str:
    return str(value).strip()


def _number(value: Any) -> float:
    return float(value)


WRITABLE_PARAMETERS: Dict[str, Dict[str, Any]] = {
    "time_range": {"attribute": "time_range", "coerce": _string},
    "streak_mode": {"attribute": "streak_mode", "coerce": _string},
    "gate_mode": {"attribute": "gate_mode", "coerce": _string},
    "streak_shutter": {"attribute": "streak_shutter", "coerce": _string},
    "streak_trigger_mode": {"attribute": "streak_trig_mode", "coerce": _string},
    "focus_time_over": {"attribute": "focus_time_over", "coerce": _string},
    "wavelength_nm": {"attribute": "wavelength_nm", "coerce": _number},
    "grating": {"attribute": "grating", "coerce": _string},
    "exit_mirror": {"attribute": "exit_mirror", "coerce": _string},
    "turret": {"attribute": "turret", "coerce": _string},
    "slit_width_um": {"attribute": "slit_width_um", "coerce": _number},
    "spectrograph_shutter": {"attribute": "spectrograph_shutter", "coerce": _string},
    "focus_mirror": {"attribute": "focus_mirror", "coerce": _string},
    "side_entry_iris": {"attribute": "side_entry_iris", "coerce": _string},
    "delay_trigger_mode": {"attribute": "delay_trig_mode", "coerce": _string},
    "delay_repetition_rate": {"attribute": "delay_repetition_rate", "coerce": _string},
    "delay_setting": {"attribute": "delay_setting", "coerce": _string},
    "delay_a": {"attribute": "delay_a", "coerce": _string},
    "delay_b": {"attribute": "delay_b", "coerce": _string},
    "delay_c": {"attribute": "delay_c", "coerce": _string},
    "delay_d": {"attribute": "delay_d", "coerce": _string},
    "delay_e": {"attribute": "delay_e", "coerce": _string},
    "delay_f": {"attribute": "delay_f", "coerce": _string},
    "delay_g": {"attribute": "delay_g", "coerce": _string},
    "delay_h": {"attribute": "delay_h", "coerce": _string},
    "delay_burst_mode": {"attribute": "delay_burst_mode", "coerce": _string},
    "delay_manual_control": {"attribute": "delay_manual_control", "coerce": _string},
    "live_exposure_time": {"attribute": "live_exposure_time", "coerce": _string},
    "acquire_exposure_time": {"attribute": "acquire_exposure_time", "coerce": _string},
    "analog_integration_count": {"attribute": "analog_integration_count", "coerce": _string},
    "sequence_loops": {"attribute": "sequence_loops", "coerce": _string},
    "mcp_gain": {"command": "SetMCPGain", "coerce": _string},
}

ALLOWED_COMMANDS = {
    "Connect",
    "Disconnect",
    "RefreshStatus",
    "StartApplication",
    "StopApplication",
    "ShutdownRemoteEx",
    "StartRemoteEx",
    "StopRemoteEx",
    "PrepareDG645ForHPDTA",
    "StartLive",
    "AcquireSingle",
    "Acquire",
    "StartAnalogIntegration",
    "StartSequence",
    "StopAcquisition",
    "StopSequence",
}


def _proxy() -> DeviceProxy:
    proxy = DeviceProxy(STREAK_DEVICE)
    proxy.set_timeout_millis(15000)
    return proxy


_measurement_protocol = Vd2MeasurementProtocol(
    _proxy, processing_worker=process_saved_sequence_in_worker, artifact_preflight=check_new_sequence,
    wait_for_idle=wait_for_sequence,
    artifact_journal=Vd2ProjectManifest(), snapshot_reader=lambda proxy: _machine_snapshot(proxy),
    artifact_finalizer=retire_source_his,
    point_recorder=_remember_measurement_point,
)
_phase_destinations = PhaseDestinations()


def _protocol_hardware_phase():
    value = _measurement_protocol.status()
    if type(value.get("acquisition_active")) is bool:
        return value.get("acquisition_phase", "acquiring") if value["acquisition_active"] else "idle"
    # Compatibility with older protocol providers: an unqualified processing
    # state does not prove that camera ownership has been released.
    return value.get("status")
_alignment_axes = None
_alignment_axes_lock = Lock()
_alignment_image_path = Path.home() / ".pyconlyse" / "vd2_alignment" / "current.img"
_live_average_readback = None
_preview_lock = Lock()
_alignment_readout = AlignmentReadout()
_preview_cache = None
_preview_cache_until = 0.0
_preview_period = 0.18


def _target(device: str, command: str) -> dict[str, str]:
    """Return one exact Tango command/attribute target for authorization."""
    return {"device": device, "command": command}


def _recovery_command(device: str) -> str:
    return "Reconnect" if device == ZABER_STAGE_DEVICE else "recover"


def _server_recovery_targets(device: str) -> list[dict[str, str]]:
    """Potential recovery calls in the order used by ``_ensure_server``."""
    astor = ELYSIUM_ASTOR_DEVICE if device == ZABER_STAGE_DEVICE else ASTOR_DEVICE
    if device in RETAINED_INSTRUMENT_SERVERS:
        return [_target(device, "recover"), _target(device, "turn_on"), _target(astor, "DevStart")]
    return [
        _target(device, _recovery_command(device)),
        _target(device, "Init"),
        _target(device, "turn_on"),
        _target(astor, "DevStop"),
        _target(astor, "DevStart"),
    ]


def _server_arguments() -> dict[str, str]:
    # USB axis 4 remains available to explicit diagnostics, but is not used by VD2.
    return {device: server for device, server in VD2_SERVERS.items() if device != OWIS_LEGACY_DEVICE}


def _recovery_plan(*devices: str) -> list[dict[str, Any]]:
    """Bind every possible Astor server argument to its ordered recovery plan."""
    return [
        {
            "device": device,
            "server": VD2_SERVERS[device],
            "commands": [
                _recovery_command(device), "Init", "turn_on", "DevStop", "DevStart"
            ] if device not in RETAINED_INSTRUMENT_SERVERS else ["recover", "turn_on", "DevStart"],
        }
        for device in devices
    ]


def _approval_or_response(
    action: str,
    targets: list[dict[str, str]],
    args: Any,
    route_id: str,
    wrapper_fields: set[str],
):
    """Fail before a Tango proxy, worker, or other hardware side effect exists."""
    return require_http_hardware(
        action=action,
        targets=targets,
        args=args,
        route_id=route_id,
        wrapper_fields=wrapper_fields,
    )


def _reject_duplicate_json_keys(pairs):
    payload = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate JSON key")
        payload[key] = value
    return payload


def _reject_nonfinite_json(value):
    raise ValueError(f"non-finite JSON value: {value}")


def _invalid_hardware_request():
    return jsonify(
        {
            "success": False,
            "error": "Hardware request is invalid",
            "code": "hardware_approval_invalid",
        }
    ), 409


def _exact_plan_required():
    """Fail closed when a conditional workflow cannot bind exact side effects."""
    return jsonify(
        {
            "success": False,
            "error": "This workflow requires an exact precomputed hardware plan",
            "code": "hardware_not_authorized",
        }
    ), 403


def _mutation_payload(wrapper_fields: set[str]):
    """Read a mutation envelope before it can reach a proxy or authorization.

    Enforcement uses a duplicate- and non-finite-safe parser.  Local opt-out
    keeps Flask's permissive JSON decoding for existing development clients.
    """
    raw = request.get_data(cache=True, as_text=True)
    if authorization_required():
        try:
            payload = {} if not raw.strip() else json.loads(
                raw,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_nonfinite_json,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, _invalid_hardware_request()
        if not isinstance(payload, Mapping) or set(payload) != wrapper_fields:
            return None, _invalid_hardware_request()
        return dict(payload), None

    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        return None, _invalid_hardware_request()
    return dict(payload), None


def _initialize_authorization() -> tuple[list[dict[str, str]], dict[str, Any]]:
    targets = _server_recovery_targets(VD2_PDU_DEVICE)
    targets.extend(_server_recovery_targets(ZABER_PDU_DEVICE))
    targets.extend(_server_recovery_targets(OWIS_PDU_DEVICE))
    targets.append(_target(VD2_PDU_DEVICE, "set_channels_states"))
    targets.append(_target(ZABER_PDU_DEVICE, "set_channels_states"))
    targets.append(_target(OWIS_PDU_DEVICE, "set_channels_states"))
    targets.extend(_server_recovery_targets(ZABER_STAGE_DEVICE))
    targets.extend(_server_recovery_targets(DG645_DEVICE))
    targets.append(_target(DG645_DEVICE, "scpi_write"))
    targets.extend(_server_recovery_targets(OWIS_CONTROLLER_DEVICE))
    targets.append(_target(OWIS_SAMPLE_DEVICE, "turn_on_axis"))
    targets.extend(_server_recovery_targets(STREAK_DEVICE))
    targets.extend(_server_recovery_targets(KYMERA_DEVICE))
    targets.extend(
        [
            _target(STREAK_DEVICE, "PrepareDG645ForHPDTA"),
            _target(STREAK_DEVICE, "StartRemoteEx"),
            _target(STREAK_DEVICE, "StartApplication"),
            _target(STREAK_DEVICE, "PrepareVD2Startup"),
            _target(STREAK_DEVICE, "write_attribute:streak_shutter"),
            _target(STREAK_DEVICE, "write_attribute:spectrograph_shutter"),
            _target(STREAK_DEVICE, "StopApplication"),
            _target(STREAK_DEVICE, "StopRemoteEx"),
            _target(KYMERA_DEVICE, "PrepareVD2Grating"),
            _target(KYMERA_DEVICE, "turn_off"),
            _target(ASTOR_DEVICE, "DevStop"),
        ]
    )
    return targets, {
        "servers": _server_arguments(),
        "recovery_plan": _recovery_plan(
            VD2_PDU_DEVICE, ZABER_PDU_DEVICE, OWIS_PDU_DEVICE,
            DG645_DEVICE, OWIS_CONTROLLER_DEVICE,
            ZABER_STAGE_DEVICE, STREAK_DEVICE, KYMERA_DEVICE,
        ),
        "pdu_output_states": [
            {"device": VD2_PDU_DEVICE, "output_id": output_id, "state": 1}
            for output_id in sorted(SD2_REQUIRED_PDU_OUTPUTS)
        ] + [
            {"device": ZABER_PDU_DEVICE, "output_id": output_id, "state": 1}
            for output_id in sorted(VD2_REQUIRED_PDU_OUTPUTS)
        ] + [
            {"device": OWIS_PDU_DEVICE, "output_id": output_id, "state": 1}
            for output_id in sorted(OWIS_REQUIRED_PDU_OUTPUTS)
        ],
        "dg645_commands": [f"*RCL {VD2_DG645_RECALL_SLOT}", "BURM 0"],
        "dg645_timing": timing_for_range("1 us").as_dict(),
        "owis_axis": OWIS_SAMPLE_AXIS,
        "kymera_grating": 2,
    }


def _deinitialize_authorization() -> tuple[list[dict[str, str]], dict[str, Any]]:
    targets = [
        _target(STREAK_DEVICE, "StopAcquisition"),
        _target(STREAK_DEVICE, "write_attribute:streak_shutter"),
        _target(STREAK_DEVICE, "write_attribute:spectrograph_shutter"),
        _target(STREAK_DEVICE, "write_attribute:streak_mode"),
        _target(STREAK_DEVICE, "StopApplication"),
        _target(STREAK_DEVICE, "StopRemoteEx"),
        _target(ZABER_STAGE_DEVICE, "Stop"),
        _target(OWIS_SAMPLE_DEVICE, "stop_axis"),
        _target(KYMERA_DEVICE, "turn_off"),
    ]
    targets.extend(_server_recovery_targets(VD2_PDU_DEVICE))
    targets.extend(_server_recovery_targets(ZABER_PDU_DEVICE))
    targets.append(_target(VD2_PDU_DEVICE, "set_channels_states"))
    targets.append(_target(ZABER_PDU_DEVICE, "set_channels_states"))
    return targets, {
        "servers": _server_arguments(),
        "recovery_plan": _recovery_plan(VD2_PDU_DEVICE, ZABER_PDU_DEVICE),
        "pdu_output_states": [
            {"device": ZABER_PDU_DEVICE, "output_id": output_id, "state": 0}
            for output_id in VD2_LAMP_SHUTDOWN_OUTPUTS
        ] + [
            {"device": VD2_PDU_DEVICE, "output_id": output_id, "state": 0}
            for output_id in (2, 1)
        ],
        "shutters": {
            "streak_shutter": "Closed",
            "spectrograph_shutter": "Closed",
        },
        "streak_mode": "Focus",
        "retained_power": [
            {"device": ZABER_PDU_DEVICE, "output_id": 2, "reason": "Xe lamp cooling; physical lamp-off required"},
            {"device": ZABER_PDU_DEVICE, "output_id": 3, "reason": "Zaber always-on supply"},
            {"device": OWIS_PDU_DEVICE, "output_id": 2, "reason": "shared V0/VD2 controller"},
            {"device": VD2_PDU_DEVICE, "output_id": 3, "reason": "control supply"},
        ],
    }


def _protocol_authorization(request_data: PhaseRequest) -> tuple[list[dict[str, str]], dict[str, Any]]:
    return [
        _target(STREAK_DEVICE, "write_attribute:sequence_loops"),
        _target(STREAK_DEVICE, "StartSequence"),
        _target(STREAK_DEVICE, "ExecuteRaw"),
        _target(STREAK_DEVICE, "SaveCurrentSequence"),
    ], {
        "phase": request_data.phase,
        "frames_per_his": request_data.frames_per_his,
        "output_root": request_data.output_root,
        "run_name": request_data.run_name,
        "his_path": request_data.his_path,
        "sequence_loops": str(request_data.frames_per_his),
        "wait_query": SEQUENCE_WAIT_QUERY,
        "wait_timeout_s": SEQUENCE_TIMEOUT_S,
        **({"sample_description": request_data.sample_description} if request_data.sample_description else {}),
        **({"reuse_bruit": request_data.reuse_bruit} if request_data.reuse_bruit != "latest" else {}),
    }


def _value(proxy: DeviceProxy, attribute: str) -> Any:
    return proxy.read_attribute(attribute).value


def _snapshot(proxy: DeviceProxy) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    requested = list(READ_ATTRIBUTES.items())
    attributes = None
    read_many = getattr(proxy, "read_attributes", None)
    if callable(read_many):
        try:
            attributes = read_many([name for _, name in requested])
            if len(attributes) != len(requested):
                attributes = None
        except Exception:
            # Older proxies and failed bulk calls retain per-attribute errors.
            attributes = None
    for index, (key, attribute) in enumerate(requested):
        try:
            item = attributes[index] if attributes is not None else proxy.read_attribute(attribute)
            failed = getattr(item, "has_failed", False)
            if (failed() if callable(failed) else failed):
                raise RuntimeError(str(item.get_err_stack()))
            value = item.value
            values[key] = value.item() if hasattr(value, "item") else value
        except Exception as exc:  # Attribute failures must not blank the whole control panel.
            values[key] = None
            errors[key] = str(exc)

    state = str(proxy.state()).split(".")[-1]
    return {
        "device": STREAK_DEVICE,
        "state": state,
        "status": str(proxy.status()) if state in {"FAULT", "ALARM"} else "",
        "connected": bool(values.get("connected", False)),
        "application_running": bool(values.get("application_running", False)),
        "remoteex_status": _string(values.get("remoteex_status", "unknown")),
        "values": values,
        "attribute_errors": errors,
    }


def _control_error(exc: Exception) -> str:
    message = str(exc)
    if "hamamatsu streak controller is not connected" in message.lower():
        return "RemoteEx camera control is disconnected. Use Refresh after the HIS measurement is idle."
    if "no camera available" in message.lower():
        return (
            "HPD-TA reports no readout camera. On Everest, the active hardware profile "
            "defaultHW.hwp is configured with CameraType=NoCamera. Load or create the "
            "C13440 hardware profile in HPD-TA, then reconnect and start Live again."
        )
    return message


def _astor(device: str = "") -> DeviceProxy:
    proxy = DeviceProxy(
        ELYSIUM_ASTOR_DEVICE if device == ZABER_STAGE_DEVICE else ASTOR_DEVICE
    )
    proxy.set_timeout_millis(15000)
    return proxy


def _wait_for_device(device: str, timeout_s: float = 15.0) -> DeviceProxy:
    deadline = time.monotonic() + timeout_s
    last_error = None
    while time.monotonic() < deadline:
        try:
            proxy = DeviceProxy(device)
            proxy.set_timeout_millis(8000)
            proxy.state()
            return proxy
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"{device} did not become available: {last_error}")


def _is_healthy_device(proxy: DeviceProxy, device: str) -> bool:
    state = str(proxy.state()).split(".")[-1].upper()
    if state in {"FAULT", "UNKNOWN", "OFF", "DISABLE", "ALARM", "INIT"}:
        return False
    if device in OWIS_DEVICES:
        # The controller can publish ON before its blocking axis initialization
        # finishes. New servers expose that separate lifecycle fact; older
        # servers without the attribute retain the state/readback contract.
        attribute_list = getattr(proxy, "get_attribute_list", None)
        if attribute_list and "initialization_state" in {str(name).lower() for name in attribute_list()}:
            if str(proxy.read_attribute("initialization_state").value).upper() != "SUCCEEDED":
                return False
    if device == DG645_DEVICE:
        return state == "ON" and bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
    if device in {VD2_PDU_DEVICE, ZABER_PDU_DEVICE, OWIS_PDU_DEVICE}:
        return bool(list(proxy.read_attribute("ids").value))
    if device == ZABER_STAGE_DEVICE:
        return proxy.read_attribute("position_mm").value is not None
    if device == KYMERA_DEVICE:
        return state == "ON" and int(proxy.read_attribute("grating").value) > 0
    if device in {OWIS_CONTROLLER_DEVICE, OWIS_SAMPLE_DEVICE}:
        # Axis commands require an initialized controller/router, not just an
        # exported transport in STANDBY. Verify the VD2 axis below separately.
        # MOVING is an operational shared controller, not a server fault. The
        # required VD2 axis is checked independently, without resetting others.
        return state in {"ON", "MOVING", "RUNNING"} and math.isfinite(float(proxy.read_attribute("pos2").value))
    if device == OWIS_LEGACY_DEVICE:
        return state in {"ON", "MOVING", "RUNNING"}
    # RemoteEx may intentionally be stopped while its Tango launcher remains ON.
    return True


def _wait_for_healthy_device(device: str, timeout_s: float = 20.0) -> DeviceProxy:
    deadline = time.monotonic() + timeout_s
    last_error = None
    while time.monotonic() < deadline:
        try:
            proxy = _wait_for_device(device, timeout_s=1.0)
            if _is_healthy_device(proxy, device):
                return proxy
            last_error = f"{device} is exported but not healthy"
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"{device} did not pass health check: {last_error}")


def _observe_owis_initialization(device, steps=None):
    """Only observe an existing/uncertain initialization; never replay it."""
    if steps is not None:
        _progress(steps, f"{device}: waiting for existing OWIS initialization/readback; no restart or initialization replay")
    try:
        return _wait_for_healthy_device(device)
    except Exception as exc:
        detail = f"{device}: readiness remains unverified; no restart or initialization replay was issued. {exc}"
        if steps is not None:
            steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
        raise RuntimeError(detail) from exc


def _readiness_failure_detail(proxy):
    """Capture available native diagnostics for the durable operation log."""
    details = []
    try:
        details.append(f"state={proxy.state()}")
    except Exception as exc:
        details.append(f"state unavailable: {exc}")
    attribute_list = getattr(proxy, "get_attribute_list", None)
    try:
        available = {str(name).lower() for name in attribute_list()} if attribute_list else set()
    except Exception:
        available = set()
    for name in ("initialization_state", "hardware_lifecycle_status", "last_error", "last_comment"):
        if name not in available:
            continue
        try:
            value = proxy.read_attribute(name).value
            if value not in (None, ""):
                details.append(f"{name}={value}")
        except Exception as exc:
            details.append(f"{name} unavailable: {exc}")
    return "; ".join(details)


def _recover_owis_device(proxy, device, steps=None):
    state = str(proxy.state()).split(".")[-1].upper()
    if state in {"ON", "MOVING", "RUNNING", "INIT"}:
        # A missing position readback is not permission to reset live axes.
        return _observe_owis_initialization(device, steps), []
    proxy.set_timeout_millis(60000)
    if steps is not None:
        _progress(steps, f"{device}: OWIS initialization command timeout is 60 s; accepted commands are not replayed")
    commands = ("turn_on",) if state in {"OFF", "STANDBY"} else ("recover", "turn_on")
    report = (lambda detail: _progress(steps, f"{device}: {detail}")) if steps is not None else None
    recovered, errors = recover_device(
        proxy, lambda candidate: _is_healthy_device(candidate, device), commands, on_progress=report,
    )
    if recovered:
        return proxy, errors
    if any("API_DeviceTimedOut" in error or "TRANSIENT_CallTimedout" in error for error in errors):
        # The accepted turn_on can still hold Tango's device lock after the
        # client timed out. Do not kill/restart that process or send Init.
        return _observe_owis_initialization(device, steps), errors
    errors.append(_readiness_failure_detail(proxy))
    return None, errors


def _recover_retained_instrument(proxy, device, steps):
    if device in OWIS_DEVICES:
        return _recover_owis_device(proxy, device, steps)
    state = str(proxy.state()).split(".")[-1].upper()
    if state in {"ON", "MOVING", "RUNNING", "INIT"}:
        _progress(steps, f"{device}: observing existing readiness; no Init or server restart")
        return _wait_for_healthy_device(device), []
    # A cold Shamrock SDK open can outlive the generic instrument timeout.
    # Keep the sole activation call pending instead of declaring failure after
    # 60 s and probing a Tango device still serialized behind that same call.
    proxy.set_timeout_millis(240000 if device == KYMERA_DEVICE else 60000)
    if device == KYMERA_DEVICE:
        _progress(steps, "Initializing Kymera SDK after power-up; allowing up to 240 s for the single activation call")
    commands = ("turn_on",) if state in {"OFF", "STANDBY"} else ("recover", "turn_on")
    recovered, errors = recover_device(
        proxy, lambda candidate: _is_healthy_device(candidate, device), commands,
        on_progress=lambda detail: _progress(steps, f"{device}: {detail}; server retained"),
    )
    if recovered:
        return proxy, errors
    if any("API_DeviceTimedOut" in error or "TRANSIENT_CallTimedout" in error for error in errors):
        _progress(steps, f"{device}: command outcome unknown; observing without replay or process restart")
        if device == KYMERA_DEVICE:
            return _observe_kymera_startup(steps), errors
        return _wait_for_healthy_device(device), errors
    errors.append(_readiness_failure_detail(proxy))
    return None, errors


def _observe_kymera_startup(steps, timeout_s=180.0):
    """Observe the already-submitted SDK open; never submit another activation."""
    _progress(steps, "Waiting for the existing Kymera SDK initialization; no command replay or server restart")
    deadline = time.monotonic() + timeout_s
    last_error = "Kymera is not ready"
    while time.monotonic() < deadline:
        try:
            proxy = DeviceProxy(KYMERA_DEVICE)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            proxy.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
            if _is_healthy_device(proxy, KYMERA_DEVICE):
                return proxy
            last_error = f"Kymera state {proxy.state()} has not reached ready"
        except Exception as exc:
            # These are read-only observations. IMP_LIMIT/communication errors
            # while the original SDK call holds Tango must not trigger Init.
            last_error = _control_error(exc)
        time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
    raise RuntimeError(f"Kymera SDK initialization remains unverified; server retained, no activation replay. {last_error}")


def _wait_for_dg645_power_up(steps, deadline):
    remaining = max(0.0, deadline - time.monotonic())
    _progress(steps, "Waiting for DG645 to complete its power-up transport check",
              wait_until=time.time() + remaining)
    last_error = "No response from the instrument server"
    while remaining > 0:
        try:
            proxy = DeviceProxy(DG645_DEVICE)
            proxy.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
            state = str(proxy.state()).split(".")[-1].upper()
            # The power monitor publishes STANDBY only after its safe probe
            # succeeds. Until then it owns transport discovery.
            if state in {"STANDBY", "ON"}:
                return proxy
            last_error = f"Tango state {state}"
        except Exception as exc:
            last_error = _control_error(exc)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(2.0, remaining))
        remaining = deadline - time.monotonic()
    raise RuntimeError(
        f"DG645 did not complete its power-up transport check within "
        f"{DG645_POWER_UP_TIMEOUT_S:g} s of power confirmation: {last_error}"
    )


def _restart_server(device: str, server: str, steps=None, *, dg645_boot_deadline=None) -> DeviceProxy:
    if device in OWIS_DEVICES:
        # Readiness can recover between the original check and escalation.
        # A fresh passive check must precede any Starter stop/start.
        proxy = None
        try:
            proxy = _wait_for_device(device, timeout_s=2.0)
            if _is_healthy_device(proxy, device):
                if steps is not None:
                    _progress(steps, f"{device}: OWIS is already operational; server retained without restart")
                return proxy
        except Exception:
            pass
        if proxy is not None and str(proxy.state()).split(".")[-1].upper() in {"ON", "MOVING", "RUNNING", "INIT"}:
            return _observe_owis_initialization(device, steps)
    astor = _astor(device)
    report = (lambda detail: _progress(steps, f"{device}: {detail}")) if steps is not None else None

    def wait_ready():
        if device in RETAINED_INSTRUMENT_SERVERS:
            proxy = (_wait_for_dg645_power_up(steps, dg645_boot_deadline) if dg645_boot_deadline is not None
                     else _wait_for_device(device, timeout_s=45.0 if device == KYMERA_DEVICE else 15.0))
            if _is_healthy_device(proxy, device):
                return proxy
            recovered, errors = _recover_retained_instrument(proxy, device, steps)
            if recovered is not None:
                return recovered
            raise RuntimeError(f"{device}: equipment readiness failed; server retained. {'; '.join(errors)}")
        return _wait_for_healthy_device(device)

    def observe_existing():
        if dg645_boot_deadline is not None:
            return wait_ready()
        _progress(steps, f"Server {server} is already running; observing equipment readiness without restart or command replay")
        try:
            return _wait_for_healthy_device(device)
        except Exception as exc:
            raise RuntimeError(f"{server} is running but equipment readiness is unverified; server retained. {exc}") from exc

    return start_managed_server(
        astor, server, wait_ready, on_progress=report,
        restart_existing=device not in RETAINED_INSTRUMENT_SERVERS,
        observe_existing=observe_existing,
    )


def _ensure_server(device: str, steps: list[dict[str, str]], *, dg645_boot_deadline=None) -> DeviceProxy:
    _progress(steps, f"Checking / recovering {device} ({VD2_SERVERS[device]})")
    if dg645_boot_deadline is not None:
        proxy = _restart_server(device, VD2_SERVERS[device], steps, dg645_boot_deadline=dg645_boot_deadline)
        steps.append({"step": f"Tango {device}", "status": "readiness verified after power-up"})
        return proxy
    initial_error = "device is exported but hardware is not ready"
    proxy = None
    try:
        proxy = _wait_for_device(device, timeout_s=2.0)
        if _is_healthy_device(proxy, device):
            steps.append({"step": f"Tango {device}", "status": "already running"})
            return proxy
        initial_error = f"state={proxy.state()}; device is exported but hardware is not ready"
    except Exception as exc:
        initial_error = str(exc)
        if proxy is None and device in RETAINED_INSTRUMENT_SERVERS:
            # A missing process should start immediately. Only an existing
            # (or unconfirmed) process needs a passive transport grace period.
            running = True
            try:
                running = VD2_SERVERS[device] in set(_astor(device).command_inout("DevGetRunningServers", True))
            except Exception:
                pass  # Unknown inventory is not permission to restart a process.
            # Power restoration can leave an already-running Tango process
            # temporarily unreachable. No activation was submitted above.
            # Reconnect first so a cold STANDBY instrument can receive its one
            # explicit turn_on through the existing recovery path below.
            if running:
                _progress(steps, f"{device}: waiting for transport after power restoration; no process restart")
                try:
                    proxy = _wait_for_device(device, timeout_s=20.0)
                    if _is_healthy_device(proxy, device):
                        steps.append({"step": f"Tango {device}", "status": "already running"})
                        return proxy
                except Exception as reconnect_error:
                    initial_error += f"; transport recheck: {reconnect_error}"

    server = VD2_SERVERS[device]
    _progress(steps, f"{device} check failed: {initial_error}")
    recovery_errors = []
    if proxy is not None:
        if device in RETAINED_INSTRUMENT_SERVERS:
            recovered_proxy, recovery_errors = _recover_retained_instrument(proxy, device, steps)
            if recovered_proxy is not None:
                steps.append({"step": f"Tango {device}", "status": "recovered"})
                return recovered_proxy
            detail = f"{device}: equipment readiness failed; server retained, no Init or process restart. {'; '.join(recovery_errors)}"
            steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
            raise RuntimeError(detail)
        else:
            recovery_commands = (_recovery_command(device), "Init", "turn_on")
            recovered, recovery_errors = recover_device(
                proxy, lambda candidate: _is_healthy_device(candidate, device),
                recovery_commands, on_progress=lambda detail: _progress(steps, f"{device}: {detail}"),
            )
            if recovered:
                steps.append({"step": f"Tango {device}", "status": "recovered"})
                return proxy

    try:
        if device in RETAINED_INSTRUMENT_SERVERS:
            _progress(steps, f"Checking process {server}; start only if absent, otherwise retain it and verify equipment")
        else:
            _progress(steps, f"Restarting / starting failed device server {server}; other independent branches will still be checked")
        proxy = _restart_server(device, server, steps)
    except Exception as exc:
        detail = (
            f"{device}: {exc}. Initial check: {initial_error}. "
            + ("Recovery: " + "; ".join(recovery_errors) + ". " if recovery_errors else "")
            + "Check the confirmed PDU output and instrument connection, then press Prepare again."
        )
        steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
        raise RuntimeError(detail) from exc
    steps.append({"step": f"Tango {device}", "status":
                  "readiness verified; server retained or started by Astor" if device in OWIS_DEVICES else "started by Astor"})
    return proxy


def _enable_required_power(
    pdu: DeviceProxy,
    steps: list[dict[str, str]],
    required_outputs: dict[int, str],
    label: str,
) -> dict[int, float]:
    ids = [int(value) for value in pdu.read_attribute("ids").value]
    states = [int(value) for value in pdu.read_attribute("states").value]
    if len(ids) != len(states) or len(set(ids)) != len(ids):
        raise RuntimeError(f"PDU {label} output IDs and states do not match")
    positions = {output_id: index for index, output_id in enumerate(ids)}
    missing = sorted(set(required_outputs) - set(positions))
    if missing:
        raise RuntimeError(f"PDU {label} required outputs are missing: {missing}")
    desired = list(states)
    camera_newly_enabled = label == "SD2" and states[positions[1]] != 1
    changed = []
    for output_id in required_outputs:
        position = positions[output_id]
        if desired[position] != 1:
            desired[position] = 1
            changed.append(output_id)
    if changed:
        if camera_newly_enabled and hasattr(steps, "power_intent"):
            steps.power_intent()
        pdu.command_inout("set_channels_states", desired)
    deadline = time.monotonic() + 8.0
    while True:
        confirmed_ids = [int(value) for value in pdu.read_attribute("ids").value]
        confirmed = [int(value) for value in pdu.read_attribute("states").value]
        if len(confirmed_ids) != len(confirmed) or len(set(confirmed_ids)) != len(confirmed_ids):
            raise RuntimeError(f"PDU {label} invalid power-on readback")
        confirmed_states = dict(zip(confirmed_ids, confirmed))
        failed = [name for output_id, name in required_outputs.items() if confirmed_states.get(output_id) != 1]
        if not failed:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"PDU {label} did not confirm power for: {', '.join(failed)}")
        time.sleep(0.5)
    confirmed_at = time.monotonic()
    steps.append({"step": f"{label} power", "status": "enabled" if changed else "already enabled"})
    if label == "SD2":
        deadline = (steps.power_deadline(camera_newly_enabled)
                    if hasattr(steps, "power_deadline")
                    else time.time() + 30.0 if camera_newly_enabled else None)
        remaining = max(0.0, deadline - time.time()) if deadline else 0.0
        if remaining:
            _progress(steps, "Waiting for streak-camera / Kymera power to settle and hardware calibration before server initialization",
                      wait_until=deadline)
            # Real elapsed time, not a page timer. Reloading cannot shorten it.
            time.sleep(remaining)
            # A timer is not proof that power remained present.
            verified_ids = [int(value) for value in _value(pdu, "ids")]
            verified_states = [int(value) for value in _value(pdu, "states")]
            if len(verified_ids) != len(verified_states) or len(set(verified_ids)) != len(verified_ids):
                raise RuntimeError("SD2 power readback invalid after camera settling delay")
            powered = dict(zip(verified_ids, verified_states))
            if any(powered.get(output_id) != 1 for output_id in required_outputs):
                if hasattr(steps, "power_intent"):
                    steps.power_intent()
                raise RuntimeError("SD2 power changed during camera settling delay; no instrument initialization attempted")
            steps.append({"step": "Streak / Kymera power settling", "status": "30 s power-up delay completed; hardware readiness will be checked next"})
        if hasattr(steps, "power_ready"):
            steps.power_ready()
        _progress(steps, "Power confirmed; checking dependent instrument servers")
        if changed and not camera_newly_enabled and not remaining:
            time.sleep(2.0)
    elif changed:
        time.sleep(2.0)
    return dict.fromkeys(changed, confirmed_at)


def _enable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> dict[int, float]:
    return _enable_required_power(pdu, steps, SD2_REQUIRED_PDU_OUTPUTS, "SD2")


def _disable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> None:
    # The trigger generator was started first and is switched off before the
    # camera supply; software and optical closure must precede this function.
    for output_id in (2, 1):
        _disable_pdu_outputs(pdu, steps, {output_id: VD2_SHUTDOWN_PDU_OUTPUTS[output_id]}, "SD2")


def _disable_pdu_outputs(pdu, steps, outputs, label):
    retained = VD2_RETAINED_PDU_OUTPUTS if label == "VD2" else {}
    forbidden = sorted(set(outputs) & set(retained))
    if forbidden:
        raise RuntimeError(f"Unprepare must retain PDU VD2 outputs: {[retained[key] for key in forbidden]}")
    ids = [int(value) for value in pdu.read_attribute("ids").value]
    states = [int(value) for value in pdu.read_attribute("states").value]
    if len(ids) != len(states) or len(set(ids)) != len(ids):
        raise RuntimeError(f"PDU {label} output IDs and states do not match")
    positions = {output_id: index for index, output_id in enumerate(ids)}
    missing = sorted((set(outputs) | set(retained)) - set(positions))
    if missing:
        raise RuntimeError(f"PDU {label} required outputs are missing: {missing}")
    desired = list(states)
    retained_states = {output_id: states[positions[output_id]] for output_id in retained}
    if any(state not in (0, 1) for state in retained_states.values()):
        raise RuntimeError("PDU VD2 retained outlet readback invalid; no power changes attempted")
    changed = []
    for output_id, output_label in outputs.items():
        position = positions[output_id]
        if desired[position] != 0:
            desired[position] = 0
            changed.append(output_label)
    if changed:
        pdu.command_inout("set_channels_states", desired)
    deadline = time.monotonic() + 8.0
    while True:
        confirmed_ids = [int(value) for value in _value(pdu, "ids")]
        confirmed = [int(value) for value in _value(pdu, "states")]
        if len(confirmed_ids) != len(confirmed) or len(set(confirmed_ids)) != len(confirmed_ids):
            raise RuntimeError(f"PDU {label} invalid power-off readback")
        readback = dict(zip(confirmed_ids, confirmed))
        altered = [name for output_id, name in retained.items()
                   if readback.get(output_id) != retained_states[output_id]]
        if altered:
            raise RuntimeError(f"PDU {label} retained power changed or unverified: {', '.join(altered)}")
        failed = [name for output_id, name in outputs.items() if readback.get(output_id) != 0]
        if not failed:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"PDU {label} did not disable: {', '.join(failed)}")
        time.sleep(0.5)
    steps.append({"step": f"{label} power: {', '.join(outputs.values())}",
                  "status": "disabled; verified OFF" if changed else "already disabled; verified OFF"})


def _initialize_experiment(steps=None) -> dict[str, Any]:
    if steps is None:
        steps = []
    try:
        result = _initialize_equipment(steps)
        if result.get("already_ready"):
            raise AlreadyPrepared(result)
        return result
    except AlreadyPrepared:
        raise
    except Exception as exc:
        raise PreparationFailure(str(exc), steps) from exc


class PreparationFailure(RuntimeError):
    def __init__(self, message, steps):
        super().__init__(message)
        self.steps = list(steps)


class AlreadyPrepared(PreparationFailure):
    code = "experiment_already_on"

    def __init__(self, result):
        super().__init__("VD2 is already switched on; all readiness checks passed. No hardware command or settings change was performed.", result["steps"])
        self.result = result


def _prepare_dg645_for_vd2(dg645, steps):
    """Apply single-trigger timing before starting any VD2 camera software."""
    label = f"DG645 Recall {VD2_DG645_RECALL_SLOT}"
    try:
        dg645.command_inout("scpi_write", f"*RCL {VD2_DG645_RECALL_SLOT}")
        time.sleep(1.0)
        dg645.command_inout("scpi_write", "BURM 0")
        dg645.command_inout("scpi_query", "*OPC?")
        burst_mode = str(dg645.command_inout("scpi_query", "BURM?")).strip()
        if float(burst_mode) != 0.0:
            raise RuntimeError(f"burst mode is still enabled (BURM?={burst_mode})")
    except Exception as exc:
        detail = f"{label} / burst-off verification failed: {exc}"
        steps.append({"step": label, "status": "failed", "detail": detail})
        raise RuntimeError(detail) from exc
    steps.append({"step": label, "status": "applied; verified BURM=0"})


def _verify_owis_sample_axis(owis, steps):
    """Verify VD2 axis 2 without issuing movement or homing commands."""
    label = f"OWIS sample axis {OWIS_SAMPLE_AXIS}"
    try:
        state = int(owis.command_inout("get_status_axis", OWIS_SAMPLE_AXIS))
        # An OFF motor can be enabled explicitly, but do not reinitialize an
        # axis or move it as a side effect of a readiness check.
        if state == int(DevState.OFF):
            result = owis.command_inout("turn_on_axis", OWIS_SAMPLE_AXIS)
            if str(result).strip() != "0":
                raise RuntimeError(f"turn_on_axis: {result}")
            state = int(owis.command_inout("get_status_axis", OWIS_SAMPLE_AXIS))
        if state != int(DevState.ON):
            raise RuntimeError(f"axis is not ready (state={state}); correct its condition and press Prepare again")
        position = float(owis.command_inout("read_position_axis", OWIS_SAMPLE_AXIS))
        if not math.isfinite(position):
            raise RuntimeError("axis position readback is invalid")
    except Exception as exc:
        detail = f"{label}: {exc}"
        steps.append({"step": label, "status": "failed", "detail": detail})
        raise RuntimeError(detail) from exc
    steps.append({"step": label, "status": f"verified ON; {position:.4f} mm"})


def _assert_preparation_idle(streak=None):
    if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
        raise RuntimeError("Stop the VD2 measurement before Prepare")
    if streak is None:
        try:
            streak = _wait_for_device(STREAK_DEVICE, timeout_s=1.0)
        except Exception:
            return
    if str(_value(streak, "remoteex_status")).lower() in {"busy", "starting", "preparing"}:
        raise RuntimeError("HPD-TA is busy; stop acquisition before Prepare")
    if bool(_value(streak, "connected")) or bool(_value(streak, "application_running")):
        try:
            status = str(streak.command_inout("ExecuteRaw", "AcqStatus()")).strip().lower()
        except Exception as exc:
            # This exact RemoteEx reply confirms a cold application; absence of
            # a response or a stale application_running=False cache does not.
            if "3,acqstatus,application not running" in str(exc).lower():
                return
            raise RuntimeError(f"Cannot confirm HPD-TA acquisition idle: {exc}") from exc
        if status != "0,acqstatus,idle":
            raise RuntimeError(f"HPD-TA acquisition is not confirmed idle: {status}")


def _assert_kymera_passive_server(kymera):
    """An idle SDK server must not reopen the hardware behind HPD-TA."""
    properties = kymera.get_property(["power_dependency_auto_probe"])
    values = list(properties.get("power_dependency_auto_probe", []))
    if len(values) != 1 or int(values[0]) != 0:
        raise RuntimeError(
            "Kymera SDK handoff requires power_dependency_auto_probe=0 in the running server; "
            "automatic SDK probing must be disabled before retaining the server alongside HPD-TA"
        )


def _verify_kymera_sdk_released(kymera):
    kymera.set_timeout_millis(2000)
    deadline = time.monotonic() + 20.0
    while str(kymera.state()).split(".")[-1].upper() != "OFF":
        if time.monotonic() >= deadline:
            raise RuntimeError("Kymera SDK ownership was not released; server retained, HPD-TA startup blocked")
        time.sleep(0.5)


def _prepare_kymera_for_vd2(streak, steps):
    """Hand Kymera from HPD-TA to its SDK server, then release it before AppStart."""
    _assert_preparation_idle(streak)
    _progress(steps, "Releasing HPD-TA / RemoteEx SDK ownership before Kymera initialization")
    streak.set_timeout_millis(30000)
    if bool(_value(streak, "application_running")):
        for attribute in ("streak_shutter", "spectrograph_shutter"):
            streak.write_attribute(attribute, "Closed")
            if str(_value(streak, attribute)).lower() != "closed":
                raise RuntimeError(f"Cannot confirm {attribute} closed before Kymera handoff")
        streak.command_inout("StopApplication")
        deadline = time.monotonic() + 20.0
        while bool(_value(streak, "application_running")):
            if time.monotonic() >= deadline:
                raise RuntimeError("HPD-TA did not stop; cannot give Kymera to its SDK server")
            time.sleep(0.5)
        steps.append({"step": "HPD-TA handoff", "status": "stopped; both shutters closed"})

    # AppEnd does not unload the spectrograph SDK from TaRemoteEx. Stop its
    # process too, otherwise a second SDK owner can hang or access-violate.
    streak.command_inout("StopRemoteEx")
    if bool(_value(streak, "connected")):
        raise RuntimeError("RemoteEx ownership was not released before Kymera SDK startup")
    steps.append({"step": "RemoteEx SDK ownership", "status": "process stopped before Kymera startup"})

    kymera = None
    try:
        kymera = _ensure_server(KYMERA_DEVICE, steps)
        _assert_kymera_passive_server(kymera)
        kymera.set_timeout_millis(45000)
        result = json.loads(kymera.command_inout("PrepareVD2Grating"))
        if not (
            int(result["grating"]) == 2
            and math.isfinite(float(result["blaze"]))
            and abs(float(result["blaze"]) - 800.0) <= 0.01
            and math.isfinite(float(result["ruling"]))
            and abs(float(result["ruling"]) - 150.0) <= 0.01
        ):
            raise RuntimeError(f"Kymera grating preparation readback mismatch: {result}")
        steps.append({"step": "Kymera grating 2", "status": "SDK verified: Blaze 800; 150 g/mm"})
    finally:
        # Close the SDK after selection (also on failure), not the Tango process.
        # Unknown/failed release blocks HPD-TA; it is never resolved by killing it.
        if kymera is not None:
            _progress(steps, "Deinitializing Kymera SDK; retaining Tango server before HPD-TA startup")
            kymera.command_inout("turn_off")
            _verify_kymera_sdk_released(kymera)
    steps.append({"step": "Kymera SDK ownership", "status": "SDK deinitialized; server retained; released to HPD-TA"})


def _initialize_equipment(steps) -> dict[str, Any]:
    _progress(steps, "Checking whether VD2 is already running; existing settings will be retained", stage=0)
    _assert_preparation_idle()
    prepared = _prepared_equipment_state()
    if prepared is not None:
        # A repeat Prepare must not silently call an old timing ready, nor
        # reset operational optics to repair it. Verification performs no writes.
        _verify_vd2_timing_ready(_wait_for_device(STREAK_DEVICE, timeout_s=2.0))
        return prepared
    # A measurement can start while the passive equipment checks are running.
    _assert_preparation_idle()
    failed = {}

    def attempt(label, action, dependencies=()):
        blocked = [dependency for dependency in dependencies if dependency in failed]
        if blocked:
            detail = f"Skipped {label}: unverified dependencies: {', '.join(blocked)}"
            failed[label] = detail
            steps.append({"step": label, "status": "skipped", "detail": detail})
            return None
        _progress(steps, f"Preparing {label}")
        try:
            value = action()
            return value
        except Exception as exc:
            failed[label] = str(exc)
            steps.append({"step": label, "status": "failed", "detail": str(exc)})
            _progress(steps, f"{label} failed; continuing independent equipment checks")
            return None

    # Check every PDU independently; only its own dependent branch is blocked.
    sd2_pdu = attempt("SD2 PDU", lambda: _ensure_server(VD2_PDU_DEVICE, steps))
    zaber_pdu = attempt("VD2 PDU", lambda: _ensure_server(ZABER_PDU_DEVICE, steps))
    owis_pdu = attempt("OWIS PDU", lambda: _ensure_server(OWIS_PDU_DEVICE, steps))
    sd2_power_on = attempt("SD2 power", lambda: _enable_vd2_power(sd2_pdu, steps), ("SD2 PDU",))
    attempt("VD2 power", lambda: _enable_required_power(zaber_pdu, steps, VD2_REQUIRED_PDU_OUTPUTS, "VD2"), ("VD2 PDU",))
    attempt("OWIS power", lambda: _enable_required_power(owis_pdu, steps, OWIS_REQUIRED_PDU_OUTPUTS, "OWIS"), ("OWIS PDU",))
    dg645_power_on = (sd2_power_on or {}).get(2)
    dg645_options = {}
    if dg645_power_on is not None:
        dg645_options["dg645_boot_deadline"] = dg645_power_on + DG645_POWER_UP_TIMEOUT_S
    dg645 = attempt("DG645 server", lambda: _ensure_server(DG645_DEVICE, steps, **dg645_options), ("SD2 power",))
    attempt("DG645 timing", lambda: _prepare_dg645_for_vd2(dg645, steps), ("DG645 server",))
    # VD2 uses axis 2 on the IP backend. The shared aggregator also depends on
    # USB axis 4, so it must not gate preparation or receive VD2 axis commands.
    owis = attempt("OWIS IP server", lambda: _ensure_server(OWIS_SAMPLE_DEVICE, steps), ("OWIS power",))
    attempt("OWIS sample axis", lambda: _verify_owis_sample_axis(owis, steps), ("OWIS IP server",))
    attempt("Zaber server", lambda: _ensure_server(ZABER_STAGE_DEVICE, steps), ("VD2 power",))
    streak = attempt("Hamamatsu server", lambda: _ensure_server(STREAK_DEVICE, steps), ("SD2 power",))
    optical = attempt("Streak / Kymera optical startup", lambda: _start_vd2_optics(streak, steps), ("Hamamatsu server", "DG645 timing"))
    if failed:
        # No global ready flag for a partially prepared rig, even if optics work.
        raise RuntimeError("VD2 preparation incomplete: " + "; ".join(f"{name}: {detail}" for name, detail in failed.items()))
    return {"steps": steps, "device": optical}


def _start_vd2_optics(streak, steps):
    """Optical branch is independent of external stages, but requires safe timing."""
    global _live_average_readback
    _live_average_readback = None  # A prior HPD-TA instance cannot verify new filter settings.
    streak.set_timeout_millis(60000)

    # StopRemoteEx below verifies actual local process exit, even when its Tango
    # flags are disconnected. A cold start must not launch it merely to stop it
    # again before Kymera's exclusive SDK initialization.
    if bool(_value(streak, "application_running")) and not bool(_value(streak, "connected")):
        _progress(steps, "Reconnecting to existing HPD-TA before releasing its SDK ownership")
        streak.command_inout("StartRemoteEx")
        if not bool(_value(streak, "connected")):
            raise RuntimeError("Cannot reconnect to running HPD-TA; Kymera SDK startup blocked")
    _prepare_kymera_for_vd2(streak, steps)
    _progress(steps, "Starting RemoteEx / HPD-TA and waiting for verified instrument readiness", stage=2)
    streak.command_inout("StartRemoteEx")
    if not bool(_value(streak, "connected")):
        raise RuntimeError("RemoteEx did not reconnect after Kymera SDK release")
    streak.command_inout("StartApplication")
    # AppStart can reconnect RemoteEx and then move the spectrograph before ready.
    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        state = str(streak.state()).split(".")[-1]
        if state in {"FAULT", "ALARM"}:
            raise RuntimeError(f"HPD-TA startup failed: {streak.status()}")
        if (
            state == "ON"
            and bool(_value(streak, "application_running"))
            and str(_value(streak, "remoteex_status")).lower() == "idle"
        ):
            # StartApplication recalls memory 9 again inside the camera server.
            # Apply calibrated A/E only after that startup and its 1 us profile.
            profile = timing_for_range(_remoteex_readback(streak, "DevParamGet(TD,Time Range)"))
            _apply_vd2_timing(profile, steps)
            steps.append({"step": "HPD-TA", "status": "running"})
            steps.append({
                "step": "VD2 optical profile",
                "status": (
                    "verified: 550 nm; grating 2 (Blaze 800); 1 us; Operate; "
                    "Kymera shutter open; streak-camera shutter closed"
                ),
            })
            return _snapshot(streak)
        time.sleep(1.0)
    raise RuntimeError(
        "HPD-TA did not become ready. Check the Everest desktop for a hardware-profile dialog."
    )


def _prepared_equipment_state() -> dict[str, Any] | None:
    """Read-only fast path; a running camera alone does not prove VD2 ready.

    The caller must first exclude acquisition. Never open the Kymera SDK here:
    HPD-TA owns it. Keep current wavelength, time range and shutter settings;
    repeating Prepare is not a request to reset an operational experiment.
    """
    steps = []
    proxies = {}
    try:
        for device in (
            VD2_PDU_DEVICE, ZABER_PDU_DEVICE, OWIS_PDU_DEVICE,
            DG645_DEVICE, OWIS_SAMPLE_DEVICE, ZABER_STAGE_DEVICE, STREAK_DEVICE,
        ):
            proxy = DeviceProxy(device)
            proxy.set_timeout_millis(3000)
            if not _is_healthy_device(proxy, device):
                return None
            proxies[device] = proxy
            steps.append({"step": f"Tango {device}", "status": "already running"})

        for device, outputs, label in (
            (VD2_PDU_DEVICE, SD2_REQUIRED_PDU_OUTPUTS, "SD2"),
            (ZABER_PDU_DEVICE, VD2_REQUIRED_PDU_OUTPUTS, "VD2"),
            (OWIS_PDU_DEVICE, OWIS_REQUIRED_PDU_OUTPUTS, "OWIS"),
        ):
            ids = [int(value) for value in _value(proxies[device], "ids")]
            states = [int(value) for value in _value(proxies[device], "states")]
            if len(ids) != len(states) or len(set(ids)) != len(ids):
                return None
            readback = dict(zip(ids, states))
            if any(readback.get(output_id) != 1 for output_id in outputs):
                return None
            steps.append({"step": f"{label} power", "status": "already enabled"})

        dg645 = proxies[DG645_DEVICE]
        if float(dg645.command_inout("scpi_query", "BURM?")) != 0.0:
            return None
        steps.append({"step": "DG645", "status": "verified BURM=0; timing unchanged"})

        owis = proxies[OWIS_SAMPLE_DEVICE]
        if int(owis.command_inout("get_status_axis", OWIS_SAMPLE_AXIS)) != int(DevState.ON):
            return None
        if not math.isfinite(float(owis.command_inout("read_position_axis", OWIS_SAMPLE_AXIS))):
            return None
        zaber = proxies[ZABER_STAGE_DEVICE]
        if str(zaber.state()).split(".")[-1] != "ON":
            return None
        if not math.isfinite(float(_value(zaber, "position_mm"))):
            return None
        steps.append({"step": "VD2 stages", "status": "verified; no movement requested"})

        streak = proxies[STREAK_DEVICE]
        if not (
            str(streak.state()).split(".")[-1] == "ON"
            and bool(_value(streak, "connected"))
            and bool(_value(streak, "application_running"))
            and str(_value(streak, "remoteex_status")).lower() == "idle"
        ):
            return None

        # Query HPD-TA directly: Tango's application/grating cache may be stale.
        for command, expected in (
            ("AppInfo(Version)", None),
            ("DevParamGet(Spec,Blaze)", 800.0),
            ("DevParamGet(Spec,Ruling)", 150.0),
            ("DevParamGet(TD,Mode)", "operate"),
            ("AcqStatus()", "idle"),
        ):
            parts = str(streak.command_inout("ExecuteRaw", command)).strip().split(",", 2)
            if len(parts) != 3 or parts[0] != "0" or parts[1] != command.split("(", 1)[0]:
                return None
            value = parts[2].strip()
            if not value:
                return None
            if isinstance(expected, float):
                number = float(value)
                if not math.isfinite(number) or abs(number - expected) > 0.01:
                    return None
            elif expected is not None and value.lower() != expected:
                return None

        running = set(_astor(KYMERA_DEVICE).command_inout("DevGetRunningServers", True))
        if VD2_SERVERS[KYMERA_DEVICE] in running:
            kymera = DeviceProxy(KYMERA_DEVICE)
            kymera.set_timeout_millis(2000)
            _assert_kymera_passive_server(kymera)
            if str(kymera.state()).split(".")[-1].upper() != "OFF":
                return None
        steps.extend([
            {"step": "RemoteEx / HPD-TA", "status": "already running; verified idle"},
            {"step": "Kymera grating 2", "status": "verified Blaze 800 / 150 g/mm via HPD-TA"},
            {"step": "Kymera SDK ownership", "status": "SDK released; HPD-TA owns spectrograph; server may remain running"},
        ])
        return {
            "already_ready": True,
            "message": "VD2 is already running; all checks passed. No restart or settings change was needed.",
            "steps": steps,
            "device": _snapshot(streak),
        }
    except Exception:
        # A failed/incomplete read is not readiness. The ordinary power-first
        # recovery path will report the specific fault instead of hiding it.
        return None


def _deinitialize_experiment(steps=None) -> dict[str, Any]:
    """Close SDK owners and optics before switching off experiment supplies."""
    if steps is None:
        steps = []
    try:
        return _shutdown_equipment(steps)
    except Exception as exc:
        steps.append({"step": "VD2 safe shutdown", "status": "failed", "detail": str(exc)})
        raise PreparationFailure(str(exc), steps) from exc


def _remoteex_readback(streak, command):
    raw = str(streak.command_inout("ExecuteRaw", command)).strip()
    parts = raw.split(",", 2)
    if len(parts) != 3 or parts[0] != "0" or parts[1] != command.split("(", 1)[0]:
        raise RuntimeError(f"Invalid {command} readback: {raw}")
    return parts[2].strip()


def _apply_vd2_timing(profile, steps):
    _progress(steps, f"Applying DG645 A=T0+{profile.delay_a_ms} ms, E=T0+{profile.delay_e_ms} ms for {profile.time_range}; gates unchanged", stage=2)
    try:
        dg645 = DeviceProxy(DG645_DEVICE)
        dg645.set_timeout_millis(5000)
        apply_timing(dg645, profile)
    except Exception as exc:
        steps.append({"step": "DG645 calibrated timing", "status": "failed", "detail": str(exc)})
        raise RuntimeError(f"DG645 timing unverified; keep acquisition stopped: {exc}") from exc
    steps.append({"step": "DG645 calibrated timing", "status":
                  f"verified {profile.time_range}: A=T0+{profile.delay_a_ms} ms; E=T0+{profile.delay_e_ms} ms; gates unchanged"})


def _verify_vd2_timing_ready(streak):
    """A partial timing write cannot silently become an Operate acquisition."""
    mode = _remoteex_readback(streak, "DevParamGet(TD,Mode)").lower()
    if mode == "focus":
        return  # Focus live imaging does not use the calibrated sweep trigger.
    if mode != "operate":
        raise RuntimeError(f"Cannot confirm streak mode before acquisition: {mode}")
    profile = timing_for_range(_remoteex_readback(streak, "DevParamGet(TD,Time Range)"))
    dg645 = DeviceProxy(DG645_DEVICE)
    dg645.set_timeout_millis(5000)
    if float(dg645.command_inout("scpi_query", "BURM?")) != 0.0:
        raise RuntimeError("DG645 burst mode is not verified OFF; acquisition blocked")
    verify_timing(dg645, profile)


def _shutdown_timed_out(exc):
    return isinstance(exc, TimeoutError) or any(token in str(exc).lower() for token in (
        "api_devicetimedout", "transient_calltimedout", "timed out", "timeout",
    ))


def _shutdown_once(action, steps, description):
    """A timed-out hardware command may already have executed: never replay it."""
    try:
        action()
    except Exception as exc:
        if not _shutdown_timed_out(exc):
            raise
        _progress(steps, f"Waiting for {description} confirmation after timeout; power retained", stage=0)


def _shutdown_acquisition_phase(streak):
    status = _remoteex_readback(streak, "AcqStatus()").lower()
    parts = [part.strip() for part in status.split(",")]
    if (parts[0] == "idle" and len(parts) == 1
            or parts[0] == "busy" and (len(parts) == 1 or len(parts) == 2 and bool(parts[1]))):
        return parts[0]
    raise RuntimeError(f"Unknown acquisition status: {status}; power retained")


def _wait_shutdown_readback(streak, read, expected, description, timeout_s=20.0):
    deadline = time.monotonic() + timeout_s
    last = "no readback"
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"Cannot confirm {description}; power retained (last readback: {last})")
        streak.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
        try:
            value = read()
            last = str(value)
            if value == expected:
                streak.set_timeout_millis(30000)
                return
        except Exception as exc:
            if not _shutdown_timed_out(exc):
                raise
            last = "readback timed out"
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))


def _shutdown_hpdta(streak, steps):
    streak.set_timeout_millis(30000)
    if str(_value(streak, "remoteex_status")).lower() in {"starting", "preparing"}:
        raise RuntimeError("Wait for HPD-TA startup/preparation before safe shutdown")
    application_running = bool(_value(streak, "application_running"))
    if bool(_value(streak, "connected")):
        try:
            status = _shutdown_acquisition_phase(streak)
        except Exception as exc:
            if "3,acqstatus,application not running" not in str(exc).lower():
                raise
            application_running = False
        else:
            application_running = True  # Direct reply overrides a stale Tango flag.
            if status != "idle":
                _progress(steps, "Stopping camera acquisition and waiting for idle", stage=0)
                _shutdown_once(lambda: streak.command_inout("StopAcquisition"), steps, "idle acquisition")
                _wait_shutdown_readback(streak, lambda: _shutdown_acquisition_phase(streak),
                                        "idle", "acquisition stopped")
            steps.append({"step": "Streak acquisition", "status": "verified idle"})
    elif application_running:
        raise RuntimeError("HPD-TA is running without a command connection; power retained")

    if application_running:
        for attribute, command in (
            ("streak_shutter", "DevParamGet(TD,Shutter)"),
            ("spectrograph_shutter", "DevParamGet(Spec,Shutter)"),
        ):
            _progress(steps, f"Closing and verifying {attribute.replace('_', ' ')}", stage=0)
            if _remoteex_readback(streak, command).lower() != "closed":
                _shutdown_once(lambda: streak.write_attribute(attribute, "Closed"), steps, attribute)
            _wait_shutdown_readback(streak, lambda: _remoteex_readback(streak, command).lower(),
                                    "closed", f"{attribute} closed")
            steps.append({"step": attribute, "status": "verified closed"})
        _progress(steps, "Switching streak camera to Focus before HPD-TA exit and power-off", stage=0)
        streak.set_timeout_millis(30000)
        if _remoteex_readback(streak, "DevParamGet(TD,Mode)").lower() != "focus":
            _shutdown_once(lambda: streak.write_attribute("streak_mode", "Focus"), steps, "streak camera Focus")
        _wait_shutdown_readback(streak, lambda: _remoteex_readback(streak, "DevParamGet(TD,Mode)").lower(),
                                "focus", "streak camera Focus")
        steps.append({"step": "Streak mode", "status": "verified Focus before shutdown"})
        streak.set_timeout_millis(30000)
        _progress(steps, "Closing HPD-TA and waiting for application exit", stage=0)
        streak.command_inout("StopApplication")
        _wait_shutdown_readback(streak, lambda: bool(_value(streak, "application_running")),
                                False, "HPD-TA closed")
        steps.append({"step": "HPD-TA", "status": "closed"})
    else:
        # Do not restart camera software just to repeat an already completed
        # shutdown. An absent application is not evidence of a safe camera mode.
        pdu = _wait_for_device(VD2_PDU_DEVICE, timeout_s=2.0)
        power = dict(zip(_value(pdu, "ids"), _value(pdu, "states")))
        if int(power.get(1, -1)) != 0:
            raise RuntimeError("Cannot confirm streak camera Focus while HPD-TA is stopped; camera power retained")
        steps.append({"step": "Streak mode", "status": "camera already unpowered; no software restart"})
    # This command checks actual local process exit, not just Tango's cache.
    _progress(steps, "Stopping RemoteEx and verifying SDK release", stage=0)
    streak.command_inout("StopRemoteEx")
    _wait_shutdown_readback(streak, lambda: bool(_value(streak, "connected")) or bool(_value(streak, "application_running")),
                            False, "RemoteEx/HPD-TA stopped")
    steps.append({"step": "RemoteEx", "status": "stopped; SDK released"})


def _shutdown_equipment(steps):
    _progress(steps, "Confirming idle acquisition, closing shutters, verifying Focus and releasing SDK owners", stage=0)
    deadline = time.monotonic() + 600.0
    previous_phase = None
    while (phase := _protocol_hardware_phase()) in {"preparing", "acquiring", "saving", "processing"}:
        if phase != previous_phase:
            _progress(steps, f"Waiting for HIS {phase} to finish before shutdown; power retained", stage=0)
            previous_phase = phase
        if time.monotonic() >= deadline:
            raise RuntimeError(f"HIS measurement/save did not finish ({phase}); power retained")
        time.sleep(0.5)
    streak = _wait_for_device(STREAK_DEVICE, timeout_s=5.0)
    _shutdown_hpdta(streak, steps)

    # Deinitialize the SDK owner, not the Tango server process.
    starter = _astor(KYMERA_DEVICE)
    if VD2_SERVERS[KYMERA_DEVICE] in set(starter.command_inout("DevGetRunningServers", True)):
        kymera = _wait_for_device(KYMERA_DEVICE, timeout_s=2.0)
        _assert_kymera_passive_server(kymera)
        if str(kymera.state()).split(".")[-1].upper() != "OFF":
            kymera.command_inout("turn_off")
        _verify_kymera_sdk_released(kymera)
    steps.append({"step": "Kymera SDK ownership", "status": "released; Tango server retained"})

    errors, warnings = [], []
    vd2_pdu = None
    try:
        vd2_pdu = _ensure_server(ZABER_PDU_DEVICE, steps)
        _progress(steps, "Switching off VD2 flashlamp only; retaining Xe lamp cooling power on output 2")
        _disable_pdu_outputs(vd2_pdu, steps, VD2_LAMP_SHUTDOWN_OUTPUTS, "VD2")
        xenon_power = dict(zip(_value(vd2_pdu, "ids"), _value(vd2_pdu, "states")))[2]
        steps.append({"step": "Xe lamp cooling supply (VD2 output 2)",
                      "status": "retained ON" if xenon_power == 1 else "already OFF; outlet unchanged",
                      "detail": "Switch the Xe lamp off manually; leave PDU power ON for cooling. Unprepare never switches this outlet off."})
        if xenon_power != 1:
            warnings.append("Xe lamp cooling outlet 2 was already OFF; Unprepare left it unchanged. Check the physical lamp switch and cooling before proceeding.")
    except Exception as exc:
        detail = f"VD2 lamp shutdown unverified: {exc}"
        errors.append(detail)
        steps.append({"step": "VD2 lamp supplies", "status": "failed", "detail": detail})
        _progress(steps, "VD2 PDU/lamp shutdown failed; continuing independent shutdown checks")
    # Zaber is always-on: stop motion, but never change its outlet or stop its
    # device server. If the outlet was already OFF, leave it OFF, without restart.
    try:
        if vd2_pdu is None:
            raise RuntimeError("VD2 PDU unavailable; motor outlet cannot be verified")
        zaber_power = dict(zip(_value(vd2_pdu, "ids"), _value(vd2_pdu, "states")))
        if int(zaber_power.get(3, 1)) != 0:
            _progress(steps, "Stopping Zaber motion; always-on motor power and device server retained")
            zaber = _wait_for_device(ZABER_STAGE_DEVICE, timeout_s=2.0)
            zaber.set_timeout_millis(10000)
            zaber.command_inout("Stop")
            deadline = time.monotonic() + 10.0
            while str(zaber.state()).split(".")[-1] != "ON":
                if time.monotonic() >= deadline:
                    raise RuntimeError("Zaber did not confirm motion stopped")
                time.sleep(0.5)
            if not math.isfinite(float(_value(zaber, "position_mm"))):
                raise RuntimeError("Zaber position readback is invalid")
            steps.append({"step": "Zaber", "status": "stopped; power retained"})
        else:
            steps.append({"step": "Zaber", "status": "already unpowered; outlet unchanged"})
    except Exception as exc:
        detail = f"Zaber power retained: cannot confirm stopped motion: {exc}"
        steps.append({"step": "Zaber", "status": "failed", "detail": detail})
        errors.append(detail)

    _progress(steps, "Verifying stopped VD2 stages; retaining shared OWIS supply", stage=1)
    # Stop only VD2's axis. The shared controller and every V0 outlet stay on.
    try:
        owis = _wait_for_device(OWIS_SAMPLE_DEVICE, timeout_s=2.0)
        owis.set_timeout_millis(5000)
        result = owis.command_inout("stop_axis", OWIS_SAMPLE_AXIS)
        if str(result).strip() != "0":
            raise RuntimeError(str(result))
        if int(owis.command_inout("get_status_axis", OWIS_SAMPLE_AXIS)) not in {int(DevState.ON), int(DevState.OFF)}:
            raise RuntimeError("OWIS axis 2 did not confirm stopped motion")
        steps.append({"step": "OWIS sample axis 2", "status": "stopped; shared power retained"})
    except Exception as exc:
        detail = f"OWIS axis 2 could not be verified; shared controller power unchanged: {exc}"
        warnings.append(detail)
        steps.append({"step": "OWIS sample axis 2", "status": "unverified", "detail": detail})

    try:
        sd2_pdu = _ensure_server(VD2_PDU_DEVICE, steps)
        _progress(steps, "Switching off verified dedicated trigger / camera supplies", stage=2)
        _disable_vd2_power(sd2_pdu, steps)
    except Exception as exc:
        detail = f"SD2 trigger/camera shutdown unverified: {exc}"
        errors.append(detail)
        steps.append({"step": "SD2 supplies", "status": "failed", "detail": detail})
    steps.append({"step": "Retained supplies", "status": "Xe lamp cooling power, Zaber power, SD2 control supply and shared V0/OWIS outputs unchanged"})

    if errors:
        raise RuntimeError("; ".join(errors))
    if warnings:
        return {"steps": steps, "warnings": warnings, "message":
                "VD2 flashlamp / camera / trigger supplies are OFF. Xe lamp cooling power unchanged; switch the lamp off manually and leave cooling powered. Zaber power unchanged. Check the reported warnings."}
    return {"steps": steps, "warnings": warnings, "message":
            "VD2 safely shut down; flashlamp / camera / trigger supplies verified OFF. Xe lamp cooling power unchanged; switch the lamp off manually and leave cooling powered. Zaber power unchanged; Tango servers retained."}


def _to_display_pixels(pixels: bytes, bytes_per_pixel: int) -> bytes:
    """Convert a Tango-delivered display frame to compact browser pixels."""
    if bytes_per_pixel == 1:
        return pixels
    if bytes_per_pixel != 2:
        raise RuntimeError(
            f"Unsupported HPD-TA display pixel format: {bytes_per_pixel} bytes/pixel"
        )

    samples = [
        pixels[index] | (pixels[index + 1] << 8)
        for index in range(0, len(pixels), 2)
    ]
    minimum, maximum = min(samples), max(samples)
    if maximum == minimum:
        return bytes(len(samples))
    scale = 255.0 / (maximum - minimum)
    return bytes(int((sample - minimum) * scale) for sample in samples)


def _read_display_frame(proxy: DeviceProxy) -> Dict[str, Any]:
    """Read a frame through Tango so RemoteEx has exactly one owner."""
    frame = json.loads(proxy.command_inout("GetCurrentDisplayFrame"))
    pixels = _to_display_pixels(
        base64.b64decode(frame["pixels_b64"]), int(frame["bytes_per_pixel"])
    )

    return {
        "width": int(frame["width"]),
        "height": int(frame["height"]),
        "data_type": frame["data_type"],
        "display_rescaled": int(frame["bytes_per_pixel"]) != 1,
        "pixels_b64": base64.b64encode(pixels).decode("ascii"),
        "minimum": min(pixels),
        "maximum": max(pixels),
    }


def _missing_current_image_status(exc: Exception, commands) -> str | None:
    """Recognize only exact empty-image replies for the specified operations."""
    descriptions = [str(error.desc) for error in exc.args if hasattr(error, "desc")]
    lines = [line.strip() for description in descriptions or [str(exc)]
             for line in description.splitlines()]
    for command in commands:
        source_status = f"7,{command.split('(', 1)[0]},No valid image"
        expected = (f"RemoteEx command failed for '{command}': {source_status}",
                    f"Invalid {command} readback: {source_status}")
        if any(line.endswith(expected) for line in lines):
            return source_status
    return None


def _waiting_for_current_image(source_status):
    return {"success": True, "frame_available": False,
            "stream_state": "no_valid_image", "source_status": source_status}


_DEFERRED_ACQUISITION_READ = "VD2 operation in progress; acquisition status not queried"


def _deferred_camera_state():
    return jsonify(success=True, state_deferred=True, device=STREAK_DEVICE,
                   acquisition_status="unknown", acquisition_mode=None,
                   attribute_errors={"acquisition_status": _DEFERRED_ACQUISITION_READ})


def _acquisition_snapshot(proxy, snapshot):
    snapshot["acquisition_status"] = "unknown"
    snapshot["acquisition_mode"] = None
    snapshot["cached_remoteex_status"] = snapshot["remoteex_status"]
    snapshot["remoteex_status"] = "unknown"
    try:
        phase, _, mode = _remoteex_readback(proxy, "AcqStatus()").partition(",")
        phase = phase.lower()
        if phase not in {"idle", "busy"}:
            raise RuntimeError(f"Unknown acquisition status: {phase}")
        snapshot.update(acquisition_status=phase, acquisition_mode=mode or None,
                        remoteex_status=phase, application_running=True)
    except Exception as exc:
        snapshot["attribute_errors"]["acquisition_status"] = (
            _DEFERRED_ACQUISITION_READ if camera_serialization_timeout(exc) else _control_error(exc)
        )
    return snapshot


def _existing_local_remoteex_listener(proxy):
    """Read Windows listener ownership; do not open a second RemoteEx socket."""
    if os.name != "nt":
        return False
    properties = proxy.get_property(["host", "command_port"])
    host = (properties.get("host") or ["localhost"])[0]
    if str(host).lower() not in {"localhost", "127.0.0.1", "::1"}:
        return False
    port = int((properties.get("command_port") or [1001])[0])
    if not 1 <= port <= 65535:
        return False
    # Get-NetTCPConnection via a new PowerShell process can itself exceed the
    # reconnection timeout. Read the same Windows socket/owner table directly;
    # psutil is already pinned in the project's requirements.
    import psutil
    try:
        for connection in psutil.net_connections(kind="tcp"):
            if (connection.status == psutil.CONN_LISTEN and connection.laddr
                    and connection.laddr.port == port and connection.pid):
                if psutil.Process(connection.pid).name().lower() in {"taremoteex.exe", "taremoteex"}:
                    return True
    except (psutil.Error, OSError) as exc:
        raise RuntimeError(f"Cannot verify local RemoteEx listener ownership: {exc}") from exc
    return False


@pump_probe_vd2_api.route("/refresh", methods=["POST"])
@_serialized_vd2_mutation
def refresh_connection():
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    blocked = _approval_or_response(
        "connection.refresh", [_target(STREAK_DEVICE, "StartRemoteEx"), _target(STREAK_DEVICE, "ExecuteRaw")],
        {}, "vd2.connection.refresh", set(),
    )
    if blocked is not None:
        return blocked
    try:
        if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            return jsonify(success=False, error="Wait for the HIS measurement before reconnecting"), 409
        proxy = _proxy()
        if not bool(_value(proxy, "connected")):
            if not _existing_local_remoteex_listener(proxy):
                return jsonify({"success": False, "error": "RemoteEx is not available. Use Prepare Experiment to start equipment."}), 409
            # Legacy command attaches first. Never invoke its cold-start path
            # unless an existing local TaRemoteEx listener was verified above.
            proxy.command_inout("StartRemoteEx")
        snapshot = _acquisition_snapshot(proxy, _snapshot(proxy))
        if snapshot["acquisition_status"] == "unknown":
            raise RuntimeError(snapshot["attribute_errors"]["acquisition_status"])
        return jsonify({"success": True, **snapshot})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/state", methods=["GET"])
def state():
    if not _preparation_lock.acquire(blocking=False):
        return _deferred_camera_state()
    try:
        # The HIS worker owns the camera after the start request releases this
        # lock. Its protocol status is available without entering Tango.
        if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            return _deferred_camera_state()
        proxy = _proxy()
        snapshot = _snapshot(proxy)
        snapshot["acquisition_status"] = "unknown"
        snapshot["acquisition_mode"] = None
        # Tango's legacy Status() cache can say idle during native Live.
        # Query only acquisition state, through the existing sole socket owner.
        if snapshot["connected"] and snapshot["remoteex_status"] not in {"starting", "preparing"}:
            snapshot = _acquisition_snapshot(proxy, snapshot)
            if (snapshot.get("application_running") and snapshot.get("acquisition_status") in {"idle", "busy"}
                    and snapshot.get("acquisition_mode") in {None, "Live"}):
                try:
                    view = "alignment" if request.headers.get("X-VD2-View") == "alignment" else "acquisition"
                    ui = {"tab": view}
                    if request.headers.get("X-Workspace-Browser") and request.headers.get("X-Workspace-Window"):
                        from vd2_workspace_api import workspace_repository, browser_identity
                        saved = workspace_repository().get(browser_identity(), request.headers["X-Workspace-Window"])
                        if saved:
                            ui["form"] = saved["settings"]
                    _remember_camera(snapshot, "alignment" if view == "alignment" else "previous", ui)
                except Exception as exc:
                    snapshot["recovery_warning"] = f"Camera return point was not saved: {exc}"
        return jsonify({"success": True, **snapshot})
    except Exception as exc:
        if camera_serialization_timeout(exc):
            return _deferred_camera_state()
        return jsonify({"success": False, "error": str(exc), "device": STREAK_DEVICE}), 503
    finally:
        _preparation_lock.release()


@pump_probe_vd2_api.route("/preview", methods=["GET"])
def preview():
    global _preview_cache, _preview_cache_until
    # One native reader for all browser tabs. Cached frames retain their original
    # timestamp; waiting clients never queue a second RemoteEx binary transfer.
    phase_status = _protocol_hardware_phase()
    if phase_status in {"saving", "processing"}:
        _alignment_readout.unavailable()
        return jsonify({"success": True, "frame_available": False,
                        "stream_state": phase_status})
    if time.monotonic() < _preview_cache_until and _preview_cache is not None:
        payload, status = _preview_cache
        return jsonify(payload), status
    if not _preview_lock.acquire(blocking=False):
        # Drop this display request when the current image is already being read.
        return jsonify({"success": True, "frame_available": False,
                        "stream_state": "waiting_for_frame"})
    started = time.monotonic()
    try:
        if started < _preview_cache_until and _preview_cache is not None:
            payload, status = _preview_cache
            return jsonify(payload), status
        proxy = _proxy()
        if str(proxy.state()).split(".")[-1] not in {"ON", "RUNNING"}:
            payload = {"success": False, "error": "Hamamatsu Tango device is not connected"}
            _alignment_readout.unavailable()
            _preview_cache = (payload, 409)
            _preview_cache_until = started + _preview_period
            return jsonify(payload), 409
        if not bool(_value(proxy, "application_running")):
            payload = {"success": False, "error": "HPD-TA is still starting"}
            _alignment_readout.unavailable()
            _preview_cache = (payload, 409)
            _preview_cache_until = started + _preview_period
            return jsonify(payload), 409
        checked_at = time.monotonic()
        phase_status = _protocol_hardware_phase()
        period = max(_preview_period, 1.0) if phase_status == "acquiring" else _preview_period
        if phase_status in {"saving", "processing"}:
            _alignment_readout.unavailable()
            return jsonify({"success": True, "frame_available": False,
                            "stream_state": phase_status})
        try:
            frame = _read_display_frame(proxy)
        except Exception as exc:
            source_status = _missing_current_image_status(exc, ("ImgDataGet(Current,Display)",))
            if source_status is None:
                raise
            # Prepare starts equipment, not acquisition. HPD-TA can legitimately
            # have no current image yet; do not start Live or reuse stale pixels.
            _alignment_readout.unavailable()
            payload = _waiting_for_current_image(source_status)
            _preview_cache = (payload, 200)
            _preview_cache_until = time.monotonic() + period
            return jsonify(payload)
        captured_at = datetime.now(timezone.utc).isoformat()
        pixels_at = time.monotonic()
        active = (_string(_value(proxy, "remoteex_status")).lower() == "busy"
                  or phase_status == "acquiring")
        with _alignment_axes_lock:
            axes = _alignment_axes
        # A HIS capture shares RemoteEx with this preview. Its pixel preview
        # needs no extra native calibration/status commands on every frame.
        if phase_status != "acquiring":
            try:
                signature, intensity_settings = _alignment_frame_metadata(proxy)
                frame["calibration_key"] = alignment_calibration_key(signature, frame["width"], frame["height"])
                frame["intensity_key"] = alignment_calibration_key(intensity_settings, frame["width"], frame["height"])
                frame["measurement_key"] = alignment_measurement_key(intensity_settings, frame["width"], frame["height"], _live_average_readback)
                if (axes and (axes["width"], axes["height"]) == (frame["width"], frame["height"])
                        and axes.get("settings") == signature):
                    frame["calibration"] = axes
            except Exception as exc:
                source_status = _missing_current_image_status(exc, ("ImgStatusGet(Current,All)",))
                if source_status is not None:
                    # The current image can disappear between pixels and metadata.
                    _alignment_readout.unavailable()
                    payload = _waiting_for_current_image(source_status)
                    _preview_cache = (payload, 200)
                    _preview_cache_until = time.monotonic() + period
                    return jsonify(payload)
                frame["calibration_error"] = _control_error(exc)
        payload = {"success": True, "frame_available": True, **frame,
                   "stream_state": "acquiring" if active else "last_frame",
                   "received_at": captured_at,
                   "read_timings_ms": {
                       "device_checks": round((checked_at - started) * 1000, 3),
                       "pixels": round((pixels_at - checked_at) * 1000, 3),
                       "metadata": round((time.monotonic() - pixels_at) * 1000, 3),
                   }}
        _alignment_readout.observe(payload, pixels_at)
        _preview_cache = (payload, 200)
        _preview_cache_until = started + period
        return jsonify(payload)
    except Exception as exc:
        payload = {"success": False, "error": _control_error(exc)}
        _alignment_readout.unavailable()
        _preview_cache = (payload, 503)
        _preview_cache_until = time.monotonic() + _preview_period
        return jsonify(payload), 503
    finally:
        _preview_lock.release()


@pump_probe_vd2_api.route("/alignment/readout", methods=["GET"])
def alignment_readout():
    """Analyse a frame already read by preview, with this window's geometry."""
    if request.args.get("capabilities") == "1":
        result = jsonify({"success": True, "version": READOUT_VERSION})
    else:
        try:
            frame_id = request.args.get("frame", "")
            if not frame_id or len(frame_id) > 64:
                raise ValueError("A preview frame identifier is required.")
            region, windows = parse_selection(request.args.get("selection", ""))
            if _protocol_hardware_phase() in {"saving", "processing"}:
                _alignment_readout.unavailable()
            result = jsonify({"success": True, **_alignment_readout.read(frame_id, region, windows)})
        except (ValueError, LookupError) as exc:
            result = jsonify({"success": False, "error": str(exc)})
            result.status_code = 404 if isinstance(exc, LookupError) else 422
    result.headers["Cache-Control"] = "no-store"
    return result


def _machine_snapshot(streak):
    """Read scalar settings from fixed VD2 devices; unavailable values remain explicit."""
    result = {"captured_at": datetime.now(timezone.utc).isoformat(), "devices": {},
              "coverage": "Available Tango scalar attributes and bounded iTest/OWIS readback arrays; image data excluded; no settings restored automatically"}
    bounded_arrays = {
        "ELYSE/pdu/iTest": {"names", "ids", "states", "currents_setpoint", "currents_meas", "current_limits"},
        OWIS_SAMPLE_DEVICE: {"states", "positions", "device_names", "friendly_names"},
    }
    try:
        result["streak_control"] = _snapshot(streak)
    except Exception as exc:
        result["streak_control"] = {"error": _control_error(exc)}
    for device in (STREAK_DEVICE, KYMERA_DEVICE, DG645_DEVICE, OWIS_SAMPLE_DEVICE,
                   ZABER_STAGE_DEVICE, "ELYSE/pdu/iTest"):
        entry = {"values": {}, "errors": {}}
        result["devices"][device] = entry
        try:
            proxy = DeviceProxy(device)
            proxy.set_timeout_millis(1500)
            configuration = proxy.attribute_list_query_ex()
            names = [item.name for item in configuration
                     if getattr(item.data_format, "name", str(item.data_format).split(".")[-1]) == "SCALAR"
                     or (getattr(item.data_format, "name", str(item.data_format).split(".")[-1]) == "SPECTRUM"
                         and item.name in bounded_arrays.get(device, set()))]
            for name, attribute in zip(names, proxy.read_attributes(names)):
                try:
                    failed = getattr(attribute, "has_failed", False)
                    if (failed() if callable(failed) else failed):
                        raise RuntimeError(str(attribute.get_err_stack()))
                    value = attribute.value
                    if hasattr(value, "tolist"):
                        value = value.tolist()
                    elif hasattr(value, "item"):
                        value = value.item()
                    if isinstance(value, (list, tuple)):
                        if len(value) > 128:
                            raise ValueError("Readback array exceeds 128 values")
                        value = list(value)
                        if any(isinstance(item, float) and not math.isfinite(item) for item in value):
                            raise ValueError("Non-finite array readback")
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValueError("Non-finite readback")
                    if not isinstance(value, (str, bool, int, float, list, type(None))):
                        value = str(value)
                    entry["values"][name] = value
                except Exception as exc:
                    entry["errors"][name] = _control_error(exc)
            entry["observed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            entry["errors"]["device"] = _control_error(exc)
    for key, reader in (("owis_sample", _owis_sample_stage_state), ("zaber_mirror", _zaber_stage_state)):
        try:
            result[key] = reader()
        except Exception as exc:
            result[key] = {"error": _control_error(exc)}
    result["live_rolling_average"] = _live_average_readback
    # Tango values can contain enums and platform numbers. Preserve their text
    # representation without allowing NaN or non-JSON values into the journal.
    return json.loads(json.dumps(result, default=str, allow_nan=False))


@pump_probe_vd2_api.route("/protocol/project", methods=["GET"])
def protocol_project():
    try:
        from treatment_api import _ensure_within_allowed_root
        root = Path(_ensure_within_allowed_root(request.args.get("output_root", "")))
        path = root / MANIFEST_NAME
        if not root.is_absolute():
            raise ValueError("Project folder must be absolute")
        if not path.exists():
            return jsonify({"success": True, "manifest_path": str(path), "samples": [], "bruit_options": []})
        return jsonify({"success": True, **inspect_project(path, verify_files=False)})
    except (OSError, ValueError, KeyError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@pump_probe_vd2_api.route("/protocol/state", methods=["GET"])
def protocol_state():
    return jsonify({"success": True, **_measurement_protocol.status()})


@pump_probe_vd2_api.route("/protocol/plan", methods=["POST"])
def protocol_plan():
    """Review destinations without creating folders or contacting a device."""
    fields = {"phase", "frames_per_his", "output_root", "run_name"}
    raw = request.get_json(silent=True)
    if isinstance(raw, Mapping):
        fields |= {"sample_description", "reuse_bruit"}.intersection(raw)
    payload, rejected = _mutation_payload(fields)
    if rejected is not None:
        return rejected
    try:
        if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            raise Vd2ProtocolError("A VD2 HIS acquisition is already running")
        if _measurement_protocol.status().get("queue_full"):
            raise Vd2ProtocolError("H5 conversion queue is full; wait for a conversion to finish")
        request_data = _measurement_protocol._build_request(
            payload.get("phase"), payload.get("frames_per_his"), payload.get("output_root"), payload.get("run_name"),
            payload.get("sample_description", ""), payload.get("reuse_bruit", "latest"))
        from treatment_api import _ensure_within_allowed_root
        _ensure_within_allowed_root(request_data.output_root)
        return jsonify(success=True, **_phase_destinations.review(request_data))
    except (OSError, ValueError, Vd2ProtocolError) as exc:
        return jsonify(success=False, error=str(exc)), 409


@pump_probe_vd2_api.route("/protocol/start", methods=["POST"])
@_serialized_vd2_mutation
def protocol_start():
    fields = {"phase", "frames_per_his", "output_root", "run_name"}
    raw = request.get_json(silent=True)
    if isinstance(raw, Mapping):
        fields |= {"sample_description", "reuse_bruit", "destination_token"}.intersection(raw)
    payload, rejected = _mutation_payload(fields)
    if rejected is not None:
        return rejected
    try:
        request_data = _measurement_protocol._build_request(
            payload.get("phase"),
            payload.get("frames_per_his"),
            payload.get("output_root"),
            payload.get("run_name"),
            payload.get("sample_description", ""),
            payload.get("reuse_bruit", "latest"),
        )
        original_request = request_data
        destination_token = payload.get("destination_token")
        if "destination_token" in payload:
            request_data = _phase_destinations.resolve(destination_token, original_request)
        targets, args = _protocol_authorization(request_data)
        if "destination_token" in payload:
            args["destination_token"] = destination_token
        blocked = _approval_or_response(
            "start",
            targets,
            args,
            "vd2.protocol.start",
            fields,
        )
        if blocked is not None:
            return blocked
        if "destination_token" in payload:
            request_data = _phase_destinations.consume(destination_token, original_request)
        _verify_vd2_timing_ready(_proxy())
        state = _measurement_protocol.start_request(request_data) if "destination_token" in payload else _measurement_protocol.start(
            phase=request_data.phase,
            frames_per_his=request_data.frames_per_his,
            output_root=request_data.output_root,
            run_name=request_data.run_name,
            sample_description=request_data.sample_description,
            reuse_bruit=request_data.reuse_bruit,
        )
        return jsonify({"success": True, **state})
    except Vd2ProtocolError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/runtime/state", methods=["GET"])
def runtime_state():
    try:
        snapshot = _snapshot(_proxy())
        return jsonify(
            {
                "success": True,
                "remoteex_running": snapshot["connected"],
                "hpdta_running": snapshot["application_running"],
                "device": snapshot,
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


def _zaber_stage_state() -> dict[str, Any]:
    result: dict[str, Any] = {
        "device": ZABER_STAGE_DEVICE,
        "state": "UNKNOWN",
        "position_mm": None,
        "minimum_mm": None,
        "maximum_mm": None,
    }
    try:
        proxy = DeviceProxy(ZABER_STAGE_DEVICE)
        proxy.set_timeout_millis(2000)
        result["state"] = str(proxy.state()).rsplit(".", 1)[-1]
        result["status"] = str(proxy.status())
        if result["state"] == "ON":
            for key in ("position_mm", "minimum_mm", "maximum_mm"):
                result[key] = float(proxy.read_attribute(key).value)
    except Exception as exc:
        result["error"] = str(exc)
    return result


def _owis_sample_stage_state() -> dict[str, Any]:
    result: dict[str, Any] = {
        "device": OWIS_SAMPLE_DEVICE,
        "axis": OWIS_SAMPLE_AXIS,
        "state": "UNKNOWN",
        "position_mm": None,
        "minimum_mm": None,
        "maximum_mm": None,
    }
    try:
        proxy = DeviceProxy(OWIS_SAMPLE_DEVICE)
        proxy.set_timeout_millis(2000)
        result["state"] = str(proxy.state()).rsplit(".", 1)[-1]
        axis_state = int(proxy.command_inout("get_status_axis", OWIS_SAMPLE_AXIS))
        result["axis_state"] = next(
            (
                str(candidate).rsplit(".", 1)[-1]
                for candidate in (DevState.ON, DevState.OFF, DevState.MOVING, DevState.FAULT)
                if int(candidate) == axis_state
            ),
            "UNKNOWN",
        )
        result["position_mm"] = float(proxy.read_attribute("pos2").value)
        properties = proxy.get_property(["delay_lines_parameters"])
        raw = properties.get("delay_lines_parameters", [])
        if raw:
            parameters = ast.literal_eval(str(raw[0]))
            axis = parameters.get(OWIS_SAMPLE_AXIS, parameters.get(str(OWIS_SAMPLE_AXIS), {}))
            result["minimum_mm"] = float(axis["limit_min"])
            result["maximum_mm"] = float(axis["limit_max"])
    except Exception as exc:
        result["error"] = str(exc)
    return result


@pump_probe_vd2_api.route("/stages/state", methods=["GET"])
def stages_state():
    """Passive, structured readings for the mirror and VD2 sample stage."""
    return jsonify({
        "success": True,
        "zaber_mirror": _zaber_stage_state(),
        "owis_sample": _owis_sample_stage_state(),
    })


@pump_probe_vd2_api.route("/lifecycle", methods=["GET"])
def lifecycle_state():
    """Read saved progress only: never start, initialize or power equipment."""
    return jsonify({"success": True, "job": _lifecycle().snapshot()})


@pump_probe_vd2_api.route("/lifecycle/log", methods=["GET"])
def lifecycle_log():
    try:
        raw_before = request.args.get("before")
        before = int(raw_before) if raw_before is not None else None
        if before is not None and before < 1:
            raise ValueError("Invalid log cursor")
        events = _lifecycle().events(before=before)
        return jsonify({"success": True, "events": events})
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid log cursor"}), 400


@pump_probe_vd2_api.route("/initialize", methods=["POST"])
def initialize_experiment():
    if authorization_required():
        # Preserve the existing empty-envelope/exact-plan guard. Saved settings
        # are never an alternative authorization path for conditional startup.
        _, rejected = _mutation_payload(set())
        return rejected if rejected is not None else _exact_plan_required()
    payload, rejected = _mutation_payload({"restore_id", "restore_mode"})
    if rejected is not None:
        return rejected
    try:
        if set(payload) - {"restore_id", "restore_mode"}:
            raise ValueError("Unsupported preparation fields")
        mode = payload.get("restore_mode", "default")
        if mode not in {"default", "previous", "alignment", "point"}:
            raise ValueError("Invalid restoration mode")
        identity = payload.get("restore_id")
        if mode in {"previous", "point"} and not identity:
            raise ValueError("Choose an existing camera return point")
        if mode == "default" and identity is not None:
            raise ValueError("Default preparation cannot include a camera return point")
        saved = _recovery_snapshots().get(identity) if identity is not None else None
        if saved and mode in {"alignment", "point"} and saved["kind"] != mode:
            raise ValueError("The selected return point belongs to another mode")
    except (ValueError, TypeError) as exc:
        return jsonify(success=False, error=str(exc)), 400
    targets, args = _initialize_authorization()
    if mode != "default":
        settings = saved["settings"] if saved else {"time_range": "1 us", "streak_mode": "Operate"}
        targets.extend(_target(STREAK_DEVICE, WRITABLE_PARAMETERS[name].get("command") or
                               f"write_attribute:{WRITABLE_PARAMETERS[name]['attribute']}")
                       for name in settings if name in WRITABLE_PARAMETERS)
        targets.append(_target(STREAK_DEVICE, "ExecuteRaw"))
        args.update(restore_mode=mode, restore_id=identity, restore_settings=settings)
    blocked = _approval_or_response(
        "initialize",
        targets,
        args,
        "vd2.initialize",
        set(payload),
    )
    if blocked is not None:
        return blocked
    action = _initialize_experiment if mode == "default" else lambda steps=None: _initialize_with_restore(mode, saved, steps)
    if request.args.get("background") == "1":
        intent = None if mode == "default" else {"restore_mode": mode, "restore_id": identity}
        return _start_lifecycle("prepare", action, intent=intent)
    if not _preparation_lock.acquire(blocking=False):
        return jsonify({"success": False, "error": "VD2 preparation is already in progress"}), 409
    try:
        result = action()
        return jsonify({"success": True, **result})
    except AlreadyPrepared as exc:
        return jsonify({"success": False, "code": exc.code, "error": str(exc), "steps": exc.steps}), 409
    except Exception as exc:
        return jsonify({
            "success": False, "error": _control_error(exc),
            "steps": getattr(exc, "steps", []),
        }), 503
    finally:
        _preparation_lock.release()


@pump_probe_vd2_api.get("/recovery/options")
def recovery_options():
    """SQLite only. Opening the choice never probes or recovers a device."""
    try:
        return jsonify(success=True, options=_recovery_snapshots().options())
    except Exception as exc:
        return jsonify(success=False, error=f"Camera return points unavailable: {exc}"), 503


def _restore_readback(proxy, name):
    try:
        return _remoteex_readback(proxy, RECOVERY_PARAMETERS[name])
    except Exception as exc:
        if name == "mcp_gain" and "DevParamGet" in str(exc) and not _shutdown_timed_out(exc):
            return _remoteex_readback(proxy, "DevParamGet(TD,II-Gain)")
        raise


def _initialize_with_restore(mode, saved, steps=None):
    global _alignment_axes
    steps = steps if steps is not None else []
    try:
        try:
            result = _initialize_experiment(steps)
        except AlreadyPrepared as exc:
            result = exc.result
        proxy = _proxy()
        # Native range/mode setters already allow 30 s. The outer Tango call
        # must observe their result rather than expire halfway through a setter.
        proxy.set_timeout_millis(45000)
        _assert_preparation_idle(proxy)
        settings = saved["settings"] if saved else {"time_range": "1 us", "streak_mode": "Operate"}
        profile = timing_for_range(settings["time_range"])
        with _alignment_axes_lock:
            _alignment_axes = None
        # Mode is restored last, after the calibrated sweep and camera settings.
        order = [name for name in settings if name not in {"streak_mode", "rolling_average"}] + ["streak_mode"]
        for name in order:
            value = settings[name]
            _progress(steps, f"Restoring camera {name}: {value}", stage=2)
            if not equivalent(name, value, _restore_readback(proxy, name)):
                spec = WRITABLE_PARAMETERS[name]
                if "attribute" in spec:
                    proxy.write_attribute(spec["attribute"], spec["coerce"](value))
                else:
                    proxy.command_inout(spec["command"], value)
                if not equivalent(name, value, _restore_readback(proxy, name)):
                    raise RuntimeError(f"Camera {name} readback does not match {value}")
                if name == "time_range":
                    _apply_vd2_timing(profile, steps)
            steps.append({"step": f"Restore {name}", "status": f"verified: {value}"})
        average = settings.get("rolling_average")
        if average is not None:
            for parameter, value in (("RecurNumber2", str(average["frames"])), ("RecurFilter2", str(int(average["enabled"])))):
                query = f"CamParamGet(Live,{parameter})"
                if _remoteex_readback(proxy, query) != value:
                    reply = str(proxy.command_inout("ExecuteRaw", f"CamParamSet(Live,{parameter},{value})")).strip().split(",")
                    if reply[:2] != ["0", "CamParamSet"]:
                        raise RuntimeError(f"Cannot restore {parameter}: {','.join(reply)}")
                    if _remoteex_readback(proxy, query) != value:
                        raise RuntimeError(f"Cannot verify restored {parameter}")
            _live_average_state(proxy)
        dg645 = DeviceProxy(DG645_DEVICE)
        dg645.set_timeout_millis(5000)
        verify_timing(dg645, profile)
        _verify_vd2_timing_ready(proxy)
        restored = {"mode": mode, "snapshot_id": (saved or {}).get("id"),
                    "settings": settings, "ui": (saved or {}).get("ui", {"tab": "alignment"})}
        # New job result is durable, so a browser reconnect never replays writes.
        return {**result, "device": _snapshot(proxy), "already_ready": False, "restored": restored, "steps": list(steps),
                "message": f"VD2 ready; {mode} camera settings verified ({profile.time_range}). Acquisition remains stopped; no shutter, magnet or stage settings restored."}
    except Exception as exc:
        raise PreparationFailure(f"Camera restoration incomplete: {exc}. Keep acquisition stopped; settings may be partially applied. No automatic replay.", steps) from exc


@pump_probe_vd2_api.route("/deinitialize", methods=["POST"])
def deinitialize_experiment():
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    if authorization_required():
        return _exact_plan_required()
    targets, args = _deinitialize_authorization()
    blocked = _approval_or_response(
        "deinitialize",
        targets,
        args,
        "vd2.deinitialize",
        set(),
    )
    if blocked is not None:
        return blocked
    if request.args.get("background") == "1":
        return _start_lifecycle("shutdown", _deinitialize_experiment)
    if not _preparation_lock.acquire(blocking=False):
        return jsonify({"success": False, "error": "VD2 preparation/shutdown is already in progress"}), 409
    try:
        result = _deinitialize_experiment()
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc),
                        "steps": getattr(exc, "steps", [])}), 503
    finally:
        _preparation_lock.release()


@pump_probe_vd2_api.route("/runtime/remoteex/<action>", methods=["POST"])
@_serialized_vd2_mutation
def remoteex_runtime(action: str):
    if action not in {"start", "stop"}:
        return jsonify({"success": False, "error": f"Unsupported RemoteEx action: {action}"}), 404
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    command_name = "StartRemoteEx" if action == "start" else "StopRemoteEx"
    blocked = _approval_or_response(
        f"remoteex.{action}",
        [_target(STREAK_DEVICE, command_name)],
        {"action": action},
        "vd2.remoteex",
        set(),
    )
    if blocked is not None:
        return blocked
    try:
        proxy = _proxy()
        if action == "start":
            proxy.command_inout("StartRemoteEx")
            snapshot = _snapshot(proxy)
            return jsonify(
                {
                    "success": True,
                    "remoteex_running": snapshot["connected"],
                    "hpdta_running": snapshot["application_running"],
                    "device": snapshot,
                }
            )
        if action == "stop":
            proxy.command_inout("StopRemoteEx")
            return jsonify(
                {
                    "success": True,
                    "remoteex_running": False,
                    "hpdta_running": False,
                    "device": _snapshot(proxy),
                }
            )
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/parameter/<name>", methods=["POST"])
@_serialized_vd2_mutation
def write_parameter(name: str):
    global _alignment_axes
    spec = WRITABLE_PARAMETERS.get(name)
    if spec is None:
        return jsonify({"success": False, "error": f"Unsupported parameter: {name}"}), 404

    payload, rejected = _mutation_payload({"value"})
    if rejected is not None:
        return rejected
    if "value" not in payload:
        return jsonify({"success": False, "error": "Missing value"}), 400

    try:
        value = spec["coerce"](payload["value"])
        timing = timing_for_range(value) if name == "time_range" else None
        if timing is not None:
            value = timing.time_range
        if "attribute" in spec:
            target_name = f"write_attribute:{spec['attribute']}"
        else:
            target_name = spec["command"]
        targets = [_target(STREAK_DEVICE, target_name)]
        args = {"name": name, "value": value}
        if timing is not None:
            targets.append(_target(DG645_DEVICE, "scpi_write"))
            args["dg645_timing"] = timing.as_dict()
        blocked = _approval_or_response(
            f"parameter.{name}.write",
            targets,
            args,
            "vd2.parameter",
            {"value"},
        )
        if blocked is not None:
            return blocked
        proxy = _proxy()
        if name in {"time_range", "grating", "wavelength_nm", "exit_mirror", "turret"}:
            with _alignment_axes_lock:
                _alignment_axes = None
        if timing is not None:
            _assert_preparation_idle(proxy)
        if "attribute" in spec:
            proxy.write_attribute(spec["attribute"], value)
        else:
            proxy.command_inout(spec["command"], value)
        if timing is not None:
            raw_range = _remoteex_readback(proxy, "DevParamGet(TD,Time Range)")
            try:
                actual = timing_for_range(raw_range)
            except ValueError as exc:
                raise RuntimeError(f"Streak time-range readback unverified: {raw_range}; DG645 unchanged") from exc
            if actual != timing:
                raise RuntimeError(f"Streak time-range readback mismatch: requested {timing.time_range}, got {actual.time_range}; DG645 unchanged")
            _apply_vd2_timing(timing, [])
        return jsonify({"success": True, **_snapshot(proxy)})
    except (TypeError, ValueError) as exc:
        return jsonify({"success": False, "error": f"Invalid value: {exc}"}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


def _alignment_signature(proxy):
    return image_alignment_settings(_remoteex_readback(proxy, "ImgStatusGet(Current,All)"))


def _alignment_frame_metadata(proxy):
    header = _remoteex_readback(proxy, "ImgStatusGet(Current,All)")
    return image_alignment_settings(header), image_intensity_settings(header)


def _assert_alignment_live_or_idle(proxy):
    status = _remoteex_readback(proxy, "AcqStatus()").lower()
    if status not in {"idle", "busy,live"}:
        raise RuntimeError(f"Alignment read is unavailable during this acquisition: {status}")


def _capture_alignment_axes(proxy):
    global _alignment_axes
    with _alignment_axes_lock:
        _alignment_axes = None
    signature = _alignment_signature(proxy)
    _alignment_image_path.parent.mkdir(parents=True, exist_ok=True)
    _alignment_image_path.unlink(missing_ok=True)
    proxy.command_inout("SaveCurrentImage", str(_alignment_image_path))
    deadline = time.monotonic() + 3.0
    while True:
        try:
            axes = read_alignment_axes(_alignment_image_path)
            break
        except (OSError, ValueError, IndexError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Current-image calibration unavailable: {exc}") from exc
            time.sleep(0.05)
    if signature != _alignment_signature(proxy):
        raise RuntimeError("Optical settings changed during calibration; refresh calibration")
    acquired = axes["acquisition_settings"]
    acquired_wavelength = float(acquired["wavelength_nm"])
    current_wavelength = float(signature["wavelength_nm"])
    if (acquired["time_range"].replace(" ", "").lower() != signature["time_range"].replace(" ", "").lower()
            or acquired["grating"].lower() != signature["grating"].lower()
            or not acquired["wavelength_nm"]
            or not all(map(math.isfinite, (acquired_wavelength, current_wavelength)))
            or abs(acquired_wavelength - current_wavelength) > 0.001):
        raise RuntimeError("Current image predates optical settings; refresh calibration after a new frame")
    axes["settings"] = signature
    axes["calibration_key"] = alignment_calibration_key(signature, axes["width"], axes["height"])
    with _alignment_axes_lock:
        _alignment_axes = axes
    return axes


@pump_probe_vd2_api.route("/alignment/calibration", methods=["GET", "POST"])
@_serialized_vd2_mutation
def alignment_calibration():
    global _alignment_axes, _preview_cache, _preview_cache_until
    if request.method == "GET":
        with _alignment_axes_lock:
            return jsonify({"success": True, "calibration": _alignment_axes})
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    blocked = _approval_or_response(
        "alignment.calibration", [_target(STREAK_DEVICE, "SaveCurrentImage")],
        {"image_path": str(_alignment_image_path)}, "vd2.alignment.calibration", set(),
    )
    if blocked is not None:
        return blocked
    try:
        if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            raise RuntimeError("Wait for the HIS measurement before refreshing calibration")
        proxy = _proxy()
        _assert_alignment_live_or_idle(proxy)
        return jsonify({"success": True, "calibration": _capture_alignment_axes(proxy)})
    except Exception as exc:
        source_status = _missing_current_image_status(exc, (
            "ImgStatusGet(Current,All)",
            f"ImgSave(Current,IMG,{_alignment_image_path},1)",
        ))
        if source_status is not None:
            with _alignment_axes_lock:
                _alignment_axes = None
            payload = _waiting_for_current_image(source_status)
            _preview_cache = (payload, 200)
            _preview_cache_until = time.monotonic() + _preview_period
            return jsonify({**payload, "calibration": None})
        return jsonify({"success": False, "error": _control_error(exc)}), 503


def _zaber_at_flash_lamp(stage):
    position = stage.get("position_mm")
    return (stage.get("state") == "ON" and not stage.get("error")
            and isinstance(position, (int, float)) and math.isfinite(position)
            and abs(position - ZABER_FLASH_LAMP_MM) <= ZABER_PRESET_TOLERANCE_MM)


def _alignment_optics_snapshot():
    result = {"observed_at": datetime.now(timezone.utc).isoformat(),
              "zaber_mirror": _zaber_stage_state(), "shutters": {}}
    for key in ("position_mm", "minimum_mm", "maximum_mm"):
        value = result["zaber_mirror"].get(key)
        if isinstance(value, float) and not math.isfinite(value):
            result["zaber_mirror"][key] = None
            result["zaber_mirror"]["error"] = "Zaber returned a non-finite position or travel limit"
    result["zaber_mirror"]["at_flash_lamp"] = _zaber_at_flash_lamp(result["zaber_mirror"])
    try:
        proxy = _proxy()
    except Exception as exc:
        proxy = None
        connection_error = _control_error(exc)
    for name, query in (("streak_shutter", "DevParamGet(TD,Shutter)"),
                        ("spectrograph_shutter", "DevParamGet(Spec,Shutter)")):
        try:
            if proxy is None:
                raise RuntimeError(connection_error)
            value = _remoteex_readback(proxy, query).strip().lower()
            if value not in {"open", "closed", "external bnc"}:
                raise RuntimeError(f"Unexpected shutter readback: {value}")
            result["shutters"][name] = {"value": value.title()}
        except Exception as exc:
            result["shutters"][name] = {"value": "UNKNOWN", "error": _control_error(exc)}
    result["ready"] = (result["zaber_mirror"]["at_flash_lamp"] and
                       all(item["value"] == "Open" for item in result["shutters"].values()))
    return result


@pump_probe_vd2_api.route("/alignment/optics", methods=["GET"])
def alignment_optics():
    """Read optical-path status without moving the mirror or changing shutters."""
    return jsonify({"success": True, **_alignment_optics_snapshot()})


@pump_probe_vd2_api.route("/alignment/flash-lamp", methods=["POST"])
@_serialized_vd2_mutation
def alignment_flash_lamp():
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    blocked = _approval_or_response(
        "alignment.flash-lamp", [_target(ZABER_STAGE_DEVICE, "MoveAbsoluteMm")],
        {"target_mm": ZABER_FLASH_LAMP_MM}, "vd2.alignment.flash-lamp", set(),
    )
    if blocked is not None:
        return blocked
    try:
        _assert_preparation_idle(_proxy())
        stage = _zaber_stage_state()
        if stage.get("error") or stage.get("state") != "ON":
            raise RuntimeError(stage.get("error") or "Zaber must be ON before selecting Flash lamp")
        readings = [stage.get(key) for key in ("position_mm", "minimum_mm", "maximum_mm")]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in readings):
            raise RuntimeError("Cannot verify Zaber position and travel limits")
        if not readings[1] <= ZABER_FLASH_LAMP_MM <= readings[2]:
            raise RuntimeError("Flash-lamp position is outside the reported Zaber travel limits")
        moved = not _zaber_at_flash_lamp(stage)
        if moved:
            mirror = DeviceProxy(ZABER_STAGE_DEVICE)
            mirror.set_timeout_millis(3000)
            mirror.command_inout("MoveAbsoluteMm", ZABER_FLASH_LAMP_MM)
            stage = _zaber_stage_state()
            if stage.get("error") or (stage.get("state") != "MOVING" and not _zaber_at_flash_lamp(stage)):
                raise RuntimeError(stage.get("error") or "Zaber did not confirm motion or Flash-lamp position")
        stage["at_flash_lamp"] = _zaber_at_flash_lamp(stage)
        return jsonify({"success": True, "command_sent": moved, "target_mm": ZABER_FLASH_LAMP_MM,
                        "zaber_mirror": stage}), 202 if stage.get("state") == "MOVING" else 200
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/alignment/open-shutters", methods=["POST"])
@_serialized_vd2_mutation
def alignment_open_shutters():
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    names = ("streak_shutter", "spectrograph_shutter")
    blocked = _approval_or_response(
        "alignment.open-shutters", [_target(STREAK_DEVICE, f"write_attribute:{name}") for name in names],
        {name: "Open" for name in names}, "vd2.alignment.open-shutters", set(),
    )
    if blocked is not None:
        return blocked
    try:
        proxy = _proxy()
        _assert_preparation_idle(proxy)
        for name, query in zip(names, ("DevParamGet(TD,Shutter)", "DevParamGet(Spec,Shutter)")):
            proxy.write_attribute(name, "Open")
            if _remoteex_readback(proxy, query).lower() != "open":
                raise RuntimeError(f"Cannot verify {name} Open; inspect optical-path readback")
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


def _live_average_state(proxy):
    global _live_average_readback
    # HPD-TA labels the software filter RecurFilter2; RecurFilter is camera hardware.
    enabled = _remoteex_readback(proxy, "CamParamGet(Live,RecurFilter2)")
    frames = _remoteex_readback(proxy, "CamParamGet(Live,RecurNumber2)")
    if enabled not in {"0", "1"} or not frames.isdigit() or not 2 <= int(frames) <= 255:
        raise RuntimeError("HPD-TA Live rolling-average readback is invalid")
    _live_average_readback = {"enabled": enabled == "1", "frames": int(frames)}
    return dict(_live_average_readback)


@pump_probe_vd2_api.route("/live/rolling-average", methods=["GET", "POST"])
@_serialized_vd2_mutation
def live_rolling_average():
    if request.method == "GET":
        try:
            if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                raise RuntimeError("Wait for the HIS measurement before reading Live rolling average")
            proxy = _proxy()
            _assert_alignment_live_or_idle(proxy)
            return jsonify({"success": True, **_live_average_state(proxy)})
        except Exception as exc:
            return jsonify({"success": False, "error": _control_error(exc)}), 503
    payload, rejected = _mutation_payload({"enabled", "frames"})
    if rejected is not None:
        return rejected
    if type(payload.get("enabled")) is not bool or type(payload.get("frames")) is not int or not 2 <= payload["frames"] <= 255:
        return jsonify({"success": False, "error": "Choose enabled true/false and an integer frame count from 2 to 255"}), 400
    commands = [f"CamParamSet(Live,RecurNumber2,{payload['frames']})",
                f"CamParamSet(Live,RecurFilter2,{int(payload['enabled'])})"]
    blocked = _approval_or_response(
        "live.rolling-average", [_target(STREAK_DEVICE, "ExecuteRaw")],
        {"enabled": payload["enabled"], "frames": payload["frames"], "commands": commands},
        "vd2.live.rolling-average", {"enabled", "frames"},
    )
    if blocked is not None:
        return blocked
    try:
        if _protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            raise RuntimeError("Wait for the HIS measurement before changing Live rolling average")
        proxy = _proxy()
        status = _remoteex_readback(proxy, "AcqStatus()").lower()
        if status not in {"idle", "busy,live"}:
            raise RuntimeError(f"Live settings cannot change during this acquisition: {status}")
        for command, parameter, expected in zip(commands, ("RecurNumber2", "RecurFilter2"),
                                                (str(payload["frames"]), str(int(payload["enabled"])))):
            reply = str(proxy.command_inout("ExecuteRaw", command)).strip().split(",", 2)
            if len(reply) < 2 or reply[:2] != ["0", "CamParamSet"]:
                raise RuntimeError(f"HPD-TA rejected {parameter}: {','.join(reply)}")
            if _remoteex_readback(proxy, f"CamParamGet(Live,{parameter})") != expected:
                raise RuntimeError(f"Cannot verify Live {parameter}; inspect current settings")
        return jsonify({"success": True, **_live_average_state(proxy)})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/alignment/start", methods=["POST"])
@_serialized_vd2_mutation
def alignment_start():
    global _alignment_axes
    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected
    profile = timing_for_range("1 us")
    targets = [_target(STREAK_DEVICE, f"write_attribute:{name}") for name in
               ("streak_mode", "time_range", "streak_shutter", "spectrograph_shutter")]
    targets += [_target(DG645_DEVICE, "scpi_write"), _target(STREAK_DEVICE, "StartLive")]
    blocked = _approval_or_response(
        "alignment.start", targets,
        {"time_range": "1 us", "streak_mode": "Operate", "streak_shutter": "Open",
         "spectrograph_shutter": "Open", "dg645_timing": profile.as_dict()},
        "vd2.alignment.start", set(),
    )
    if blocked is not None:
        return blocked
    try:
        proxy = _proxy()
        _assert_preparation_idle(proxy)
        with _alignment_axes_lock:
            _alignment_axes = None
        proxy.write_attribute("streak_mode", "Operate")
        if _remoteex_readback(proxy, "DevParamGet(TD,Mode)").lower() != "operate":
            raise RuntimeError("Cannot verify Operate mode; Live not started")
        proxy.write_attribute("time_range", "1 us")
        if timing_for_range(_remoteex_readback(proxy, "DevParamGet(TD,Time Range)")) != profile:
            raise RuntimeError("Alignment time-range readback mismatch; Live not started")
        _apply_vd2_timing(profile, [])
        for attribute in ("streak_shutter", "spectrograph_shutter"):
            proxy.write_attribute(attribute, "Open")
            if str(_value(proxy, attribute)).lower() != "open":
                raise RuntimeError(f"Cannot verify {attribute} Open; Live not started")
        _verify_vd2_timing_ready(proxy)
        proxy.command_inout("StartLive")
        return jsonify({"success": True, **_snapshot(proxy)})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/command/<name>", methods=["POST"])
@_serialized_vd2_mutation
def command(name: str):
    if name not in ALLOWED_COMMANDS:
        return jsonify({"success": False, "error": f"Unsupported command: {name}"}), 404

    _, rejected = _mutation_payload(set())
    if rejected is not None:
        return rejected

    blocked = _approval_or_response(
        f"command.{name}.execute",
        [_target(STREAK_DEVICE, name)],
        {"name": name},
        "vd2.command",
        set(),
    )
    if blocked is not None:
        return blocked

    command_acknowledged = False
    try:
        proxy = _proxy()
        if name in {"StartLive", "AcquireSingle", "Acquire", "StartAnalogIntegration", "StartSequence"}:
            _verify_vd2_timing_ready(proxy)
        proxy.command_inout(name)
        command_acknowledged = True
        return jsonify({"success": True, **_snapshot(proxy)})
    except Exception as exc:
        payload = {"success": False, "error": _control_error(exc)}
        if command_acknowledged:
            payload.update(code="READBACK_UNAVAILABLE", command_acknowledged=True)
        return jsonify(payload), 503
