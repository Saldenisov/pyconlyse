"""Opt-in Web lifecycle and Live routes backed by the VD2 Tango coordinator."""

from base64 import b64encode
from contextlib import nullcontext
from datetime import datetime, timezone
from gzip import compress
import json
import struct
from time import monotonic

from flask import jsonify, request
import numpy as np


LIVE_COMMANDS = {
    "/command/StartLive": "StartLive",
    "/command/StopAcquisition": "StopLive",
    "/alignment/start": "StartAlignment",
    "/alignment/confirmed-start": "StartAlignmentWithShutters",
    "/command/StartLiveWithShutters": "StartLiveWithShutters",
    "/coordinator/prepare-measurement": "PrepareMeasurement",
}


def exposure_ms(value):
    return float(str(value).strip().removesuffix(" ms"))


PARAMETERS = {
    "/parameter/trigger_rate_hz": ("SetRate", int),
    "/parameter/time_range": ("SetTimeRange", str),
    "/parameter/streak_mode": ("SetStreakMode", str),
    "/parameter/live_exposure_time": ("SetLiveExposure", exposure_ms),
    "/parameter/delay_trigger_mode": ("SetLiveTriggerSource", str),
    "/parameter/delay_repetition_rate": ("SetRate", int),
    "/parameter/wavelength_nm": ("SetWavelength", float),
    "/parameter/grating_index": ("SetGrating", int),
    "/parameter/mcp_gain": ("SetMcpGain", int),
    "/parameter/streak_shutter": ("SetStreakShutter", str),
    "/parameter/spectrograph_shutter": ("SetSpectrographShutter", str),
    **{f"/parameter/delay_{channel}": ("SetDelay", str, channel) for channel in "abcdefgh"},
}
PREVIEW_HEADER = struct.Struct("<qqHH")
PREVIEW_ADJUSTMENTS = {
    "SetWavelength", "SetGrating", "SetSpectrographShutter", "SetMcpGain", "SetDelay", "SetRate",
    "SetLiveTriggerSource", "SetStreakShutter", "SetLiveExposure", "SetTimeRange", "SetStreakMode",
}
ADJUSTMENT_CONFLICTS = {
    "Finish the VD2 measurement before adjusting Kymera",
    "Kymera must be ON before adjusting its controls",
    "Cannot read the Kymera shutter. Refresh the instrument status and retry.",
    "Select Open or Closed on the Kymera shutter before changing the optics",
    "Could not confirm the Kymera shutter closed. Check the shutter and retry.",
    "Kymera did not confirm the new setting. Its shutter was left closed.",
    "Kymera moved, but shutter reopening is unverified. Check the shutter.",
    "Kymera settings changed. Live calibration is unavailable. Restart Live to retry.",
    "Finish the VD2 measurement before adjusting II-Gain",
    "Start VD2 Live before adjusting II-Gain",
    "Wait for verified Live settings before adjusting II-Gain",
    "II-Gain is outside the configured VD2 Live range",
    "Finish the VD2 measurement before changing Live settings",
    "VD2 Live is no longer active. Stop Live and retry.",
    "DG645 delay must be between 0 and 2000 seconds",
    "Enter a numerical DG645 delay in seconds",
    "VD2 Live exposure must be between 1 and 25 ms",
    "Set II-Gain to zero before opening the streak shutter",
    "Stop Live before changing the streak camera mode",
    "Choose 5 or 10 Hz",
    "Select Operate before opening the shutters for Live",
    "Stop Focus preview before changing synchronized Live settings",
    "Switch the VD2 flashlamp supply off before dark checkout",
}


def adjustment_conflict(exc):
    descriptions = [str(error.desc) for error in exc.args if hasattr(error, "desc")]
    for description in descriptions or [str(exc)]:
        for line in description.splitlines():
            message = line.strip().removeprefix("RuntimeError: ").removeprefix("ValueError: ")
            if message in ADJUSTMENT_CONFLICTS:
                return message
    return None


def install_vd2_coordinator_routes(api):
    routes = api.pump_probe_vd2_api
    cached_preview = None
    cached_preview_response = None
    preview_status = None
    preview_axes = None

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
                **state.get("values", {}),
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

    def operation_in_progress():
        return api._preparation_lock.locked() or api._protocol_hardware_phase() in {"preparing", "saving"}

    def deferred(coordinator_route):
        if coordinator_route == "/preview":
            return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
        response = {"success": True, "readout_backend": "tango", "state_deferred": True}
        if coordinator_route == "/runtime/state":
            return jsonify(success=True, readout_backend="tango", device=response)
        return jsonify(response)

    def preview_response(payload):
        nonlocal cached_preview_response
        if cached_preview_response is None or cached_preview_response[0] is not payload:
            raw = jsonify(payload).get_data()
            cached_preview_response = (payload, raw, compress(raw, compresslevel=1))
        _, raw, zipped = cached_preview_response
        from flask import Response
        response = Response(zipped if request.accept_encodings["gzip"] > 0 else raw,
                            mimetype="application/json")
        if request.accept_encodings["gzip"] > 0:
            response.headers["Content-Encoding"] = "gzip"
        response.vary.add("Accept-Encoding")
        return response

    def preview(coordinator):
        nonlocal cached_preview, preview_status, preview_axes
        now = monotonic()
        if not api._preview_lock.acquire(blocking=False):
            cached = cached_preview
            if cached and now - cached[2] < .4:
                return preview_response(cached[1])
            return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
        try:
            if preview_status is None or now - preview_status[0] >= .3:
                preview_status = (now, status(coordinator)["coordinator"])
            state = preview_status[1]
            if state["state"] == "FAULT":
                return jsonify(success=False, error=state["error"]), 503
            if state["state"] != "RUNNING":
                api._alignment_readout.unavailable()
                return jsonify(success=True, frame_available=False, stream_state="no_valid_image")
            if state.get("preview_configuration_pending"):
                api._alignment_readout.unavailable()
                return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
            ccd = proxy(api.VD2_COORDINATOR_CCD, 5000)
            encoding, data = ccd.ReadPreviewFrame()
            if encoding == "vd2-idle-v1":
                return jsonify(success=True, frame_available=False, stream_state="no_valid_image")
            if not data:
                return jsonify(success=True, frame_available=False, stream_state="waiting_for_frame")
            timestamp, stamp, width, height = PREVIEW_HEADER.unpack_from(data)
            if encoding != "vd2-preview-v1" or stamp < 0 or timestamp < 0 or not width or not height:
                raise RuntimeError("Invalid synchronized DCAM frame or metadata")
            image = np.frombuffer(data, dtype="<u2", offset=PREVIEW_HEADER.size).reshape(height, width)
            identity = (stamp, timestamp)
            if cached_preview is not None and cached_preview[0] == identity:
                return preview_response(cached_preview[1])
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
                "peak_counts": high,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            configuration = state.get("preview_configuration")
            if configuration and (preview_axes is None or preview_axes[0] != configuration):
                try:
                    from vd2_direct_recording import recording_axes
                    _, (wavelengths, spectral_id, columns), delays, time_profile = recording_axes(configuration)
                    key = api.alignment_calibration_key(configuration, width, height)
                    preview_axes = (configuration, {
                        "calibration_key": key, "intensity_key": key, "measurement_key": key,
                        "calibration": {"width": width, "height": height, "wavelengths": wavelengths,
                                        "timedelays": delays.tolist(), "time_unit": time_profile["unit"],
                                        "wavelength_unit": "nm", "source": "direct_tango",
                                        "spectral_calibration": [spectral_id, columns], "calibration_key": key},
                    })
                except (KeyError, ValueError, RuntimeError) as exc:
                    preview_axes = (configuration, {"calibration_error": str(exc)})
            if configuration and preview_axes:
                payload.update(preview_axes[1])
                if "calibration" in payload:
                    api._alignment_readout.observe(payload, now, image)
                else:
                    api._alignment_readout.unavailable()
            cached_preview = (identity, payload, now)
            return preview_response(payload)
        finally:
            api._preview_lock.release()

    @api._serialized_vd2_mutation
    def mutate(command, converter=None, channel=None):
        nonlocal cached_preview, preview_status
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
                if channel is not None:
                    args = [[channel, args[0]]]
        except (ValueError, TypeError) as exc:
            return jsonify(success=False, error=str(exc)), 400
        blocked = api._approval_or_response(
            f"coordinator.{command}" if channel is None else f"coordinator.{command}.{channel.upper()}",
            [api._target(api.VD2_COORDINATOR_DEVICE, command)],
            payload, "vd2.coordinator", fields,
        )
        if blocked is not None:
            return blocked
        coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 85000)
        adjusts_preview = command in PREVIEW_ADJUSTMENTS
        with api._preview_lock if adjusts_preview else nullcontext():
            try:
                actual = coordinator.command_inout(command, *args)
            except Exception as exc:
                conflict = adjustment_conflict(exc)
                if conflict:
                    return jsonify(success=False, error=conflict), 409
                raise
            finally:
                cached_preview = None
                preview_status = None
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
        if set(payload) - fields or mode not in ("default", "alignment", "dark") or payload.get("restore_id") is not None:
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
                if mode == "dark":
                    coordinator.command_inout("SetSpectrographShutter", "Closed")
                    coordinator.command_inout("PrepareDarkCheckout")
                else:
                    coordinator.command_inout("PrepareStandard")
                if mode == "alignment":
                    coordinator.command_inout("SetTimeRange", "1 us")
                result = status(coordinator)
                if not result["coordinator"]["prepared"]:
                    raise RuntimeError("Direct Tango optics did not confirm preparation")
                steps.append({"step": "Direct Tango optics", "status": "prepared; DG645 in standby"})
                return result

            arguments = {"prepare_optics": prepare_optics}
            if mode == "dark":
                arguments["dark_checkout"] = True
            result = api._initialize_equipment(steps, **arguments)
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
                return jsonify(success=True, options={"previous": None, "alignment": None, "point": None,
                                                      "dark_checkout_available": True})
            if (request.method, path) in {
                ("GET", "/state"), ("POST", "/refresh"), ("GET", "/runtime/state"), ("GET", "/preview")
            }:
                if operation_in_progress():
                    return deferred(path)
                coordinator = proxy(api.VD2_COORDINATOR_DEVICE, 5000)
                try:
                    if path == "/runtime/state":
                        return jsonify(success=True, readout_backend="tango", hpdta_running=False,
                                       remoteex_running=False, device=status(coordinator))
                    if path == "/preview":
                        return preview(coordinator)
                    if path == "/refresh":
                        coordinator.command_inout("RefreshInstrumentValues")
                    return jsonify(status(coordinator))
                except Exception as exc:
                    if api.camera_serialization_timeout(exc):
                        return deferred(path)
                    raise
        except Exception as exc:
            return jsonify(success=False, error=api._control_error(exc)), 503
        return None
