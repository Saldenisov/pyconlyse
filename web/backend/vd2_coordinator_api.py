"""Opt-in Web Live routes backed by the VD2 Tango coordinator."""

from base64 import b64encode
from datetime import datetime, timezone
import json

from flask import jsonify, request
import numpy as np


LIVE_COMMANDS = {
    "/command/StartLive": "StartLive",
    "/command/StopAcquisition": "StopLive",
    "/alignment/start": "StartAlignment",
    "/coordinator/prepare-measurement": "PrepareMeasurement",
}
PARAMETERS = {
    "/parameter/time_range": ("SetTimeRange", str),
    "/parameter/wavelength_nm": ("SetWavelength", float),
    "/parameter/grating_index": ("SetGrating", int),
}


def install_vd2_coordinator_routes(api):
    routes = api.pump_probe_vd2_api
    cached_preview = None

    def status(coordinator):
        state = json.loads(coordinator.command_inout("GetState"))
        active = state["state"] == "RUNNING"
        return {
            "success": True,
            "device": api.VD2_COORDINATOR_DEVICE,
            "state": state["state"],
            "status": state["error"],
            "connected": state["state"] != "FAULT",
            "application_running": state["state"] != "FAULT",
            "acquisition_status": "busy" if active else "idle",
            "acquisition_mode": "Live" if active else None,
            "remoteex_status": "busy" if active else "idle",
            "readout_backend": "tango",
            "coordinator": state,
            "values": {
                "time_range": state["time_range"],
                "streak_mode": "Operate" if active else None,
                "live_exposure_time": "10 ms" if active else None,
                **state.get("optics", {}),
                "grating_options": [
                    {"value": index, "label": f"{index} · Blaze {blaze} nm"}
                    for index, blaze in api.tango_optics.VD2_GRATING_BLAZE_NM.items()
                ],
            },
        }

    def proxy(name, timeout):
        device = api.DeviceProxy(name)
        device.set_timeout_millis(timeout)
        return device

    def preview(coordinator):
        nonlocal cached_preview
        if not api._preview_lock.acquire(blocking=False):
            return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
        try:
            state = status(coordinator)["coordinator"]
            if state["state"] == "FAULT":
                return jsonify(success=False, error=state["error"]), 503
            if state["state"] != "RUNNING":
                return jsonify(success=True, frame_available=False, stream_state="no_valid_image")
            if not state["frames"]:
                return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
            ccd = proxy(api.VD2_COORDINATOR_CCD, 5000)
            image = np.asarray(ccd.RawFrame)
            stamp = int(ccd.FrameStamp)
            timestamp = int(ccd.FrameTimestampUs)
            if image.ndim != 2 or image.dtype != np.uint16 or stamp < 0 or timestamp < 0:
                raise RuntimeError("Invalid synchronized DCAM frame or metadata")
            identity = (stamp, timestamp)
            if cached_preview is not None and cached_preview[0] == identity:
                return jsonify(cached_preview[1])
            display = api._to_display_pixels(image.astype("<u2", copy=False).tobytes(), 2)
            payload = {
                "success": True, "frame_available": True, "stream_state": "acquiring",
                "width": image.shape[1], "height": image.shape[0], "data_type": "DCAM",
                "pixels_b64": b64encode(display).decode("ascii"), "display_rescaled": True,
                "minimum": min(display), "maximum": max(display), "frame_stamp": stamp,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            cached_preview = (identity, payload)
            return jsonify(payload)
        finally:
            api._preview_lock.release()

    @api._serialized_vd2_mutation
    def mutate(command, converter=None):
        nonlocal cached_preview
        fields = set() if converter is None else {"value"}
        payload, rejected = api._mutation_payload(fields)
        if rejected is not None:
            return rejected
        try:
            if converter is None:
                args = []
            else:
                raw_value = payload.get("value")
                if raw_value is None or isinstance(raw_value, bool):
                    raise ValueError("A parameter value is required")
                if converter is int and not (type(raw_value) is int or
                                             isinstance(raw_value, str) and raw_value.isdecimal()):
                    raise ValueError("The grating index must be an integer")
                args = [converter(raw_value)]
        except (ValueError, TypeError) as exc:
            return jsonify(success=False, error=str(exc)), 400
        blocked = api._approval_or_response(
            f"coordinator.{command}", [api._target(api.VD2_COORDINATOR_DEVICE, command)],
            payload, "vd2.coordinator", fields,
        )
        if blocked is not None:
            return blocked
        coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 85000)
        actual = coordinator.command_inout(command, *args)
        cached_preview = None
        result = status(coordinator)
        if converter is not None:
            result["value"] = actual
        return jsonify(result)

    @routes.post("/coordinator/prepare-measurement")
    def prepare_measurement():
        if not api.VD2_COORDINATOR_DEVICE:
            return jsonify(success=False, error="VD2 Tango coordinator is not selected"), 404
        return mutate("PrepareMeasurement")

    @routes.before_request
    def route_coordinator():
        if not api.VD2_COORDINATOR_DEVICE:
            return None
        path = request.path.removeprefix(routes.url_prefix)
        try:
            if request.method == "POST":
                if path in LIVE_COMMANDS:
                    return mutate(LIVE_COMMANDS[path])
                if path in PARAMETERS:
                    return mutate(*PARAMETERS[path])
                if path in {"/initialize", "/deinitialize", "/protocol/start", "/alignment/calibration",
                            "/alignment/open-shutters", "/alignment/flash-lamp", "/live/rolling-average"} or path.startswith(
                    ("/command/", "/parameter/", "/runtime/remoteex/", "/dcam/", "/paired/")
                ):
                    return jsonify(success=False, error="This operation has no direct Tango VD2 implementation"), 409
            if (request.method, path) in {
                ("GET", "/state"), ("POST", "/refresh"), ("GET", "/runtime/state"), ("GET", "/preview")
            }:
                coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 5000)
                if path == "/runtime/state":
                    return jsonify(success=True, hpdta_running=False, remoteex_running=False, device=status(coordinator))
                if path == "/preview":
                    return preview(coordinator)
                return jsonify(status(coordinator))
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc)), 503
        return None
