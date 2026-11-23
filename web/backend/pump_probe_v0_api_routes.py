"""pump probe v0 api routes operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def pump_probe_state():
        return api.jsonify(api._emulator.state(advance_active=True))


    def pump_probe_configure():
        payload = api.request.get_json(silent=True)
        if not isinstance(payload, dict):
            return api.jsonify({"success": False, "error": "Scan configuration must be a JSON object"}), 400
        rejected = api._v0_reject_runtime_hardware_rewire(payload)
        if rejected is not None:
            return rejected
        try:
            return api.jsonify(api._emulator.configure(payload))
        except (ValueError, RuntimeError) as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_hardware_config():
        if api.request.method == "POST":
            payload = api.request.get_json(silent=True)
            if not isinstance(payload, dict):
                return api.jsonify({"success": False, "error": "Scan configuration must be a JSON object"}), 400
            rejected = api._v0_reject_runtime_hardware_rewire(payload)
            if rejected is not None:
                return rejected
            try:
                return api.jsonify(api._emulator.configure(payload))
            except (ValueError, RuntimeError) as exc:
                return api.jsonify({"success": False, "error": str(exc)}), 400
        return api.jsonify({
            "success": True,
            "hardware_config": api._emulator.hardware_config(),
        })


    def pump_probe_hardware_preflight():
        try:
            return api.jsonify(api._emulator.hardware_preflight(fix=False))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_hardware_initialize():
        try:
            if api.V0_PREPARATION_READ_ONLY:
                return api.jsonify({"success": False, "code": "v0_prepare_read_only", "read_only": True,
                                "error": "Prepare V0 is check-only; automatic server startup, recovery and power-on are disabled. Use /hardware/preflight."}), 409
            payload = api.request.get_json(silent=True)
            if payload is None and not api.request.get_data():
                payload = {}
            if not isinstance(payload, dict) or payload:
                return api.jsonify({"success": False, "error": "V0 preparation accepts no per-request hardware settings"}), 400
            if api.authorization_required():
                return api.jsonify({
                    "success": False,
                    "error": "Hardware action is not authorized",
                    "code": "hardware_not_authorized",
                }), 403
            blocked = api._guard_v0_hardware("v0.initialize", payload)
            if blocked is not None:
                return blocked
            lifecycle = api._v0_lifecycle()
            if not api.EXPERIMENT_MUTATION_LOCK.acquire(blocking=False):
                job = lifecycle.snapshot()
                if job.get("status") == "running" and job.get("operation") == "prepare":
                    return api.jsonify({"success": True, "job": job, "attached": True}), 202
                return api.jsonify({"success": False, "error": "Another experiment operation is active; shared equipment retained"}), 409
            if api.request.args.get("background") == "1":
                try:
                    job = lifecycle.start("prepare", api._prepare_v0_experiment, api.EXPERIMENT_MUTATION_LOCK.release)
                    return api.jsonify({"success": True, "job": job}), 202
                except Exception:
                    api.EXPERIMENT_MUTATION_LOCK.release()
                    raise
            try:
                return api.jsonify(api._prepare_v0_experiment())
            finally:
                api.EXPERIMENT_MUTATION_LOCK.release()
        except api.V0PreparationFailure as exc:
            return api.jsonify({"success": False, "error": str(exc), "checks": exc.checks, "steps": exc.steps}), 503
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_tango_plan():
        payload = api.request.get_json(silent=True) or {}
        try:
            if not isinstance(payload, dict):
                raise ValueError("Run request must be an object")
            plan = api._emulator.prepare_tango_run(payload, require_commissioned=False)
            return api.jsonify({"success": True, "plan": plan.to_dict(), "fingerprint": plan.fingerprint,
                            "commissioned": plan.profile["commissioned"], "diagnostic_dark": plan.profile.get("diagnostic_dark", False),
                            "authorization": {"route_id": "v0.run", "action": "v0.run", "method": "POST",
                                              "targets": plan.authorization_targets(), "args": plan.authorization_args()}})
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_andor_snapshot():
        """One authorized readback, with no acquisition/parameter/axis commands."""
        payload = api.request.get_json(silent=True)
        if (api.request.get_data(cache=True).strip() and not isinstance(payload, dict)) or (payload is not None and (set(payload) - {"diagnostic_dark"} or ("diagnostic_dark" in payload and type(payload["diagnostic_dark"]) is not bool))):
            return api.jsonify({"success": False, "error": "Snapshot request must be an empty object"}), 400
        diagnostic = bool((payload or {}).get("diagnostic_dark"))
        with api._emulator._lock:
            if (api._emulator._running or api._emulator._real_time or api._emulator._run_writer is not None
                    or api._emulator._tango_stop_event is not None or not api._emulator._tango_done_event.is_set()):
                return api.jsonify({"success": False, "error": "Wait for V0 acquisition and cleanup before sampling its configuration"}), 409
            config = api._emulator.hardware_config()
            if config["control_mode"] != "tango":
                return api.jsonify({"success": False, "error": "Select Tango mode before reading Andor configuration"}), 400
            device = config["andor_device"]
            args = {"andor_device": device, "readback": "V0Capabilities", "purpose": "BG_level_and_sampling_fingerprint"}
            if diagnostic:
                args["diagnostic_dark"] = True
            blocked = api.require_http_hardware("v0.andor-snapshot", [{"device": device, "command": "V0Capabilities"}], args,
                                            route_id="v0.andor-snapshot", wrapper_fields={"diagnostic_dark"} if diagnostic else set())
            if blocked is not None:
                return blocked
            try:
                response = api._tango_proxy(device, timeout_ms=2500).command_inout("V0Capabilities")
                def reject_constant(_value):
                    raise ValueError("Andor capability JSON must be finite")
                caps = api.json.loads(response, parse_constant=reject_constant)
                if not isinstance(caps, dict) or caps.get("schema") != "andor-v0-raw-order-v1":
                    raise ValueError("Andor does not expose the V0 RAW capability contract")
                snapshot = {"schema": "v0-andor-capability-snapshot-v1", "device": device,
                            "captured_at_utc": api.datetime.now(api.timezone.utc).isoformat(), "capabilities": caps}
                extra = {"diagnostic_snapshot_id": api.retain_snapshot(api._emulator, caps)} if diagnostic else {}
                return api.jsonify({"success": True, "snapshot": snapshot, **extra})
            except Exception as exc:
                return api.jsonify({"success": False, "error": str(exc)}), 503


    def pump_probe_run():
        payload = api.request.get_json(silent=True) or {}
        try:
            if not isinstance(payload, dict):
                raise ValueError("Run request must be an object")
            starting = payload.get("run_action") != "cancel" and bool(payload.get("running", True))
            if api._v0_tango_active(payload) and starting:
                fields = {"running", "run_action", "save_path", "sample_name", "plan_fingerprint", "diagnostic_dark", "diagnostic_snapshot_id"}
                if set(payload) - fields:
                    raise ValueError("Unknown Tango run request field")
                with api._emulator._lock:
                    plan = api._emulator.prepare_tango_run(payload)
                    if payload.get("plan_fingerprint", plan.fingerprint) != plan.fingerprint:
                        return api.jsonify({"success": False, "error": "Tango run plan changed; refresh its preview",
                                        "code": "v0_run_plan_stale"}), 409
                    blocked = api.require_http_hardware("v0.run", plan.authorization_targets(), plan.authorization_args(),
                                                    route_id="v0.run", wrapper_fields=fields)
                    if blocked is not None:
                        return blocked
                    return api.jsonify(api._emulator.set_running(True, payload, tango_plan=plan))
            return api.jsonify(api._emulator.set_running(payload.get("running", True), payload))
        except api.TangoProfileNotCommissioned as exc:
            return api.jsonify({"success": False, "error": str(exc), "code": "hardware_not_authorized"}), (403 if api.authorization_required() else 409)
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_realtime():
        payload = api.request.get_json(silent=True) or {}
        if api._v0_tango_active(payload) and bool(payload.get("enabled", True)):
            if api.authorization_required():
                return api._v0_reject_unbound_tango_sequence()
            blocked = api._guard_v0_hardware("v0.realtime", api._v0_sequence_args(payload, realtime=True))
            if blocked is not None:
                return blocked
        return api.jsonify(api._emulator.set_real_time(payload.get("enabled", True)))


    def pump_probe_faraday():
        payload = api.request.get_json(silent=True) or {}
        return api.jsonify(api._emulator.set_faraday(payload.get("closed", True)))


    def pump_probe_stage_move():
        try:
            payload = api.request.get_json(silent=True) or {}
            if api._v0_tango_active(payload):
                normalized = api._v0_stage_move_args(payload)
                blocked = api._guard_v0_hardware("v0.stage-move", normalized)
                if blocked is not None:
                    return blocked
                return api.jsonify(api._emulator.move_stage({"position_mm": normalized["position_mm"]}))
            return api.jsonify(api._emulator.move_stage(payload))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_stage_stop():
        try:
            if api._v0_tango_active():
                blocked = api._guard_v0_hardware("v0.stage-stop", api._v0_stage_stop_args())
                if blocked is not None:
                    return blocked
            return api.jsonify(api._emulator.stop_stage())
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_sample_stage_move():
        try:
            payload = api.request.get_json(silent=True) or {}
            if api._v0_tango_active(payload):
                normalized = api._v0_stage_move_args(payload, sample_stage=True)
                blocked = api._guard_v0_hardware("v0.sample-stage-move", normalized)
                if blocked is not None:
                    return blocked
                return api.jsonify(api._emulator.move_sample_stage({"position_mm": normalized["position_mm"]}))
            return api.jsonify(api._emulator.move_sample_stage(payload))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_sample_stage_stop():
        try:
            if api._v0_tango_active():
                blocked = api._guard_v0_hardware("v0.sample-stage-stop", api._v0_stage_stop_args(sample_stage=True))
                if blocked is not None:
                    return blocked
            return api.jsonify(api._emulator.stop_sample_stage())
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_crystal_move():
        return api.jsonify(api._emulator.move_crystal())


    def pump_probe_reset():
        return api.jsonify(api._emulator.reset())

    api.pump_probe_state = pump_probe_state
    api.pump_probe_configure = pump_probe_configure
    api.pump_probe_hardware_config = pump_probe_hardware_config
    api.pump_probe_hardware_preflight = pump_probe_hardware_preflight
    api.pump_probe_hardware_initialize = pump_probe_hardware_initialize
    api.pump_probe_tango_plan = pump_probe_tango_plan
    api.pump_probe_andor_snapshot = pump_probe_andor_snapshot
    api.pump_probe_run = pump_probe_run
    api.pump_probe_realtime = pump_probe_realtime
    api.pump_probe_faraday = pump_probe_faraday
    api.pump_probe_stage_move = pump_probe_stage_move
    api.pump_probe_stage_stop = pump_probe_stage_stop
    api.pump_probe_sample_stage_move = pump_probe_sample_stage_move
    api.pump_probe_sample_stage_stop = pump_probe_sample_stage_stop
    api.pump_probe_crystal_move = pump_probe_crystal_move
    api.pump_probe_reset = pump_probe_reset
