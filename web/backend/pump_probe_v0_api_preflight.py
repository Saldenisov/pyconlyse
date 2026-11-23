"""V0 preflight controller operations."""


def bind(api):
    class V0Preflight:
        def _owis_aggregator_locked(self):
            return api._tango_proxy(self._hardware_config["owis_aggregator_device"])

        def _move_owis_axis_locked(self, axis, position):
            proxy = self._owis_aggregator_locked()
            proxy.command_inout("move_axis", [float(axis), float(position)])

        def _stop_owis_axis_locked(self, axis):
            proxy = self._owis_aggregator_locked()
            proxy.command_inout("stop_axis", int(axis))

        def _preflight_dg645_locked(self):
            policy = str(self._hardware_config.get("dg645_preflight_policy") or "apply_recall_then_verify").strip().lower()
            if policy in {"off", "skip", "disabled"}:
                return

            config = api._load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
            dg645 = api._tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
            recall_slot = int(config.get("recall_slot", 8))

            if policy in {"apply_recall_then_verify", "recall_then_verify", "apply"}:
                dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
                api.time.sleep(1.0)
                try:
                    dg645.command_inout("scpi_query", "*OPC?")
                except Exception:
                    pass
            elif policy not in {"verify", "verify_only"}:
                raise ValueError(f"Unsupported DG645 preflight policy: {policy}")

            expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
            expected_queries.pop("*IDN?", None)
            mismatches = []
            for command, expected in expected_queries.items():
                actual = str(dg645.command_inout("scpi_query", command)).strip()
                if not api._values_match(expected, actual):
                    mismatches.append(f"{command} expected {expected!r} got {actual!r}")

            if mismatches:
                preview = "; ".join(mismatches[:5])
                suffix = f"; +{len(mismatches) - 5} more" if len(mismatches) > 5 else ""
                raise ValueError(f"DG645 recall {recall_slot} preflight failed: {preview}{suffix}")

        def _check_device(
            self,
            label,
            device_name,
            fix=False,
            starter_name=None,
            starter_running=None,
            on_progress=None,
        ):
            repair = None
            errors = []
            server_name = None

            def ready(proxy):
                state = str(proxy.state()).upper().rsplit(".", 1)[-1]
                if state not in {"ON", "RUNNING", "MOVING"}:
                    return False
                if device_name == self._hardware_config["dg645_device"]:
                    return bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
                if device_name in api.V0_PDU_DEVICES:
                    return bool(list(proxy.read_attribute("ids").value))
                return True

            try:
                server_name = api._server_name_for_device(device_name)
                # A composite or a rewired configuration must not indirectly repair
                # a STANDA axis. Only its Elysium2 owner may initialise it.
                if server_name.lower().startswith("ds_standa_motor/"):
                    fix = False
                    if starter_name != api.V0_STANDA_STARTER_DEVICE:
                        starter_name = api.V0_STANDA_STARTER_DEVICE
                        starter = api._tango_proxy(starter_name, timeout_ms=2500)
                        starter_running = set(starter.command_inout("DevGetRunningServers", True))
                stopped = (
                    starter_running is not None and server_name not in starter_running
                )
                if stopped and not fix:
                    raise RuntimeError(f"{server_name} is not running on {starter_name}")
                # An initially stopped shared server may already have been started
                # for another device in this preparation pass.
                if stopped and fix:
                    starter = api._tango_proxy(starter_name, timeout_ms=5000)
                    stopped = server_name not in set(starter.command_inout("DevGetRunningServers", False))
                if stopped:
                    if on_progress:
                        on_progress(f"Starting missing server {server_name} on {starter_name}")
                    repair = api._restart_server_for_device(device_name, preferred_starter=starter_name)
                    starter_running.add(server_name)
                try:
                    # Newton SDK cold initialization and I2C optical discovery
                    # exceed the generic 5 s RPC deadline. Keep one bounded
                    # call in flight; a timeout must not trigger a second Init.
                    timeout_ms = 60000 if device_name in {
                        self._hardware_config.get('andor_device'),
                        self._hardware_config.get('spectrograph_device'),
                    } else 5000
                    proxy = api._tango_proxy(device_name, timeout_ms=timeout_ms)
                    ok = ready(proxy)
                    if not ok:
                        errors.append(f"Initial state={proxy.state()}")
                except Exception as exc:
                    proxy = None
                    ok = False
                    errors.append(str(exc))
                if not ok and fix and proxy is not None:
                    ok, recovery_errors = api.recover_device(
                        proxy, ready, ("recover", "turn_on", "Init", "turn_on"),
                        on_progress=on_progress,
                    )
                    errors.extend(recovery_errors)
                    if ok:
                        repair = repair or {"action": "reinitialized"}
                # Never stop an existing SDK process or replay a timed-out Init.
                # Report this branch and continue checking independent equipment.
                state = str(proxy.state()) if proxy is not None else "UNREACHABLE"
                device_error = ""
                if not ok and proxy is not None:
                    try:
                        device_error = str(proxy.read_attribute("last_error").value or "").strip()
                    except Exception:
                        pass
                    if device_error and device_error not in errors:
                        errors.append(device_error)
                detail = f"state={state}; hardware verified" if ok else (
                    f"state={state}; {'; '.join(errors)}. Check power and connection, then press Prepare again."
                )
                return (api._json_ok if ok else api._json_fail)(
                    label, detail, device=device_name, server=server_name,
                    starter=starter_name, repair=repair, device_error=device_error,
                )
            except Exception as exc:
                return api._json_fail(
                    label, f"{exc}; {'; '.join(errors)}", device=device_name,
                    server=server_name, starter=starter_name, repair=repair,
                )

        def _netio_outputs_for_device(self, device_name):
            proxy = api._tango_proxy(device_name, timeout_ms=5000)
            ids = [int(value) for value in list(proxy.read_attribute("ids").value)]
            names = [str(value) for value in list(proxy.read_attribute("names").value)]
            states = [int(value) for value in list(proxy.read_attribute("states").value)]
            return proxy, ids, names, states

        def _check_netio_output(self, item, fix=False):
            try:
                proxy, ids, names, states = self._netio_outputs_for_device(item["device"])
                output_id = int(item["output_id"])
                if output_id not in ids or len(ids) != len(states):
                    raise RuntimeError(f"PDU output {output_id} is missing or its state readback is invalid")
                index = ids.index(output_id)
                state = int(states[index]) if 0 <= index < len(states) else 0
                name = names[index] if 0 <= index < len(names) else f"Output {output_id}"
                if state != 1 and fix:
                    # NETIO Action 5 means No Change. Do not rewrite stale states
                    # of unrelated outlets (in particular the streak-camera supply).
                    next_states = [5] * len(states)
                    next_states[index] = 1
                    proxy.command_inout("set_channels_states", next_states)
                    api.time.sleep(max(0.5, float(item.get("settle_seconds", 0.5))))
                    deadline = api.time.monotonic() + 3.0
                    _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
                    if output_id not in _ids or len(_ids) != len(states):
                        raise RuntimeError(f"PDU output {output_id} readback is unavailable")
                    index = _ids.index(output_id)
                    state = int(states[index]) if 0 <= index < len(states) else 0
                    while state != 1 and api.time.monotonic() < deadline:
                        api.time.sleep(0.25)
                        _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
                        if output_id not in _ids or len(_ids) != len(states):
                            raise RuntimeError(f"PDU output {output_id} readback is unavailable")
                        state = int(states[_ids.index(output_id)])
                ok = state == 1
                return (api._json_ok if ok else api._json_fail)(
                    item["label"],
                    f"{name} output {output_id} is {'ON' if ok else 'OFF'}",
                    device=item["device"],
                    output_id=output_id,
                    state=state,
                )
            except Exception as exc:
                return api._json_fail(item["label"], exc, device=item["device"], output_id=item["output_id"])

        def _check_owis_axes(self, fix=False, starter_running=None, on_progress=None):
            checks = []
            aggregator = self._hardware_config["owis_aggregator_device"]
            backend = self._hardware_config["owis_backend_device"]
            legacy = self._hardware_config["owis_legacy_device"]
            axes = [
                (
                    "Sample holder V0 axis",
                    backend,
                    int(self._hardware_config["sample_stage_axis"]),
                ),
                (
                    "Delay line long axis",
                    backend,
                    int(self._hardware_config["delay_line_axis"]),
                ),
                ("OWIS legacy axis 4", legacy, 4),
            ]
            for label, device in (
                ("OWIS Ethernet backend", backend),
                ("OWIS legacy backend", legacy),
                ("OWIS aggregator", aggregator),
            ):
                if on_progress:
                    on_progress(f"Checking {label}")
                checks.append(self._check_device(
                    label, device, fix=fix, starter_name=api.V0_STARTER_DEVICE,
                    starter_running=starter_running,
                    on_progress=on_progress,
                ))
            for label, axis_device, axis in axes:
                try:
                    proxy = api._tango_proxy(axis_device, timeout_ms=5000)
                    state = str(proxy.command_inout("get_status_axis", axis))
                    position = float(proxy.command_inout("read_position_axis", axis))
                    ok = api._axis_is_ready(state, position)
                    if not ok and fix:
                        try:
                            if on_progress:
                                on_progress(f"Enabling {label} axis {axis}; no move or home command")
                            proxy.command_inout("turn_on_axis", axis)
                            api.time.sleep(0.5)
                            state = str(proxy.command_inout("get_status_axis", axis))
                            position = float(proxy.command_inout("read_position_axis", axis))
                            ok = api._axis_is_ready(state, position)
                        except Exception:
                            pass
                    checks.append(
                        (api._json_ok if ok else api._json_fail)(
                            label,
                            f"axis {axis}: {state}, {position:.4f} mm",
                            device=axis_device,
                            axis=axis,
                        )
                    )
                except Exception as exc:
                    checks.append(
                        api._json_fail(label, exc, device=axis_device, axis=axis)
                    )
            return checks

        def _check_camera_stream(self, device_name, fix=False):
            label = f"Camera stream {device_name}"
            try:
                proxy = api._tango_proxy(device_name, timeout_ms=2500)
                if fix and device_name in api.V0_CAMERA_DEVICES and int(proxy.read_attribute("trigger_mode").value) != 0:
                    proxy.write_attribute("trigger_mode", 0)
                grabbing = bool(proxy.read_attribute("isgrabbing").value)
                if not grabbing and fix:
                    proxy.command_inout("start_grabbing")
                deadline = api.time.monotonic() + (3.0 if fix else 0.0)
                while True:
                    grabbing = bool(proxy.read_attribute("isgrabbing").value)
                    if grabbing:
                        try:
                            image = api.np.asarray(proxy.read_attribute("image").value)
                            if image.ndim >= 2 and image.size and api.np.isfinite(image).all():
                                return api._json_ok(label, f"Image stream available: {image.shape}; no alignment or motion started", device=device_name)
                        except Exception as exc:
                            if not fix or "API_AttrValueNotSet" not in str(exc):
                                raise
                    if api.time.monotonic() >= deadline:
                        break
                    api.time.sleep(0.2)
                return api._json_fail(label, "Camera has no verified image stream", device=device_name)
            except Exception as exc:
                return api._json_fail(label, exc, device=device_name)

        def _check_laser_pointing(self, device_name, fix=False, starter_running=None,
                                  remote_running=None, on_progress=None):
            label = f"Laser Pointing {api.V0_LASER_POINTING_DEVICES.index(device_name) + 1}"
            checks = [self._check_device(label, device_name, fix=fix,
                      starter_name=api.V0_STARTER_DEVICE, starter_running=starter_running,
                      on_progress=on_progress)]
            try:
                proxy = api._tango_proxy(device_name, timeout_ms=2500)
                raw = list(proxy.get_property(["ds_dict"]).get("ds_dict", []))
                dependencies = api._parse_tango_dict(raw[0] if raw else None)
                actuators = [role for role in dependencies if str(role).startswith("Actuator")]
                if not dependencies.get("Camera") or len(actuators) < 4:
                    raise RuntimeError("Camera or four mirror actuator dependencies are missing from ds_dict")
                for role, target in dependencies.items():
                    axes = ()
                    if isinstance(target, (list, tuple)) and len(target) == 2:
                        target, axes = target
                    if not isinstance(target, str) or not target.strip():
                        raise RuntimeError(f"Invalid dependency for {role}")
                    child_label = f"{label}: {role}"
                    # Dependencies are always passive, including mirror motors,
                    # diaphragms and shutters. Never call a composite motion command.
                    server = api._server_name_for_device(target)
                    is_standa = server.lower().startswith("ds_standa_motor/")
                    result = self._check_device(child_label, target, fix=False,
                        starter_name=api.V0_STANDA_STARTER_DEVICE if is_standa else None,
                        starter_running=remote_running if is_standa else None)
                    if result.get("ok") and axes:
                        child = api._tango_proxy(target, timeout_ms=2500)
                        for axis in axes:
                            state = str(child.command_inout("get_status_axis", int(axis)))
                            position = float(child.command_inout("read_position_axis", int(axis)))
                            if not api._axis_is_ready(state, position):
                                raise RuntimeError(f"{child_label}: axis {axis} is not ready")
                    checks.append(result)
            except Exception as exc:
                checks.append(api._json_fail(f"{label} dependencies", exc, device=device_name))
            ready = all(check.get("ok") for check in checks)
            checks.append((api._json_ok if ready else api._json_fail)(
                f"{label} functional readiness",
                "Controller and all configured dependencies are available" if ready else
                "A camera/actuator dependency is unavailable; no alignment or motor initialisation was attempted",
                device=device_name))
            return checks

        def _read_daq_counter(self, timeout_ms=5000):
            proxy = api._tango_proxy(self._hardware_config["daqmx_device"], timeout_ms=timeout_ms)
            return int(float(proxy.command_inout("read_counter", self._hardware_config["daqmx_counter_channel"])))

        def _counter_status_locked(self):
            try:
                value = self._read_daq_counter(timeout_ms=700)
                now = api.time.monotonic()
                rate = self._counter_rate_hz
                active = False
                if self._counter_last_value is not None and self._counter_last_time is not None:
                    dt = max(1e-6, now - self._counter_last_time)
                    delta = value - self._counter_last_value
                    rate = max(0.0, delta / dt)
                    self._counter_rate_hz = 0.65 * self._counter_rate_hz + 0.35 * rate
                    active = delta > 0
                self._counter_last_value = value
                self._counter_last_time = now
                return {
                    "value": value,
                    "rate_hz": round(self._counter_rate_hz if rate is not None else 0.0, 3),
                    "active": active or self._counter_rate_hz > 1.0,
                    "error": "",
                }
            except Exception as exc:
                return {"value": None, "rate_hz": 0.0, "active": False, "error": str(exc)}

        def _check_counter_activity(self, seconds=1.25):
            try:
                first = self._read_daq_counter(timeout_ms=5000)
                api.time.sleep(max(0.5, float(seconds)))
                second = self._read_daq_counter(timeout_ms=5000)
                rate = (second - first) / max(0.5, float(seconds))
                ok = second > first and rate >= 1.0
                return (api._json_ok if ok else api._json_fail)(
                    "ELYSE pulse counter",
                    f"{first} -> {second}, {rate:.2f} Hz",
                    value=second,
                    rate_hz=round(rate, 3),
                )
            except Exception as exc:
                return api._json_fail("ELYSE pulse counter", exc)

        def _check_dg645_recall(self, apply_recall=False):
            try:
                config = api._load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
                dg645 = api._tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
                recall_slot = int(config.get("recall_slot", 8))
                if apply_recall:
                    dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
                    api.time.sleep(1.0)
                    try:
                        dg645.command_inout("scpi_query", "*OPC?")
                    except Exception:
                        pass
                expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
                expected_queries.pop("*IDN?", None)
                mismatches = []
                for command, expected in expected_queries.items():
                    actual = str(dg645.command_inout("scpi_query", command)).strip()
                    if not api._values_match(expected, actual):
                        mismatches.append(f"{command}: expected {expected!r}, got {actual!r}")
                if mismatches:
                    preview = "; ".join(mismatches[:5])
                    return api._json_fail("DG645 recall 8", preview, mismatch_count=len(mismatches))
                return api._json_ok("DG645 recall 8", "Recall 8 matches V0 DirectLine preset", recall_slot=recall_slot)
            except Exception as exc:
                return api._json_fail("DG645 recall 8", exc)

        def _starter_server_snapshot(self, starter_name):
            try:
                starter = api._tango_proxy(starter_name, timeout_ms=2500)
                running = set(starter.command_inout("DevGetRunningServers", True))
                stopped = set(starter.command_inout("DevGetStopServers", False))
                return (
                    api._json_ok(
                        f"Tango Starter {starter_name}",
                        f"{len(running)} server(s) running; {len(stopped)} stopped",
                        device=starter_name,
                        running_count=len(running),
                        stopped_count=len(stopped),
                    ),
                    running,
                )
            except Exception as exc:
                return (
                    api._json_fail(
                        f"Tango Starter {starter_name}",
                        exc,
                        device=starter_name,
                    ),
                    set(),
                )

        def _everest_server_snapshot(self):
            return self._starter_server_snapshot(api.V0_STARTER_DEVICE)

        def _v0_preparation_checks(self, fix=False, progress=None):
            if fix and api.V0_PREPARATION_READ_ONLY:
                raise ValueError("Prepare V0 is read-only: no server start, recovery, initialization, power or DG645 recall is allowed")
            starter_check, running_servers = self._everest_server_snapshot()
            checks = []

            def record(result):
                checks.append(result)
                if progress is not None:
                    progress.append({**result, "step": result["label"],
                                     "status": "verified" if result.get("ok") else "failed"})
                return result

            def phase(message, stage=1):
                if progress is not None:
                    progress.phase(message, stage=stage)

            record(starter_check)
            if not starter_check.get("ok"):
                # Existing exported devices can still be checked without Starter.
                # A missing Starter must not stop independent power branches.
                running_servers = None

            power_checks = {}

            def check_device(label, device_name, power_keys=()):
                phase(f"Checking {label}", stage=0 if device_name in api.V0_PREPARATION_PDU_DEVICES else 1)
                failed_power = [key for key in power_keys if not power_checks[key].get("ok")]
                if failed_power:
                    result = api._json_fail(
                        label, "Blocked by unconfirmed power: " + ", ".join(
                            power_checks[key]["label"] for key in failed_power
                        ), device=device_name, blocked=True,
                    )
                else:
                    result = self._check_device(
                        label, device_name, fix=fix, starter_name=api.V0_STARTER_DEVICE,
                        starter_running=running_servers,
                        on_progress=phase,
                    )
                return record(result)

            phase("Checking PDU servers before enabling the explicit V0 supplies", stage=0)
            pdu_checks = {
                device_name: check_device(f"PDU server {device_name}", device_name)
                for device_name in api.V0_PREPARATION_PDU_DEVICES
            }
            for item in api.V0_PREPARATION_NETIO_OUTPUTS:
                phase(f"{'Confirming/enabling' if fix else 'Checking'} power: {item['label']}", stage=0)
                result = (
                    self._check_netio_output(item, fix=fix)
                    if pdu_checks[item["device"]].get("ok")
                    else api._json_fail(item["label"], "PDU is unavailable; power cannot be verified", blocked=True)
                )
                power_checks[item["key"]] = result
                record(result)

            # Power-dependent device servers are checked only after their outputs.
            dg645_check = check_device(
                "DG645 Tango server", self._hardware_config["dg645_device"], ("dg645",)
            )
            daq_check = check_device("DAQmx DS", self._hardware_config["daqmx_device"])

            for index, device_name in enumerate(api.V0_CAMERA_DEVICES, start=1):
                camera_check = check_device(f"V0 camera {index}", device_name)
                record(self._check_camera_stream(device_name, fix=fix) if camera_check.get("ok") else
                       api._json_fail(f"Camera stream {device_name}", "Camera is unavailable", device=device_name, blocked=True))
            remote_check, remote_running = self._starter_server_snapshot(api.V0_STANDA_STARTER_DEVICE)
            record(remote_check)
            phase("Checking STANDA on Elysium2 only; no STANDA start, Init, recovery or motion")
            for device_name in api.V0_REQUIRED_STANDA_DEVICES:
                label = f"STANDA {device_name.rsplit('/', 1)[-1]} (Elysium2)"
                if not remote_check.get("ok") or not power_checks["v0_standa"].get("ok"):
                    record(api._json_fail(label, "Remote Elysium2 server or STANDA power unavailable; no local start attempted",
                                             device=device_name, starter=api.V0_STANDA_STARTER_DEVICE, blocked=True))
                else:
                    record(self._check_device(label, device_name, fix=False,
                                                     starter_name=api.V0_STANDA_STARTER_DEVICE, starter_running=remote_running))

            if power_checks["v0_owis"].get("ok"):
                phase("Verifying OWIS backends, routing and V0 axes without motion")
                for result in self._check_owis_axes(fix=fix, starter_running=running_servers, on_progress=phase):
                    record(result)
            else:
                record(api._json_fail("OWIS controllers and axes", "Blocked by unconfirmed OWIS power", blocked=True))
            for device_name in api.V0_LASER_POINTING_DEVICES:
                phase(f"Verifying {device_name} and its actual camera/actuator dependencies")
                for result in self._check_laser_pointing(device_name, fix=fix,
                        starter_running=running_servers, remote_running=remote_running if remote_check.get("ok") else set(),
                        on_progress=phase):
                    record(result)
            phase("Checking DG645 timing and the pulse counter; DG645 settings are retained", stage=2)
            record(
                self._check_dg645_recall(apply_recall=False)
                if dg645_check.get("ok")
                else api._json_fail("DG645 recall 8", "DG645 is unavailable; preset was not applied", blocked=True)
            )
            record(
                self._check_counter_activity()
                if daq_check.get("ok")
                else api._json_fail("DAQ counter", "DAQmx is unavailable", blocked=True)
            )
            return checks

        def hardware_preflight(self, fix=False, progress=None):
            if fix and api.V0_PREPARATION_READ_ONLY:
                raise ValueError("V0 automatic initialization is disabled; use passive preflight only")
            with self._lock:
                if not fix:
                    # Passive diagnostics may read state/attributes and approved
                    # query commands, but never repair, move, power, recall, or
                    # start/register a camera order.
                    checks = self._v0_preparation_checks(fix=False)
                    ok = all(check.get("ok") for check in checks)
                    return {
                        "success": ok,
                        "fixed": False,
                        "read_only": True,
                        "excluded_devices": [self._hardware_config["andor_device"], self._hardware_config["spectrograph_device"],
                                             *api.V0_OPTIONAL_STANDA_DEVICES],
                        "message": "Passive hardware preflight" if ok else "Passive hardware preflight found unavailable hardware",
                        "recommendation": "Press Prepare to confirm/enable the required V0 supplies and prepare local controls. STANDA is check-only on Elysium2; DG645 timing remains unchanged. Andor CCD / UV-vis are excluded.",
                        "checks": checks,
                        "counter": self._counter_status_locked(),
                    }
                checks = self._v0_preparation_checks(fix=fix, progress=progress)
                ok = all(check.get("ok") for check in checks)
                return {
                    "success": ok,
                    "fixed": bool(fix),
                    "read_only": False,
                    "dg645_timing_read_only": True,
                    "standa_read_only": True,
                    "excluded_devices": list(api.V0_OPTIONAL_STANDA_DEVICES),
                    "message": "V0 laser-setup preparation completed; DG645 timing retained; acquisition not started" if ok else "V0 preparation incomplete; independent checks continued and DG645 timing was retained",
                    "recommendation": "" if ok else (
                        "Correct power or connection for: "
                        + ", ".join(check["label"] for check in checks if not check.get("ok"))
                        + ". Then press Prepare again to repeat all checks."
                    ),
                    "checks": checks,
                    "counter": self._counter_status_locked(),
                }

    return V0Preflight
