"""Implementation for _start_vd2_optics and related operations."""

from __future__ import annotations


def _bind_pump_probe_vd2_api_parts_start_vd2_optics(api):
    """Bind implementation to the owning module and its runtime state."""

    def _start_tango_optics(streak, steps):
        api._assert_preparation_idle(streak)
        if not bool(api._value(streak, "application_running")):
            api._progress(steps, "Starting the camera-only RemoteEx profile", stage=2)
            streak.command_inout("StartRemoteEx")
            streak.command_inout("StartCameraOnlyApplication")
        deadline = api.time.monotonic() + 180.0
        while api.time.monotonic() < deadline:
            state = str(streak.state()).split(".")[-1]
            if state in {"FAULT", "ALARM"}:
                raise RuntimeError(f"Camera-only HPD-TA startup failed: {streak.status()}")
            if state == "ON" and bool(api._value(streak, "application_running")):
                if not bool(api._value(streak, "camera_only_application")):
                    raise RuntimeError("Close the manual HPD-TA session before preparing remote VD2")
                if str(api._value(streak, "remoteex_status")).lower() == "idle":
                    break
            api.time.sleep(1.0)
        else:
            raise RuntimeError("Camera-only HPD-TA did not confirm readiness")

        dg645 = api.DeviceProxy(api.DG645_DEVICE)
        dg645.set_timeout_millis(5000)
        try:
            api._prepare_dg645_for_vd2(dg645, steps)
        finally:
            api.tango_optics.pause_internal_clock(dg645)
        profile = api.timing_for_range(api._remoteex_readback(streak, "DevParamGet(TD,Time Range)"))
        api._apply_vd2_timing(profile, steps)
        dg645.command_inout("scpi_write", "TRAT 5")
        if float(dg645.command_inout("scpi_query", "TRAT?")) != 5.0:
            raise RuntimeError("DG645 internal 5 Hz setpoint unverified")
        kymera = api._ensure_server(api.KYMERA_DEVICE, steps)
        kymera.set_timeout_millis(45000)
        kymera.write_attribute("shutter", "Closed")
        kymera.command_inout("PrepareVD2Grating")
        kymera.write_attribute("wavelength_nm", 550.0)
        wavelength = float(api._value(kymera, "wavelength_nm"))
        if not api.math.isfinite(wavelength) or abs(wavelength - 550.0) > 0.1:
            raise RuntimeError("Kymera did not verify 550 nm")
        if api._remoteex_readback(streak, "DevParamGet(TD,Shutter)").lower() != "closed":
            raise RuntimeError("Confirm streak shutter Closed before opening Kymera")
        kymera.write_attribute("shutter", "Open")
        if str(api._value(kymera, "shutter")).lower() != "open":
            raise RuntimeError("Kymera shutter did not verify Open")
        steps.append({"step": "VD2 optics", "status": "camera-only HPD-TA; Kymera and DG645 via Tango"})
        return api._snapshot(streak)

    def _start_vd2_optics(streak, steps):
        """Optical branch is independent of external stages, but requires safe timing."""
        api._live_average_readback = None  # A prior HPD-TA instance cannot verify new filter settings.
        streak.set_timeout_millis(60000)
        if api.VD2_CAMERA_ONLY:
            return _start_tango_optics(streak, steps)

        # StopRemoteEx below verifies actual local process exit, even when its Tango
        # flags are disconnected. A cold start must not launch it merely to stop it
        # again before Kymera's exclusive SDK initialization.
        if bool(api._value(streak, "application_running")) and not bool(api._value(streak, "connected")):
            api._progress(steps, "Reconnecting to existing HPD-TA before releasing its SDK ownership")
            streak.command_inout("StartRemoteEx")
            if not bool(api._value(streak, "connected")):
                raise RuntimeError("Cannot reconnect to running HPD-TA; Kymera SDK startup blocked")
        api._prepare_kymera_for_vd2(streak, steps)
        api._progress(steps, "Starting RemoteEx / HPD-TA and waiting for verified instrument readiness", stage=2)
        streak.command_inout("StartRemoteEx")
        if not bool(api._value(streak, "connected")):
            raise RuntimeError("RemoteEx did not reconnect after Kymera SDK release")
        streak.command_inout("StartApplication")
        # AppStart can reconnect RemoteEx and then move the spectrograph before ready.
        deadline = api.time.monotonic() + 180.0
        while api.time.monotonic() < deadline:
            state = str(streak.state()).split(".")[-1]
            if state in {"FAULT", "ALARM"}:
                raise RuntimeError(f"HPD-TA startup failed: {streak.status()}")
            if (
                state == "ON"
                and bool(api._value(streak, "application_running"))
                and str(api._value(streak, "remoteex_status")).lower() == "idle"
            ):
                # StartApplication recalls memory 9 again inside the camera server.
                # Apply calibrated A/E only after that startup and its 1 us profile.
                profile = api.timing_for_range(api._remoteex_readback(streak, "DevParamGet(TD,Time Range)"))
                api._apply_vd2_timing(profile, steps)
                steps.append({"step": "HPD-TA", "status": "running"})
                steps.append({
                    "step": "VD2 optical profile",
                    "status": (
                        "verified: 550 nm; grating 2 (Blaze 800); 1 us; Operate; "
                        "Kymera shutter open; streak-camera shutter closed"
                    ),
                })
                return api._snapshot(streak)
            api.time.sleep(1.0)
        raise RuntimeError(
            "HPD-TA did not become ready. Check the Everest desktop for a hardware-profile dialog."
        )

    _start_vd2_optics.__module__ = api.__name__
    _start_vd2_optics.__qualname__ = "_start_vd2_optics"

    def _prepared_equipment_state() -> dict[str, Any] | None:
        """Read-only fast path; a running camera alone does not prove VD2 ready.

    The caller must first exclude acquisition. Never open the Kymera SDK here:
    HPD-TA owns it. Keep current wavelength, time range and shutter settings;
    repeating Prepare is not a request to reset an operational experiment.
    """
        steps = []
        proxies = {}
        try:
            for device in (
                api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE, api.OWIS_PDU_DEVICE,
                api.DG645_DEVICE, api.OWIS_SAMPLE_DEVICE, api.ZABER_STAGE_DEVICE, api.STREAK_DEVICE,
            ):
                proxy = api.DeviceProxy(device)
                proxy.set_timeout_millis(3000)
                if not api._is_healthy_device(proxy, device):
                    return None
                proxies[device] = proxy
                steps.append({"step": f"Tango {device}", "status": "already running"})

            for device, outputs, label in (
                (api.VD2_PDU_DEVICE, api.SD2_REQUIRED_PDU_OUTPUTS, "SD2"),
                (api.ZABER_PDU_DEVICE, api.VD2_REQUIRED_PDU_OUTPUTS, "VD2"),
                (api.OWIS_PDU_DEVICE, api.OWIS_REQUIRED_PDU_OUTPUTS, "OWIS"),
            ):
                ids = [int(value) for value in api._value(proxies[device], "ids")]
                states = [int(value) for value in api._value(proxies[device], "states")]
                if len(ids) != len(states) or len(set(ids)) != len(ids):
                    return None
                readback = dict(zip(ids, states))
                if any(readback.get(output_id) != 1 for output_id in outputs):
                    return None
                steps.append({"step": f"{label} power", "status": "already enabled"})

            dg645 = proxies[api.DG645_DEVICE]
            if api.tango_optics.burst_armed(dg645):
                return None
            steps.append({"step": "DG645", "status": "verified; timing unchanged"})

            owis = proxies[api.OWIS_SAMPLE_DEVICE]
            if int(owis.command_inout("get_status_axis", api.OWIS_SAMPLE_AXIS)) != int(api.DevState.ON):
                return None
            if not api.math.isfinite(float(owis.command_inout("read_position_axis", api.OWIS_SAMPLE_AXIS))):
                return None
            zaber = proxies[api.ZABER_STAGE_DEVICE]
            if str(zaber.state()).split(".")[-1] != "ON":
                return None
            if not api.math.isfinite(float(api._value(zaber, "position_mm"))):
                return None
            steps.append({"step": "VD2 stages", "status": "verified; no movement requested"})

            streak = proxies[api.STREAK_DEVICE]
            if not (
                str(streak.state()).split(".")[-1] == "ON"
                and bool(api._value(streak, "connected"))
                and bool(api._value(streak, "application_running"))
                and str(api._value(streak, "remoteex_status")).lower() == "idle"
            ):
                return None

            if api.VD2_CAMERA_ONLY and not bool(api._value(streak, "camera_only_application")):
                return None

            # Verify the active camera and grating through their owners.
            for command, expected in (
                ("AppInfo(Version)", None),
                ("DevParamGet(Spec,Blaze)", 800.0),
                ("DevParamGet(Spec,Ruling)", 150.0),
                ("DevParamGet(TD,Mode)", "operate"),
                ("AcqStatus()", "idle"),
            ):
                value = api._remoteex_readback(streak, command)
                if not value:
                    return None
                if isinstance(expected, float):
                    number = float(value)
                    if not api.math.isfinite(number) or abs(number - expected) > 0.01:
                        return None
                elif expected is not None and value.lower() != expected:
                    return None

            running = set(api._astor(api.KYMERA_DEVICE).command_inout("DevGetRunningServers", True))
            if not api.VD2_CAMERA_ONLY and api.VD2_SERVERS[api.KYMERA_DEVICE] in running:
                kymera = api.DeviceProxy(api.KYMERA_DEVICE)
                kymera.set_timeout_millis(2000)
                api._assert_kymera_passive_server(kymera)
                if str(kymera.state()).split(".")[-1].upper() != "OFF":
                    return None
            steps.extend([
                {"step": "RemoteEx / HPD-TA", "status": "already running; verified idle"},
                {"step": "Kymera grating 2", "status": "verified Blaze 800 / 150 g/mm"},
                {"step": "Kymera SDK ownership", "status": "Tango owns spectrograph" if api.VD2_CAMERA_ONLY else "HPD-TA owns spectrograph"},
            ])
            return {
                "already_ready": True,
                "message": "VD2 is already running; all checks passed. No restart or settings change was needed.",
                "steps": steps,
                "device": api._snapshot(streak),
            }
        except Exception:
            # A failed/incomplete read is not readiness. The ordinary power-first
            # recovery path will report the specific fault instead of hiding it.
            return None

    _prepared_equipment_state.__module__ = api.__name__
    _prepared_equipment_state.__qualname__ = "_prepared_equipment_state"

    def _deinitialize_experiment(steps=None) -> dict[str, Any]:
        """Close SDK owners and optics before switching off experiment supplies."""
        if steps is None:
            steps = []
        try:
            return api._shutdown_equipment(steps)
        except Exception as exc:
            steps.append({"step": "VD2 safe shutdown", "status": "failed", "detail": str(exc)})
            raise api.PreparationFailure(str(exc), steps) from exc

    _deinitialize_experiment.__module__ = api.__name__
    _deinitialize_experiment.__qualname__ = "_deinitialize_experiment"

    def _remoteex_readback(streak, command):
        if api.VD2_CAMERA_ONLY and command in api.tango_optics.SPEC_QUERIES:
            return str(api.tango_optics.read_external(api, api.tango_optics.SPEC_QUERIES[command]))
        raw = str(streak.command_inout("ExecuteRaw", command)).strip()
        parts = raw.split(",", 2)
        if len(parts) != 3 or parts[0] != "0" or parts[1] != command.split("(", 1)[0]:
            raise RuntimeError(f"Invalid {command} readback: {raw}")
        return parts[2].strip()

    _remoteex_readback.__module__ = api.__name__
    _remoteex_readback.__qualname__ = "_remoteex_readback"

    def _apply_vd2_timing(profile, steps):
        api._progress(steps, f"Applying DG645 A=T0+{profile.delay_a_ms} ms, E=T0+{profile.delay_e_ms} ms for {profile.time_range}; gates unchanged", stage=2)
        try:
            dg645 = api.DeviceProxy(api.DG645_DEVICE)
            dg645.set_timeout_millis(5000)
            api.apply_timing(dg645, profile)
        except Exception as exc:
            steps.append({"step": "DG645 calibrated timing", "status": "failed", "detail": str(exc)})
            raise RuntimeError(f"DG645 timing unverified; keep acquisition stopped: {exc}") from exc
        steps.append({"step": "DG645 calibrated timing", "status":
                      f"verified {profile.time_range}: A=T0+{profile.delay_a_ms} ms; E=T0+{profile.delay_e_ms} ms; gates unchanged"})

    _apply_vd2_timing.__module__ = api.__name__
    _apply_vd2_timing.__qualname__ = "_apply_vd2_timing"

    def _verify_vd2_timing_ready(streak):
        """A partial timing write cannot silently become an Operate acquisition."""
        if api.VD2_CAMERA_ONLY and not bool(api._value(streak, "camera_only_application")):
            raise RuntimeError("VD2 requires the camera-only HPD-TA profile")
        mode = api._remoteex_readback(streak, "DevParamGet(TD,Mode)").lower()
        if mode == "focus" and not api.VD2_CAMERA_ONLY:
            return  # Focus live imaging does not use the calibrated sweep trigger.
        if api.VD2_CAMERA_ONLY:
            dg645 = api.DeviceProxy(api.DG645_DEVICE)
            dg645.set_timeout_millis(5000)
            if api.tango_optics.burst_armed(dg645):
                raise RuntimeError("DG645 Burst is reserved for paired ABS/BASE acquisition")
            if mode == "focus":
                return
        if mode != "operate":
            raise RuntimeError(f"Cannot confirm streak mode before acquisition: {mode}")
        profile = api.timing_for_range(api._remoteex_readback(streak, "DevParamGet(TD,Time Range)"))
        dg645 = api.DeviceProxy(api.DG645_DEVICE)
        dg645.set_timeout_millis(5000)
        if not api.VD2_CAMERA_ONLY and float(dg645.command_inout("scpi_query", "BURM?")) != 0.0:
            raise RuntimeError("DG645 burst mode is not verified OFF; acquisition blocked")
        api.verify_timing(dg645, profile)

    _verify_vd2_timing_ready.__module__ = api.__name__
    _verify_vd2_timing_ready.__qualname__ = "_verify_vd2_timing_ready"

    def _shutdown_timed_out(exc):
        return isinstance(exc, TimeoutError) or any(token in str(exc).lower() for token in (
            "api_devicetimedout", "transient_calltimedout", "timed out", "timeout",
        ))

    _shutdown_timed_out.__module__ = api.__name__
    _shutdown_timed_out.__qualname__ = "_shutdown_timed_out"

    def _shutdown_once(action, steps, description):
        """A timed-out hardware command may already have executed: never replay it."""
        try:
            action()
        except Exception as exc:
            if not api._shutdown_timed_out(exc):
                raise
            api._progress(steps, f"Waiting for {description} confirmation after timeout; power retained", stage=0)

    _shutdown_once.__module__ = api.__name__
    _shutdown_once.__qualname__ = "_shutdown_once"

    def _shutdown_acquisition_phase(streak):
        status = api._remoteex_readback(streak, "AcqStatus()").lower()
        parts = [part.strip() for part in status.split(",")]
        if (parts[0] == "idle" and len(parts) == 1
                or parts[0] == "busy" and (len(parts) == 1 or len(parts) == 2 and bool(parts[1]))):
            return parts[0]
        raise RuntimeError(f"Unknown acquisition status: {status}; power retained")

    _shutdown_acquisition_phase.__module__ = api.__name__
    _shutdown_acquisition_phase.__qualname__ = "_shutdown_acquisition_phase"

    def _wait_shutdown_readback(streak, read, expected, description, timeout_s=20.0):
        deadline = api.time.monotonic() + timeout_s
        last = "no readback"
        while True:
            remaining = deadline - api.time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"Cannot confirm {description}; power retained (last readback: {last})")
            streak.set_timeout_millis(max(1, min(2000, int(remaining * 1000))))
            try:
                value = read()
                last = str(value)
                if value == expected:
                    streak.set_timeout_millis(30000)
                    return
            except Exception as exc:
                if not api._shutdown_timed_out(exc):
                    raise
                last = "readback timed out"
            api.time.sleep(min(0.5, max(0.0, deadline - api.time.monotonic())))

    _wait_shutdown_readback.__module__ = api.__name__
    _wait_shutdown_readback.__qualname__ = "_wait_shutdown_readback"

    def _shutdown_hpdta(streak, steps):
        streak.set_timeout_millis(30000)
        if str(api._value(streak, "remoteex_status")).lower() in {"starting", "preparing"}:
            raise RuntimeError("Wait for HPD-TA startup/preparation before safe shutdown")
        application_running = bool(api._value(streak, "application_running"))
        if bool(api._value(streak, "connected")):
            try:
                status = api._shutdown_acquisition_phase(streak)
            except Exception as exc:
                if "3,acqstatus,application not running" not in str(exc).lower():
                    raise
                application_running = False
            else:
                application_running = True  # Direct reply overrides a stale Tango flag.
                if api.VD2_CAMERA_ONLY and not bool(api._value(streak, "camera_only_application")):
                    raise RuntimeError("HPD-TA profile is unverified; close the manual session before remote shutdown")
                if status != "idle":
                    api._progress(steps, "Stopping camera acquisition and waiting for idle", stage=0)
                    api._shutdown_once(lambda: streak.command_inout("StopAcquisition"), steps, "idle acquisition")
                    api._wait_shutdown_readback(streak, lambda: api._shutdown_acquisition_phase(streak),
                                            "idle", "acquisition stopped")
                steps.append({"step": "Streak acquisition", "status": "verified idle"})
        elif application_running:
            raise RuntimeError("HPD-TA is running without a command connection; power retained")

        if application_running:
            for attribute, command in (
                ("streak_shutter", "DevParamGet(TD,Shutter)"),
                ("spectrograph_shutter", "DevParamGet(Spec,Shutter)"),
            ):
                api._progress(steps, f"Closing and verifying {attribute.replace('_', ' ')}", stage=0)
                if api._remoteex_readback(streak, command).lower() != "closed":
                    api._shutdown_once(lambda: api.tango_optics.write_parameter(api, streak, attribute, "Closed"), steps, attribute)
                api._wait_shutdown_readback(streak, lambda: api._remoteex_readback(streak, command).lower(),
                                        "closed", f"{attribute} closed")
                steps.append({"step": attribute, "status": "verified closed"})
            api._progress(steps, "Switching streak camera to Focus before HPD-TA exit and power-off", stage=0)
            streak.set_timeout_millis(30000)
            if api._remoteex_readback(streak, "DevParamGet(TD,Mode)").lower() != "focus":
                api._shutdown_once(lambda: streak.write_attribute("streak_mode", "Focus"), steps, "streak camera Focus")
            api._wait_shutdown_readback(streak, lambda: api._remoteex_readback(streak, "DevParamGet(TD,Mode)").lower(),
                                    "focus", "streak camera Focus")
            steps.append({"step": "Streak mode", "status": "verified Focus before shutdown"})
            streak.set_timeout_millis(30000)
            api._progress(steps, "Closing HPD-TA and waiting for application exit", stage=0)
            streak.command_inout("StopApplication")
            api._wait_shutdown_readback(streak, lambda: bool(api._value(streak, "application_running")),
                                    False, "HPD-TA closed")
            steps.append({"step": "HPD-TA", "status": "closed"})
        # This command refuses to stop RemoteEx while the HPD-TA process exists,
        # even when the Tango application flag is false.
        api._progress(steps, "Stopping RemoteEx and verifying SDK release", stage=0)
        streak.command_inout("StopRemoteEx")
        api._wait_shutdown_readback(streak, lambda: bool(api._value(streak, "connected")) or bool(api._value(streak, "application_running")),
                                False, "RemoteEx/HPD-TA stopped")
        steps.append({"step": "RemoteEx", "status": "stopped; SDK released"})
        if not application_running:
            steps.append({"step": "Streak mode", "status": "Focus unavailable; HPD-TA and RemoteEx verified stopped"})

    _shutdown_hpdta.__module__ = api.__name__
    _shutdown_hpdta.__qualname__ = "_shutdown_hpdta"

    def _shutdown_equipment(steps):
        api._progress(steps, "Confirming idle acquisition, closing shutters, verifying Focus and releasing SDK owners", stage=0)
        deadline = api.time.monotonic() + 600.0
        previous_phase = None
        while (phase := api._protocol_hardware_phase()) in {"preparing", "acquiring", "saving", "processing"}:
            if phase != previous_phase:
                api._progress(steps, f"Waiting for HIS {phase} to finish before shutdown; power retained", stage=0)
                previous_phase = phase
            if api.time.monotonic() >= deadline:
                raise RuntimeError(f"HIS measurement/save did not finish ({phase}); power retained")
            api.time.sleep(0.5)
        streak = api._wait_for_device(api.STREAK_DEVICE, timeout_s=5.0)
        api._shutdown_hpdta(streak, steps)

        # Deinitialize the SDK owner, not the Tango server process.
        starter = api._astor(api.KYMERA_DEVICE)
        if api.VD2_SERVERS[api.KYMERA_DEVICE] in set(starter.command_inout("DevGetRunningServers", True)):
            kymera = api._wait_for_device(api.KYMERA_DEVICE, timeout_s=2.0)
            if not api.VD2_CAMERA_ONLY:
                api._assert_kymera_passive_server(kymera)
            if str(kymera.state()).split(".")[-1].upper() != "OFF":
                if api.VD2_CAMERA_ONLY:
                    kymera.write_attribute("shutter", "Closed")
                    if str(api._value(kymera, "shutter")).lower() != "closed":
                        raise RuntimeError("Cannot confirm Kymera shutter closed; power retained")
                kymera.command_inout("turn_off")
            api._verify_kymera_sdk_released(kymera)
        steps.append({"step": "Kymera SDK ownership", "status": "released; Tango server retained"})

        errors, warnings = [], []
        vd2_pdu = None
        try:
            vd2_pdu = api._ensure_server(api.ZABER_PDU_DEVICE, steps)
            api._progress(steps, "Switching off VD2 flashlamp only; retaining Xe lamp cooling power on output 2")
            api._disable_pdu_outputs(vd2_pdu, steps, api.VD2_LAMP_SHUTDOWN_OUTPUTS, "VD2")
            xenon_power = dict(zip(api._value(vd2_pdu, "ids"), api._value(vd2_pdu, "states")))[2]
            steps.append({"step": "Xe lamp cooling supply (VD2 output 2)",
                          "status": "retained ON" if xenon_power == 1 else "already OFF; outlet unchanged",
                          "detail": "Switch the Xe lamp off manually; leave PDU power ON for cooling. Unprepare never switches this outlet off."})
            if xenon_power != 1:
                warnings.append("Xe lamp cooling outlet 2 was already OFF; Unprepare left it unchanged. Check the physical lamp switch and cooling before proceeding.")
        except Exception as exc:
            detail = f"VD2 lamp shutdown unverified: {exc}"
            errors.append(detail)
            steps.append({"step": "VD2 lamp supplies", "status": "failed", "detail": detail})
            api._progress(steps, "VD2 PDU/lamp shutdown failed; continuing independent shutdown checks")
        # Zaber is always-on: stop motion, but never change its outlet or stop its
        # device server. If the outlet was already OFF, leave it OFF, without restart.
        try:
            if vd2_pdu is None:
                raise RuntimeError("VD2 PDU unavailable; motor outlet cannot be verified")
            zaber_power = dict(zip(api._value(vd2_pdu, "ids"), api._value(vd2_pdu, "states")))
            if int(zaber_power.get(3, 1)) != 0:
                api._progress(steps, "Stopping Zaber motion; always-on motor power and device server retained")
                zaber = api._wait_for_device(api.ZABER_STAGE_DEVICE, timeout_s=2.0)
                zaber.set_timeout_millis(10000)
                zaber.command_inout("Stop")
                deadline = api.time.monotonic() + 10.0
                while str(zaber.state()).split(".")[-1] != "ON":
                    if api.time.monotonic() >= deadline:
                        raise RuntimeError("Zaber did not confirm motion stopped")
                    api.time.sleep(0.5)
                if not api.math.isfinite(float(api._value(zaber, "position_mm"))):
                    raise RuntimeError("Zaber position readback is invalid")
                steps.append({"step": "Zaber", "status": "stopped; power retained"})
            else:
                steps.append({"step": "Zaber", "status": "already unpowered; outlet unchanged"})
        except Exception as exc:
            detail = f"Zaber power retained: cannot confirm stopped motion: {exc}"
            steps.append({"step": "Zaber", "status": "failed", "detail": detail})
            errors.append(detail)

        api._progress(steps, "Verifying stopped VD2 stages; retaining shared OWIS supply", stage=1)
        # Stop only VD2's axis. The shared controller and every V0 outlet stay on.
        try:
            owis = api._wait_for_device(api.OWIS_SAMPLE_DEVICE, timeout_s=2.0)
            owis.set_timeout_millis(5000)
            result = owis.command_inout("stop_axis", api.OWIS_SAMPLE_AXIS)
            if str(result).strip() != "0":
                raise RuntimeError(str(result))
            if int(owis.command_inout("get_status_axis", api.OWIS_SAMPLE_AXIS)) not in {int(api.DevState.ON), int(api.DevState.OFF)}:
                raise RuntimeError("OWIS axis 2 did not confirm stopped motion")
            steps.append({"step": "OWIS sample axis 2", "status": "stopped; shared power retained"})
        except Exception as exc:
            detail = f"OWIS axis 2 could not be verified; shared controller power unchanged: {exc}"
            warnings.append(detail)
            steps.append({"step": "OWIS sample axis 2", "status": "unverified", "detail": detail})

        try:
            sd2_pdu = api._ensure_server(api.VD2_PDU_DEVICE, steps)
            api._progress(steps, "Switching off dedicated camera supply" if api.VD2_CAMERA_ONLY
                          else "Switching off verified dedicated trigger / camera supplies", stage=2)
            api._disable_vd2_power(sd2_pdu, steps)
        except Exception as exc:
            detail = f"SD2 trigger/camera shutdown unverified: {exc}"
            errors.append(detail)
            steps.append({"step": "SD2 supplies", "status": "failed", "detail": detail})
        steps.append({"step": "Retained supplies", "status": "Xe lamp cooling power, Zaber power, SD2 control supply and shared V0/OWIS outputs unchanged"})

        if errors:
            raise RuntimeError("; ".join(errors))
        message = ("VD2 lamp and camera supplies are OFF. DG645 power retained."
                   if api.VD2_CAMERA_ONLY else "VD2 flashlamp / camera / trigger supplies are OFF.")
        return {"steps": steps, "warnings": warnings,
                "message": message + " Xe lamp cooling supply and Zaber power retained."}

    _shutdown_equipment.__module__ = api.__name__
    _shutdown_equipment.__qualname__ = "_shutdown_equipment"

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

    _to_display_pixels.__module__ = api.__name__
    _to_display_pixels.__qualname__ = "_to_display_pixels"

    def _read_display_frame(proxy: DeviceProxy) -> Dict[str, Any]:
        """Read a frame through Tango so RemoteEx has exactly one owner."""
        frame = api.json.loads(proxy.command_inout("GetCurrentDisplayFrame"))
        pixels = api._to_display_pixels(
            api.base64.b64decode(frame["pixels_b64"]), int(frame["bytes_per_pixel"])
        )

        return {
            "width": int(frame["width"]),
            "height": int(frame["height"]),
            "data_type": frame["data_type"],
            "display_rescaled": int(frame["bytes_per_pixel"]) != 1,
            "pixels_b64": api.base64.b64encode(pixels).decode("ascii"),
            "minimum": min(pixels),
            "maximum": max(pixels),
        }

    _read_display_frame.__module__ = api.__name__
    _read_display_frame.__qualname__ = "_read_display_frame"

    def _missing_current_image_status(exc: Exception, commands) -> str | None:
        """Recognize only exact empty-image replies for the specified operations."""
        descriptions = [str(error.desc) for error in exc.args if hasattr(error, "desc")]
        lines = [line.strip() for description in descriptions or [str(exc)]
                 for line in description.splitlines()]
        for command in commands:
            source_status = f"7,{command.split('(', 1)[0]},No valid image"
            expected = (f"RemoteEx command failed for '{command}': {source_status}",
                        f"Invalid {command} readback: {source_status}")
            if any(line.endswith(expected) for line in lines):
                return source_status
        return None

    _missing_current_image_status.__module__ = api.__name__
    _missing_current_image_status.__qualname__ = "_missing_current_image_status"

    def _deferred_camera_state():
        return api.jsonify(success=True, state_deferred=True, device=api.STREAK_DEVICE,
                       acquisition_status="unknown", acquisition_mode=None,
                       attribute_errors={"acquisition_status": api._DEFERRED_ACQUISITION_READ})

    _deferred_camera_state.__module__ = api.__name__
    _deferred_camera_state.__qualname__ = "_deferred_camera_state"

    def _acquisition_snapshot(proxy, snapshot):
        snapshot["acquisition_status"] = "unknown"
        snapshot["acquisition_mode"] = None
        snapshot["cached_remoteex_status"] = snapshot["remoteex_status"]
        snapshot["remoteex_status"] = "unknown"
        try:
            phase, _, mode = api._remoteex_readback(proxy, "AcqStatus()").partition(",")
            phase = phase.lower()
            if phase not in {"idle", "busy"}:
                raise RuntimeError(f"Unknown acquisition status: {phase}")
            snapshot.update(acquisition_status=phase, acquisition_mode=mode or None,
                            remoteex_status=phase, application_running=True)
        except Exception as exc:
            snapshot["attribute_errors"]["acquisition_status"] = (
                api._DEFERRED_ACQUISITION_READ if api.camera_serialization_timeout(exc) else api._control_error(exc)
            )
        return snapshot

    _acquisition_snapshot.__module__ = api.__name__
    _acquisition_snapshot.__qualname__ = "_acquisition_snapshot"

    def _existing_local_remoteex_listener(proxy):
        """Read Windows listener ownership; do not open a second RemoteEx socket."""
        if api.os.name != "nt":
            return False
        properties = proxy.get_property(["host", "command_port"])
        host = (properties.get("host") or ["localhost"])[0]
        if str(host).lower() not in {"localhost", "127.0.0.1", "::1"}:
            return False
        port = int((properties.get("command_port") or [1001])[0])
        if not 1 <= port <= 65535:
            return False
        # Get-NetTCPConnection via a new PowerShell process can itself exceed the
        # reconnection timeout. Read the same Windows socket/owner table directly;
        # psutil is already pinned in the project's requirements.
        import psutil
        try:
            for connection in psutil.net_connections(kind="tcp"):
                if (connection.status == psutil.CONN_LISTEN and connection.laddr
                        and connection.laddr.port == port and connection.pid):
                    if psutil.Process(connection.pid).name().lower() in {"taremoteex.exe", "taremoteex"}:
                        return True
        except (psutil.Error, OSError) as exc:
            raise RuntimeError(f"Cannot verify local RemoteEx listener ownership: {exc}") from exc
        return False

    _existing_local_remoteex_listener.__module__ = api.__name__
    _existing_local_remoteex_listener.__qualname__ = "_existing_local_remoteex_listener"

    def refresh_connection():
        _, rejected = api._mutation_payload(set())
        if rejected is not None:
            return rejected
        blocked = api._approval_or_response(
            "connection.refresh", [api._target(api.STREAK_DEVICE, "StartRemoteEx"), api._target(api.STREAK_DEVICE, "ExecuteRaw")],
            {}, "vd2.connection.refresh", set(),
        )
        if blocked is not None:
            return blocked
        try:
            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                return api.jsonify(success=False, error="Wait for the HIS measurement before reconnecting"), 409
            proxy = api._proxy()
            if not bool(api._value(proxy, "connected")):
                if not api._existing_local_remoteex_listener(proxy):
                    return api.jsonify({"success": False, "error": "RemoteEx is not available. Use Prepare Experiment to start equipment."}), 409
                # Legacy command attaches first. Never invoke its cold-start path
                # unless an existing local TaRemoteEx listener was verified above.
                proxy.command_inout("StartRemoteEx")
            snapshot = api._acquisition_snapshot(proxy, api._snapshot(proxy))
            if snapshot["acquisition_status"] == "unknown":
                raise RuntimeError(snapshot["attribute_errors"]["acquisition_status"])
            return api.jsonify({"success": True, **snapshot})
        except Exception as exc:
            return api.jsonify({"success": False, "error": api._control_error(exc)}), 503

    refresh_connection.__module__ = api.__name__
    refresh_connection.__qualname__ = "refresh_connection"

    def state():
        if not api._preparation_lock.acquire(blocking=False):
            return api._deferred_camera_state()
        try:
            # The HIS worker owns the camera after the start request releases this
            # lock. Its protocol status is available without entering Tango.
            if api._protocol_hardware_phase() in {"preparing", "acquiring", "saving", "processing"}:
                return api._deferred_camera_state()
            proxy = api._proxy()
            snapshot = api._snapshot(proxy)
            snapshot["acquisition_status"] = "unknown"
            snapshot["acquisition_mode"] = None
            # Tango's legacy Status() cache can say idle during native Live.
            # Query only acquisition state, through the existing sole socket owner.
            if snapshot["connected"] and snapshot["remoteex_status"] not in {"starting", "preparing"}:
                snapshot = api._acquisition_snapshot(proxy, snapshot)
                if (snapshot.get("application_running") and snapshot.get("acquisition_status") in {"idle", "busy"}
                        and snapshot.get("acquisition_mode") in {None, "Live"}):
                    try:
                        view = "alignment" if api.request.headers.get("X-VD2-View") == "alignment" else "acquisition"
                        ui = {"tab": view}
                        if api.request.headers.get("X-Workspace-Browser") and api.request.headers.get("X-Workspace-Window"):
                            from vd2_workspace_api import workspace_repository, browser_identity
                            saved = workspace_repository().get(browser_identity(), api.request.headers["X-Workspace-Window"])
                            if saved:
                                ui["form"] = saved["settings"]
                        api._remember_camera(snapshot, "alignment" if view == "alignment" else "previous", ui)
                    except Exception as exc:
                        snapshot["recovery_warning"] = f"Camera return point was not saved: {exc}"
            return api.jsonify({"success": True, **snapshot})
        except Exception as exc:
            if api.camera_serialization_timeout(exc):
                return api._deferred_camera_state()
            return api.jsonify({"success": False, "error": str(exc), "device": api.STREAK_DEVICE}), 503
        finally:
            api._preparation_lock.release()

    state.__module__ = api.__name__
    state.__qualname__ = "state"

    return {
        "_start_vd2_optics": _start_vd2_optics,
        "_prepared_equipment_state": _prepared_equipment_state,
        "_deinitialize_experiment": _deinitialize_experiment,
        "_remoteex_readback": _remoteex_readback,
        "_apply_vd2_timing": _apply_vd2_timing,
        "_verify_vd2_timing_ready": _verify_vd2_timing_ready,
        "_shutdown_timed_out": _shutdown_timed_out,
        "_shutdown_once": _shutdown_once,
        "_shutdown_acquisition_phase": _shutdown_acquisition_phase,
        "_wait_shutdown_readback": _wait_shutdown_readback,
        "_shutdown_hpdta": _shutdown_hpdta,
        "_shutdown_equipment": _shutdown_equipment,
        "_to_display_pixels": _to_display_pixels,
        "_read_display_frame": _read_display_frame,
        "_missing_current_image_status": _missing_current_image_status,
        "_deferred_camera_state": _deferred_camera_state,
        "_acquisition_snapshot": _acquisition_snapshot,
        "_existing_local_remoteex_listener": _existing_local_remoteex_listener,
        "refresh_connection": refresh_connection,
        "state": state,
    }
