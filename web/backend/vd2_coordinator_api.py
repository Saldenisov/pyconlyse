"""Opt-in Web lifecycle and Live routes backed by the VD2 Tango coordinator."""

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
    "/parameter/trigger_rate_hz": ("SetRate", int),
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
                "trigger_rate_hz": state.get("trigger_rate_hz"),
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
            low, high = int(image.min()), int(image.max())
            if low == high:
                display = bytes(image.size)
            else:
                display = ((image - low) * (255.0 / (high - low))).astype(np.uint8).tobytes()
            payload = {
                "success": True, "frame_available": True, "stream_state": "acquiring",
                "width": image.shape[1], "height": image.shape[0], "data_type": "DCAM",
                "pixels_b64": b64encode(display).decode("ascii"), "display_rescaled": True,
                "minimum": 0, "maximum": 255 if high > low else 0, "frame_stamp": stamp,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            cached_preview = (identity, payload)
            return jsonify(payload)
        finally:
            api._preview_lock.release()

    @api._serialized_vd2_mutation
    def mutate(command, converter=None):
        nonlocal cached_preview
        if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving"}:
            return jsonify(success=False, error="A VD2 measurement owns the optics and trigger"), 409
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
                    raise ValueError("An integer parameter value is required")
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

    def lifecycle(prepare):
        authorization_required = api.authorization_required()
        fields = {"restore_id", "restore_mode"} if prepare and not authorization_required else set()
        payload, rejected = api._mutation_payload(fields)
        if rejected is not None:
            return rejected
        if authorization_required:
            return api._exact_plan_required()
        mode = payload.get("restore_mode", "default")
        if set(payload) - fields or mode not in ("default", "alignment") or payload.get("restore_id") is not None:
            return jsonify(success=False, error="Choose Standard preparation or the direct 1 us Alignment setup"), 400

        def action(steps):
            coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 85000)
            if not prepare:
                def stop_optics():
                    coordinator.command_inout("Unprepare")
                    steps.append({"step": "Direct Tango optical shutdown", "status": "CCD released; streak head parked; DG645 in standby"})

                result = api._shutdown_equipment(steps, shutdown_optics=stop_optics)
                return {**result, "readout_backend": "tango"}

            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                raise RuntimeError("Stop the VD2 measurement before Prepare")
            if status(coordinator)["acquisition_status"] == "busy":
                raise RuntimeError("Stop Live before preparing VD2")

            def prepare_optics():
                coordinator.command_inout("Prepare")
                if mode == "alignment":
                    coordinator.command_inout("SetTimeRange", "1 us")
                result = status(coordinator)
                if not result["coordinator"]["prepared"]:
                    raise RuntimeError("Direct Tango optics did not confirm preparation")
                steps.append({"step": "Direct Tango optics", "status": "prepared; DG645 in standby"})
                return result

            result = api._initialize_equipment(steps, prepare_optics=prepare_optics)
            if mode == "alignment":
                result["restored"] = {"ui": {"tab": "alignment"}}
            return {**result, "readout_backend": "tango"}

        operation = "prepare" if prepare else "shutdown"
        if request.args.get("background") == "1":
            intent = {"restore_mode": mode} if prepare else None
            return api._start_lifecycle(operation, action, intent=intent)
        if not api._preparation_lock.acquire(blocking=False):
            return jsonify(success=False, error=api._vd2_busy_message()), 409
        steps = []
        try:
            return jsonify(success=True, **action(steps))
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc), steps=steps), 503
        finally:
            api._preparation_lock.release()

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
                if path in {"/initialize", "/deinitialize"}:
                    return lifecycle(path == "/initialize")
                if path in LIVE_COMMANDS:
                    return mutate(LIVE_COMMANDS[path])
                if path in PARAMETERS:
                    return mutate(*PARAMETERS[path])
                if path in {"/alignment/calibration",
                            "/alignment/open-shutters", "/alignment/flash-lamp", "/live/rolling-average"} or path.startswith(
                    ("/command/", "/parameter/", "/runtime/remoteex/", "/dcam/", "/paired/")
                ):
                    return jsonify(success=False, error="This operation has no direct Tango VD2 implementation"), 409
            if request.method == "GET" and path == "/recovery/options":
                return jsonify(success=True, options={"previous": None, "alignment": None, "point": None})
            if (request.method, path) in {
                ("GET", "/state"), ("POST", "/refresh"), ("GET", "/runtime/state"), ("GET", "/preview")
            }:
                coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 5000)
                if path == "/runtime/state":
                    return jsonify(success=True, readout_backend="tango", hpdta_running=False,
                                   remoteex_running=False, device=status(coordinator))
                if path == "/preview":
                    return preview(coordinator)
                return jsonify(status(coordinator))
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc)), 503
        return None
