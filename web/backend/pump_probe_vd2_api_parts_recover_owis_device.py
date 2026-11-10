"""Implementation for _recover_owis_device and related operations."""

from __future__ import annotations


def _bind_pump_probe_vd2_api_parts_recover_owis_device(api):
    """Bind implementation to the owning module and its runtime state."""

    def _recover_owis_device(proxy, device, steps=None):
        state = str(proxy.state()).split(".")[-1].upper()
        if state in {"ON", "MOVING", "RUNNING", "INIT"}:
            # A missing position readback is not permission to reset live axes.
            return api._observe_owis_initialization(device, steps), []
        proxy.set_timeout_millis(60000)
        if steps is not None:
            api._progress(steps, f"{device}: OWIS initialization command timeout is 60 s; accepted commands are not replayed")
        commands = ("turn_on",) if state in {"OFF", "STANDBY"} else ("recover", "turn_on")
        report = (lambda detail: api._progress(steps, f"{device}: {detail}")) if steps is not None else None
        recovered, errors = api.recover_device(
            proxy, lambda candidate: api._is_healthy_device(candidate, device), commands, on_progress=report,
        )
        if recovered:
            return proxy, errors
        if any("API_DeviceTimedOut" in error or "TRANSIENT_CallTimedout" in error for error in errors):
            # The accepted turn_on can still hold Tango's device lock after the
            # client timed out. Do not kill/restart that process or send Init.
            return api._observe_owis_initialization(device, steps), errors
        errors.append(api._readiness_failure_detail(proxy))
        return None, errors

    _recover_owis_device.__module__ = api.__name__
    _recover_owis_device.__qualname__ = "_recover_owis_device"

    def _recover_retained_instrument(proxy, device, steps):
        if device in api.OWIS_DEVICES:
            return api._recover_owis_device(proxy, device, steps)
        state = str(proxy.state()).split(".")[-1].upper()
        if state in {"ON", "MOVING", "RUNNING", "INIT"}:
            api._progress(steps, f"{device}: observing existing readiness; no Init or server restart")
            return api._wait_for_healthy_device(device), []
        # A cold Shamrock SDK open can outlive the generic instrument timeout.
        # Keep the sole activation call pending instead of declaring failure after
        # 60 s and probing a Tango device still serialized behind that same call.
        proxy.set_timeout_millis(240000 if device == api.KYMERA_DEVICE else 60000)
        if device == api.KYMERA_DEVICE:
            api._progress(steps, "Initializing Kymera SDK after power-up; allowing up to 240 s for the single activation call")
        commands = ("turn_on",) if state in {"OFF", "STANDBY"} else ("recover", "turn_on")
        recovered, errors = api.recover_device(
            proxy, lambda candidate: api._is_healthy_device(candidate, device), commands,
            on_progress=lambda detail: api._progress(steps, f"{device}: {detail}; server retained"),
        )
        if recovered:
            return proxy, errors
        if any("API_DeviceTimedOut" in error or "TRANSIENT_CallTimedout" in error for error in errors):
            api._progress(steps, f"{device}: command outcome unknown; observing without replay or process restart")
            if device == api.KYMERA_DEVICE:
                return api._observe_kymera_startup(steps), errors
            return api._wait_for_healthy_device(device), errors
        errors.append(api._readiness_failure_detail(proxy))
        return None, errors

    _recover_retained_instrument.__module__ = api.__name__
    _recover_retained_instrument.__qualname__ = "_recover_retained_instrument"

    def _observe_kymera_startup(steps, timeout_s=180.0):
        """Observe the already-submitted SDK open; never submit another activation."""
        api._progress(steps, "Waiting for the existing Kymera SDK initialization; no command replay or server restart")
        deadline = api.time.monotonic() + timeout_s
        last_error = "Kymera is not ready"
        while api.time.monotonic() < deadline:
            try:
                proxy = api.DeviceProxy(api.KYMERA_DEVICE)
                remaining = deadline - api.time.monotonic()
                if remaining <= 0:
                    break
                proxy.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
                if api._is_healthy_device(proxy, api.KYMERA_DEVICE):
                    return proxy
                last_error = f"Kymera state {proxy.state()} has not reached ready"
            except Exception as exc:
                # These are read-only observations. IMP_LIMIT/communication errors
                # while the original SDK call holds Tango must not trigger Init.
                last_error = api._control_error(exc)
            api.time.sleep(min(2.0, max(0.0, deadline - api.time.monotonic())))
        raise RuntimeError(f"Kymera SDK initialization remains unverified; server retained, no activation replay. {last_error}")

    _observe_kymera_startup.__module__ = api.__name__
    _observe_kymera_startup.__qualname__ = "_observe_kymera_startup"

    def _wait_for_dg645_power_up(steps, deadline):
        remaining = max(0.0, deadline - api.time.monotonic())
        api._progress(steps, "Waiting for DG645 to complete its power-up transport check",
                  wait_until=api.time.time() + remaining)
        last_error = "No response from the instrument server"
        while remaining > 0:
            try:
                proxy = api.DeviceProxy(api.DG645_DEVICE)
                proxy.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
                state = str(proxy.state()).split(".")[-1].upper()
                # The power monitor publishes STANDBY only after its safe probe
                # succeeds. Until then it owns transport discovery.
                if state in {"STANDBY", "ON"}:
                    return proxy
                last_error = f"Tango state {state}"
            except Exception as exc:
                last_error = api._control_error(exc)
            remaining = deadline - api.time.monotonic()
            if remaining > 0:
                api.time.sleep(min(2.0, remaining))
            remaining = deadline - api.time.monotonic()
        raise RuntimeError(
            f"DG645 did not complete its power-up transport check within "
            f"{api.DG645_POWER_UP_TIMEOUT_S:g} s of power confirmation: {last_error}"
        )

    _wait_for_dg645_power_up.__module__ = api.__name__
    _wait_for_dg645_power_up.__qualname__ = "_wait_for_dg645_power_up"

    def _restart_server(device: str, server: str, steps=None, *, dg645_boot_deadline=None) -> DeviceProxy:
        if device in api.OWIS_DEVICES:
            # Readiness can recover between the original check and escalation.
            # A fresh passive check must precede any Starter stop/start.
            proxy = None
            try:
                proxy = api._wait_for_device(device, timeout_s=2.0)
                if api._is_healthy_device(proxy, device):
                    if steps is not None:
                        api._progress(steps, f"{device}: OWIS is already operational; server retained without restart")
                    return proxy
            except Exception:
                pass
            if proxy is not None and str(proxy.state()).split(".")[-1].upper() in {"ON", "MOVING", "RUNNING", "INIT"}:
                return api._observe_owis_initialization(device, steps)
        astor = api._astor(device)
        report = (lambda detail: api._progress(steps, f"{device}: {detail}")) if steps is not None else None

        def wait_ready():
            if device in api.RETAINED_INSTRUMENT_SERVERS:
                proxy = (api._wait_for_dg645_power_up(steps, dg645_boot_deadline) if dg645_boot_deadline is not None
                         else api._wait_for_device(device, timeout_s=45.0 if device == api.KYMERA_DEVICE else 15.0))
                if api._is_healthy_device(proxy, device):
                    return proxy
                recovered, errors = api._recover_retained_instrument(proxy, device, steps)
                if recovered is not None:
                    return recovered
                raise RuntimeError(f"{device}: equipment readiness failed; server retained. {'; '.join(errors)}")
            return api._wait_for_healthy_device(device)

        def observe_existing():
            if dg645_boot_deadline is not None:
                return wait_ready()
            api._progress(steps, f"Server {server} is already running; observing equipment readiness without restart or command replay")
            try:
                return api._wait_for_healthy_device(device)
            except Exception as exc:
                raise RuntimeError(f"{server} is running but equipment readiness is unverified; server retained. {exc}") from exc

        return api.start_managed_server(
            astor, server, wait_ready, on_progress=report,
            restart_existing=device not in api.RETAINED_INSTRUMENT_SERVERS,
            observe_existing=observe_existing,
        )

    _restart_server.__module__ = api.__name__
    _restart_server.__qualname__ = "_restart_server"

    def _ensure_server(device: str, steps: list[dict[str, str]], *, dg645_boot_deadline=None) -> DeviceProxy:
        api._progress(steps, f"Checking / recovering {device} ({api.VD2_SERVERS[device]})")
        if dg645_boot_deadline is not None:
            proxy = api._restart_server(device, api.VD2_SERVERS[device], steps, dg645_boot_deadline=dg645_boot_deadline)
            steps.append({"step": f"Tango {device}", "status": "readiness verified after power-up"})
            return proxy
        initial_error = "device is exported but hardware is not ready"
        proxy = None
        try:
            proxy = api._wait_for_device(device, timeout_s=2.0)
            if api._is_healthy_device(proxy, device):
                steps.append({"step": f"Tango {device}", "status": "already running"})
                return proxy
            initial_error = f"state={proxy.state()}; device is exported but hardware is not ready"
        except Exception as exc:
            initial_error = str(exc)
            if proxy is None and device in api.RETAINED_INSTRUMENT_SERVERS:
                # A missing process should start immediately. Only an existing
                # (or unconfirmed) process needs a passive transport grace period.
                running = True
                try:
                    running = api.VD2_SERVERS[device] in set(api._astor(device).command_inout("DevGetRunningServers", True))
                except Exception:
                    pass  # Unknown inventory is not permission to restart a process.
                # Power restoration can leave an already-running Tango process
                # temporarily unreachable. No activation was submitted above.
                # Reconnect first so a cold STANDBY instrument can receive its one
                # explicit turn_on through the existing recovery path below.
                if running:
                    api._progress(steps, f"{device}: waiting for transport after power restoration; no process restart")
                    try:
                        proxy = api._wait_for_device(device, timeout_s=20.0)
                        if api._is_healthy_device(proxy, device):
                            steps.append({"step": f"Tango {device}", "status": "already running"})
                            return proxy
                    except Exception as reconnect_error:
                        initial_error += f"; transport recheck: {reconnect_error}"

        server = api.VD2_SERVERS[device]
        api._progress(steps, f"{device} check failed: {initial_error}")
        recovery_errors = []
        if proxy is not None:
            if device in api.RETAINED_INSTRUMENT_SERVERS:
                recovered_proxy, recovery_errors = api._recover_retained_instrument(proxy, device, steps)
                if recovered_proxy is not None:
                    steps.append({"step": f"Tango {device}", "status": "recovered"})
                    return recovered_proxy
                detail = f"{device}: equipment readiness failed; server retained, no Init or process restart. {'; '.join(recovery_errors)}"
                steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
                raise RuntimeError(detail)
            else:
                recovery_commands = (api._recovery_command(device), "Init", "turn_on")
                recovered, recovery_errors = api.recover_device(
                    proxy, lambda candidate: api._is_healthy_device(candidate, device),
                    recovery_commands, on_progress=lambda detail: api._progress(steps, f"{device}: {detail}"),
                )
                if recovered:
                    steps.append({"step": f"Tango {device}", "status": "recovered"})
                    return proxy

        try:
            if device in api.RETAINED_INSTRUMENT_SERVERS:
                api._progress(steps, f"Checking process {server}; start only if absent, otherwise retain it and verify equipment")
            else:
                api._progress(steps, f"Restarting / starting failed device server {server}; other independent branches will still be checked")
            proxy = api._restart_server(device, server, steps)
        except Exception as exc:
            detail = (
                f"{device}: {exc}. Initial check: {initial_error}. "
                + ("Recovery: " + "; ".join(recovery_errors) + ". " if recovery_errors else "")
                + "Check the confirmed PDU output and instrument connection, then press Prepare again."
            )
            steps.append({"step": f"Tango {device}", "status": "failed", "detail": detail})
            raise RuntimeError(detail) from exc
        steps.append({"step": f"Tango {device}", "status":
                      "readiness verified; server retained or started by Astor" if device in api.OWIS_DEVICES else "started by Astor"})
        return proxy

    _ensure_server.__module__ = api.__name__
    _ensure_server.__qualname__ = "_ensure_server"

    def _enable_required_power(
        pdu: DeviceProxy,
        steps: list[dict[str, str]],
        required_outputs: dict[int, str],
        label: str,
    ) -> dict[int, float]:
        ids = [int(value) for value in pdu.read_attribute("ids").value]
        states = [int(value) for value in pdu.read_attribute("states").value]
        if len(ids) != len(states) or len(set(ids)) != len(ids):
            raise RuntimeError(f"PDU {label} output IDs and states do not match")
        positions = {output_id: index for index, output_id in enumerate(ids)}
        missing = sorted(set(required_outputs) - set(positions))
        if missing:
            raise RuntimeError(f"PDU {label} required outputs are missing: {missing}")
        desired = list(states)
        camera_newly_enabled = label == "SD2" and states[positions[1]] != 1
        changed = []
        for output_id in required_outputs:
            position = positions[output_id]
            if desired[position] != 1:
                desired[position] = 1
                changed.append(output_id)
        if changed:
            if camera_newly_enabled and hasattr(steps, "power_intent"):
                steps.power_intent()
            pdu.command_inout("set_channels_states", desired)
        deadline = api.time.monotonic() + 8.0
        while True:
            confirmed_ids = [int(value) for value in pdu.read_attribute("ids").value]
            confirmed = [int(value) for value in pdu.read_attribute("states").value]
            if len(confirmed_ids) != len(confirmed) or len(set(confirmed_ids)) != len(confirmed_ids):
                raise RuntimeError(f"PDU {label} invalid power-on readback")
            confirmed_states = dict(zip(confirmed_ids, confirmed))
            failed = [name for output_id, name in required_outputs.items() if confirmed_states.get(output_id) != 1]
            if not failed:
                break
            if api.time.monotonic() >= deadline:
                raise RuntimeError(f"PDU {label} did not confirm power for: {', '.join(failed)}")
            api.time.sleep(0.5)
        confirmed_at = api.time.monotonic()
        steps.append({"step": f"{label} power", "status": "enabled" if changed else "already enabled"})
        if label == "SD2":
            deadline = (steps.power_deadline(camera_newly_enabled)
                        if hasattr(steps, "power_deadline")
                        else api.time.time() + 30.0 if camera_newly_enabled else None)
            remaining = max(0.0, deadline - api.time.time()) if deadline else 0.0
            if remaining:
                api._progress(steps, "Waiting for streak-camera / Kymera power to settle and hardware calibration before server initialization",
                          wait_until=deadline)
                # Real elapsed time, not a page timer. Reloading cannot shorten it.
                api.time.sleep(remaining)
                # A timer is not proof that power remained present.
                verified_ids = [int(value) for value in api._value(pdu, "ids")]
                verified_states = [int(value) for value in api._value(pdu, "states")]
                if len(verified_ids) != len(verified_states) or len(set(verified_ids)) != len(verified_ids):
                    raise RuntimeError("SD2 power readback invalid after camera settling delay")
                powered = dict(zip(verified_ids, verified_states))
                if any(powered.get(output_id) != 1 for output_id in required_outputs):
                    if hasattr(steps, "power_intent"):
                        steps.power_intent()
                    raise RuntimeError("SD2 power changed during camera settling delay; no instrument initialization attempted")
                steps.append({"step": "Streak / Kymera power settling", "status": "30 s power-up delay completed; hardware readiness will be checked next"})
            if hasattr(steps, "power_ready"):
                steps.power_ready()
            api._progress(steps, "Power confirmed; checking dependent instrument servers")
            if changed and not camera_newly_enabled and not remaining:
                api.time.sleep(2.0)
        elif changed:
            api.time.sleep(2.0)
        return dict.fromkeys(changed, confirmed_at)

    _enable_required_power.__module__ = api.__name__
    _enable_required_power.__qualname__ = "_enable_required_power"

    def _disable_vd2_power(pdu: DeviceProxy, steps: list[dict[str, str]]) -> None:
        # The trigger generator was started first and is switched off before the
        # camera supply; software and optical closure must precede this function.
        for output_id in (2, 1):
            api._disable_pdu_outputs(pdu, steps, {output_id: api.VD2_SHUTDOWN_PDU_OUTPUTS[output_id]}, "SD2")

    _disable_vd2_power.__module__ = api.__name__
    _disable_vd2_power.__qualname__ = "_disable_vd2_power"

    def _disable_pdu_outputs(pdu, steps, outputs, label):
        retained = api.VD2_RETAINED_PDU_OUTPUTS if label == "VD2" else {}
        forbidden = sorted(set(outputs) & set(retained))
        if forbidden:
            raise RuntimeError(f"Unprepare must retain PDU VD2 outputs: {[retained[key] for key in forbidden]}")
        ids = [int(value) for value in pdu.read_attribute("ids").value]
        states = [int(value) for value in pdu.read_attribute("states").value]
        if len(ids) != len(states) or len(set(ids)) != len(ids):
            raise RuntimeError(f"PDU {label} output IDs and states do not match")
        positions = {output_id: index for index, output_id in enumerate(ids)}
        missing = sorted((set(outputs) | set(retained)) - set(positions))
        if missing:
            raise RuntimeError(f"PDU {label} required outputs are missing: {missing}")
        desired = list(states)
        retained_states = {output_id: states[positions[output_id]] for output_id in retained}
        if any(state not in (0, 1) for state in retained_states.values()):
            raise RuntimeError("PDU VD2 retained outlet readback invalid; no power changes attempted")
        changed = []
        for output_id, output_label in outputs.items():
            position = positions[output_id]
            if desired[position] != 0:
                desired[position] = 0
                changed.append(output_label)
        if changed:
            pdu.command_inout("set_channels_states", desired)
        deadline = api.time.monotonic() + 8.0
        while True:
            confirmed_ids = [int(value) for value in api._value(pdu, "ids")]
            confirmed = [int(value) for value in api._value(pdu, "states")]
            if len(confirmed_ids) != len(confirmed) or len(set(confirmed_ids)) != len(confirmed_ids):
                raise RuntimeError(f"PDU {label} invalid power-off readback")
            readback = dict(zip(confirmed_ids, confirmed))
            altered = [name for output_id, name in retained.items()
                       if readback.get(output_id) != retained_states[output_id]]
            if altered:
                raise RuntimeError(f"PDU {label} retained power changed or unverified: {', '.join(altered)}")
            failed = [name for output_id, name in outputs.items() if readback.get(output_id) != 0]
            if not failed:
                break
            if api.time.monotonic() >= deadline:
                raise RuntimeError(f"PDU {label} did not disable: {', '.join(failed)}")
            api.time.sleep(0.5)
        steps.append({"step": f"{label} power: {', '.join(outputs.values())}",
                      "status": "disabled; verified OFF" if changed else "already disabled; verified OFF"})

    _disable_pdu_outputs.__module__ = api.__name__
    _disable_pdu_outputs.__qualname__ = "_disable_pdu_outputs"

    def _initialize_experiment(steps=None) -> dict[str, Any]:
        if steps is None:
            steps = []
        try:
            result = api._initialize_equipment(steps)
            if result.get("already_ready"):
                raise api.AlreadyPrepared(result)
            return result
        except api.AlreadyPrepared:
            raise
        except Exception as exc:
            raise api.PreparationFailure(str(exc), steps) from exc

    _initialize_experiment.__module__ = api.__name__
    _initialize_experiment.__qualname__ = "_initialize_experiment"

    class PreparationFailure(RuntimeError):
        def __init__(self, message, steps):
            super().__init__(message)
            self.steps = list(steps)

    PreparationFailure.__module__ = api.__name__
    PreparationFailure.__qualname__ = "PreparationFailure"

    class AlreadyPrepared(PreparationFailure):
        code = "experiment_already_on"

        def __init__(self, result):
            super().__init__("VD2 is already switched on; all readiness checks passed. No hardware command or settings change was performed.", result["steps"])
            self.result = result

    AlreadyPrepared.__module__ = api.__name__
    AlreadyPrepared.__qualname__ = "AlreadyPrepared"

    def _prepare_dg645_for_vd2(dg645, steps):
        """Apply single-trigger timing before starting any VD2 camera software."""
        label = f"DG645 Recall {api.VD2_DG645_RECALL_SLOT}"
        try:
            dg645.command_inout("scpi_write", f"*RCL {api.VD2_DG645_RECALL_SLOT}")
            api.time.sleep(1.0)
            dg645.command_inout("scpi_write", "BURM 0")
            dg645.command_inout("scpi_query", "*OPC?")
            burst_mode = str(dg645.command_inout("scpi_query", "BURM?")).strip()
            if float(burst_mode) != 0.0:
                raise RuntimeError(f"burst mode is still enabled (BURM?={burst_mode})")
        except Exception as exc:
            detail = f"{label} / burst-off verification failed: {exc}"
            steps.append({"step": label, "status": "failed", "detail": detail})
            raise RuntimeError(detail) from exc
        steps.append({"step": label, "status": "applied; verified BURM=0"})

    _prepare_dg645_for_vd2.__module__ = api.__name__
    _prepare_dg645_for_vd2.__qualname__ = "_prepare_dg645_for_vd2"

    def _verify_owis_sample_axis(owis, steps):
        """Verify VD2 axis 2 without issuing movement or homing commands."""
        label = f"OWIS sample axis {api.OWIS_SAMPLE_AXIS}"
        try:
            state = int(owis.command_inout("get_status_axis", api.OWIS_SAMPLE_AXIS))
            # An OFF motor can be enabled explicitly, but do not reinitialize an
            # axis or move it as a side effect of a readiness check.
            if state == int(api.DevState.OFF):
                result = owis.command_inout("turn_on_axis", api.OWIS_SAMPLE_AXIS)
                if str(result).strip() != "0":
                    raise RuntimeError(f"turn_on_axis: {result}")
                state = int(owis.command_inout("get_status_axis", api.OWIS_SAMPLE_AXIS))
            if state != int(api.DevState.ON):
                raise RuntimeError(f"axis is not ready (state={state}); correct its condition and press Prepare again")
            position = float(owis.command_inout("read_position_axis", api.OWIS_SAMPLE_AXIS))
            if not api.math.isfinite(position):
                raise RuntimeError("axis position readback is invalid")
        except Exception as exc:
            detail = f"{label}: {exc}"
            steps.append({"step": label, "status": "failed", "detail": detail})
            raise RuntimeError(detail) from exc
        steps.append({"step": label, "status": f"verified ON; {position:.4f} mm"})

    _verify_owis_sample_axis.__module__ = api.__name__
    _verify_owis_sample_axis.__qualname__ = "_verify_owis_sample_axis"

    def _assert_preparation_idle(streak=None):
        if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
            raise RuntimeError("Stop the VD2 measurement before Prepare")
        if streak is None:
            try:
                streak = api._wait_for_device(api.STREAK_DEVICE, timeout_s=1.0)
            except Exception:
                return
        if str(api._value(streak, "remoteex_status")).lower() in {"busy", "starting", "preparing"}:
            raise RuntimeError("HPD-TA is busy; stop acquisition before Prepare")
        if bool(api._value(streak, "connected")) or bool(api._value(streak, "application_running")):
            try:
                status = str(streak.command_inout("ExecuteRaw", "AcqStatus()")).strip().lower()
            except Exception as exc:
                # This exact RemoteEx reply confirms a cold application; absence of
                # a response or a stale application_running=False cache does not.
                if "3,acqstatus,application not running" in str(exc).lower():
                    return
                raise RuntimeError(f"Cannot confirm HPD-TA acquisition idle: {exc}") from exc
            if status != "0,acqstatus,idle":
                raise RuntimeError(f"HPD-TA acquisition is not confirmed idle: {status}")

    _assert_preparation_idle.__module__ = api.__name__
    _assert_preparation_idle.__qualname__ = "_assert_preparation_idle"

    def _assert_kymera_passive_server(kymera):
        """An idle SDK server must not reopen the hardware behind HPD-TA."""
        properties = kymera.get_property(["power_dependency_auto_probe"])
        values = list(properties.get("power_dependency_auto_probe", []))
        if len(values) != 1 or int(values[0]) != 0:
            raise RuntimeError(
                "Kymera SDK handoff requires power_dependency_auto_probe=0 in the running server; "
                "automatic SDK probing must be disabled before retaining the server alongside HPD-TA"
            )

    _assert_kymera_passive_server.__module__ = api.__name__
    _assert_kymera_passive_server.__qualname__ = "_assert_kymera_passive_server"

    def _verify_kymera_sdk_released(kymera):
        kymera.set_timeout_millis(2000)
        deadline = api.time.monotonic() + 20.0
        while str(kymera.state()).split(".")[-1].upper() != "OFF":
            if api.time.monotonic() >= deadline:
                raise RuntimeError("Kymera SDK ownership was not released; server retained, HPD-TA startup blocked")
            api.time.sleep(0.5)

    _verify_kymera_sdk_released.__module__ = api.__name__
    _verify_kymera_sdk_released.__qualname__ = "_verify_kymera_sdk_released"

    def _prepare_kymera_for_vd2(streak, steps):
        """Hand Kymera from HPD-TA to its SDK server, then release it before AppStart."""
        api._assert_preparation_idle(streak)
        api._progress(steps, "Releasing HPD-TA / RemoteEx SDK ownership before Kymera initialization")
        streak.set_timeout_millis(30000)
        if bool(api._value(streak, "application_running")):
            for attribute in ("streak_shutter", "spectrograph_shutter"):
                streak.write_attribute(attribute, "Closed")
                if str(api._value(streak, attribute)).lower() != "closed":
                    raise RuntimeError(f"Cannot confirm {attribute} closed before Kymera handoff")
            streak.command_inout("StopApplication")
            deadline = api.time.monotonic() + 20.0
            while bool(api._value(streak, "application_running")):
                if api.time.monotonic() >= deadline:
                    raise RuntimeError("HPD-TA did not stop; cannot give Kymera to its SDK server")
                api.time.sleep(0.5)
            steps.append({"step": "HPD-TA handoff", "status": "stopped; both shutters closed"})

        # AppEnd does not unload the spectrograph SDK from TaRemoteEx. Stop its
        # process too, otherwise a second SDK owner can hang or access-violate.
        streak.command_inout("StopRemoteEx")
        if bool(api._value(streak, "connected")):
            raise RuntimeError("RemoteEx ownership was not released before Kymera SDK startup")
        steps.append({"step": "RemoteEx SDK ownership", "status": "process stopped before Kymera startup"})

        kymera = None
        try:
            kymera = api._ensure_server(api.KYMERA_DEVICE, steps)
            api._assert_kymera_passive_server(kymera)
            kymera.set_timeout_millis(45000)
            result = api.json.loads(kymera.command_inout("PrepareVD2Grating"))
            if not (
                int(result["grating"]) == 2
                and api.math.isfinite(float(result["blaze"]))
                and abs(float(result["blaze"]) - 800.0) <= 0.01
                and api.math.isfinite(float(result["ruling"]))
                and abs(float(result["ruling"]) - 150.0) <= 0.01
            ):
                raise RuntimeError(f"Kymera grating preparation readback mismatch: {result}")
            steps.append({"step": "Kymera grating 2", "status": "SDK verified: Blaze 800; 150 g/mm"})
        finally:
            # Close the SDK after selection (also on failure), not the Tango process.
            # Unknown/failed release blocks HPD-TA; it is never resolved by killing it.
            if kymera is not None:
                api._progress(steps, "Deinitializing Kymera SDK; retaining Tango server before HPD-TA startup")
                kymera.command_inout("turn_off")
                api._verify_kymera_sdk_released(kymera)
        steps.append({"step": "Kymera SDK ownership", "status": "SDK deinitialized; server retained; released to HPD-TA"})

    _prepare_kymera_for_vd2.__module__ = api.__name__
    _prepare_kymera_for_vd2.__qualname__ = "_prepare_kymera_for_vd2"

    def _initialize_equipment(steps) -> dict[str, Any]:
        api._progress(steps, "Checking whether VD2 is already running; existing settings will be retained", stage=0)
        api._assert_preparation_idle()
        prepared = api._prepared_equipment_state()
        if prepared is not None:
            # A repeat Prepare must not silently call an old timing ready, nor
            # reset operational optics to repair it. Verification performs no writes.
            streak = api._wait_for_device(api.STREAK_DEVICE, timeout_s=2.0)
            api._verify_vd2_timing_ready(streak)
            return prepared
        # A measurement can start while the passive equipment checks are running.
        api._assert_preparation_idle()
        failed = {}

        def attempt(label, action, dependencies=()):
            blocked = [dependency for dependency in dependencies if dependency in failed]
            if blocked:
                detail = f"Skipped {label}: unverified dependencies: {', '.join(blocked)}"
                failed[label] = detail
                steps.append({"step": label, "status": "skipped", "detail": detail})
                return None
            api._progress(steps, f"Preparing {label}")
            try:
                value = action()
                return value
            except Exception as exc:
                failed[label] = str(exc)
                steps.append({"step": label, "status": "failed", "detail": str(exc)})
                api._progress(steps, f"{label} failed; continuing independent equipment checks")
                return None

        # Check every PDU independently; only its own dependent branch is blocked.
        sd2_pdu = attempt("SD2 PDU", lambda: api._ensure_server(api.VD2_PDU_DEVICE, steps))
        zaber_pdu = attempt("VD2 PDU", lambda: api._ensure_server(api.ZABER_PDU_DEVICE, steps))
        owis_pdu = attempt("OWIS PDU", lambda: api._ensure_server(api.OWIS_PDU_DEVICE, steps))
        sd2_power_on = attempt("SD2 power", lambda: api._enable_vd2_power(sd2_pdu, steps), ("SD2 PDU",))
        attempt("VD2 power", lambda: api._enable_required_power(zaber_pdu, steps, api.VD2_REQUIRED_PDU_OUTPUTS, "VD2"), ("VD2 PDU",))
        attempt("OWIS power", lambda: api._enable_required_power(owis_pdu, steps, api.OWIS_REQUIRED_PDU_OUTPUTS, "OWIS"), ("OWIS PDU",))
        dg645_power_on = (sd2_power_on or {}).get(2)
        dg645_options = {}
        if dg645_power_on is not None:
            dg645_options["dg645_boot_deadline"] = dg645_power_on + api.DG645_POWER_UP_TIMEOUT_S
        dg645 = attempt("DG645 server", lambda: api._ensure_server(api.DG645_DEVICE, steps, **dg645_options), ("SD2 power",))
        if not api.VD2_CAMERA_ONLY:
            attempt("DG645 timing", lambda: api._prepare_dg645_for_vd2(dg645, steps), ("DG645 server",))
        # VD2 uses axis 2 on the IP backend. The shared aggregator also depends on
        # USB axis 4, so it must not gate preparation or receive VD2 axis commands.
        owis = attempt("OWIS IP server", lambda: api._ensure_server(api.OWIS_SAMPLE_DEVICE, steps), ("OWIS power",))
        attempt("OWIS sample axis", lambda: api._verify_owis_sample_axis(owis, steps), ("OWIS IP server",))
        attempt("Zaber server", lambda: api._ensure_server(api.ZABER_STAGE_DEVICE, steps), ("VD2 power",))
        streak = attempt("Hamamatsu server", lambda: api._ensure_server(api.STREAK_DEVICE, steps), ("SD2 power",))
        dg645_step = "DG645 server" if api.VD2_CAMERA_ONLY else "DG645 timing"
        optical = attempt("Streak / Kymera optical startup", lambda: api._start_vd2_optics(streak, steps), ("Hamamatsu server", dg645_step))
        if failed:
            # No global ready flag for a partially prepared rig, even if optics work.
            raise RuntimeError("VD2 preparation incomplete: " + "; ".join(f"{name}: {detail}" for name, detail in failed.items()))
        return {"steps": steps, "device": optical}

    _initialize_equipment.__module__ = api.__name__
    _initialize_equipment.__qualname__ = "_initialize_equipment"

    return {
        "_recover_owis_device": _recover_owis_device,
        "_recover_retained_instrument": _recover_retained_instrument,
        "_observe_kymera_startup": _observe_kymera_startup,
        "_wait_for_dg645_power_up": _wait_for_dg645_power_up,
        "_restart_server": _restart_server,
        "_ensure_server": _ensure_server,
        "_enable_required_power": _enable_required_power,
        "_disable_vd2_power": _disable_vd2_power,
        "_disable_pdu_outputs": _disable_pdu_outputs,
        "_initialize_experiment": _initialize_experiment,
        "PreparationFailure": PreparationFailure,
        "AlreadyPrepared": AlreadyPrepared,
        "_prepare_dg645_for_vd2": _prepare_dg645_for_vd2,
        "_verify_owis_sample_axis": _verify_owis_sample_axis,
        "_assert_preparation_idle": _assert_preparation_idle,
        "_assert_kymera_passive_server": _assert_kymera_passive_server,
        "_verify_kymera_sdk_released": _verify_kymera_sdk_released,
        "_prepare_kymera_for_vd2": _prepare_kymera_for_vd2,
        "_initialize_equipment": _initialize_equipment,
    }
