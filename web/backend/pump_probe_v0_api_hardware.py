"""V0 Tango access, recovery and hardware authorization targets."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _clamp(value, low, high):
        return max(low, min(high, value))


    def _clean_control_mode(value):
        mode = str(value or "emulator").strip().lower()
        return mode if mode in {"emulator", "tango"} else "emulator"


    def _parse_tango_dict(value):
        import ast

        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = ast.literal_eval(str(value))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


    def _tango_proxy(device_name, timeout_ms=3000):
        import tango

        proxy = tango.DeviceProxy(str(device_name))
        proxy.set_timeout_millis(int(timeout_ms))
        return proxy


    def _numeric_list(value):
        try:
            return [float(part.strip()) for part in str(value).split(",")]
        except ValueError:
            return None


    def _values_match(expected, actual, tolerance=1e-9):
        expected_numbers = api._numeric_list(expected)
        actual_numbers = api._numeric_list(actual)
        if expected_numbers is not None and actual_numbers is not None:
            if len(expected_numbers) != len(actual_numbers):
                return False
            return all(abs(left - right) <= tolerance for left, right in zip(expected_numbers, actual_numbers))
        return str(expected).strip() == str(actual).strip()


    def _load_dg645_recall_config(config_path):
        path = api.Path(str(config_path or api.DEFAULT_DG645_RECALL_CONFIG)).expanduser()
        with open(path, "r", encoding="utf-8") as handle:
            return api.json.load(handle)


    def _json_ok(label, detail=None, **extra):
        return {"label": label, "ok": True, "detail": detail or "OK", **extra}


    def _json_fail(label, detail, **extra):
        return {"label": label, "ok": False, "detail": str(detail), **extra}


    def _server_name_for_device(device_name):
        import tango

        db = tango.Database()
        info = db.get_device_info(str(device_name))
        server_name = getattr(info, "ds_full_name", None) or getattr(info, "server", None)
        if not server_name:
            raise RuntimeError(f"Could not resolve server for {device_name}")
        return str(server_name)


    def _starter_devices():
        import tango

        db = tango.Database()
        return [str(name) for name in db.get_device_exported("*") if str(name).startswith("tango/admin/")]


    def _starter_for_server(server_name):
        for starter_name in api._starter_devices():
            try:
                starter = api._tango_proxy(starter_name, timeout_ms=5000)
                running = set(starter.command_inout("DevGetRunningServers", False))
                stopped = set(starter.command_inout("DevGetStopServers", False))
                if server_name in running or server_name in stopped:
                    return starter_name, starter, running, stopped
            except Exception:
                continue
        raise RuntimeError(f"No Starter manages server {server_name}")


    def _restart_server_for_device(device_name):
        server_name = api._server_name_for_device(device_name)
        starter_name, starter, running, _stopped = api._starter_for_server(server_name)
        if server_name in running:
            try:
                starter.command_inout("DevStop", server_name)
                api.time.sleep(2)
            except Exception:
                try:
                    starter.command_inout("HardKillServer", server_name)
                    api.time.sleep(2)
                except Exception:
                    pass
        try:
            starter.command_inout("DevStart", server_name)
        except Exception as exc:
            text = str(exc).lower()
            if "already_running" not in text and "already running" not in text:
                raise
        api.time.sleep(2)
        return {"server": server_name, "starter": starter_name}


    def _v0_hardware_config(payload=None):
        config = api._emulator.hardware_config()
        payload = payload or {}
        requested = payload.get("hardware_config") if isinstance(payload, dict) else None
        if isinstance(requested, dict):
            config = {**config, **{key: value for key, value in requested.items() if key in api.DEFAULT_HARDWARE_CONFIG}}
        if isinstance(payload, dict) and "control_mode" in payload:
            config["control_mode"] = payload["control_mode"]
        return config


    def _v0_reject_runtime_hardware_rewire(payload):
        """Production/local-auth policy owns physical V0 topology, not requests."""
        if not api.authorization_required() or not isinstance(payload, dict):
            return None
        raw_config = payload.get("hardware_config")
        if raw_config is None:
            return None
        if not isinstance(raw_config, dict) or set(raw_config) - {"control_mode"}:
            return api.jsonify({
                "success": False,
                "error": "Hardware configuration rewiring is not authorized",
                "code": "hardware_not_authorized",
            }), 403
        return None


    def _v0_tango_active(payload=None):
        current = api._clean_control_mode(api._emulator.hardware_config().get("control_mode"))
        requested = api._clean_control_mode(api._v0_hardware_config(payload).get("control_mode"))
        return current == "tango" or requested == "tango"


    def _v0_reject_unbound_tango_sequence():
        """Fail closed until V0 can bind its complete runtime plan to approval."""
        return api.jsonify({
            "success": False,
            "error": "A precomputed exact hardware plan is required",
            "code": "hardware_not_authorized",
        }), 403


    def _v0_targets(config, action):
        aggregator = str(config["owis_aggregator_device"])
        backend = str(config["owis_backend_device"])
        andor = str(config["andor_device"])
        dg645 = str(config["dg645_device"])
        daqmx = str(config["daqmx_device"])
        if action == "v0.initialize":
            targets = [
                {"device": backend, "command": "get_status_axis"},
                {"device": backend, "command": "read_position_axis"},
                {"device": backend, "command": "turn_on_axis"},
                {"device": dg645, "command": "scpi_write"},
                {"device": dg645, "command": "scpi_query"},
                {"device": daqmx, "command": "read_counter"},
            ]
            for output in api.REQUIRED_NETIO_OUTPUTS:
                targets.append({"device": str(output["device"]), "command": "set_channels_states"})
            return targets
        if action in {"v0.stage-move", "v0.sample-stage-move"}:
            return [{"device": aggregator, "command": "move_axis"}]
        if action in {"v0.stage-stop", "v0.sample-stage-stop"}:
            return [{"device": aggregator, "command": "stop_axis"}]
        if action == "v0.run":
            return [
                {"device": dg645, "command": "scpi_write"},
                {"device": dg645, "command": "scpi_query"},
                {"device": andor, "command": "start_grabbing"},
                {"device": andor, "command": "register_order"},
                {"device": andor, "command": "is_order_ready"},
                {"device": andor, "command": "give_order"},
            ]
        if action == "v0.realtime":
            return [
                {"device": andor, "command": "start_grabbing"},
                {"device": andor, "command": "register_order"},
                {"device": andor, "command": "is_order_ready"},
                {"device": andor, "command": "give_order"},
            ]
        raise ValueError(f"Unsupported V0 hardware action: {action}")


    def _guard_v0_hardware(action, payload):
        config = api._v0_hardware_config(payload)
        return api.require_http_hardware(action, api._v0_targets(config, action), payload, route_id=action)


    def _v0_stage_move_args(payload, *, sample_stage=False):
        with api._emulator._lock:
            config = api._emulator.hardware_config()
            if sample_stage:
                position = api._clamp(float(payload.get("position_mm", api._emulator._sample_set_position_mm)), 0.0, 150.0)
                axis = int(config["sample_stage_axis"])
            else:
                position = api._emulator._set_position_mm
                if "position_mm" in payload:
                    position = float(payload["position_mm"])
                elif "delta_ps" in payload:
                    position -= float(payload["delta_ps"]) * api.MM_PER_PS
                elif "delta_mm" in payload:
                    position += float(payload["delta_mm"])
                position = api._clamp(position, api.STAGE_MIN_MM, api.STAGE_MAX_MM)
                axis = int(config["delay_line_axis"])
        return {"axis": axis, "position_mm": float(position)}


    def _v0_stage_stop_args(*, sample_stage=False):
        config = api._emulator.hardware_config()
        axis_name = "sample_stage_axis" if sample_stage else "delay_line_axis"
        return {"axis": int(config[axis_name])}


    def _v0_sequence_args(payload, *, realtime=False):
        config = api._v0_hardware_config(payload)
        recall = api._load_dg645_recall_config(config.get("dg645_recall_config"))
        args = {
            "spectrometer_burst": int(api.SPECTROMETER_BURST),
            "order_token": "device_generated",
        }
        if not realtime:
            args.update({
                "dg645_preflight_policy": str(config.get("dg645_preflight_policy") or "apply_recall_then_verify").strip().lower(),
                "dg645_recall_slot": int(recall.get("recall_slot", 8)),
            })
        return args

    api._clamp = _clamp
    api._clean_control_mode = _clean_control_mode
    api._parse_tango_dict = _parse_tango_dict
    api._tango_proxy = _tango_proxy
    api._numeric_list = _numeric_list
    api._values_match = _values_match
    api._load_dg645_recall_config = _load_dg645_recall_config
    api._json_ok = _json_ok
    api._json_fail = _json_fail
    api._server_name_for_device = _server_name_for_device
    api._starter_devices = _starter_devices
    api._starter_for_server = _starter_for_server
    api._restart_server_for_device = _restart_server_for_device
    api._v0_hardware_config = _v0_hardware_config
    api._v0_reject_runtime_hardware_rewire = _v0_reject_runtime_hardware_rewire
    api._v0_tango_active = _v0_tango_active
    api._v0_reject_unbound_tango_sequence = _v0_reject_unbound_tango_sequence
    api._v0_targets = _v0_targets
    api._guard_v0_hardware = _guard_v0_hardware
    api._v0_stage_move_args = _v0_stage_move_args
    api._v0_stage_stop_args = _v0_stage_stop_args
    api._v0_sequence_args = _v0_sequence_args
