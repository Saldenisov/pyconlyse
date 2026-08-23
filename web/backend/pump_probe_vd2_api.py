"""Narrow control API for the VD2 streak-camera pump-probe experiment."""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from tango import DeviceProxy

from mutation_auth import install_mutation_auth
from vd2_measurement_protocol import Vd2MeasurementProtocol, Vd2ProtocolError

pump_probe_vd2_api = Blueprint(
    "pump_probe_vd2_api", __name__, url_prefix="/api/pump-probe-vd2"
)
install_mutation_auth(pump_probe_vd2_api)

STREAK_DEVICE = "manip/camera/hamamatsu_streak_main"
DG645_DEVICE = "manip/sync/DG645"
VD2_PDU_DEVICE = "manip/SD2/PDU_SD2"
ASTOR_DEVICE = "tango/admin/everest"

VD2_SERVERS = {
    VD2_PDU_DEVICE: "DS_Netio_pdu/4_SD2",
    DG645_DEVICE: "DS_DG645/1_DG645",
    STREAK_DEVICE: "DS_HAMAMATSU_STREAK/1_hamamatsu_streak_main",
}
VD2_REQUIRED_PDU_OUTPUTS = {1: "Streak camera / spectrograph", 2: "DG645"}

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


_measurement_protocol = Vd2MeasurementProtocol(_proxy)


def _value(proxy: DeviceProxy, attribute: str) -> Any:
    return proxy.read_attribute(attribute).value


def _snapshot(proxy: DeviceProxy) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for key, attribute in READ_ATTRIBUTES.items():
        try:
            value = _value(proxy, attribute)
            values[key] = value.item() if hasattr(value, "item") else value
        except Exception as exc:  # Attribute failures must not blank the whole control panel.
            values[key] = None
            errors[key] = str(exc)

    state = str(proxy.state()).split(".")[-1]
    return {
        "device": STREAK_DEVICE,
        "state": state,
        "connected": bool(values.get("connected", False)),
        "application_running": bool(values.get("application_running", False)),
        "remoteex_status": _string(values.get("remoteex_status", "unknown")),
        "values": values,
        "attribute_errors": errors,
    }


def _control_error(exc: Exception) -> str:
    message = str(exc)
    if "no camera available" in message.lower():
        return (
            "HPD-TA reports no readout camera. On Everest, the active hardware profile "
            "defaultHW.hwp is configured with CameraType=NoCamera. Load or create the "
            "C13440 hardware profile in HPD-TA, then reconnect and start Live again."
        )
    return message


def _astor() -> DeviceProxy:
    proxy = DeviceProxy(ASTOR_DEVICE)
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
    if state in {"FAULT", "UNKNOWN"}:
        return False
    if device == DG645_DEVICE:
        return bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
    if device == VD2_PDU_DEVICE:
        return bool(list(proxy.read_attribute("ids").value))
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


def _restart_server(device: str, server: str) -> DeviceProxy:
    astor = _astor()
    try:
        astor.command_inout("DevStop", server)
    except Exception as exc:
        if "not running" not in str(exc).lower():
            raise

    # Astor acknowledges DevStop before the child Python process has unregistered.
    # Waiting here prevents the misleading "already running" start failure.
    stopped_deadline = time.monotonic() + 12.0
    while time.monotonic() < stopped_deadline:
        try:
            _wait_for_device(device, timeout_s=0.5)
        except Exception:
            break
        time.sleep(0.5)

    astor.command_inout("DevStart", server)
    return _wait_for_healthy_device(device)


def _ensure_server(device: str, steps: list[dict[str, str]]) -> DeviceProxy:
    try:
        proxy = _wait_for_device(device, timeout_s=2.0)
        if _is_healthy_device(proxy, device):
            steps.append({"step": f"Tango {device}", "status": "already running"})
            return proxy
    except Exception:
        pass

    server = VD2_SERVERS[device]
    try:
        proxy = _wait_for_device(device, timeout_s=2.0)
        proxy.command_inout("recover")
        if _is_healthy_device(proxy, device):
            steps.append({"step": f"Tango {device}", "status": "recovered"})
            return proxy
    except Exception:
        pass

    try:
        proxy = _restart_server(device, server)
    except Exception as exc:
        if "already running" in str(exc).lower():
            # A stale process can retain Astor's running flag after its device
            # has disappeared. One explicit stop/start resolves that state.
            astor = _astor()
            try:
                astor.command_inout("DevStop", server)
            except Exception:
                pass
            time.sleep(3.0)
            astor.command_inout("DevStart", server)
            proxy = _wait_for_healthy_device(device)
        else:
            raise
    steps.append({"step": f"Tango {device}", "status": "started by Astor"})
    return proxy


def _enable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> None:
    ids = [int(value) for value in pdu.read_attribute("ids").value]
    states = [int(value) for value in pdu.read_attribute("states").value]
    positions = {output_id: index for index, output_id in enumerate(ids)}
    missing = sorted(set(VD2_REQUIRED_PDU_OUTPUTS) - set(positions))
    if missing:
        raise RuntimeError(f"PDU SD2 required outputs are missing: {missing}")
    desired = list(states)
    changed = []
    for output_id, label in VD2_REQUIRED_PDU_OUTPUTS.items():
        position = positions[output_id]
        if desired[position] != 1:
            desired[position] = 1
            changed.append(label)
    if changed:
        pdu.command_inout("set_channels_states", desired)
        time.sleep(2.0)
    confirmed = [int(value) for value in pdu.read_attribute("states").value]
    for output_id, label in VD2_REQUIRED_PDU_OUTPUTS.items():
        if confirmed[positions[output_id]] != 1:
            raise RuntimeError(f"PDU SD2 did not enable {label}")
    steps.append(
        {
            "step": "VD2 power",
            "status": "enabled" if changed else "already enabled",
        }
    )


def _disable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> None:
    ids = [int(value) for value in pdu.read_attribute("ids").value]
    states = [int(value) for value in pdu.read_attribute("states").value]
    positions = {output_id: index for index, output_id in enumerate(ids)}
    missing = sorted(set(VD2_REQUIRED_PDU_OUTPUTS) - set(positions))
    if missing:
        raise RuntimeError(f"PDU SD2 required outputs are missing: {missing}")
    desired = list(states)
    changed = []
    for output_id, label in VD2_REQUIRED_PDU_OUTPUTS.items():
        position = positions[output_id]
        if desired[position] != 0:
            desired[position] = 0
            changed.append(label)
    if changed:
        pdu.command_inout("set_channels_states", desired)
        time.sleep(1.0)
    confirmed = [int(value) for value in pdu.read_attribute("states").value]
    for output_id, label in VD2_REQUIRED_PDU_OUTPUTS.items():
        if confirmed[positions[output_id]] != 0:
            raise RuntimeError(f"PDU SD2 did not disable {label}")
    steps.append(
        {
            "step": "VD2 power",
            "status": "disabled" if changed else "already disabled",
        }
    )


def _initialize_experiment() -> dict[str, Any]:
    steps: list[dict[str, str]] = []
    pdu = _ensure_server(VD2_PDU_DEVICE, steps)
    _enable_vd2_power(pdu, steps)
    _ensure_server(DG645_DEVICE, steps)
    streak = _ensure_server(STREAK_DEVICE, steps)

    streak.command_inout("PrepareDG645ForHPDTA")
    steps.append({"step": "DG645 Recall 9", "status": "applied; burst mode off"})

    if not bool(_value(streak, "connected")):
        streak.command_inout("StartRemoteEx")
    streak = _wait_for_device(STREAK_DEVICE)
    if not bool(_value(streak, "connected")):
        raise RuntimeError("RemoteEx did not connect after startup")
    steps.append({"step": "RemoteEx", "status": "connected"})

    if not bool(_value(streak, "application_running")):
        streak.command_inout("StartApplication")
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        if bool(_value(streak, "application_running")):
            steps.append({"step": "HPD-TA", "status": "running"})
            return {"steps": steps, "device": _snapshot(streak)}
        time.sleep(1.0)
    raise RuntimeError(
        "HPD-TA did not become ready. Check the Everest desktop for a hardware-profile dialog."
    )


def _deinitialize_experiment() -> dict[str, Any]:
    """Leave VD2 hardware dark and electrically de-energized."""
    steps: list[dict[str, str]] = []
    errors: list[str] = []

    try:
        streak = _wait_for_device(STREAK_DEVICE, timeout_s=5.0)
        if bool(_value(streak, "application_running")):
            try:
                streak.command_inout("StopAcquisition")
                steps.append({"step": "Streak acquisition", "status": "stopped"})
            except Exception as exc:
                errors.append(f"Stop acquisition: {exc}")

            for attribute, label in (
                ("streak_shutter", "Streak-camera shutter"),
                ("spectrograph_shutter", "Kymera shutter"),
            ):
                try:
                    streak.write_attribute(attribute, "Closed")
                    steps.append({"step": label, "status": "closed"})
                except Exception as exc:
                    errors.append(f"{label}: {exc}")

            try:
                streak.command_inout("StopApplication")
                steps.append({"step": "HPD-TA", "status": "closed"})
            except Exception as exc:
                errors.append(f"Close HPD-TA: {exc}")

        try:
            streak.command_inout("StopRemoteEx")
            steps.append({"step": "RemoteEx", "status": "stopped"})
        except Exception as exc:
            errors.append(f"Stop RemoteEx: {exc}")
    except Exception as exc:
        errors.append(f"Hamamatsu Tango: {exc}")

    try:
        pdu = _ensure_server(VD2_PDU_DEVICE, steps)
        _disable_vd2_power(pdu, steps)
    except Exception as exc:
        errors.append(f"VD2 power-down: {exc}")

    if errors:
        raise RuntimeError("; ".join(errors))
    return {"steps": steps}


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
        "pixels_b64": base64.b64encode(pixels).decode("ascii"),
        "minimum": min(pixels),
        "maximum": max(pixels),
    }


@pump_probe_vd2_api.route("/state", methods=["GET"])
def state():
    try:
        proxy = _proxy()
        return jsonify({"success": True, **_snapshot(proxy)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc), "device": STREAK_DEVICE}), 503


@pump_probe_vd2_api.route("/preview", methods=["GET"])
def preview():
    try:
        proxy = _proxy()
        if str(proxy.state()).split(".")[-1] not in {"ON", "RUNNING"}:
            return jsonify({"success": False, "error": "Hamamatsu Tango device is not connected"}), 409
        if not bool(_value(proxy, "application_running")):
            return jsonify({"success": False, "error": "HPD-TA is still starting"}), 409
        if _string(_value(proxy, "remoteex_status")).lower() != "busy":
            return jsonify({"success": False, "error": "Live acquisition is not active"}), 409
        frame = _read_display_frame(proxy)
        return jsonify({"success": True, "frame_available": True, **frame})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/protocol/state", methods=["GET"])
def protocol_state():
    return jsonify({"success": True, **_measurement_protocol.status()})


@pump_probe_vd2_api.route("/protocol/start", methods=["POST"])
def protocol_start():
    payload = request.get_json(silent=True) or {}
    try:
        state = _measurement_protocol.start(
            phase=payload.get("phase"),
            frames_per_his=payload.get("frames_per_his"),
            output_root=payload.get("output_root"),
            run_name=payload.get("run_name"),
        )
        return jsonify({"success": True, **state})
    except Vd2ProtocolError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409


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


@pump_probe_vd2_api.route("/initialize", methods=["POST"])
def initialize_experiment():
    try:
        result = _initialize_experiment()
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/deinitialize", methods=["POST"])
def deinitialize_experiment():
    try:
        result = _deinitialize_experiment()
        return jsonify({"success": True, **result})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/runtime/remoteex/<action>", methods=["POST"])
def remoteex_runtime(action: str):
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
        return jsonify({"success": False, "error": f"Unsupported RemoteEx action: {action}"}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/parameter/<name>", methods=["POST"])
def write_parameter(name: str):
    spec = WRITABLE_PARAMETERS.get(name)
    if spec is None:
        return jsonify({"success": False, "error": f"Unsupported parameter: {name}"}), 404

    payload = request.get_json(silent=True) or {}
    if "value" not in payload:
        return jsonify({"success": False, "error": "Missing value"}), 400

    try:
        proxy = _proxy()
        value = spec["coerce"](payload["value"])
        if "attribute" in spec:
            proxy.write_attribute(spec["attribute"], value)
        else:
            proxy.command_inout(spec["command"], value)
        return jsonify({"success": True, **_snapshot(proxy)})
    except (TypeError, ValueError) as exc:
        return jsonify({"success": False, "error": f"Invalid value: {exc}"}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503


@pump_probe_vd2_api.route("/command/<name>", methods=["POST"])
def command(name: str):
    if name not in ALLOWED_COMMANDS:
        return jsonify({"success": False, "error": f"Unsupported command: {name}"}), 404

    try:
        proxy = _proxy()
        proxy.command_inout(name)
        return jsonify({"success": True, **_snapshot(proxy)})
    except Exception as exc:
        return jsonify({"success": False, "error": _control_error(exc)}), 503
