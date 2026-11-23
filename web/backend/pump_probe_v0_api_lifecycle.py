"""pump probe v0 api lifecycle operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    class V0PreparationFailure(RuntimeError):
        code = "v0_preparation_incomplete"

        def __init__(self, result):
            self.checks = list(result.get("checks", []))
            self.steps = [{**check, "step": check["label"],
                           "status": "verified" if check.get("ok") else "failed"}
                          for check in self.checks]
            super().__init__(result.get("recommendation") or result.get("message") or "V0 preparation incomplete")


    def _prepare_v0_experiment(steps=None):
        # Do not initialise shared controls while a live experiment owns them.
        import pump_probe_vd2_api as vd2
        with api._emulator._lock:
            if api._emulator._running or api._emulator._real_time or vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"}:
                raise RuntimeError("Acquisition is active; V0 preparation did not change hardware")
        if vd2.VD2_COORDINATOR_DEVICE:
            coordinator = api._tango_proxy(vd2.VD2_COORDINATOR_DEVICE, timeout_ms=3000)
            state = api.json.loads(coordinator.command_inout("GetState"))
            if state.get("state") == "RUNNING":
                raise RuntimeError("VD2 owns the DG645 clock; stop VD2 before preparing V0")
        result = api._emulator.hardware_preflight(fix=True, progress=steps)
        from v0_acquisition_preparation import prepare_acquisition

        # The full experiment now includes the CCD and a verified clock source.
        # Preserve the raw counter result in the lifecycle history, while the
        # synchronization check distinguishes absent ELYSE pulses from failure.
        acquisition_checks = prepare_acquisition(api, steps)
        checks = [check for check in result["checks"]
                  if check["label"] not in {"DG645 recall 8", "ELYSE pulse counter"}]
        checks.extend(acquisition_checks)
        result.update(checks=checks, success=all(check.get("ok") for check in checks),
                      dg645_timing_read_only=False, message="V0 preparation completed", recommendation="")
        if not result["success"]:
            result["recommendation"] = "V0 preparation incomplete: " + ", ".join(
                check["label"] for check in checks if not check.get("ok"))
        if not result["success"]:
            raise api.V0PreparationFailure(result)
        return {**result, "steps": [
            {**check, "step": check["label"], "status": "verified"} for check in result["checks"]]}


    def _serialized_v0_mutation(function):
        @api.wraps(function)
        def wrapped(*args, **kwargs):
            if not api.EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
                return api.jsonify({"success": False, "error": "Experiment preparation/shutdown is in progress; hardware commands are locked"}), 409
            try:
                return function(*args, **kwargs)
            finally:
                api.EXPERIMENT_MUTATION_LOCK.release()
        return wrapped


    def _v0_shutdown_vd2_status():
        import pump_probe_vd2_api as vd2
        streak = api._tango_proxy(vd2.STREAK_DEVICE, timeout_ms=2500)
        return {"application_running": bool(streak.read_attribute("application_running").value),
                "connected": bool(streak.read_attribute("connected").value),
                "protocol_active": vd2._measurement_protocol.status().get("status") in {"acquiring", "saving"},
                "lifecycle_active": vd2._lifecycle().snapshot().get("status") == "running"}


    def v0_uses_dg645(device):
        with api._emulator._lock:
            return (
                api._emulator._hardware_config.get("dg645_device", "").lower() == device.lower()
                and (api._emulator._tango_stop_event is not None or not api._emulator._tango_done_event.is_set()
                     or (api._emulator._control_mode_locked() == "tango" and (api._emulator._running or api._emulator._real_time)))
            )


    def _stop_v0_web_sequence():
        api._emulator.set_running(False)
        api._emulator.wait_for_tango_cleanup()
        api._emulator.set_real_time(False)


    def _v0_shutdown_authorization():
        targets = [{"device": api.V0_SHUTDOWN_CAMERA, "command": command}
                   for command in ("BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup")]
        targets.extend({"device": device, "command": "set_channels_states"}
                       for device in dict.fromkeys(item[0] for item in api.V0_SHUTDOWN_OUTPUT_PLAN))
        targets.extend({"device": api.V0_SHUTDOWN_STAGE, "command": command}
                       for command in ("move_axis", "stop_axis"))
        return targets, {"pdu_output_states": [{"device": device, "output_id": output, "state": 0}
                                               for device, output, _label in api.V0_SHUTDOWN_OUTPUT_PLAN],
                         "translation_stage_return": {"device": api.V0_SHUTDOWN_STAGE, "backend": api.V0_SHUTDOWN_STAGE_BACKEND,
                                                      "axis": api.V0_SHUTDOWN_STAGE_AXIS, "position_mm": 0.0,
                                                      "tolerance_mm": api.V0_SHUTDOWN_STAGE_TOLERANCE,
                                                      "timeout_s": api.V0_SHUTDOWN_STAGE_TIMEOUT,
                                                      "home_or_redefine": False},
                         "camera_warmup_minimum_c": 0, "camera_warmup_timeout_s": 900,
                         "preserve": "Elysium2/STANDA, shared OWIS power and other axes, all VD2 outlets, Xe cooling",
                         "block_if_vd2_active": True, "server_start_or_restart": False}


    def v0_lifecycle_state():
        return api.jsonify({"success": True, "job": api._v0_lifecycle().snapshot()})


    def v0_lifecycle_log():
        try:
            before = api.request.args.get("before", type=int)
            if before is not None and before < 1:
                raise ValueError("Invalid log cursor")
            return api.jsonify({"success": True, "events": api._v0_lifecycle().events(before=before)})
        except ValueError as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def v0_deinitialize():
        targets, args = api._v0_shutdown_authorization()
        blocked = api.require_http_hardware("deinitialize", targets, args, route_id="v0.deinitialize", wrapper_fields=set())
        if blocked is not None:
            return blocked
        lifecycle = api._v0_lifecycle()
        if not api.EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
            job = lifecycle.snapshot()
            if job.get("status") == "running" and job.get("operation") == "shutdown":
                return api.jsonify({"success": True, "job": job, "attached": True}), 202
            return api.jsonify({"success": False, "error": "Another experiment operation is active; shared power retained"}), 409
        try:
            job = lifecycle.start("shutdown", lambda steps: api.execute_v0_shutdown(
                api._tango_proxy, steps, api._stop_v0_web_sequence, api._v0_shutdown_vd2_status), api.EXPERIMENT_MUTATION_LOCK.release)
            return api.jsonify({"success": True, "job": job}), 202
        except Exception as exc:
            api.EXPERIMENT_MUTATION_LOCK.release()
            return api.jsonify({"success": False, "error": str(exc)}), 503

    api.V0PreparationFailure = V0PreparationFailure
    api._prepare_v0_experiment = _prepare_v0_experiment
    api._serialized_v0_mutation = _serialized_v0_mutation
    api._v0_shutdown_vd2_status = _v0_shutdown_vd2_status
    api.v0_uses_dg645 = v0_uses_dg645
    api._stop_v0_web_sequence = _stop_v0_web_sequence
    api._v0_shutdown_authorization = _v0_shutdown_authorization
    api.v0_lifecycle_state = v0_lifecycle_state
    api.v0_lifecycle_log = v0_lifecycle_log
    api.v0_deinitialize = v0_deinitialize
