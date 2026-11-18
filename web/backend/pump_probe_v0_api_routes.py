"""V0 experiment status, settings and operation endpoints."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def pump_probe_state():
        return api.jsonify(api._emulator.state(advance_active=True))


    def pump_probe_configure():
        payload = api.request.get_json(silent=True) or {}
        rejected = api._v0_reject_runtime_hardware_rewire(payload)
        if rejected is not None:
            return rejected
        return api.jsonify(api._emulator.configure(payload))


    def pump_probe_hardware_config():
        if api.request.method == "POST":
            payload = api.request.get_json(silent=True) or {}
            rejected = api._v0_reject_runtime_hardware_rewire(payload)
            if rejected is not None:
                return rejected
            return api.jsonify(api._emulator.configure(payload))
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
            payload = api.request.get_json(silent=True) or {}
            if api.authorization_required():
                return api.jsonify({
                    "success": False,
                    "error": "Hardware action is not authorized",
                    "code": "hardware_not_authorized",
                }), 403
            blocked = api._guard_v0_hardware("v0.initialize", payload)
            if blocked is not None:
                return blocked
            return api.jsonify(api._emulator.hardware_preflight(fix=True))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_run():
        payload = api.request.get_json(silent=True) or {}
        try:
            if api._v0_tango_active(payload) and bool(payload.get("running", True)):
                if api.authorization_required():
                    return api._v0_reject_unbound_tango_sequence()
                blocked = api._guard_v0_hardware("v0.run", api._v0_sequence_args(payload))
                if blocked is not None:
                    return blocked
            return api.jsonify(api._emulator.set_running(payload.get("running", True), payload))
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
    api.pump_probe_run = pump_probe_run
    api.pump_probe_realtime = pump_probe_realtime
    api.pump_probe_faraday = pump_probe_faraday
    api.pump_probe_stage_move = pump_probe_stage_move
    api.pump_probe_stage_stop = pump_probe_stage_stop
    api.pump_probe_sample_stage_move = pump_probe_sample_stage_move
    api.pump_probe_sample_stage_stop = pump_probe_sample_stage_stop
    api.pump_probe_crystal_move = pump_probe_crystal_move
    api.pump_probe_reset = pump_probe_reset
