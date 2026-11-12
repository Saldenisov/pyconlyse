"""Implementation for write_parameter and related operations."""

from __future__ import annotations


def _bind_pump_probe_vd2_api_parts_write_parameter(api):
    """Bind implementation to the owning module and its runtime state."""

    def write_parameter(name: str):
        spec = api.WRITABLE_PARAMETERS.get(name)
        if spec is None:
            return api.jsonify({"success": False, "error": f"Unsupported parameter: {name}"}), 404

        payload, rejected = api._mutation_payload({"value"})
        if rejected is not None:
            return rejected
        if "value" not in payload:
            return api.jsonify({"success": False, "error": "Missing value"}), 400

        try:
            value = spec["coerce"](payload["value"])
            timing = api.timing_for_range(value) if name == "time_range" else None
            if timing is not None:
                value = timing.time_range
            device, target_name = api.tango_optics.parameter_target(api, name)
            targets = [api._target(device, target_name)]
            args = {"name": name, "value": value}
            if timing is not None:
                targets.append(api._target(api.DG645_DEVICE, "scpi_write"))
                args["dg645_timing"] = timing.as_dict()
            blocked = api._approval_or_response(
                f"parameter.{name}.write",
                targets,
                args,
                "vd2.parameter",
                {"value"},
            )
            if blocked is not None:
                return blocked
            proxy = api._proxy()
            if name in {"time_range", "grating", "wavelength_nm", "exit_mirror", "turret"}:
                with api._alignment_axes_lock:
                    api._alignment_axes = None
            if timing is not None or device != api.STREAK_DEVICE:
                api._assert_preparation_idle(proxy)
            if api.VD2_CAMERA_ONLY and not bool(api._value(proxy, "camera_only_application")):
                raise RuntimeError("Start the camera-only HPD-TA profile before changing VD2 settings")
            api.tango_optics.write_parameter(api, proxy, name, value)
            if timing is not None:
                raw_range = api._remoteex_readback(proxy, "DevParamGet(TD,Time Range)")
                try:
                    actual = api.timing_for_range(raw_range)
                except ValueError as exc:
                    raise RuntimeError(f"Streak time-range readback unverified: {raw_range}; DG645 unchanged") from exc
                if actual != timing:
                    raise RuntimeError(f"Streak time-range readback mismatch: requested {timing.time_range}, got {actual.time_range}; DG645 unchanged")
                api._apply_vd2_timing(timing, [])
            return api.jsonify({"success": True, **api._snapshot(proxy)})
        except (TypeError, ValueError) as exc:
            return api.jsonify({"success": False, "error": f"Invalid value: {exc}"}), 400
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    write_parameter.__module__ = api.__name__
    write_parameter.__qualname__ = "write_parameter"

    def _assert_alignment_live_or_idle(proxy):
        status = api._remoteex_readback(proxy, "AcqStatus()").lower()
        if status not in {"idle", "busy,live"}:
            raise RuntimeError(f"Alignment read is unavailable during this acquisition: {status}")

    _assert_alignment_live_or_idle.__module__ = api.__name__
    _assert_alignment_live_or_idle.__qualname__ = "_assert_alignment_live_or_idle"

    def _capture_alignment_axes(proxy):
        with api._alignment_axes_lock:
            api._alignment_axes = None
        signature = api._alignment_signature(proxy)
        api._alignment_image_path.parent.mkdir(parents=True, exist_ok=True)
        api._alignment_image_path.unlink(missing_ok=True)
        proxy.command_inout("SaveCurrentImage", str(api._alignment_image_path))
        deadline = api.time.monotonic() + 3.0
        while True:
            try:
                axes = api.read_alignment_axes(api._alignment_image_path)
                break
            except (OSError, ValueError, IndexError) as exc:
                if api.time.monotonic() >= deadline:
                    raise RuntimeError(f"Current-image calibration unavailable: {exc}") from exc
                api.time.sleep(0.05)
        if signature != api._alignment_signature(proxy):
            raise RuntimeError("Optical settings changed during calibration; refresh calibration")
        acquired = axes["acquisition_settings"]
        acquired_wavelength = float(acquired["wavelength_nm"])
        current_wavelength = float(signature["wavelength_nm"])
        if (acquired["time_range"].replace(" ", "").lower() != signature["time_range"].replace(" ", "").lower()
                or acquired["grating"].lower() != signature["grating"].lower()
                or not acquired["wavelength_nm"]
                or not all(map(api.math.isfinite, (acquired_wavelength, current_wavelength)))
                or abs(acquired_wavelength - current_wavelength) > 0.001):
            raise RuntimeError("Current image predates optical settings; refresh calibration after a new frame")
        axes["settings"] = signature
        axes["calibration_key"] = api.alignment_calibration_key(signature, axes["width"], axes["height"])
        with api._alignment_axes_lock:
            api._alignment_axes = axes
        return axes

    _capture_alignment_axes.__module__ = api.__name__
    _capture_alignment_axes.__qualname__ = "_capture_alignment_axes"

    def alignment_calibration():
        if api.request.method == "GET":
            with api._alignment_axes_lock:
                return api.jsonify({"success": True, "calibration": api._alignment_axes})
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        blocked = api._approval_or_response(
            "alignment.calibration", [api._target(api.STREAK_DEVICE, "SaveCurrentImage")],
            {"image_path": str(api._alignment_image_path)}, "vd2.alignment.calibration", set(),
        )
        if blocked is not None:
            return blocked
        try:
            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                raise RuntimeError("Wait for the HIS measurement before refreshing calibration")
            proxy = api._proxy()
            api._assert_alignment_live_or_idle(proxy)
            return api.jsonify({"success": True, "calibration": api._capture_alignment_axes(proxy)})
        except Exception as exc:
            source_status = api._missing_current_image_status(exc, (
                "ImgStatusGet(Current,All)",
                f"ImgSave(Current,IMG,{api._alignment_image_path},1)",
            ))
            if source_status is not None:
                with api._alignment_axes_lock:
                    api._alignment_axes = None
                payload = api._waiting_for_current_image(source_status)
                api._preview_cache = (payload, 200)
                api._preview_cache_until = api.time.monotonic() + api._preview_period
                return api.jsonify({**payload, "calibration": None})
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    alignment_calibration.__module__ = api.__name__
    alignment_calibration.__qualname__ = "alignment_calibration"

    def _zaber_at_flash_lamp(stage):
        position = stage.get("position_mm")
        return (stage.get("state") == "ON" and not stage.get("error")
                and isinstance(position, (int, float)) and api.math.isfinite(position)
                and abs(position - api.ZABER_FLASH_LAMP_MM) <= api.ZABER_PRESET_TOLERANCE_MM)

    _zaber_at_flash_lamp.__module__ = api.__name__
    _zaber_at_flash_lamp.__qualname__ = "_zaber_at_flash_lamp"

    def _alignment_optics_snapshot():
        result = {"observed_at": api.datetime.now(api.timezone.utc).isoformat(),
                  "zaber_mirror": api._zaber_stage_state(), "shutters": {}}
        for key in ("position_mm", "minimum_mm", "maximum_mm"):
            value = result["zaber_mirror"].get(key)
            if isinstance(value, float) and not api.math.isfinite(value):
                result["zaber_mirror"][key] = None
                result["zaber_mirror"]["error"] = "Zaber returned a non-finite position or travel limit"
        result["zaber_mirror"]["at_flash_lamp"] = api._zaber_at_flash_lamp(result["zaber_mirror"])
        try:
            proxy = api._proxy()
        except Exception as exc:
            proxy = None
            connection_error = api._control_error(exc)
        for name, query in (("streak_shutter", "DevParamGet(TD,Shutter)"),
                            ("spectrograph_shutter", "DevParamGet(Spec,Shutter)")):
            try:
                if proxy is None:
                    raise RuntimeError(connection_error)
                value = api._remoteex_readback(proxy, query).strip().lower()
                if value not in {"open", "closed", "external bnc"}:
                    raise RuntimeError(f"Unexpected shutter readback: {value}")
                result["shutters"][name] = {"value": value.title()}
            except Exception as exc:
                result["shutters"][name] = {"value": "UNKNOWN", "error": api._control_error(exc)}
        result["ready"] = (result["zaber_mirror"]["at_flash_lamp"] and
                           all(item["value"] == "Open" for item in result["shutters"].values()))
        return result

    _alignment_optics_snapshot.__module__ = api.__name__
    _alignment_optics_snapshot.__qualname__ = "_alignment_optics_snapshot"

    def alignment_optics():
        """Read optical-path status without moving the mirror or changing shutters."""
        return api.jsonify({"success": True, **api._alignment_optics_snapshot()})

    alignment_optics.__module__ = api.__name__
    alignment_optics.__qualname__ = "alignment_optics"

    def alignment_flash_lamp():
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        blocked = api._approval_or_response(
            "alignment.flash-lamp", [api._target(api.ZABER_STAGE_DEVICE, "MoveAbsoluteMm")],
            {"target_mm": api.ZABER_FLASH_LAMP_MM}, "vd2.alignment.flash-lamp", set(),
        )
        if blocked is not None:
            return blocked
        try:
            api._assert_preparation_idle(api._proxy())
            stage = api._zaber_stage_state()
            if stage.get("error") or stage.get("state") != "ON":
                raise RuntimeError(stage.get("error") or "Zaber must be ON before selecting Flash lamp")
            readings = [stage.get(key) for key in ("position_mm", "minimum_mm", "maximum_mm")]
            if not all(isinstance(value, (int, float)) and api.math.isfinite(value) for value in readings):
                raise RuntimeError("Cannot verify Zaber position and travel limits")
            if not readings[1] <= api.ZABER_FLASH_LAMP_MM <= readings[2]:
                raise RuntimeError("Flash-lamp position is outside the reported Zaber travel limits")
            moved = not api._zaber_at_flash_lamp(stage)
            if moved:
                mirror = api.DeviceProxy(api.ZABER_STAGE_DEVICE)
                mirror.set_timeout_millis(3000)
                mirror.command_inout("MoveAbsoluteMm", api.ZABER_FLASH_LAMP_MM)
                stage = api._zaber_stage_state()
                if stage.get("error") or (stage.get("state") != "MOVING" and not api._zaber_at_flash_lamp(stage)):
                    raise RuntimeError(stage.get("error") or "Zaber did not confirm motion or Flash-lamp position")
            stage["at_flash_lamp"] = api._zaber_at_flash_lamp(stage)
            return api.jsonify({"success": True, "command_sent": moved, "target_mm": api.ZABER_FLASH_LAMP_MM,
                            "zaber_mirror": stage}), 202 if stage.get("state") == "MOVING" else 200
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    alignment_flash_lamp.__module__ = api.__name__
    alignment_flash_lamp.__qualname__ = "alignment_flash_lamp"

    def alignment_open_shutters():
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        names = ("streak_shutter", "spectrograph_shutter")
        blocked = api._approval_or_response(
            "alignment.open-shutters", [api._target(*api.tango_optics.parameter_target(api, name)) for name in names],
            {name: "Open" for name in names}, "vd2.alignment.open-shutters", set(),
        )
        if blocked is not None:
            return blocked
        try:
            proxy = api._proxy()
            api._assert_preparation_idle(proxy)
            if api.VD2_CAMERA_ONLY and not bool(api._value(proxy, "camera_only_application")):
                raise RuntimeError("VD2 requires the camera-only HPD-TA profile")
            for name, query in zip(names, ("DevParamGet(TD,Shutter)", "DevParamGet(Spec,Shutter)")):
                api.tango_optics.write_parameter(api, proxy, name, "Open")
                if api._remoteex_readback(proxy, query).lower() != "open":
                    raise RuntimeError(f"Cannot verify {name} Open; inspect optical-path readback")
            return api.jsonify({"success": True})
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    alignment_open_shutters.__module__ = api.__name__
    alignment_open_shutters.__qualname__ = "alignment_open_shutters"

    return {
        "write_parameter": write_parameter,
        "_assert_alignment_live_or_idle": _assert_alignment_live_or_idle,
        "_capture_alignment_axes": _capture_alignment_axes,
        "alignment_calibration": alignment_calibration,
        "_zaber_at_flash_lamp": _zaber_at_flash_lamp,
        "_alignment_optics_snapshot": _alignment_optics_snapshot,
        "alignment_optics": alignment_optics,
        "alignment_flash_lamp": alignment_flash_lamp,
        "alignment_open_shutters": alignment_open_shutters,
    }
