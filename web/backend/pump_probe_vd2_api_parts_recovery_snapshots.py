"""Implementation for _recovery_snapshots and related operations."""

from __future__ import annotations


def _bind_pump_probe_vd2_api_parts_recovery_snapshots(api):
    """Bind implementation to the owning module and its runtime state."""

    def _recovery_snapshots():
        path = api.os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or str(
            api.Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3")
        return api.RecoverySnapshots(path)

    _recovery_snapshots.__module__ = api.__name__
    _recovery_snapshots.__qualname__ = "_recovery_snapshots"

    def _remember_camera(state, kind="previous", ui=None):
        try:
            job = api._lifecycle_instance.get("job") if api._lifecycle_instance is not None else None
            if job and job.get("operation") == "prepare" and job.get("status") in {"failed", "interrupted"}:
                raise ValueError("Preparation/restoration is incomplete; earlier return points are retained")
            settings = api.settings_from_state(state, api._live_average_readback)
            return api._recovery_snapshots().capture(settings, kind, ui)
        except Exception as exc:
            # Persistence cannot turn a valid camera read into a transport fault.
            # Keep the previous good record and expose the failed save separately.
            state["recovery_warning"] = f"Camera return point was not saved: {exc}"
            return None

    _remember_camera.__module__ = api.__name__
    _remember_camera.__qualname__ = "_remember_camera"

    def _remember_measurement_point(measurement, machine_after):
        state = (machine_after or {}).get("streak_control", {})
        settings = api.settings_from_state(state, (machine_after or {}).get("live_rolling_average"))
        ui = {"tab": "acquisition", "form": {
            "outputRoot": measurement.output_root, "runName": measurement.run_name,
            "framesPerHis": str(measurement.frames_per_his), "sampleDescription": measurement.sample_description,
            "reuseBruit": "none" if measurement.reuse_bruit == "none" else "latest"}}
        return api._recovery_snapshots().capture(settings, "point", ui)

    _remember_measurement_point.__module__ = api.__name__
    _remember_measurement_point.__qualname__ = "_remember_measurement_point"

    def _alignment_snapshots():
        # Share the durable application DB without constructing ExperimentLifecycle,
        # whose startup recovery must not run during a snapshot request.
        path = (api.os.environ.get("PYCONLYSE_ALIGNMENT_STATE_DB") or
                api.os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or
                str(api.Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3"))
        return api.AlignmentSnapshots(path)

    _alignment_snapshots.__module__ = api.__name__
    _alignment_snapshots.__qualname__ = "_alignment_snapshots"

    def _alignment_current_snapshot():
        proxy = api.DeviceProxy(api.ALIGNMENT_DEVICE)
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
        for name in api.ALIGNMENT_CHANNELS:
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

    _alignment_current_snapshot.__module__ = api.__name__
    _alignment_current_snapshot.__qualname__ = "_alignment_current_snapshot"

    def alignment_snapshots():
        if api.request.method == "GET":
            try:
                device = api.alignment_device_name(api.request.args.get("device", api.ALIGNMENT_DEVICE))
            except ValueError as exc:
                return api.jsonify(success=False, error=str(exc)), 400
            try:
                return api.jsonify(success=True, **api._alignment_snapshots().history(device))
            except Exception as exc:
                return api.jsonify(success=False, error=f"Alignment database unavailable: {exc}"), 503
        if (api.request.content_length or 0) > 32768:
            return api.jsonify(success=False, error="Alignment snapshot request is too large"), 413
        try:
            payload = api.json.loads(api.request.get_data(cache=True, as_text=True),
                                 object_pairs_hook=api._reject_duplicate_json_keys,
                                 parse_constant=api._reject_nonfinite_json)
            intent = api.validate_intent(payload)
        except (TypeError, ValueError) as exc:
            return api.jsonify(success=False, error=str(exc)), 400
        try:
            repository = api._alignment_snapshots()
            existing = repository.preflight(intent)
            if existing:
                return api.jsonify(success=True, snapshot=existing)
            # Only attribute reads. Saving cannot set currents or enable outputs.
            snapshot = repository.capture(intent, api._alignment_current_snapshot())
            return api.jsonify(success=True, snapshot=snapshot), 201
        except api.SnapshotConflict as exc:
            return api.jsonify(success=False, error=str(exc)), 409
        except ValueError as exc:
            return api.jsonify(success=False, error=str(exc)), 409
        except Exception as exc:
            return api.jsonify(success=False, error=f"Settings were not saved: {exc}"), 503

    alignment_snapshots.__module__ = api.__name__
    alignment_snapshots.__qualname__ = "alignment_snapshots"

    def _lifecycle():
        global _lifecycle_instance
        with api._lifecycle_factory_lock:
            if api._lifecycle_instance is None:
                path = api.os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or str(
                    api.Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3"
                )
                _lifecycle_instance = api.ExperimentLifecycle(path)
            return api._lifecycle_instance

    _lifecycle.__module__ = api.__name__
    _lifecycle.__qualname__ = "_lifecycle"

    def _progress(steps, detail, stage=1, wait_until=None):
        publish = getattr(steps, "phase", None)
        if publish:
            publish(detail, stage=stage, wait_until=wait_until)

    _progress.__module__ = api.__name__
    _progress.__qualname__ = "_progress"

    def _start_lifecycle(operation, action, intent=None):
        lifecycle = api._lifecycle()
        if not api._preparation_lock.acquire(blocking=False):
            job = lifecycle.snapshot()
            if job["status"] == "running" and job.get("operation") == operation:
                if intent is not None and job.get("intent") != intent:
                    return api.jsonify(success=False, error="Prepare is already running with another return point; follow its current progress", job=job), 409
                return api.jsonify({"success": True, "job": job, "attached": True}), 202
            return api.jsonify({"success": False, "error": api._vd2_busy_message(job), "job": job}), 409
        try:
            def execute(steps):
                try:
                    return action(steps)
                except api.AlreadyPrepared as exc:
                    # Synchronous POST retains its 409 contract. A durable Prepare
                    # that verified every dependency has completed successfully.
                    return {**exc.result, "already_ready": True,
                            "message": exc.result.get("message") or str(exc)}
                except Exception as exc:
                    raise api.PreparationFailure(api._control_error(exc), getattr(exc, "steps", steps)) from exc
            if intent is None:
                job = lifecycle.start(operation, execute, api._preparation_lock.release)
            else:
                job = lifecycle.start(operation, execute, api._preparation_lock.release, intent=intent)
            return api.jsonify({"success": True, "job": job}), 202
        except Exception as exc:
            api._preparation_lock.release()
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    _start_lifecycle.__module__ = api.__name__
    _start_lifecycle.__qualname__ = "_start_lifecycle"

    def _vd2_busy_message(job=None):
        job = job if job is not None else (api._lifecycle_instance.snapshot() if api._lifecycle_instance else {})
        return ("VD2 preparation/shutdown is already in progress" if job.get("status") == "running"
                else "VD2 control is busy with another camera read or command; wait for it to finish")

    _vd2_busy_message.__module__ = api.__name__
    _vd2_busy_message.__qualname__ = "_vd2_busy_message"

    def _serialized_vd2_mutation(function):
        """Prevent a new acquisition/parameter write from racing power-down."""
        @api.wraps(function)
        def wrapped(*args, **kwargs):
            if not api._preparation_lock.acquire(blocking=False):
                return api.jsonify(success=False, code="VD2_CONTROL_LOCKED", error=api._vd2_busy_message()), 409
            try:
                return function(*args, **kwargs)
            finally:
                api._preparation_lock.release()
        return wrapped

    _serialized_vd2_mutation.__module__ = api.__name__
    _serialized_vd2_mutation.__qualname__ = "_serialized_vd2_mutation"

    def _proxy() -> DeviceProxy:
        proxy = api.DeviceProxy(api.STREAK_DEVICE)
        proxy.set_timeout_millis(15000)
        return proxy

    _proxy.__module__ = api.__name__
    _proxy.__qualname__ = "_proxy"

    def _protocol_hardware_phase():
        value = api._measurement_protocol.status()
        if type(value.get("acquisition_active")) is bool:
            return value.get("acquisition_phase", "acquiring") if value["acquisition_active"] else "idle"
        # Compatibility with older protocol providers: an unqualified processing
        # state does not prove that camera ownership has been released.
        return value.get("status")

    _protocol_hardware_phase.__module__ = api.__name__
    _protocol_hardware_phase.__qualname__ = "_protocol_hardware_phase"

    def _server_recovery_targets(device: str) -> list[dict[str, str]]:
        """Potential recovery calls in the order used by ``_ensure_server``."""
        astor = api.ELYSIUM_ASTOR_DEVICE if device == api.ZABER_STAGE_DEVICE else api.ASTOR_DEVICE
        if device in api.RETAINED_INSTRUMENT_SERVERS:
            return [api._target(device, "recover"), api._target(device, "turn_on"), api._target(astor, "DevStart")]
        return [
            api._target(device, api._recovery_command(device)),
            api._target(device, "Init"),
            api._target(device, "turn_on"),
            api._target(astor, "DevStop"),
            api._target(astor, "DevStart"),
        ]

    _server_recovery_targets.__module__ = api.__name__
    _server_recovery_targets.__qualname__ = "_server_recovery_targets"

    def _recovery_plan(*devices: str) -> list[dict[str, Any]]:
        """Bind every possible Astor server argument to its ordered recovery plan."""
        return [
            {
                "device": device,
                "server": api.VD2_SERVERS[device],
                "commands": [
                    api._recovery_command(device), "Init", "turn_on", "DevStop", "DevStart"
                ] if device not in api.RETAINED_INSTRUMENT_SERVERS else ["recover", "turn_on", "DevStart"],
            }
            for device in devices
        ]

    _recovery_plan.__module__ = api.__name__
    _recovery_plan.__qualname__ = "_recovery_plan"

    def _approval_or_response(
        action: str,
        targets: list[dict[str, str]],
        args: Any,
        route_id: str,
        wrapper_fields: set[str],
    ):
        """Fail before a Tango proxy, worker, or other hardware side effect exists."""
        return api.require_http_hardware(
            action=action,
            targets=targets,
            args=args,
            route_id=route_id,
            wrapper_fields=wrapper_fields,
        )

    _approval_or_response.__module__ = api.__name__
    _approval_or_response.__qualname__ = "_approval_or_response"

    def _reject_duplicate_json_keys(pairs):
        payload = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError("duplicate JSON key")
            payload[key] = value
        return payload

    _reject_duplicate_json_keys.__module__ = api.__name__
    _reject_duplicate_json_keys.__qualname__ = "_reject_duplicate_json_keys"

    def _invalid_hardware_request():
        return api.jsonify(
            {
                "success": False,
                "error": "Hardware request is invalid",
                "code": "hardware_approval_invalid",
            }
        ), 409

    _invalid_hardware_request.__module__ = api.__name__
    _invalid_hardware_request.__qualname__ = "_invalid_hardware_request"

    def _exact_plan_required():
        """Fail closed when a conditional workflow cannot bind exact side effects."""
        return api.jsonify(
            {
                "success": False,
                "error": "This workflow requires an exact precomputed hardware plan",
                "code": "hardware_not_authorized",
            }
        ), 403

    _exact_plan_required.__module__ = api.__name__
    _exact_plan_required.__qualname__ = "_exact_plan_required"

    def _mutation_payload(wrapper_fields: set[str]):
        """Read a mutation envelope before it can reach a proxy or authorization.

    Enforcement uses a duplicate- and non-finite-safe parser.  Local opt-out
    keeps Flask's permissive JSON decoding for existing development clients.
    """
        raw = api.request.get_data(cache=True, as_text=True)
        if api.authorization_required():
            try:
                payload = {} if not raw.strip() else api.json.loads(
                    raw,
                    object_pairs_hook=api._reject_duplicate_json_keys,
                    parse_constant=api._reject_nonfinite_json,
                )
            except (TypeError, ValueError, api.json.JSONDecodeError):
                return None, api._invalid_hardware_request()
            if not isinstance(payload, api.Mapping) or set(payload) != wrapper_fields:
                return None, api._invalid_hardware_request()
            return dict(payload), None

        payload = api.request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, api.Mapping):
            return None, api._invalid_hardware_request()
        return dict(payload), None

    _mutation_payload.__module__ = api.__name__
    _mutation_payload.__qualname__ = "_mutation_payload"

    def _initialize_authorization() -> tuple[list[dict[str, str]], dict[str, Any]]:
        targets = api._server_recovery_targets(api.VD2_PDU_DEVICE)
        targets.extend(api._server_recovery_targets(api.ZABER_PDU_DEVICE))
        targets.extend(api._server_recovery_targets(api.OWIS_PDU_DEVICE))
        targets.append(api._target(api.VD2_PDU_DEVICE, "set_channels_states"))
        targets.append(api._target(api.ZABER_PDU_DEVICE, "set_channels_states"))
        targets.append(api._target(api.OWIS_PDU_DEVICE, "set_channels_states"))
        targets.extend(api._server_recovery_targets(api.ZABER_STAGE_DEVICE))
        targets.extend(api._server_recovery_targets(api.DG645_DEVICE))
        targets.append(api._target(api.DG645_DEVICE, "scpi_write"))
        targets.extend(api._server_recovery_targets(api.OWIS_CONTROLLER_DEVICE))
        targets.append(api._target(api.OWIS_SAMPLE_DEVICE, "turn_on_axis"))
        targets.extend(api._server_recovery_targets(api.STREAK_DEVICE))
        targets.extend(api._server_recovery_targets(api.KYMERA_DEVICE))
        targets.extend(
            [
                api._target(api.STREAK_DEVICE, "PrepareDG645ForHPDTA"),
                api._target(api.STREAK_DEVICE, "StartRemoteEx"),
                api._target(api.STREAK_DEVICE, "StartApplication"),
                api._target(api.STREAK_DEVICE, "PrepareVD2Startup"),
                api._target(api.STREAK_DEVICE, "write_attribute:streak_shutter"),
                api._target(api.STREAK_DEVICE, "write_attribute:spectrograph_shutter"),
                api._target(api.STREAK_DEVICE, "StopApplication"),
                api._target(api.STREAK_DEVICE, "StopRemoteEx"),
                api._target(api.KYMERA_DEVICE, "PrepareVD2Grating"),
                api._target(api.KYMERA_DEVICE, "turn_off"),
                api._target(api.ASTOR_DEVICE, "DevStop"),
            ]
        )
        return targets, {
            "servers": api._server_arguments(),
            "recovery_plan": api._recovery_plan(
                api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE, api.OWIS_PDU_DEVICE,
                api.DG645_DEVICE, api.OWIS_CONTROLLER_DEVICE,
                api.ZABER_STAGE_DEVICE, api.STREAK_DEVICE, api.KYMERA_DEVICE,
            ),
            "pdu_output_states": [
                {"device": api.VD2_PDU_DEVICE, "output_id": output_id, "state": 1}
                for output_id in sorted(api.SD2_REQUIRED_PDU_OUTPUTS)
            ] + [
                {"device": api.ZABER_PDU_DEVICE, "output_id": output_id, "state": 1}
                for output_id in sorted(api.VD2_REQUIRED_PDU_OUTPUTS)
            ] + [
                {"device": api.OWIS_PDU_DEVICE, "output_id": output_id, "state": 1}
                for output_id in sorted(api.OWIS_REQUIRED_PDU_OUTPUTS)
            ],
            "dg645_commands": [f"*RCL {api.VD2_DG645_RECALL_SLOT}", "BURM 0"],
            "dg645_timing": api.timing_for_range("1 us").as_dict(),
            "owis_axis": api.OWIS_SAMPLE_AXIS,
            "kymera_grating": 2,
        }

    _initialize_authorization.__module__ = api.__name__
    _initialize_authorization.__qualname__ = "_initialize_authorization"

    def _deinitialize_authorization() -> tuple[list[dict[str, str]], dict[str, Any]]:
        targets = [
            api._target(api.STREAK_DEVICE, "StopAcquisition"),
            api._target(api.STREAK_DEVICE, "write_attribute:streak_shutter"),
            api._target(api.STREAK_DEVICE, "write_attribute:spectrograph_shutter"),
            api._target(api.STREAK_DEVICE, "write_attribute:streak_mode"),
            api._target(api.STREAK_DEVICE, "StopApplication"),
            api._target(api.STREAK_DEVICE, "StopRemoteEx"),
            api._target(api.ZABER_STAGE_DEVICE, "Stop"),
            api._target(api.OWIS_SAMPLE_DEVICE, "stop_axis"),
            api._target(api.KYMERA_DEVICE, "turn_off"),
        ]
        targets.extend(api._server_recovery_targets(api.VD2_PDU_DEVICE))
        targets.extend(api._server_recovery_targets(api.ZABER_PDU_DEVICE))
        targets.append(api._target(api.VD2_PDU_DEVICE, "set_channels_states"))
        targets.append(api._target(api.ZABER_PDU_DEVICE, "set_channels_states"))
        return targets, {
            "servers": api._server_arguments(),
            "recovery_plan": api._recovery_plan(api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE),
            "pdu_output_states": [
                {"device": api.ZABER_PDU_DEVICE, "output_id": output_id, "state": 0}
                for output_id in api.VD2_LAMP_SHUTDOWN_OUTPUTS
            ] + [
                {"device": api.VD2_PDU_DEVICE, "output_id": output_id, "state": 0}
                for output_id in (2, 1)
            ],
            "shutters": {
                "streak_shutter": "Closed",
                "spectrograph_shutter": "Closed",
            },
            "streak_mode": "Focus",
            "retained_power": [
                {"device": api.ZABER_PDU_DEVICE, "output_id": 2, "reason": "Xe lamp cooling; physical lamp-off required"},
                {"device": api.ZABER_PDU_DEVICE, "output_id": 3, "reason": "Zaber always-on supply"},
                {"device": api.OWIS_PDU_DEVICE, "output_id": 2, "reason": "shared V0/VD2 controller"},
                {"device": api.VD2_PDU_DEVICE, "output_id": 3, "reason": "control supply"},
            ],
        }

    _deinitialize_authorization.__module__ = api.__name__
    _deinitialize_authorization.__qualname__ = "_deinitialize_authorization"

    def _protocol_authorization(request_data: PhaseRequest) -> tuple[list[dict[str, str]], dict[str, Any]]:
        return [
            api._target(api.STREAK_DEVICE, "write_attribute:sequence_loops"),
            api._target(api.STREAK_DEVICE, "StartSequence"),
            api._target(api.STREAK_DEVICE, "ExecuteRaw"),
            api._target(api.STREAK_DEVICE, "SaveCurrentSequence"),
        ], {
            "phase": request_data.phase,
            "frames_per_his": request_data.frames_per_his,
            "output_root": request_data.output_root,
            "run_name": request_data.run_name,
            "his_path": request_data.his_path,
            "sequence_loops": str(request_data.frames_per_his),
            "wait_query": api.SEQUENCE_WAIT_QUERY,
            "wait_timeout_s": api.SEQUENCE_TIMEOUT_S,
            **({"sample_description": request_data.sample_description} if request_data.sample_description else {}),
            **({"reuse_bruit": request_data.reuse_bruit} if request_data.reuse_bruit != "latest" else {}),
        }

    _protocol_authorization.__module__ = api.__name__
    _protocol_authorization.__qualname__ = "_protocol_authorization"

    def _snapshot(proxy: DeviceProxy) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        requested = list(api.READ_ATTRIBUTES.items())
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
            "device": api.STREAK_DEVICE,
            "state": state,
            "status": str(proxy.status()) if state in {"FAULT", "ALARM"} else "",
            "connected": bool(values.get("connected", False)),
            "application_running": bool(values.get("application_running", False)),
            "remoteex_status": api._string(values.get("remoteex_status", "unknown")),
            "values": values,
            "attribute_errors": errors,
        }

    _snapshot.__module__ = api.__name__
    _snapshot.__qualname__ = "_snapshot"

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

    _control_error.__module__ = api.__name__
    _control_error.__qualname__ = "_control_error"

    def _astor(device: str = "") -> DeviceProxy:
        proxy = api.DeviceProxy(
            api.ELYSIUM_ASTOR_DEVICE if device == api.ZABER_STAGE_DEVICE else api.ASTOR_DEVICE
        )
        proxy.set_timeout_millis(15000)
        return proxy

    _astor.__module__ = api.__name__
    _astor.__qualname__ = "_astor"

    def _wait_for_device(device: str, timeout_s: float = 15.0) -> DeviceProxy:
        deadline = api.time.monotonic() + timeout_s
        last_error = None
        while api.time.monotonic() < deadline:
            try:
                proxy = api.DeviceProxy(device)
                proxy.set_timeout_millis(8000)
                proxy.state()
                return proxy
            except Exception as exc:
                last_error = exc
                api.time.sleep(0.5)
        raise RuntimeError(f"{device} did not become available: {last_error}")

    _wait_for_device.__module__ = api.__name__
    _wait_for_device.__qualname__ = "_wait_for_device"

    def _is_healthy_device(proxy: DeviceProxy, device: str) -> bool:
        state = str(proxy.state()).split(".")[-1].upper()
        if state in {"FAULT", "UNKNOWN", "OFF", "DISABLE", "ALARM", "INIT"}:
            return False
        if device in api.OWIS_DEVICES:
            # The controller can publish ON before its blocking axis initialization
            # finishes. New servers expose that separate lifecycle fact; older
            # servers without the attribute retain the state/readback contract.
            attribute_list = getattr(proxy, "get_attribute_list", None)
            if attribute_list and "initialization_state" in {str(name).lower() for name in attribute_list()}:
                if str(proxy.read_attribute("initialization_state").value).upper() != "SUCCEEDED":
                    return False
        if device == api.DG645_DEVICE:
            return state == "ON" and bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
        if device in {api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE, api.OWIS_PDU_DEVICE}:
            return bool(list(proxy.read_attribute("ids").value))
        if device == api.ZABER_STAGE_DEVICE:
            return proxy.read_attribute("position_mm").value is not None
        if device == api.KYMERA_DEVICE:
            return state == "ON" and int(proxy.read_attribute("grating").value) > 0
        if device in {api.OWIS_CONTROLLER_DEVICE, api.OWIS_SAMPLE_DEVICE}:
            # Axis commands require an initialized controller/router, not just an
            # exported transport in STANDBY. Verify the VD2 axis below separately.
            # MOVING is an operational shared controller, not a server fault. The
            # required VD2 axis is checked independently, without resetting others.
            return state in {"ON", "MOVING", "RUNNING"} and api.math.isfinite(float(proxy.read_attribute("pos2").value))
        if device == api.OWIS_LEGACY_DEVICE:
            return state in {"ON", "MOVING", "RUNNING"}
        # RemoteEx may intentionally be stopped while its Tango launcher remains ON.
        return True

    _is_healthy_device.__module__ = api.__name__
    _is_healthy_device.__qualname__ = "_is_healthy_device"

    def _wait_for_healthy_device(device: str, timeout_s: float = 20.0) -> DeviceProxy:
        deadline = api.time.monotonic() + timeout_s
        last_error = None
        while api.time.monotonic() < deadline:
            try:
                proxy = api._wait_for_device(device, timeout_s=1.0)
                if api._is_healthy_device(proxy, device):
                    return proxy
                last_error = f"{device} is exported but not healthy"
            except Exception as exc:
                last_error = exc
            api.time.sleep(0.5)
        raise RuntimeError(f"{device} did not pass health check: {last_error}")

    _wait_for_healthy_device.__module__ = api.__name__
    _wait_for_healthy_device.__qualname__ = "_wait_for_healthy_device"

    def _observe_owis_initialization(device, steps=None):
        """Only observe an existing/uncertain initialization; never replay it."""
        if steps is not None:
            api._progress(steps, f"{device}: waiting for existing OWIS initialization/readback; no restart or initialization replay")
        try:
            return api._wait_for_healthy_device(device)
        except Exception as exc:
            detail = f"{device}: readiness remains unverified; no restart or initialization replay was issued. {exc}"
            if steps is not None:
                steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
            raise RuntimeError(detail) from exc

    _observe_owis_initialization.__module__ = api.__name__
    _observe_owis_initialization.__qualname__ = "_observe_owis_initialization"

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

    _readiness_failure_detail.__module__ = api.__name__
    _readiness_failure_detail.__qualname__ = "_readiness_failure_detail"

    return {
        "_recovery_snapshots": _recovery_snapshots,
        "_remember_camera": _remember_camera,
        "_remember_measurement_point": _remember_measurement_point,
        "_alignment_snapshots": _alignment_snapshots,
        "_alignment_current_snapshot": _alignment_current_snapshot,
        "alignment_snapshots": alignment_snapshots,
        "_lifecycle": _lifecycle,
        "_progress": _progress,
        "_start_lifecycle": _start_lifecycle,
        "_vd2_busy_message": _vd2_busy_message,
        "_serialized_vd2_mutation": _serialized_vd2_mutation,
        "_proxy": _proxy,
        "_protocol_hardware_phase": _protocol_hardware_phase,
        "_server_recovery_targets": _server_recovery_targets,
        "_recovery_plan": _recovery_plan,
        "_approval_or_response": _approval_or_response,
        "_reject_duplicate_json_keys": _reject_duplicate_json_keys,
        "_invalid_hardware_request": _invalid_hardware_request,
        "_exact_plan_required": _exact_plan_required,
        "_mutation_payload": _mutation_payload,
        "_initialize_authorization": _initialize_authorization,
        "_deinitialize_authorization": _deinitialize_authorization,
        "_protocol_authorization": _protocol_authorization,
        "_snapshot": _snapshot,
        "_control_error": _control_error,
        "_astor": _astor,
        "_wait_for_device": _wait_for_device,
        "_is_healthy_device": _is_healthy_device,
        "_wait_for_healthy_device": _wait_for_healthy_device,
        "_observe_owis_initialization": _observe_owis_initialization,
        "_readiness_failure_detail": _readiness_failure_detail,
    }
