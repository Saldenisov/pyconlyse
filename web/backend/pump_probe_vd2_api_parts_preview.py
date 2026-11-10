"""Implementation for preview and related operations."""

from __future__ import annotations


def _bind_pump_probe_vd2_api_parts_preview(api):
    """Bind implementation to the owning module and its runtime state."""

    def preview():
        # One native reader for all browser tabs. Cached frames retain their original
        # timestamp; waiting clients never queue a second RemoteEx binary transfer.
        phase_status = api._protocol_hardware_phase()
        if phase_status in {"saving", "processing"}:
            api._alignment_readout.unavailable()
            return api.jsonify({"success": True, "frame_available": False,
                            "stream_state": phase_status})
        if api.time.monotonic() < api._preview_cache_until and api._preview_cache is not None:
            payload, status = api._preview_cache
            return api.jsonify(payload), status
        if not api._preview_lock.acquire(blocking=False):
            # Drop this display request when the current image is already being read.
            return api.jsonify({"success": True, "frame_available": False,
                            "stream_state": "waiting_for_frame"})
        started = api.time.monotonic()
        try:
            if started < api._preview_cache_until and api._preview_cache is not None:
                payload, status = api._preview_cache
                return api.jsonify(payload), status
            proxy = api._proxy()
            if str(proxy.state()).split(".")[-1] not in {"ON", "RUNNING"}:
                payload = {"success": False, "error": "Hamamatsu Tango device is not connected"}
                api._alignment_readout.unavailable()
                api._preview_cache = (payload, 409)
                api._preview_cache_until = started + api._preview_period
                return api.jsonify(payload), 409
            if not bool(api._value(proxy, "application_running")):
                payload = {"success": False, "error": "HPD-TA is still starting"}
                api._alignment_readout.unavailable()
                api._preview_cache = (payload, 409)
                api._preview_cache_until = started + api._preview_period
                return api.jsonify(payload), 409
            checked_at = api.time.monotonic()
            phase_status = api._protocol_hardware_phase()
            period = max(api._preview_period, 1.0) if phase_status == "acquiring" else api._preview_period
            if phase_status in {"saving", "processing"}:
                api._alignment_readout.unavailable()
                return api.jsonify({"success": True, "frame_available": False,
                                "stream_state": phase_status})
            try:
                frame = api._read_display_frame(proxy)
            except Exception as exc:
                source_status = api._missing_current_image_status(exc, ("ImgDataGet(Current,Display)",))
                if source_status is None:
                    raise
                # Prepare starts equipment, not acquisition. HPD-TA can legitimately
                # have no current image yet; do not start Live or reuse stale pixels.
                api._alignment_readout.unavailable()
                payload = api._waiting_for_current_image(source_status)
                api._preview_cache = (payload, 200)
                api._preview_cache_until = api.time.monotonic() + period
                return api.jsonify(payload)
            captured_at = api.datetime.now(api.timezone.utc).isoformat()
            pixels_at = api.time.monotonic()
            active = (api._string(api._value(proxy, "remoteex_status")).lower() == "busy"
                      or phase_status == "acquiring")
            with api._alignment_axes_lock:
                axes = api._alignment_axes
            # A HIS capture shares RemoteEx with this preview. Its pixel preview
            # needs no extra native calibration/status commands on every frame.
            if phase_status != "acquiring":
                try:
                    signature, intensity_settings = api._alignment_frame_metadata(proxy)
                    frame["calibration_key"] = api.alignment_calibration_key(signature, frame["width"], frame["height"])
                    frame["intensity_key"] = api.alignment_calibration_key(intensity_settings, frame["width"], frame["height"])
                    frame["measurement_key"] = api.alignment_measurement_key(intensity_settings, frame["width"], frame["height"], api._live_average_readback)
                    if (axes and (axes["width"], axes["height"]) == (frame["width"], frame["height"])
                            and axes.get("settings") == signature):
                        frame["calibration"] = axes
                except Exception as exc:
                    source_status = api._missing_current_image_status(exc, ("ImgStatusGet(Current,All)",))
                    if source_status is not None:
                        # The current image can disappear between pixels and metadata.
                        api._alignment_readout.unavailable()
                        payload = api._waiting_for_current_image(source_status)
                        api._preview_cache = (payload, 200)
                        api._preview_cache_until = api.time.monotonic() + period
                        return api.jsonify(payload)
                    frame["calibration_error"] = api._control_error(exc)
            payload = {"success": True, "frame_available": True, **frame,
                       "stream_state": "acquiring" if active else "last_frame",
                       "received_at": captured_at,
                       "read_timings_ms": {
                           "device_checks": round((checked_at - started) * 1000, 3),
                           "pixels": round((pixels_at - checked_at) * 1000, 3),
                           "metadata": round((api.time.monotonic() - pixels_at) * 1000, 3),
                       }}
            api._alignment_readout.observe(payload, pixels_at)
            api._preview_cache = (payload, 200)
            api._preview_cache_until = started + period
            return api.jsonify(payload)
        except Exception as exc:
            payload = {"success": False, "error": api._control_error(exc)}
            api._alignment_readout.unavailable()
            api._preview_cache = (payload, 503)
            api._preview_cache_until = api.time.monotonic() + api._preview_period
            return api.jsonify(payload), 503
        finally:
            api._preview_lock.release()

    preview.__module__ = api.__name__
    preview.__qualname__ = "preview"

    def alignment_readout():
        """Analyse a frame already read by preview, with this window's geometry."""
        if api.request.args.get("capabilities") == "1":
            result = api.jsonify({"success": True, "version": api.READOUT_VERSION})
        else:
            try:
                frame_id = api.request.args.get("frame", "")
                if not frame_id or len(frame_id) > 64:
                    raise ValueError("A preview frame identifier is required.")
                region, windows = api.parse_selection(api.request.args.get("selection", ""))
                if api._protocol_hardware_phase() in {"saving", "processing"}:
                    api._alignment_readout.unavailable()
                result = api.jsonify({"success": True, **api._alignment_readout.read(frame_id, region, windows)})
            except (ValueError, LookupError) as exc:
                result = api.jsonify({"success": False, "error": str(exc)})
                result.status_code = 404 if isinstance(exc, LookupError) else 422
        result.headers["Cache-Control"] = "no-store"
        return result

    alignment_readout.__module__ = api.__name__
    alignment_readout.__qualname__ = "alignment_readout"

    def _machine_snapshot(streak):
        """Read scalar settings from fixed VD2 devices; unavailable values remain explicit."""
        result = {"captured_at": api.datetime.now(api.timezone.utc).isoformat(), "devices": {},
                  "coverage": "Available Tango scalar attributes and bounded iTest/OWIS readback arrays; image data excluded; no settings restored automatically"}
        bounded_arrays = {
            "ELYSE/pdu/iTest": {"names", "ids", "states", "currents_setpoint", "currents_meas", "current_limits"},
            api.OWIS_SAMPLE_DEVICE: {"states", "positions", "device_names", "friendly_names"},
        }
        try:
            result["streak_control"] = api._snapshot(streak)
        except Exception as exc:
            result["streak_control"] = {"error": api._control_error(exc)}
        for device in (api.STREAK_DEVICE, api.KYMERA_DEVICE, api.DG645_DEVICE, api.OWIS_SAMPLE_DEVICE,
                       api.ZABER_STAGE_DEVICE, "ELYSE/pdu/iTest"):
            entry = {"values": {}, "errors": {}}
            result["devices"][device] = entry
            try:
                proxy = api.DeviceProxy(device)
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
                            if any(isinstance(item, float) and not api.math.isfinite(item) for item in value):
                                raise ValueError("Non-finite array readback")
                        if isinstance(value, float) and not api.math.isfinite(value):
                            raise ValueError("Non-finite readback")
                        if not isinstance(value, (str, bool, int, float, list, type(None))):
                            value = str(value)
                        entry["values"][name] = value
                    except Exception as exc:
                        entry["errors"][name] = api._control_error(exc)
                entry["observed_at"] = api.datetime.now(api.timezone.utc).isoformat()
            except Exception as exc:
                entry["errors"]["device"] = api._control_error(exc)
        for key, reader in (("owis_sample", api._owis_sample_stage_state), ("zaber_mirror", api._zaber_stage_state)):
            try:
                result[key] = reader()
            except Exception as exc:
                result[key] = {"error": api._control_error(exc)}
        result["live_rolling_average"] = api._live_average_readback
        # Tango values can contain enums and platform numbers. Preserve their text
        # representation without allowing NaN or non-JSON values into the journal.
        return api.json.loads(api.json.dumps(result, default=str, allow_nan=False))

    _machine_snapshot.__module__ = api.__name__
    _machine_snapshot.__qualname__ = "_machine_snapshot"

    def protocol_project():
        try:
            from treatment_api import _ensure_within_allowed_root
            root = api.Path(_ensure_within_allowed_root(api.request.args.get("output_root", "")))
            path = root / api.MANIFEST_NAME
            if not root.is_absolute():
                raise ValueError("Project folder must be absolute")
            if not path.exists():
                return api.jsonify({"success": True, "manifest_path": str(path), "samples": [], "bruit_options": []})
            return api.jsonify({"success": True, **api.inspect_project(path, verify_files=False)})
        except (OSError, ValueError, KeyError) as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400

    protocol_project.__module__ = api.__name__
    protocol_project.__qualname__ = "protocol_project"

    def protocol_plan():
        """Review destinations without creating folders or contacting a device."""
        fields = {"phase", "frames_per_his", "output_root", "run_name"}
        raw = api.request.get_json(silent=True)
        if isinstance(raw, api.Mapping):
            fields |= {"sample_description", "reuse_bruit"}.intersection(raw)
        payload, rejected = api._mutation_payload(fields)
        if rejected is not None:
            return rejected
        try:
            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                raise api.Vd2ProtocolError("A VD2 HIS acquisition is already running")
            if api._measurement_protocol.status().get("queue_full"):
                raise api.Vd2ProtocolError("H5 conversion queue is full; wait for a conversion to finish")
            request_data = api._measurement_protocol._build_request(
                payload.get("phase"), payload.get("frames_per_his"), payload.get("output_root"), payload.get("run_name"),
                payload.get("sample_description", ""), payload.get("reuse_bruit", "latest"))
            from treatment_api import _ensure_within_allowed_root
            _ensure_within_allowed_root(request_data.output_root)
            return api.jsonify(success=True, **api._phase_destinations.review(request_data))
        except (OSError, ValueError, api.Vd2ProtocolError) as exc:
            return api.jsonify(success=False, error=str(exc)), 409

    protocol_plan.__module__ = api.__name__
    protocol_plan.__qualname__ = "protocol_plan"

    def protocol_start():
        fields = {"phase", "frames_per_his", "output_root", "run_name"}
        raw = api.request.get_json(silent=True)
        if isinstance(raw, api.Mapping):
            fields |= {"sample_description", "reuse_bruit", "destination_token"}.intersection(raw)
        payload, rejected = api._mutation_payload(fields)
        if rejected is not None:
            return rejected
        try:
            request_data = api._measurement_protocol._build_request(
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
                request_data = api._phase_destinations.resolve(destination_token, original_request)
            targets, args = api._protocol_authorization(request_data)
            if "destination_token" in payload:
                args["destination_token"] = destination_token
            blocked = api._approval_or_response(
                "start",
                targets,
                args,
                "vd2.protocol.start",
                fields,
            )
            if blocked is not None:
                return blocked
            if "destination_token" in payload:
                request_data = api._phase_destinations.consume(destination_token, original_request)
            proxy = api._proxy()
            if api.VD2_CAMERA_ONLY:
                api._assert_preparation_idle(proxy)
            api._verify_vd2_timing_ready(proxy)
            state = api._measurement_protocol.start_request(request_data) if "destination_token" in payload else api._measurement_protocol.start(
                phase=request_data.phase,
                frames_per_his=request_data.frames_per_his,
                output_root=request_data.output_root,
                run_name=request_data.run_name,
                sample_description=request_data.sample_description,
                reuse_bruit=request_data.reuse_bruit,
            )
            return api.jsonify({"success": True, **state})
        except api.Vd2ProtocolError as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 409
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    protocol_start.__module__ = api.__name__
    protocol_start.__qualname__ = "protocol_start"

    def runtime_state():
        try:
            snapshot = api._snapshot(api._proxy())
            return api.jsonify(
                {
                    "success": True,
                    "remoteex_running": snapshot["connected"],
                    "hpdta_running": snapshot["application_running"],
                    "device": snapshot,
                }
            )
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    runtime_state.__module__ = api.__name__
    runtime_state.__qualname__ = "runtime_state"

    def _zaber_stage_state() -> dict[str, Any]:
        result: dict[str, Any] = {
            "device": api.ZABER_STAGE_DEVICE,
            "state": "UNKNOWN",
            "position_mm": None,
            "minimum_mm": None,
            "maximum_mm": None,
        }
        try:
            proxy = api.DeviceProxy(api.ZABER_STAGE_DEVICE)
            proxy.set_timeout_millis(2000)
            result["state"] = str(proxy.state()).rsplit(".", 1)[-1]
            result["status"] = str(proxy.status())
            if result["state"] == "ON":
                for key in ("position_mm", "minimum_mm", "maximum_mm"):
                    result[key] = float(proxy.read_attribute(key).value)
        except Exception as exc:
            result["error"] = str(exc)
        return result

    _zaber_stage_state.__module__ = api.__name__
    _zaber_stage_state.__qualname__ = "_zaber_stage_state"

    def _owis_sample_stage_state() -> dict[str, Any]:
        result: dict[str, Any] = {
            "device": api.OWIS_SAMPLE_DEVICE,
            "axis": api.OWIS_SAMPLE_AXIS,
            "state": "UNKNOWN",
            "position_mm": None,
            "minimum_mm": None,
            "maximum_mm": None,
        }
        try:
            proxy = api.DeviceProxy(api.OWIS_SAMPLE_DEVICE)
            proxy.set_timeout_millis(2000)
            result["state"] = str(proxy.state()).rsplit(".", 1)[-1]
            axis_state = int(proxy.command_inout("get_status_axis", api.OWIS_SAMPLE_AXIS))
            result["axis_state"] = next(
                (
                    str(candidate).rsplit(".", 1)[-1]
                    for candidate in (api.DevState.ON, api.DevState.OFF, api.DevState.MOVING, api.DevState.FAULT)
                    if int(candidate) == axis_state
                ),
                "UNKNOWN",
            )
            result["position_mm"] = float(proxy.read_attribute("pos2").value)
            properties = proxy.get_property(["delay_lines_parameters"])
            raw = properties.get("delay_lines_parameters", [])
            if raw:
                parameters = api.ast.literal_eval(str(raw[0]))
                axis = parameters.get(api.OWIS_SAMPLE_AXIS, parameters.get(str(api.OWIS_SAMPLE_AXIS), {}))
                result["minimum_mm"] = float(axis["limit_min"])
                result["maximum_mm"] = float(axis["limit_max"])
        except Exception as exc:
            result["error"] = str(exc)
        return result

    _owis_sample_stage_state.__module__ = api.__name__
    _owis_sample_stage_state.__qualname__ = "_owis_sample_stage_state"

    def stages_state():
        """Passive, structured readings for the mirror and VD2 sample stage."""
        return api.jsonify({
            "success": True,
            "zaber_mirror": api._zaber_stage_state(),
            "owis_sample": api._owis_sample_stage_state(),
        })

    stages_state.__module__ = api.__name__
    stages_state.__qualname__ = "stages_state"

    def lifecycle_state():
        """Read saved progress only: never start, initialize or power equipment."""
        return api.jsonify({"success": True, "job": api._lifecycle().snapshot()})

    lifecycle_state.__module__ = api.__name__
    lifecycle_state.__qualname__ = "lifecycle_state"

    def lifecycle_log():
        try:
            raw_before = api.request.args.get("before")
            before = int(raw_before) if raw_before is not None else None
            if before is not None and before < 1:
                raise ValueError("Invalid log cursor")
            events = api._lifecycle().events(before=before)
            return api.jsonify({"success": True, "events": events})
        except (ValueError, TypeError):
            return api.jsonify({"success": False, "error": "Invalid log cursor"}), 400

    lifecycle_log.__module__ = api.__name__
    lifecycle_log.__qualname__ = "lifecycle_log"

    def initialize_experiment():
        if api.authorization_required():
            # Preserve the existing empty-envelope/exact-plan guard. Saved settings
            # are never an alternative authorization path for conditional startup.
            _, rejected = api._mutation_payload(set())
            return rejected if rejected is not None else api._exact_plan_required()
        payload, rejected = api._mutation_payload({"restore_id", "restore_mode"})
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
            saved = api._recovery_snapshots().get(identity) if identity is not None else None
            if saved and mode in {"alignment", "point"} and saved["kind"] != mode:
                raise ValueError("The selected return point belongs to another mode")
        except (ValueError, TypeError) as exc:
            return api.jsonify(success=False, error=str(exc)), 400
        targets, args = api._initialize_authorization()
        if mode != "default":
            settings = saved["settings"] if saved else {"time_range": "1 us", "streak_mode": "Operate"}
            targets.extend(api._target(*api.tango_optics.parameter_target(api, name))
                           for name in settings if name in api.WRITABLE_PARAMETERS)
            targets.append(api._target(api.STREAK_DEVICE, "ExecuteRaw"))
            args.update(restore_mode=mode, restore_id=identity, restore_settings=settings)
        blocked = api._approval_or_response(
            "initialize",
            targets,
            args,
            "vd2.initialize",
            set(payload),
        )
        if blocked is not None:
            return blocked
        action = api._initialize_experiment if mode == "default" else lambda steps=None: api._initialize_with_restore(mode, saved, steps)
        if api.request.args.get("background") == "1":
            intent = None if mode == "default" else {"restore_mode": mode, "restore_id": identity}
            return api._start_lifecycle("prepare", action, intent=intent)
        if not api._preparation_lock.acquire(blocking=False):
            return api.jsonify({"success": False, "error": "VD2 preparation is already in progress"}), 409
        try:
            result = action()
            return api.jsonify({"success": True, **result})
        except api.AlreadyPrepared as exc:
            return api.jsonify({"success": False, "code": exc.code, "error": str(exc), "steps": exc.steps}), 409
        except Exception as exc:
            return api.jsonify({
                "success": False, "error": api._control_error(exc),
                "steps": getattr(exc, "steps", []),
            }), 503
        finally:
            api._preparation_lock.release()

    initialize_experiment.__module__ = api.__name__
    initialize_experiment.__qualname__ = "initialize_experiment"

    def recovery_options():
        """SQLite only. Opening the choice never probes or recovers a device."""
        try:
            return api.jsonify(success=True, options=api._recovery_snapshots().options())
        except Exception as exc:
            return api.jsonify(success=False, error=f"Camera return points unavailable: {exc}"), 503

    recovery_options.__module__ = api.__name__
    recovery_options.__qualname__ = "recovery_options"

    def _restore_readback(proxy, name):
        try:
            return api._remoteex_readback(proxy, api.RECOVERY_PARAMETERS[name])
        except Exception as exc:
            if name == "mcp_gain" and "DevParamGet" in str(exc) and not api._shutdown_timed_out(exc):
                return api._remoteex_readback(proxy, "DevParamGet(TD,II-Gain)")
            raise

    _restore_readback.__module__ = api.__name__
    _restore_readback.__qualname__ = "_restore_readback"

    def _initialize_with_restore(mode, saved, steps=None):
        steps = steps if steps is not None else []
        try:
            try:
                result = api._initialize_experiment(steps)
            except api.AlreadyPrepared as exc:
                result = exc.result
            proxy = api._proxy()
            # Native range/mode setters already allow 30 s. The outer Tango call
            # must observe their result rather than expire halfway through a setter.
            proxy.set_timeout_millis(45000)
            api._assert_preparation_idle(proxy)
            settings = saved["settings"] if saved else {"time_range": "1 us", "streak_mode": "Operate"}
            profile = api.timing_for_range(settings["time_range"])
            with api._alignment_axes_lock:
                api._alignment_axes = None
            # Mode is restored last, after the calibrated sweep and camera settings.
            order = [name for name in settings if name not in {"streak_mode", "rolling_average"}] + ["streak_mode"]
            for name in order:
                value = settings[name]
                api._progress(steps, f"Restoring camera {name}: {value}", stage=2)
                if not api.equivalent(name, value, api._restore_readback(proxy, name)):
                    spec = api.WRITABLE_PARAMETERS[name]
                    api.tango_optics.write_parameter(api, proxy, name, spec["coerce"](value))
                    if not api.equivalent(name, value, api._restore_readback(proxy, name)):
                        raise RuntimeError(f"Camera {name} readback does not match {value}")
                    if name == "time_range":
                        api._apply_vd2_timing(profile, steps)
                steps.append({"step": f"Restore {name}", "status": f"verified: {value}"})
            average = settings.get("rolling_average")
            if average is not None:
                for parameter, value in (("RecurNumber2", str(average["frames"])), ("RecurFilter2", str(int(average["enabled"])))):
                    query = f"CamParamGet(Live,{parameter})"
                    if api._remoteex_readback(proxy, query) != value:
                        reply = str(proxy.command_inout("ExecuteRaw", f"CamParamSet(Live,{parameter},{value})")).strip().split(",")
                        if reply[:2] != ["0", "CamParamSet"]:
                            raise RuntimeError(f"Cannot restore {parameter}: {','.join(reply)}")
                        if api._remoteex_readback(proxy, query) != value:
                            raise RuntimeError(f"Cannot verify restored {parameter}")
                api._live_average_state(proxy)
            dg645 = api.DeviceProxy(api.DG645_DEVICE)
            dg645.set_timeout_millis(5000)
            api.verify_timing(dg645, profile)
            api._verify_vd2_timing_ready(proxy)
            restored = {"mode": mode, "snapshot_id": (saved or {}).get("id"),
                        "settings": settings, "ui": (saved or {}).get("ui", {"tab": "alignment"})}
            # New job result is durable, so a browser reconnect never replays writes.
            return {**result, "device": api._snapshot(proxy), "already_ready": False, "restored": restored, "steps": list(steps),
                    "message": f"VD2 ready; {mode} camera settings verified ({profile.time_range}). Acquisition remains stopped; no shutter, magnet or stage settings restored."}
        except Exception as exc:
            raise api.PreparationFailure(f"Camera restoration incomplete: {exc}. Keep acquisition stopped; settings may be partially applied. No automatic replay.", steps) from exc

    _initialize_with_restore.__module__ = api.__name__
    _initialize_with_restore.__qualname__ = "_initialize_with_restore"

    def deinitialize_experiment():
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        if api.authorization_required():
            return api._exact_plan_required()
        targets, args = api._deinitialize_authorization()
        blocked = api._approval_or_response(
            "deinitialize",
            targets,
            args,
            "vd2.deinitialize",
            set(),
        )
        if blocked is not None:
            return blocked
        if api.request.args.get("background") == "1":
            return api._start_lifecycle("shutdown", api._deinitialize_experiment)
        if not api._preparation_lock.acquire(blocking=False):
            return api.jsonify({"success": False, "error": "VD2 preparation/shutdown is already in progress"}), 409
        try:
            result = api._deinitialize_experiment()
            return api.jsonify({"success": True, **result})
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc),
                            "steps": getattr(exc, "steps", [])}), 503
        finally:
            api._preparation_lock.release()

    deinitialize_experiment.__module__ = api.__name__
    deinitialize_experiment.__qualname__ = "deinitialize_experiment"

    def remoteex_runtime(action: str):
        if action not in {"start", "stop"}:
            return api.jsonify({"success": False, "error": f"Unsupported RemoteEx action: {action}"}), 404
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        command_name = "StartRemoteEx" if action == "start" else "StopRemoteEx"
        blocked = api._approval_or_response(
            f"remoteex.{action}",
            [api._target(api.STREAK_DEVICE, command_name)],
            {"action": action},
            "vd2.remoteex",
            set(),
        )
        if blocked is not None:
            return blocked
        try:
            proxy = api._proxy()
            if action == "start":
                proxy.command_inout("StartRemoteEx")
                snapshot = api._snapshot(proxy)
                return api.jsonify(
                    {
                        "success": True,
                        "remoteex_running": snapshot["connected"],
                        "hpdta_running": snapshot["application_running"],
                        "device": snapshot,
                    }
                )
            if action == "stop":
                proxy.command_inout("StopRemoteEx")
                return api.jsonify(
                    {
                        "success": True,
                        "remoteex_running": False,
                        "hpdta_running": False,
                        "device": api._snapshot(proxy),
                    }
                )
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    remoteex_runtime.__module__ = api.__name__
    remoteex_runtime.__qualname__ = "remoteex_runtime"

    return {
        "preview": preview,
        "alignment_readout": alignment_readout,
        "_machine_snapshot": _machine_snapshot,
        "protocol_project": protocol_project,
        "protocol_plan": protocol_plan,
        "protocol_start": protocol_start,
        "runtime_state": runtime_state,
        "_zaber_stage_state": _zaber_stage_state,
        "_owis_sample_stage_state": _owis_sample_stage_state,
        "stages_state": stages_state,
        "lifecycle_state": lifecycle_state,
        "lifecycle_log": lifecycle_log,
        "initialize_experiment": initialize_experiment,
        "recovery_options": recovery_options,
        "_restore_readback": _restore_readback,
        "_initialize_with_restore": _initialize_with_restore,
        "deinitialize_experiment": deinitialize_experiment,
        "remoteex_runtime": remoteex_runtime,
    }
