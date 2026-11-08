"""Implementation for _build_psp_series and related operations."""


def _bind_device_api_parts_build_psp_series(api):
    """Bind implementation to the owning module and its runtime state."""

    def _build_psp_series(history):
        channel_series = {}
        latest_by_channel = {}

        for item in history:
            channel = str(item.get("channel", "")).strip()
            if not channel:
                continue

            recv_ts = api._to_float_or_none(item.get("recv_ts"))
            source_ts = api._to_float_or_none(item.get("source_ts"))
            ts = recv_ts if recv_ts is not None else source_ts
            if ts is None:
                continue

            value = api._to_float_or_none(item.get("value"))
            if value is None:
                continue

            point = {
                "ts": ts,
                "recv_ts": recv_ts,
                "source_ts": source_ts,
                "value": value,
                "id": item.get("id"),
            }
            channel_series.setdefault(channel, []).append(point)
            latest_by_channel[channel] = {
                "value": value,
                "ts": ts,
                "recv_ts": recv_ts,
                "source_ts": source_ts,
                "id": item.get("id"),
            }

        for points in channel_series.values():
            points.sort(key=lambda point: point["ts"])

        return channel_series, latest_by_channel

    _build_psp_series.__module__ = api.__name__
    _build_psp_series.__qualname__ = "_build_psp_series"

    def _read_psp_group_history(device, group_name, seconds, limit):
        group = api._normalize_psp_group(group_name)
        commands = api._list_device_commands_lower(device)
        history_raw = []

        get_group_cmd = commands.get("get_group_history_json")
        if get_group_cmd:
            query = f"{group}|{max(0.0, float(seconds))}|{max(0, int(limit))}"
            raw = device.command_inout(get_group_cmd, query)
            payload = api._safe_json_loads(raw, default={})
            if isinstance(payload, dict):
                history_raw = payload.get("history", [])
            elif isinstance(payload, list):
                history_raw = payload

        if not history_raw:
            get_history_cmd = commands.get("get_history_json")
            if get_history_cmd:
                raw = device.command_inout(get_history_cmd, max(0.0, float(seconds)))
                payload = api._safe_json_loads(raw, default=[])
                if isinstance(payload, list):
                    history_raw = payload

        normalized = [api._normalize_psp_entry(item) for item in history_raw]
        normalized = [item for item in normalized if item.get("group") == group]
        if limit > 0:
            normalized = normalized[-int(limit) :]
        return normalized

    _read_psp_group_history.__module__ = api.__name__
    _read_psp_group_history.__qualname__ = "_read_psp_group_history"

    def _write_daqmx_channel(device, channel, value, command_variant=None):
        """
    Attempt to write DAQmx/PSP variable using any supported command signature.
    Raises Exception when no supported write command is found.
    """
        commands = api._list_device_commands_lower(device)
        channel = str(channel)
        scalar_value = api._to_scalar_value(value)

        json_payload_name_value = api.json.dumps({"name": channel, "value": scalar_value})
        json_payload_channel_value = api.json.dumps({"channel": channel, "value": scalar_value})
        eq_payload = f"{channel}={scalar_value}"

        if command_variant is not None:
            if command_variant not in api._DAQMX_WRITE_COMMANDS:
                raise ValueError("Unsupported write command")
            command_name = command_variant
            if command_variant == "write_variable_json":
                return device.command_inout(command_name, json_payload_name_value)
            if command_variant == "set_variable_value_json":
                return device.command_inout(command_name, json_payload_name_value)
            if command_variant == "set_channel_value_json":
                return device.command_inout(command_name, json_payload_channel_value)
            if command_variant in {"write_digital_output", "write_channel"}:
                return device.command_inout(command_name, [channel, str(scalar_value)])
            if command_variant == "write_variable":
                return device.command_inout(command_name, [channel, scalar_value])
            if command_variant == "set_variable_value":
                return device.command_inout(command_name, [channel, scalar_value])
            return device.command_inout(command_name, [channel, scalar_value])

        if "write_variable_json" in commands:
            return device.command_inout(commands["write_variable_json"], json_payload_name_value)
        if "set_variable_value_json" in commands:
            return device.command_inout(commands["set_variable_value_json"], json_payload_name_value)
        if "set_channel_value_json" in commands:
            return device.command_inout(commands["set_channel_value_json"], json_payload_channel_value)

        if "write_variable" in commands:
            cmd = commands["write_variable"]
            try:
                return device.command_inout(cmd, [channel, scalar_value])
            except Exception:
                return device.command_inout(cmd, json_payload_name_value)

        if "set_variable_value" in commands:
            cmd = commands["set_variable_value"]
            try:
                return device.command_inout(cmd, [channel, scalar_value])
            except Exception:
                return device.command_inout(cmd, eq_payload)

        if "set_channel_value" in commands:
            cmd = commands["set_channel_value"]
            try:
                return device.command_inout(cmd, [channel, scalar_value])
            except Exception:
                return device.command_inout(cmd, eq_payload)

        for direct_command in ("write_digital_output", "write_channel"):
            if direct_command in commands:
                return device.command_inout(
                    commands[direct_command], [channel, str(scalar_value)]
                )

        raise Exception(
            "Device does not expose a supported write command "
            "(expected one of: write_variable*, set_variable_value*, set_channel_value*)"
        )

    _write_daqmx_channel.__module__ = api.__name__
    _write_daqmx_channel.__qualname__ = "_write_daqmx_channel"

    def _env_bool(name, default=False):
        value = api.os.environ.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

    _env_bool.__module__ = api.__name__
    _env_bool.__qualname__ = "_env_bool"

    def _query_bool(name, default=False):
        value = api.request.args.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

    _query_bool.__module__ = api.__name__
    _query_bool.__qualname__ = "_query_bool"

    def _maybe_require_auth():
        if api._env_bool("PYCONLYSE_PRODUCTION", False) or api._env_bool(
            "PYCONLYSE_ENFORCE_DEVICE_AUTH", False
        ):
            api.verify_jwt_in_request()

    _maybe_require_auth.__module__ = api.__name__
    _maybe_require_auth.__qualname__ = "_maybe_require_auth"

    def _hardware_payload():
        """Return the JSON object used for an authorized hardware mutation."""
        data = api.request.get_json(silent=True)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return None
        return data

    _hardware_payload.__module__ = api.__name__
    _hardware_payload.__qualname__ = "_hardware_payload"

    def _mutation_payload(required=()):
        data = api._hardware_payload()
        if data is None or not data:
            return None
        if any(name not in data for name in required):
            return None
        return data

    _mutation_payload.__module__ = api.__name__
    _mutation_payload.__qualname__ = "_mutation_payload"

    def _finite_number(value):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if api.math.isfinite(number) else None

    _finite_number.__module__ = api.__name__
    _finite_number.__qualname__ = "_finite_number"

    def _invalid_psp_acknowledgement():
        if api.authorization_required():
            return api.jsonify({
                'error': 'Hardware request is invalid',
                'success': False,
                'code': 'hardware_approval_invalid',
            }), 409
        return api.jsonify({'error': 'Acknowledgment payload is invalid', 'success': False}), 400

    _invalid_psp_acknowledgement.__module__ = api.__name__
    _invalid_psp_acknowledgement.__qualname__ = "_invalid_psp_acknowledgement"

    def _command_variant(data, candidates):
        """Require one exact branch before authorization in an enforced mode."""
        selected = data.get('command_variant')
        if api.authorization_required():
            if not isinstance(selected, str) or selected not in candidates:
                return None
            return selected
        if selected is not None and (not isinstance(selected, str) or selected not in candidates):
            return None
        return selected

    _command_variant.__module__ = api.__name__
    _command_variant.__qualname__ = "_command_variant"

    def _parameter_write_plan(data):
        names = sorted(data)
        return (
            [{'name': name, 'value': data[name]} for name in names],
            names,
        )

    _parameter_write_plan.__module__ = api.__name__
    _parameter_write_plan.__qualname__ = "_parameter_write_plan"

    def debug_monitor_device(device_name):
        """Expose a passive GET status and explicitly start monitoring by POST."""
        try:
            if api.request.method == 'GET':
                return api.jsonify({
                    'device': device_name,
                    'monitoring': False,
                    'message': 'Use POST to start debug monitoring',
                    'success': True,
                })
            from websocket_handler import monitor
            monitor.monitor_device(device_name, "debug_room")
            return api.jsonify({
                'message': f'Manual monitoring triggered for {device_name}',
                'success': True
            })
        except Exception as e:
            return api.jsonify({
                'error': str(e),
                'success': False
            }), 500

    debug_monitor_device.__module__ = api.__name__
    debug_monitor_device.__qualname__ = "debug_monitor_device"

    def _device_proxy_target(device_name):
        name = str(device_name)
        if name.startswith("tango://"):
            return name
        tango_host = api.os.environ.get("TANGO_HOST", "").strip()
        return f"tango://{tango_host}/{name}" if tango_host else name

    _device_proxy_target.__module__ = api.__name__
    _device_proxy_target.__qualname__ = "_device_proxy_target"

    class DeviceManager:
        """Manages Tango device connections and operations"""

        @staticmethod
        def get_device(device_name):
            """Get or create device proxy with caching"""
            with api.device_cache_lock:
                if device_name not in api.device_cache:
                    try:
                        api.device_cache[device_name] = api.tango_gateway.create_device_proxy(
                            api._device_proxy_target(device_name)
                        )
                    except Exception as e:
                        raise Exception(f"Could not connect to device {device_name}: {str(e)}")
                return api.device_cache[device_name]

        @staticmethod
        def discard_device(device_name):
            """Forget a proxy whose CORBA connection became stale."""
            with api.device_cache_lock:
                api.device_cache.pop(device_name, None)

        @staticmethod
        def operation_lock(device_name):
            """Serialize calls for one Tango proxy; DeviceProxy is not request-thread safe."""
            with api.device_cache_lock:
                return api.device_operation_locks.setdefault(device_name, api.threading.RLock())

        @staticmethod
        def get_device_summary(device_name):
            device = api.DeviceManager.get_device(device_name)
            device_info = device.info()
            return {
                'name': device_name,
                'state': str(device.state()),
                'status': device.status(),
                'info': getattr(device_info, 'dev_class', ''),
                'server': getattr(device_info, 'server_id', ''),
                'connected': True,
                'timestamp': api.datetime.now().isoformat()
            }

        @staticmethod
        def get_device_properties(device_name):
            properties = {}
            db = api.tango_gateway.create_database()
            prop_list = db.get_device_property_list(device_name, '*')
            for prop_name in prop_list:
                try:
                    prop_values = db.get_device_property(device_name, prop_name)
                    properties[prop_name] = api.make_json_safe(prop_values.get(prop_name, []))
                except Exception as e:
                    properties[prop_name] = {'error': str(e)}
            return properties

        @staticmethod
        def get_device_attributes(device):
            attributes = {}
            attr_list = device.get_attribute_list()
            for attr_name in attr_list:
                try:
                    attr = device.read_attribute(attr_name)
                    attr_config = device.get_attribute_config(attr_name)
                    value = attr.value if hasattr(attr, 'value') else None
                    attributes[attr_name] = {
                        'value': api.make_json_safe(value),
                        'quality': str(attr.quality),
                        'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                        'writable': attr_config.writable != api.tango.AttrWriteType.READ,
                        'data_type': str(attr_config.data_type),
                        'unit': attr_config.unit if hasattr(attr_config, 'unit') else '',
                        'description': attr_config.description if hasattr(attr_config, 'description') else ''
                    }
                except Exception as e:
                    attributes[attr_name] = {'error': str(e)}
            return attributes

        @staticmethod
        def get_device_commands(device):
            commands = {}
            cmd_list = device.get_command_list()
            for cmd_name in cmd_list:
                try:
                    cmd_config = device.get_command_config(cmd_name)
                    commands[cmd_name] = {
                        'in_type': str(cmd_config.in_type),
                        'out_type': str(cmd_config.out_type),
                        'in_type_desc': cmd_config.in_type_desc,
                        'out_type_desc': cmd_config.out_type_desc
                    }
                except Exception as e:
                    commands[cmd_name] = {'error': str(e)}
            return commands

    DeviceManager.__module__ = api.__name__
    DeviceManager.__qualname__ = "DeviceManager"

    def _read_device_snapshot(device_name, server_name, dev_class):
        """Read one device through the existing cache and reconnect retry contract."""
        def read_state_and_info():
            device = api.DeviceManager.get_device(device_name)
            current_state = str(device.state())
            current_server = server_name
            current_class = dev_class
            if not current_server or not current_class:
                info = device.info()
                current_server = current_server or getattr(info, "server_id", None)
                current_class = current_class or getattr(info, "dev_class", None)
            return current_state, current_server, current_class

        return api._with_device_retry(device_name, read_state_and_info)

    _read_device_snapshot.__module__ = api.__name__
    _read_device_snapshot.__qualname__ = "_read_device_snapshot"

    def _get_starter_devices():
        db = api.tango_gateway.create_database()
        devices = list(db.get_device_exported("*"))
        return [device_name for device_name in devices if str(device_name).startswith("tango/admin/")]

    _get_starter_devices.__module__ = api.__name__
    _get_starter_devices.__qualname__ = "_get_starter_devices"

    def _get_starter_server_lists(starter_name):
        starter = api.tango_gateway.create_device_proxy(starter_name)
        # True includes every server managed by this Starter, not only controlled ones.
        running = set(starter.command_inout('DevGetRunningServers', True))
        stopped = set(starter.command_inout('DevGetStopServers', True))
        return starter, running, stopped

    _get_starter_server_lists.__module__ = api.__name__
    _get_starter_server_lists.__qualname__ = "_get_starter_server_lists"

    def _wait_for_starter_server(starter_name, server_name, timeout_s=12.0):
        """Wait until Starter reports a server as running after a control command."""
        deadline = api.time.monotonic() + max(0.0, float(timeout_s))
        while True:
            _, running, stopped = api._get_starter_server_lists(starter_name)
            if server_name in running or api.time.monotonic() >= deadline:
                return running, stopped
            api.time.sleep(0.5)

    _wait_for_starter_server.__module__ = api.__name__
    _wait_for_starter_server.__qualname__ = "_wait_for_starter_server"

    def _find_starter_for_server(server_name, allow_db_host_fallback=False):
        for starter_name in api._get_starter_devices():
            try:
                starter, running, stopped = api._get_starter_server_lists(starter_name)
            except Exception:
                continue
            if server_name in running or server_name in stopped:
                return starter_name, starter, running, stopped

        if allow_db_host_fallback:
            try:
                server_info = api.tango_gateway.create_database().get_server_info(server_name)
                host = str(getattr(server_info, "host", "")).strip().lower()
                if host:
                    short_host = host.split(".", 1)[0]
                    starter_name = next(
                        (
                            str(candidate)
                            for candidate in api._get_starter_devices()
                            if str(candidate).rsplit("/", 1)[-1].lower()
                            in {host, short_host}
                        ),
                        f"tango/admin/{short_host}",
                    )
                    starter, running, stopped = api._get_starter_server_lists(starter_name)
                    return starter_name, starter, running, stopped
            except Exception:
                pass

        raise Exception(f"No Starter manages server {server_name}")

    _find_starter_for_server.__module__ = api.__name__
    _find_starter_for_server.__qualname__ = "_find_starter_for_server"

    def _resolve_server_name(device_name):
        db = api.tango_gateway.create_database()
        try:
            return api.DeviceManager.get_device(device_name).info().server_id
        except Exception:
            info = db.get_device_info(device_name)
            server_name = getattr(info, 'ds_full_name', None) or getattr(info, 'server', None)
            if not server_name:
                raise Exception(f"Could not resolve server for device {device_name}")
        return str(server_name)

    _resolve_server_name.__module__ = api.__name__
    _resolve_server_name.__qualname__ = "_resolve_server_name"

    def _tail_log_text(value, line_limit=240, char_limit=60000):
        """Bound a Starter log response before returning it to a browser client."""
        text = str(value or "").replace("\r\n", "\n")
        truncated = len(text) > char_limit
        if truncated:
            text = text[-char_limit:]

        lines = text.splitlines()
        if len(lines) > line_limit:
            truncated = True
            lines = lines[-line_limit:]
        return "\n".join(lines), truncated

    _tail_log_text.__module__ = api.__name__
    _tail_log_text.__qualname__ = "_tail_log_text"

    def _read_starter_log(starter, log_name):
        """Read a log captured by Tango Starter without making any equipment call."""
        try:
            text, truncated = api._tail_log_text(starter.command_inout("DevReadLog", log_name))
            return {
                "available": True,
                "text": text,
                "truncated": truncated,
                "error": "",
            }
        except Exception as exc:
            return {
                "available": False,
                "text": "",
                "truncated": False,
                "error": str(exc),
            }

    _read_starter_log.__module__ = api.__name__
    _read_starter_log.__qualname__ = "_read_starter_log"

    def _read_device_diagnostics(device_name):
        """Return state, status, and common server-reported error attributes."""
        result = {
            "name": device_name,
            "available": False,
            "state": "UNREACHABLE",
            "status": "",
            "error_attributes": {},
            "error": "",
        }
        try:
            def read_diagnostics():
                device = api.DeviceManager.get_device(device_name)
                try:
                    attr_names = {str(name).lower(): str(name) for name in device.get_attribute_list()}
                except Exception:
                    attr_names = {}

                error_attributes = {}
                for candidate in (
                    "last_error",
                    "error",
                    "error_message",
                    "fault_recovery_status",
                    "connection_status",
                    "controller_connection_status",
                    "power_dependency_status",
                    "hardware_connection_state",
                    "initialization_state",
                    "hardware_lifecycle_status",
                ):
                    attr_name = attr_names.get(candidate)
                    if not attr_name:
                        continue
                    try:
                        value = api.make_json_safe(device.read_attribute(attr_name).value)
                    except Exception as exc:
                        value = {"error": str(exc)}
                    error_attributes[attr_name] = value
                return str(device.state()), str(device.status()), error_attributes

            state, status, error_attributes = api._with_device_retry(device_name, read_diagnostics)
            result.update({
                "available": True,
                "state": state,
                "status": status,
                "error_attributes": error_attributes,
            })
        except Exception as exc:
            result["error"] = str(exc)
        return result

    _read_device_diagnostics.__module__ = api.__name__
    _read_device_diagnostics.__qualname__ = "_read_device_diagnostics"

    def get_server_diagnostics(server_name):
        """Read-only operational diagnostics for one Tango server and its device."""
        try:
            device_name = str(api.request.args.get("device_name", "")).strip()
            if not device_name:
                return api.jsonify({"success": False, "error": "device_name is required"}), 400

            device = api._read_device_diagnostics(device_name)
            starter_name = ""
            running = set()
            stopped = set()
            starter_error = ""
            server_log = {"available": False, "text": "", "truncated": False, "error": ""}
            starter_log = {"available": False, "text": "", "truncated": False, "error": ""}

            try:
                starter_name, starter, running, stopped = api._find_starter_for_server(
                    server_name,
                    allow_db_host_fallback=True,
                )
                server_log = api._read_starter_log(starter, server_name)
                starter_log = api._read_starter_log(starter, "Starter")
            except Exception as exc:
                starter_error = str(exc)
                server_log["error"] = starter_error
                starter_log["error"] = starter_error

            capture_note = ""
            if not server_log["available"]:
                capture_note = "Tango Starter log is unavailable. "
                if starter_error:
                    capture_note += "Starter could not be contacted."
                else:
                    capture_note += "The server may be writing only to its terminal window."

            return api.jsonify({
                "success": True,
                "server_name": server_name,
                "starter": starter_name,
                "running": server_name in running,
                "stopped": server_name in stopped,
                "starter_error": starter_error,
                "device": device,
                "server_log": server_log,
                "starter_log": starter_log,
                "capture_note": capture_note,
                "timestamp": api.datetime.now().isoformat(),
            })
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 500

    get_server_diagnostics.__module__ = api.__name__
    get_server_diagnostics.__qualname__ = "get_server_diagnostics"

    return {
        "_build_psp_series": _build_psp_series,
        "_read_psp_group_history": _read_psp_group_history,
        "_write_daqmx_channel": _write_daqmx_channel,
        "_env_bool": _env_bool,
        "_query_bool": _query_bool,
        "_maybe_require_auth": _maybe_require_auth,
        "_hardware_payload": _hardware_payload,
        "_mutation_payload": _mutation_payload,
        "_finite_number": _finite_number,
        "_invalid_psp_acknowledgement": _invalid_psp_acknowledgement,
        "_command_variant": _command_variant,
        "_parameter_write_plan": _parameter_write_plan,
        "debug_monitor_device": debug_monitor_device,
        "_device_proxy_target": _device_proxy_target,
        "DeviceManager": DeviceManager,
        "_read_device_snapshot": _read_device_snapshot,
        "_get_starter_devices": _get_starter_devices,
        "_get_starter_server_lists": _get_starter_server_lists,
        "_wait_for_starter_server": _wait_for_starter_server,
        "_find_starter_for_server": _find_starter_for_server,
        "_resolve_server_name": _resolve_server_name,
        "_tail_log_text": _tail_log_text,
        "_read_starter_log": _read_starter_log,
        "_read_device_diagnostics": _read_device_diagnostics,
        "get_server_diagnostics": get_server_diagnostics,
    }
