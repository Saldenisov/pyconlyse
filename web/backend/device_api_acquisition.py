"""device api acquisition operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _read_daqmx_latest_payload(device):
        command_candidates = [
            "get_latest_values_json",
            "GetLatestValuesJson",
        ]
        attr_candidates = [
            "latest_values_json",
            "LatestValuesJson",
            "snapshot_json",
            "SnapshotJson",
        ]

        for command_name in command_candidates:
            try:
                raw = device.command_inout(command_name)
                payload = api._safe_json_loads(raw, default={})
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass

        for attr_name in attr_candidates:
            try:
                raw = device.read_attribute(attr_name).value
                payload = api._safe_json_loads(raw, default={})
                if isinstance(payload, dict):
                    if attr_name.lower() == "snapshot_json" and "data" not in payload:
                        return {
                            "timestamp": api.time.time(),
                            "source": "direct",
                            "data": payload,
                        }
                    return payload
            except Exception:
                pass

        return {}


    def _normalize_daqmx_channels(payload):
        if not isinstance(payload, dict):
            return []

        data = payload.get("data", payload if isinstance(payload, dict) else {})
        if not isinstance(data, dict):
            return []

        channels = []
        for channel_name, channel_value in data.items():
            if isinstance(channel_value, dict) and (
                "value" in channel_value or "kind" in channel_value
            ):
                details = api.make_json_safe(channel_value)
                kind = str(details.get("kind", details.get("type", "")) or "")
                item = {
                    "name": str(channel_name),
                    "value": api._to_scalar_value(details.get("value")),
                    "kind": kind,
                    "physical_channel": str(details.get("channel", "") or ""),
                    "counter": str(details.get("counter", "") or ""),
                    "unit": str(details.get("unit", "") or ""),
                    "alarm": bool(details.get("alarm", False)),
                    "value_known": bool(details.get("value_known", True)),
                    "writable": kind == "DigitalOut",
                    "raw_value": api._to_scalar_value(details.get("raw_value")),
                    "multiplier": api._to_scalar_value(details.get("multiplier", 1.0)),
                    "limit_alarm_min": api._to_scalar_value(details.get("limit_alarm_min")),
                    "limit_alarm_max": api._to_scalar_value(details.get("limit_alarm_max")),
                }
                if details.get("error"):
                    item["error"] = str(details["error"])
                channels.append(item)
                continue

            channels.append({
                "name": str(channel_name),
                "value": api._to_scalar_value(channel_value),
                "kind": "",
                "physical_channel": "",
                "counter": "",
                "unit": "",
                "alarm": False,
                "value_known": True,
                "writable": False,
            })
        return channels


    def _read_daqmx_device_info(device):
        for attr_name in ("device_info_json", "DeviceInfoJson"):
            try:
                raw = device.read_attribute(attr_name).value
                payload = api._safe_json_loads(raw, default={})
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        return {}


    def _normalize_psp_group(group_name):
        normalized = str(group_name or "").strip().lower()
        aliases = {
            "high_tension": "ht",
            "hightension": "ht",
            "magnet": "magnets",
            "time": "timestamp",
        }
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in api.PSP_GROUPS else "other"


    def _parse_psp_payload(raw_payload):
        payload = str(raw_payload or "")
        first_colon = payload.find(":")
        second_colon = payload.find(":", first_colon + 1) if first_colon >= 0 else -1

        if first_colon < 0:
            channel = payload
            value_raw = ""
            source_ts = None
        elif second_colon < 0:
            channel = payload[:first_colon]
            value_raw = payload[first_colon + 1 :]
            source_ts = None
        else:
            channel = payload[:first_colon]
            value_raw = payload[first_colon + 1 : second_colon]
            source_ts = api._to_float_or_none(payload[second_colon + 1 :])

        parts = [part for part in str(channel).split("/") if part]
        group_raw = parts[1] if len(parts) >= 2 else ""
        group = api._normalize_psp_group(group_raw)

        value_number = api._to_float_or_none(value_raw)
        value = value_number if value_number is not None else value_raw

        return {
            "payload": payload,
            "channel": str(channel),
            "group": group,
            "value_raw": str(value_raw),
            "value": value,
            "source_ts": source_ts,
        }


    def _normalize_psp_entry(raw_entry):
        if isinstance(raw_entry, dict):
            item = api.make_json_safe(raw_entry)
        else:
            item = {"payload": str(raw_entry)}

        payload = str(item.get("payload", ""))
        parsed = api._parse_psp_payload(payload)

        channel = str(item.get("channel", parsed["channel"]))
        group = api._normalize_psp_group(item.get("group", parsed["group"]))
        source_ts = item.get("source_ts", parsed["source_ts"])
        source_ts = api._to_float_or_none(source_ts)
        recv_ts = api._to_float_or_none(item.get("recv_ts"))
        msg_id = item.get("id")
        msg_id = api._as_int(msg_id, 0) if msg_id is not None else None

        value = item.get("value", parsed["value"])
        if isinstance(value, (dict, list)):
            value = api.make_json_safe(value)
        else:
            value_number = api._to_float_or_none(value)
            value = value_number if value_number is not None else str(value)

        return {
            "id": msg_id,
            "payload": payload,
            "channel": channel,
            "group": group,
            "value_raw": str(item.get("value_raw", parsed["value_raw"])),
            "value": value,
            "source_ts": source_ts,
            "recv_ts": recv_ts,
        }


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


    # DAQmx / Supervision endpoints
    def list_daqmx_devices():
        """List DAQmx-related Tango devices (ZMQ reader and PSP supervision readers)."""
        try:
            db = api.tango_gateway.create_database()
            probe_state = api._query_bool('probe_state', True)
            devices = api._device_catalog_service.list_class_devices(
                db,
                api.DAQMX_DEVICE_CLASSES,
                probe_state,
                api._catalog_device_state,
                deduplicate=True,
            )
            return api.jsonify({'devices': devices, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def list_psp_devices():
        """List DS_PSP devices available in Tango DB."""
        try:
            db = api.tango_gateway.create_database()
            probe_state = api._query_bool('probe_state', True)
            devices = api._device_catalog_service.list_class_devices(
                db,
                ('DS_PSP',),
                probe_state,
                api._catalog_device_state,
                deduplicate=False,
            )
            return api.jsonify({'devices': devices, 'success': True})
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_psp_group_history(device_name, group_name):
        """Read PSP FIFO history for one group and return graph-ready series."""
        try:
            device = api.DeviceManager.get_device(device_name)
            seconds = max(0.0, float(api.request.args.get('seconds', 1800.0)))
            limit = max(1, int(api.request.args.get('limit', 5000)))
            group = api._normalize_psp_group(group_name)

            history = api._read_psp_group_history(device, group, seconds, limit)
            series, latest = api._build_psp_series(history)

            return api.jsonify({
                'device': device_name,
                'group': group,
                'seconds': seconds,
                'limit': limit,
                'sample_count': len(history),
                'channel_count': len(series),
                'history': history,
                'series': series,
                'latest_by_channel': latest,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_psp_pending_commands(device_name):
        """Read pending outbound commands queued for LabVIEW bridge."""
        try:
            if api._query_bool('pop', False):
                return api.jsonify({
                    'error': 'pop=true is disabled; use a guarded mutation endpoint',
                    'success': False,
                }), 400
            device = api.DeviceManager.get_device(device_name)
            commands = api._list_device_commands_lower(device)
            limit = max(1, int(api.request.args.get('limit', 200)))

            cmd_name = commands.get('get_pending_commands_json')
            if not cmd_name:
                return api.jsonify({'error': 'Device does not support pending command queue', 'success': False}), 400

            raw = device.command_inout(cmd_name, limit)
            payload = api._safe_json_loads(raw, default={})
            if not isinstance(payload, dict):
                payload = {}

            items = payload.get('items', [])
            if not isinstance(items, list):
                items = []
            pending_count = api._as_int(payload.get('pending_count'), len(items))

            return api.jsonify({
                'device': device_name,
                'pending_count': pending_count,
                'items': api.make_json_safe(items),
                'popped': False,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def acknowledge_psp_command(device_name):
        """Store LabVIEW execution acknowledgment for one queued command."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload()
            if data is None or set(data) - api._PSP_ACK_FIELDS:
                return api._invalid_psp_acknowledgement()
            if (
                ('id' in data and (isinstance(data['id'], bool) or not isinstance(data['id'], (str, int))))
                or ('command' in data and (not isinstance(data['command'], str) or not data['command'].strip()))
                or ('ok' in data and type(data['ok']) is not bool)
                or any(name in data and not isinstance(data[name], str) for name in ('status', 'error', 'message', 'timestamp'))
            ):
                return api._invalid_psp_acknowledgement()
            command_variant = api._command_variant(data, api._PSP_ACK_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api._invalid_psp_acknowledgement()
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            acknowledgement = {key: data[key] for key in api._PSP_ACK_FIELDS - {'command_variant'} if key in data}
            blocked = api.require_http_hardware(
                action='acknowledge',
                targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in api._PSP_ACK_COMMANDS],
                args={'command_variant': command_variant or 'legacy_autodetect', 'acknowledgement': acknowledgement},
                route_id='psp.ack', wrapper_fields=api._PSP_ACK_FIELDS,
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)
            if command_variant is not None:
                cmd_name = command_variant
            else:
                commands = api._list_device_commands_lower(device)
                cmd_name = commands.get('acknowledge_command_json')
            if not cmd_name:
                return api.jsonify({'error': 'Device does not support command acknowledgments', 'success': False}), 400
            raw = device.command_inout(cmd_name, api.json.dumps(acknowledgement))
            payload = api._safe_json_loads(raw, default={})
            if not isinstance(payload, dict):
                payload = {'raw': api.make_json_safe(raw)}

            return api.jsonify({'device': device_name, **api.make_json_safe(payload), 'success': True})
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_daqmx_latest(device_name):
        """Get latest DAQmx/PSP data payload and normalized channel list."""
        try:
            device = api.DeviceManager.get_device(device_name)
            payload = api._read_daqmx_latest_payload(device)
            channels = api._normalize_daqmx_channels(payload)
            device_info = api._read_daqmx_device_info(device)

            return api.jsonify({
                'device': device_name,
                'state': str(device.state()),
                'latest': payload,
                'channels': channels,
                'channel_count': len(channels),
                'device_info': device_info,
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def get_daqmx_history(device_name):
        """Get DAQmx history if the device supports get_history_json(seconds)."""
        try:
            device = api.DeviceManager.get_device(device_name)
            seconds = float(api.request.args.get('seconds', 10.0))
            commands = api._list_device_commands_lower(device)
            cmd = commands.get('get_history_json')
            if not cmd:
                return api.jsonify({
                    'error': 'History is not supported by this device',
                    'success': False,
                }), 400

            raw = device.command_inout(cmd, seconds)
            history = api._safe_json_loads(raw, default=[])
            if not isinstance(history, list):
                history = []

            return api.jsonify({
                'device': device_name,
                'seconds': seconds,
                'history': history,
                'sample_count': len(history),
                'success': True,
            })
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def write_daqmx_channel(device_name):
        """Write one channel/variable value via DAQmx/PSP write command."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload()
            if data is None:
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            channel_fields = [name for name in ('channel', 'name', 'variable') if data.get(name) not in (None, '')]
            if len(channel_fields) != 1:
                return api.jsonify({'error': 'exactly one channel, name, or variable is required', 'success': False}), 400
            channel = data[channel_fields[0]]
            value = data.get('value')

            if channel in (None, ''):
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            if value is None:
                return api.jsonify({'error': 'value is required', 'success': False}), 400
            if not isinstance(channel, str) or not channel.strip():
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            command_variant = api._command_variant(data, api._DAQMX_WRITE_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            blocked = api.require_http_hardware(
                action='write',
                targets=[{'device': str(device_name), 'command': command_variant}] if command_variant else [{'device': str(device_name), 'command': command} for command in api._DAQMX_WRITE_COMMANDS],
                args={'channel_selector': channel_fields[0], 'channel': channel.strip(), 'value': api._to_scalar_value(value), 'command_variant': command_variant or 'legacy_autodetect'},
                route_id='daqmx.write', wrapper_fields={'channel', 'name', 'variable', 'value', 'command_variant'},
            )
            if blocked is not None:
                return blocked
            device = api.DeviceManager.get_device(device_name)

            result = api._write_daqmx_channel(device, channel, value, command_variant=command_variant)
            return api.jsonify({
                'device': device_name,
                'channel': str(channel),
                'value': api._to_scalar_value(value),
                'result': api.make_json_safe(result),
                'success': True,
            })
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500


    def reset_daqmx_counter(device_name):
        """Reset one counter exposed by the direct physical-card DAQmx server."""
        try:
            api._maybe_require_auth()
            data = api._mutation_payload(required=('channel',))
            if data is None or set(data) - {'channel', 'command_variant'}:
                return api.jsonify({'error': 'channel is required', 'success': False}), 400
            channel = data.get('channel')
            if not isinstance(channel, str) or not channel.strip():
                return api.jsonify({'error': 'channel is required', 'success': False}), 400

            command_variant = api._command_variant(data, api._DAQMX_RESET_COMMANDS)
            if api.authorization_required() and command_variant is None:
                return api.jsonify({'error': 'command_variant is required', 'success': False}), 400
            if command_variant is None and data.get('command_variant') is not None:
                return api.jsonify({'error': 'command_variant is invalid', 'success': False}), 400
            command_name = command_variant or 'reset_counter'
            blocked = api.require_http_hardware(
                action='reset',
                targets=[{'device': str(device_name), 'command': command_name}],
                args={'channel': channel.strip(), 'command_variant': command_name},
                route_id='daqmx.reset',
                wrapper_fields={'channel', 'command_variant'},
            )
            if blocked is not None:
                return blocked

            device = api.DeviceManager.get_device(device_name)
            commands = api._list_device_commands_lower(device)
            resolved_command = commands.get(command_name.lower())
            if not resolved_command:
                return api.jsonify({
                    'error': 'Device does not support counter reset',
                    'success': False,
                }), 400
            result = device.command_inout(resolved_command, channel.strip())
            return api.jsonify({
                'device': device_name,
                'channel': channel.strip(),
                'result': api.make_json_safe(result),
                'success': True,
            })
        except api.AuthorizationError as exc:
            return api._authorization_error_response(exc)
        except Exception as e:
            return api.jsonify({'error': str(e), 'success': False}), 500

    api._read_daqmx_latest_payload = _read_daqmx_latest_payload
    api._normalize_daqmx_channels = _normalize_daqmx_channels
    api._read_daqmx_device_info = _read_daqmx_device_info
    api._normalize_psp_group = _normalize_psp_group
    api._parse_psp_payload = _parse_psp_payload
    api._normalize_psp_entry = _normalize_psp_entry
    api._build_psp_series = _build_psp_series
    api._read_psp_group_history = _read_psp_group_history
    api._write_daqmx_channel = _write_daqmx_channel
    api.list_daqmx_devices = list_daqmx_devices
    api.list_psp_devices = list_psp_devices
    api.get_psp_group_history = get_psp_group_history
    api.get_psp_pending_commands = get_psp_pending_commands
    api.acknowledge_psp_command = acknowledge_psp_command
    api.get_daqmx_latest = get_daqmx_latest
    api.get_daqmx_history = get_daqmx_history
    api.write_daqmx_channel = write_daqmx_channel
    api.reset_daqmx_counter = reset_daqmx_counter
