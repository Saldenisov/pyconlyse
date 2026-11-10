"""Narrow control API for the VD2 streak-camera pump-probe experiment."""

from __future__ import annotations

from sys import modules as _refactor_modules

from pump_probe_vd2_api_parts_recovery_snapshots import _bind_pump_probe_vd2_api_parts_recovery_snapshots

from pump_probe_vd2_api_parts_recover_owis_device import _bind_pump_probe_vd2_api_parts_recover_owis_device

from pump_probe_vd2_api_parts_start_vd2_optics import _bind_pump_probe_vd2_api_parts_start_vd2_optics

from pump_probe_vd2_api_parts_preview import _bind_pump_probe_vd2_api_parts_preview

from pump_probe_vd2_api_parts_write_parameter import _bind_pump_probe_vd2_api_parts_write_parameter

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
import vd2_tango_optics as tango_optics
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


_pump_probe_vd2_api_parts_recovery_snapshots = _bind_pump_probe_vd2_api_parts_recovery_snapshots(_refactor_modules[__name__])
_recovery_snapshots = _pump_probe_vd2_api_parts_recovery_snapshots["_recovery_snapshots"]


_remember_camera = _pump_probe_vd2_api_parts_recovery_snapshots["_remember_camera"]


_remember_measurement_point = _pump_probe_vd2_api_parts_recovery_snapshots["_remember_measurement_point"]


_alignment_snapshots = _pump_probe_vd2_api_parts_recovery_snapshots["_alignment_snapshots"]


_alignment_current_snapshot = _pump_probe_vd2_api_parts_recovery_snapshots["_alignment_current_snapshot"]


alignment_snapshots = (pump_probe_vd2_api.route("/alignment/snapshots", methods=["GET", "POST"]))(_pump_probe_vd2_api_parts_recovery_snapshots["alignment_snapshots"])


_lifecycle = _pump_probe_vd2_api_parts_recovery_snapshots["_lifecycle"]


_progress = _pump_probe_vd2_api_parts_recovery_snapshots["_progress"]


_start_lifecycle = _pump_probe_vd2_api_parts_recovery_snapshots["_start_lifecycle"]


_vd2_busy_message = _pump_probe_vd2_api_parts_recovery_snapshots["_vd2_busy_message"]


_serialized_vd2_mutation = _pump_probe_vd2_api_parts_recovery_snapshots["_serialized_vd2_mutation"]

VD2_CAMERA_ONLY = os.environ.get("PYCONLYSE_VD2_CAMERA_ONLY") == "1"
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


_proxy = _pump_probe_vd2_api_parts_recovery_snapshots["_proxy"]


_measurement_protocol = Vd2MeasurementProtocol(
    _proxy, processing_worker=process_saved_sequence_in_worker, artifact_preflight=check_new_sequence,
    wait_for_idle=wait_for_sequence,
    artifact_journal=Vd2ProjectManifest(), snapshot_reader=lambda proxy: _machine_snapshot(proxy),
    artifact_finalizer=retire_source_his,
    point_recorder=_remember_measurement_point,
    capture_clock=(lambda proxy, request: tango_optics.measurement_clock(_refactor_modules[__name__], proxy, request))
    if VD2_CAMERA_ONLY else None,
    capture_validator=lambda request, before, rate: tango_optics.validate_saved_capture(
        _refactor_modules[__name__], request, before, rate
    ),
)
_phase_destinations = PhaseDestinations()


_protocol_hardware_phase = _pump_probe_vd2_api_parts_recovery_snapshots["_protocol_hardware_phase"]
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


_server_recovery_targets = _pump_probe_vd2_api_parts_recovery_snapshots["_server_recovery_targets"]


def _server_arguments() -> dict[str, str]:
    # USB axis 4 remains available to explicit diagnostics, but is not used by VD2.
    return {device: server for device, server in VD2_SERVERS.items() if device != OWIS_LEGACY_DEVICE}


_recovery_plan = _pump_probe_vd2_api_parts_recovery_snapshots["_recovery_plan"]


_approval_or_response = _pump_probe_vd2_api_parts_recovery_snapshots["_approval_or_response"]


_reject_duplicate_json_keys = _pump_probe_vd2_api_parts_recovery_snapshots["_reject_duplicate_json_keys"]


def _reject_nonfinite_json(value):
    raise ValueError(f"non-finite JSON value: {value}")


_invalid_hardware_request = _pump_probe_vd2_api_parts_recovery_snapshots["_invalid_hardware_request"]


_exact_plan_required = _pump_probe_vd2_api_parts_recovery_snapshots["_exact_plan_required"]


_mutation_payload = _pump_probe_vd2_api_parts_recovery_snapshots["_mutation_payload"]


_initialize_authorization = _pump_probe_vd2_api_parts_recovery_snapshots["_initialize_authorization"]


_deinitialize_authorization = _pump_probe_vd2_api_parts_recovery_snapshots["_deinitialize_authorization"]


_protocol_authorization = _pump_probe_vd2_api_parts_recovery_snapshots["_protocol_authorization"]


def _value(proxy: DeviceProxy, attribute: str) -> Any:
    return proxy.read_attribute(attribute).value


_snapshot = _pump_probe_vd2_api_parts_recovery_snapshots["_snapshot"]


_control_error = _pump_probe_vd2_api_parts_recovery_snapshots["_control_error"]


_astor = _pump_probe_vd2_api_parts_recovery_snapshots["_astor"]


_wait_for_device = _pump_probe_vd2_api_parts_recovery_snapshots["_wait_for_device"]


_is_healthy_device = _pump_probe_vd2_api_parts_recovery_snapshots["_is_healthy_device"]


_wait_for_healthy_device = _pump_probe_vd2_api_parts_recovery_snapshots["_wait_for_healthy_device"]


_observe_owis_initialization = _pump_probe_vd2_api_parts_recovery_snapshots["_observe_owis_initialization"]


_readiness_failure_detail = _pump_probe_vd2_api_parts_recovery_snapshots["_readiness_failure_detail"]
del _pump_probe_vd2_api_parts_recovery_snapshots


_pump_probe_vd2_api_parts_recover_owis_device = _bind_pump_probe_vd2_api_parts_recover_owis_device(_refactor_modules[__name__])
_recover_owis_device = _pump_probe_vd2_api_parts_recover_owis_device["_recover_owis_device"]


_recover_retained_instrument = _pump_probe_vd2_api_parts_recover_owis_device["_recover_retained_instrument"]


_observe_kymera_startup = _pump_probe_vd2_api_parts_recover_owis_device["_observe_kymera_startup"]


_wait_for_dg645_power_up = _pump_probe_vd2_api_parts_recover_owis_device["_wait_for_dg645_power_up"]


_restart_server = _pump_probe_vd2_api_parts_recover_owis_device["_restart_server"]


_ensure_server = _pump_probe_vd2_api_parts_recover_owis_device["_ensure_server"]


_enable_required_power = _pump_probe_vd2_api_parts_recover_owis_device["_enable_required_power"]


def _enable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> dict[int, float]:
    return _enable_required_power(pdu, steps, SD2_REQUIRED_PDU_OUTPUTS, "SD2")


_disable_vd2_power = _pump_probe_vd2_api_parts_recover_owis_device["_disable_vd2_power"]


_disable_pdu_outputs = _pump_probe_vd2_api_parts_recover_owis_device["_disable_pdu_outputs"]


_initialize_experiment = _pump_probe_vd2_api_parts_recover_owis_device["_initialize_experiment"]


PreparationFailure = _pump_probe_vd2_api_parts_recover_owis_device["PreparationFailure"]


AlreadyPrepared = _pump_probe_vd2_api_parts_recover_owis_device["AlreadyPrepared"]


_prepare_dg645_for_vd2 = _pump_probe_vd2_api_parts_recover_owis_device["_prepare_dg645_for_vd2"]


_verify_owis_sample_axis = _pump_probe_vd2_api_parts_recover_owis_device["_verify_owis_sample_axis"]


_assert_preparation_idle = _pump_probe_vd2_api_parts_recover_owis_device["_assert_preparation_idle"]


_assert_kymera_passive_server = _pump_probe_vd2_api_parts_recover_owis_device["_assert_kymera_passive_server"]


_verify_kymera_sdk_released = _pump_probe_vd2_api_parts_recover_owis_device["_verify_kymera_sdk_released"]


_prepare_kymera_for_vd2 = _pump_probe_vd2_api_parts_recover_owis_device["_prepare_kymera_for_vd2"]


_initialize_equipment = _pump_probe_vd2_api_parts_recover_owis_device["_initialize_equipment"]
del _pump_probe_vd2_api_parts_recover_owis_device


_pump_probe_vd2_api_parts_start_vd2_optics = _bind_pump_probe_vd2_api_parts_start_vd2_optics(_refactor_modules[__name__])
_start_vd2_optics = _pump_probe_vd2_api_parts_start_vd2_optics["_start_vd2_optics"]


_prepared_equipment_state = _pump_probe_vd2_api_parts_start_vd2_optics["_prepared_equipment_state"]


_deinitialize_experiment = _pump_probe_vd2_api_parts_start_vd2_optics["_deinitialize_experiment"]


_remoteex_readback = _pump_probe_vd2_api_parts_start_vd2_optics["_remoteex_readback"]


_apply_vd2_timing = _pump_probe_vd2_api_parts_start_vd2_optics["_apply_vd2_timing"]


_verify_vd2_timing_ready = _pump_probe_vd2_api_parts_start_vd2_optics["_verify_vd2_timing_ready"]


_shutdown_timed_out = _pump_probe_vd2_api_parts_start_vd2_optics["_shutdown_timed_out"]


_shutdown_once = _pump_probe_vd2_api_parts_start_vd2_optics["_shutdown_once"]


_shutdown_acquisition_phase = _pump_probe_vd2_api_parts_start_vd2_optics["_shutdown_acquisition_phase"]


_wait_shutdown_readback = _pump_probe_vd2_api_parts_start_vd2_optics["_wait_shutdown_readback"]


_shutdown_hpdta = _pump_probe_vd2_api_parts_start_vd2_optics["_shutdown_hpdta"]


_shutdown_equipment = _pump_probe_vd2_api_parts_start_vd2_optics["_shutdown_equipment"]


_to_display_pixels = _pump_probe_vd2_api_parts_start_vd2_optics["_to_display_pixels"]


_read_display_frame = _pump_probe_vd2_api_parts_start_vd2_optics["_read_display_frame"]


_missing_current_image_status = _pump_probe_vd2_api_parts_start_vd2_optics["_missing_current_image_status"]


def _waiting_for_current_image(source_status):
    return {"success": True, "frame_available": False,
            "stream_state": "no_valid_image", "source_status": source_status}


_DEFERRED_ACQUISITION_READ = "VD2 operation in progress; acquisition status not queried"


_deferred_camera_state = _pump_probe_vd2_api_parts_start_vd2_optics["_deferred_camera_state"]


_acquisition_snapshot = _pump_probe_vd2_api_parts_start_vd2_optics["_acquisition_snapshot"]


_existing_local_remoteex_listener = _pump_probe_vd2_api_parts_start_vd2_optics["_existing_local_remoteex_listener"]


refresh_connection = (pump_probe_vd2_api.route("/refresh", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_start_vd2_optics["refresh_connection"]))


state = (pump_probe_vd2_api.route("/state", methods=["GET"]))(_pump_probe_vd2_api_parts_start_vd2_optics["state"])
del _pump_probe_vd2_api_parts_start_vd2_optics


_pump_probe_vd2_api_parts_preview = _bind_pump_probe_vd2_api_parts_preview(_refactor_modules[__name__])
preview = (pump_probe_vd2_api.route("/preview", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["preview"])


alignment_readout = (pump_probe_vd2_api.route("/alignment/readout", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["alignment_readout"])


_machine_snapshot = _pump_probe_vd2_api_parts_preview["_machine_snapshot"]


protocol_project = (pump_probe_vd2_api.route("/protocol/project", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["protocol_project"])


@pump_probe_vd2_api.route("/protocol/state", methods=["GET"])
def protocol_state():
    return jsonify({"success": True, **_measurement_protocol.status()})


protocol_plan = (pump_probe_vd2_api.route("/protocol/plan", methods=["POST"]))(_pump_probe_vd2_api_parts_preview["protocol_plan"])


protocol_start = (pump_probe_vd2_api.route("/protocol/start", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_preview["protocol_start"]))


runtime_state = (pump_probe_vd2_api.route("/runtime/state", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["runtime_state"])


_zaber_stage_state = _pump_probe_vd2_api_parts_preview["_zaber_stage_state"]


_owis_sample_stage_state = _pump_probe_vd2_api_parts_preview["_owis_sample_stage_state"]


stages_state = (pump_probe_vd2_api.route("/stages/state", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["stages_state"])


lifecycle_state = (pump_probe_vd2_api.route("/lifecycle", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["lifecycle_state"])


lifecycle_log = (pump_probe_vd2_api.route("/lifecycle/log", methods=["GET"]))(_pump_probe_vd2_api_parts_preview["lifecycle_log"])


initialize_experiment = (pump_probe_vd2_api.route("/initialize", methods=["POST"]))(_pump_probe_vd2_api_parts_preview["initialize_experiment"])


recovery_options = (pump_probe_vd2_api.get("/recovery/options"))(_pump_probe_vd2_api_parts_preview["recovery_options"])


_restore_readback = _pump_probe_vd2_api_parts_preview["_restore_readback"]


_initialize_with_restore = _pump_probe_vd2_api_parts_preview["_initialize_with_restore"]


deinitialize_experiment = (pump_probe_vd2_api.route("/deinitialize", methods=["POST"]))(_pump_probe_vd2_api_parts_preview["deinitialize_experiment"])


remoteex_runtime = (pump_probe_vd2_api.route("/runtime/remoteex/<action>", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_preview["remoteex_runtime"]))
del _pump_probe_vd2_api_parts_preview


_pump_probe_vd2_api_parts_write_parameter = _bind_pump_probe_vd2_api_parts_write_parameter(_refactor_modules[__name__])
write_parameter = (pump_probe_vd2_api.route("/parameter/<name>", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_write_parameter["write_parameter"]))


def _alignment_signature(proxy):
    settings = image_alignment_settings(_remoteex_readback(proxy, "ImgStatusGet(Current,All)"))
    if VD2_CAMERA_ONLY:
        kymera = DeviceProxy(KYMERA_DEVICE)
        kymera.set_timeout_millis(5000)
        if str(kymera.state()).split(".")[-1] != "ON":
            raise RuntimeError("Kymera is not ON; wavelength calibration unavailable")
        tango_optics.verify_image_optics(settings, {
            key: _value(kymera, key) for key in ("wavelength_nm", "lines_per_mm", "grating")
        })
    return settings


def _alignment_frame_metadata(proxy):
    header = _remoteex_readback(proxy, "ImgStatusGet(Current,All)")
    return image_alignment_settings(header), image_intensity_settings(header)


_assert_alignment_live_or_idle = _pump_probe_vd2_api_parts_write_parameter["_assert_alignment_live_or_idle"]


_capture_alignment_axes = _pump_probe_vd2_api_parts_write_parameter["_capture_alignment_axes"]


alignment_calibration = (pump_probe_vd2_api.route("/alignment/calibration", methods=["GET", "POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_write_parameter["alignment_calibration"]))


_zaber_at_flash_lamp = _pump_probe_vd2_api_parts_write_parameter["_zaber_at_flash_lamp"]


_alignment_optics_snapshot = _pump_probe_vd2_api_parts_write_parameter["_alignment_optics_snapshot"]


alignment_optics = (pump_probe_vd2_api.route("/alignment/optics", methods=["GET"]))(_pump_probe_vd2_api_parts_write_parameter["alignment_optics"])


alignment_flash_lamp = (pump_probe_vd2_api.route("/alignment/flash-lamp", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_write_parameter["alignment_flash_lamp"]))


alignment_open_shutters = (pump_probe_vd2_api.route("/alignment/open-shutters", methods=["POST"]))((_serialized_vd2_mutation)(_pump_probe_vd2_api_parts_write_parameter["alignment_open_shutters"]))
del _pump_probe_vd2_api_parts_write_parameter


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
    targets = [_target(*tango_optics.parameter_target(_refactor_modules[__name__], name)) for name in
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
        if VD2_CAMERA_ONLY and not bool(_value(proxy, "camera_only_application")):
            raise RuntimeError("VD2 requires the camera-only HPD-TA profile")
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
            tango_optics.write_parameter(_refactor_modules[__name__], proxy, attribute, "Open")
            shutter = (tango_optics.read_external(_refactor_modules[__name__], attribute)
                       if VD2_CAMERA_ONLY and attribute == "spectrograph_shutter" else _value(proxy, attribute))
            if str(shutter).lower() != "open":
                raise RuntimeError(f"Cannot verify {attribute} Open; Live not started")
        _verify_vd2_timing_ready(proxy)
        if VD2_CAMERA_ONLY:
            tango_optics.run_camera_acquisition(_refactor_modules[__name__], proxy, "StartLive")
        else:
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

    if VD2_CAMERA_ONLY and name == "PrepareDG645ForHPDTA":
        return jsonify(success=False, error="DG645 timing is owned by its Tango server"), 409
    actual_command = "StartCameraOnlyApplication" if VD2_CAMERA_ONLY and name == "StartApplication" else name
    start_commands = {"StartLive", "AcquireSingle", "Acquire", "StartAnalogIntegration", "StartSequence"}
    clock_managed = VD2_CAMERA_ONLY and name in start_commands | {"StopAcquisition", "StopSequence"}
    if clock_managed and _protocol_hardware_phase() in {"preparing", "acquiring", "saving"}:
        return jsonify(success=False, error="VD2 measurement owns the acquisition clock"), 409
    if VD2_CAMERA_ONLY and name == "StartSequence":
        return jsonify(success=False, error="Select an ABS, BASE, or BRUIT measurement to record a sequence"), 409
    targets = [_target(STREAK_DEVICE, actual_command)]
    if clock_managed:
        targets.append(_target(DG645_DEVICE, "scpi_write"))
    blocked = _approval_or_response(
        f"command.{name}.execute",
        targets,
        {"name": name},
        "vd2.command",
        set(),
    )
    if blocked is not None:
        return blocked

    command_acknowledged = False
    try:
        proxy = _proxy()
        if name in start_commands:
            if clock_managed:
                _assert_preparation_idle(proxy)
            _verify_vd2_timing_ready(proxy)
        if clock_managed:
            tango_optics.run_camera_acquisition(_refactor_modules[__name__], proxy, actual_command)
        else:
            proxy.command_inout(actual_command)
        command_acknowledged = True
        return jsonify({"success": True, **_snapshot(proxy)})
    except Exception as exc:
        payload = {"success": False, "error": _control_error(exc)}
        if command_acknowledged:
            payload.update(code="READBACK_UNAVAILABLE", command_acknowledged=True)
        return jsonify(payload), 503
