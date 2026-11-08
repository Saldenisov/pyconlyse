
from pump_probe_v0_api_parts_parse_tango_dict import _bind_pump_probe_v0_api_parts_parse_tango_dict

from pump_probe_v0_api_parts_v0_targets import _bind_pump_probe_v0_api_parts_v0_targets

from sys import modules as _refactor_modules

from pump_probe_v0_api_methods_control_mode_locked import _bind_pump_probe_v0_api_methods_control_mode_locked

from pump_probe_v0_api_methods_start_emulator_run_locked import _bind_pump_probe_v0_api_methods_start_emulator_run_locked

from pump_probe_v0_api_methods_check_owis_axes import _bind_pump_probe_v0_api_methods_check_owis_axes

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


_pump_probe_v0_api_parts_parse_tango_dict = _bind_pump_probe_v0_api_parts_parse_tango_dict(_refactor_modules[__name__])
_parse_tango_dict = _pump_probe_v0_api_parts_parse_tango_dict["_parse_tango_dict"]


_tango_proxy = _pump_probe_v0_api_parts_parse_tango_dict["_tango_proxy"]


_numeric_list = _pump_probe_v0_api_parts_parse_tango_dict["_numeric_list"]


_values_match = _pump_probe_v0_api_parts_parse_tango_dict["_values_match"]


_axis_is_ready = _pump_probe_v0_api_parts_parse_tango_dict["_axis_is_ready"]


_load_dg645_recall_config = _pump_probe_v0_api_parts_parse_tango_dict["_load_dg645_recall_config"]


def _json_ok(label, detail=None, **extra):
    return {"label": label, "ok": True, "detail": detail or "OK", **extra}


def _json_fail(label, detail, **extra):
    return {"label": label, "ok": False, "detail": str(detail), **extra}


_server_name_for_device = _pump_probe_v0_api_parts_parse_tango_dict["_server_name_for_device"]


_starter_devices = _pump_probe_v0_api_parts_parse_tango_dict["_starter_devices"]


_starter_for_server = _pump_probe_v0_api_parts_parse_tango_dict["_starter_for_server"]


_restart_server_for_device = _pump_probe_v0_api_parts_parse_tango_dict["_restart_server_for_device"]


_linspace = _pump_probe_v0_api_parts_parse_tango_dict["_linspace"]


def _gaussian(x_value, center, width):
    scaled = (x_value - center) / width
    return math.exp(-0.5 * scaled * scaled)


def _data_root():
    return os.environ.get("PYCONLYSE_PUMP_PROBE_DATA_ROOT", DEFAULT_DATA_ROOT)


_normalize_data_path = _pump_probe_v0_api_parts_parse_tango_dict["_normalize_data_path"]


_is_data_path_allowed = _pump_probe_v0_api_parts_parse_tango_dict["_is_data_path_allowed"]


_local_listdir = _pump_probe_v0_api_parts_parse_tango_dict["_local_listdir"]


_list_data_path = _pump_probe_v0_api_parts_parse_tango_dict["_list_data_path"]


_parent_data_path = _pump_probe_v0_api_parts_parse_tango_dict["_parent_data_path"]


_safe_folder_name = _pump_probe_v0_api_parts_parse_tango_dict["_safe_folder_name"]


_mkdir_data_path = _pump_probe_v0_api_parts_parse_tango_dict["_mkdir_data_path"]


_read_data_file = _pump_probe_v0_api_parts_parse_tango_dict["_read_data_file"]


_publish_data_file = _pump_probe_v0_api_parts_parse_tango_dict["_publish_data_file"]


_data_file_name = _pump_probe_v0_api_parts_parse_tango_dict["_data_file_name"]


def _data_file_suffix(path):
    return Path(_data_file_name(path)).suffix.lower()


PumpProbeV0Controller = _pump_probe_v0_api_parts_parse_tango_dict["PumpProbeV0Controller"]


_emulator = PumpProbeV0Controller()
_v0_lifecycle_instance = None
_v0_lifecycle_factory_lock = threading.Lock()


_v0_lifecycle = _pump_probe_v0_api_parts_parse_tango_dict["_v0_lifecycle"]


V0PreparationFailure = _pump_probe_v0_api_parts_parse_tango_dict["V0PreparationFailure"]


_prepare_v0_experiment = _pump_probe_v0_api_parts_parse_tango_dict["_prepare_v0_experiment"]


_serialized_v0_mutation = _pump_probe_v0_api_parts_parse_tango_dict["_serialized_v0_mutation"]


_v0_shutdown_vd2_status = _pump_probe_v0_api_parts_parse_tango_dict["_v0_shutdown_vd2_status"]


_stop_v0_web_sequence = _pump_probe_v0_api_parts_parse_tango_dict["_stop_v0_web_sequence"]


_v0_shutdown_authorization = _pump_probe_v0_api_parts_parse_tango_dict["_v0_shutdown_authorization"]


_v0_hardware_config = _pump_probe_v0_api_parts_parse_tango_dict["_v0_hardware_config"]


_v0_reject_runtime_hardware_rewire = _pump_probe_v0_api_parts_parse_tango_dict["_v0_reject_runtime_hardware_rewire"]


_v0_tango_active = _pump_probe_v0_api_parts_parse_tango_dict["_v0_tango_active"]


_v0_reject_unbound_tango_sequence = _pump_probe_v0_api_parts_parse_tango_dict["_v0_reject_unbound_tango_sequence"]
del _pump_probe_v0_api_parts_parse_tango_dict


_pump_probe_v0_api_parts_v0_targets = _bind_pump_probe_v0_api_parts_v0_targets(_refactor_modules[__name__])
_v0_targets = _pump_probe_v0_api_parts_v0_targets["_v0_targets"]
del _pump_probe_v0_api_parts_v0_targets


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
