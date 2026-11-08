"""Implementation for make_json_safe and related operations."""


def _bind_device_api_parts_make_json_safe(api):
    """Bind implementation to the owning module and its runtime state."""

    def make_json_safe(value):
        """Convert numpy arrays and other non-JSON-serializable types to safe types"""
        if isinstance(value, api.np.ndarray):
            return [api.make_json_safe(item) for item in value.tolist()]
        elif isinstance(value, (float, api.np.float64, api.np.float32)):
            if api.math.isnan(float(value)) or api.math.isinf(float(value)):
                return None
            return float(value)
        elif isinstance(value, (api.np.int64, api.np.int32, api.np.int16, api.np.int8)):
            return int(value)
        elif isinstance(value, dict):
            return {key: api.make_json_safe(item) for key, item in value.items()}
        elif isinstance(value, (list, tuple)):
            return [api.make_json_safe(item) for item in value]
        elif isinstance(value, (set, frozenset)):
            return [api.make_json_safe(item) for item in sorted(value)]
        elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes, bytearray)):
            # Tango DB can return custom iterable containers (e.g. StdStringVector).
            try:
                return [api.make_json_safe(item) for item in list(value)]
            except Exception:
                return str(value)
        else:
            return value

    make_json_safe.__module__ = api.__name__
    make_json_safe.__qualname__ = "make_json_safe"

    def _parse_controller_mapping(value):
        """Parse the trusted mapping representation exported by DS_ControlPosition.

    OrderedDict uses a constructor-style repr which ``ast.literal_eval`` does
    not accept directly.  Its argument is still a plain literal list of pairs,
    so unwrap only that exact representation and keep arbitrary evaluation out
    of the web process.
    """
        text = str(value or '').strip()
        if text.startswith('OrderedDict(') and text.endswith(')'):
            pairs = api.ast.literal_eval(text[len('OrderedDict('):-1])
            return dict(pairs)
        parsed = api.ast.literal_eval(text)
        if not isinstance(parsed, dict):
            raise ValueError('controller attribute is not a mapping')
        return parsed

    _parse_controller_mapping.__module__ = api.__name__
    _parse_controller_mapping.__qualname__ = "_parse_controller_mapping"

    def _read_selected_device_properties(device_name, property_names):
        """Read a small immutable property set without enumerating every property."""
        database = api.tango_gateway.create_database()
        names = [str(name) for name in property_names]
        try:
            values = database.get_device_property(device_name, names)
            if isinstance(values, dict):
                return {name: api.make_json_safe(values.get(name, [])) for name in names}
        except Exception:
            pass

        # Lightweight test gateways and older Tango bindings may only accept one
        # property name at a time.
        result = {}
        for name in names:
            try:
                values = database.get_device_property(device_name, name)
                result[name] = api.make_json_safe(values.get(name, []))
            except Exception:
                result[name] = []
        return result

    _read_selected_device_properties.__module__ = api.__name__
    _read_selected_device_properties.__qualname__ = "_read_selected_device_properties"

    def _read_attr_sequence(device, attr_name):
        """Best-effort read of an attribute as a Python list."""
        try:
            value = api.make_json_safe(device.read_attribute(attr_name).value)
        except Exception:
            return []

        return api._sequence_from_value(value)

    _read_attr_sequence.__module__ = api.__name__
    _read_attr_sequence.__qualname__ = "_read_attr_sequence"

    def _sequence_from_value(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    _sequence_from_value.__module__ = api.__name__
    _sequence_from_value.__qualname__ = "_sequence_from_value"

    def _as_int(value, fallback=0):
        try:
            return int(float(value))
        except Exception:
            return fallback

    _as_int.__module__ = api.__name__
    _as_int.__qualname__ = "_as_int"

    def _is_delayed_tango_reconnect(exc):
        text = str(exc).lower()
        return (
            "connection request was delayed" in text
            or "last connection request was done less than" in text
            or "api_cantconnecttodevice" in text
            or "api_cantconnecttodatabase" in text
            or "transient_connectfailed" in text
        )

    _is_delayed_tango_reconnect.__module__ = api.__name__
    _is_delayed_tango_reconnect.__qualname__ = "_is_delayed_tango_reconnect"

    def _is_transient_tango_read_failure(exc):
        """Return whether a read can safely be retried after Tango releases its monitor."""
        text = str(exc).lower()
        return api._is_delayed_tango_reconnect(exc) or (
            "api_commandtimedout" in text
            or "api_commandtimeout" in text
            or "not able to acquire serialization" in text
        )

    _is_transient_tango_read_failure.__module__ = api.__name__
    _is_transient_tango_read_failure.__qualname__ = "_is_transient_tango_read_failure"

    def _with_tango_retry(operation, attempts=4, delay=1.05):
        last_exc = None
        for attempt in range(max(1, int(attempts))):
            try:
                return operation()
            except Exception as exc:
                last_exc = exc
                if not api._is_transient_tango_read_failure(exc) or attempt + 1 >= attempts:
                    raise
                api.time.sleep(delay)
        raise last_exc

    _with_tango_retry.__module__ = api.__name__
    _with_tango_retry.__qualname__ = "_with_tango_retry"

    def _with_device_retry(device_name, operation, attempts=4, delay=1.05):
        """Retry one device serially and replace its proxy after a transient reconnect error."""
        with api.DeviceManager.operation_lock(device_name):
            last_exc = None
            for attempt in range(max(1, int(attempts))):
                try:
                    return operation()
                except Exception as exc:
                    last_exc = exc
                    if not api._is_delayed_tango_reconnect(exc) or attempt + 1 >= attempts:
                        raise
                    api.DeviceManager.discard_device(device_name)
                    api.time.sleep(delay)
            raise last_exc

    _with_device_retry.__module__ = api.__name__
    _with_device_retry.__qualname__ = "_with_device_retry"

    def _coerce_binary_state_args(args):
        """Return list[int] of 0/1 states when args is a scalar/list of numbers; otherwise None."""
        if isinstance(args, api.np.ndarray):
            args = args.tolist()
        if not isinstance(args, (list, tuple)):
            return None

        normalized = []
        for value in args:
            if isinstance(value, (list, tuple, dict)):
                return None
            try:
                normalized.append(1 if int(float(value)) else 0)
            except Exception:
                return None
        return normalized

    _coerce_binary_state_args.__module__ = api.__name__
    _coerce_binary_state_args.__qualname__ = "_coerce_binary_state_args"

    def _read_pdu_states(device):
        states = api._read_attr_sequence(device, "states")
        if not states:
            states = api._read_attr_sequence(device, "output_statuses")
        return [1 if api._as_int(raw_state, 0) else 0 for raw_state in states]

    _read_pdu_states.__module__ = api.__name__
    _read_pdu_states.__qualname__ = "_read_pdu_states"

    def _is_missing_attribute_error(exc):
        """Return whether a Tango read error means this compatibility attribute is absent."""
        if isinstance(exc, KeyError):
            return True
        message = str(exc).lower()
        return any(
            marker in message
            for marker in ("api_attrnotfound", "attribute not found", "unknown attribute")
        )

    _is_missing_attribute_error.__module__ = api.__name__
    _is_missing_attribute_error.__qualname__ = "_is_missing_attribute_error"

    def _read_optional_attr_sequence_strict(device, attr_name):
        """Read an optional compatibility attribute without hiding real read failures."""
        try:
            return api._read_attr_sequence_strict(device, attr_name)
        except Exception as exc:
            if api._is_missing_attribute_error(exc):
                return []
            raise

    _read_optional_attr_sequence_strict.__module__ = api.__name__
    _read_optional_attr_sequence_strict.__qualname__ = "_read_optional_attr_sequence_strict"

    def _read_pdu_states_strict(device):
        """Read current PDU outputs, accepting the legacy ``output_statuses`` name.

    Connection and other read failures remain visible to the retry/error path.
    Only an absent ``states`` attribute activates the documented legacy fallback.
    """
        states = api._read_optional_attr_sequence_strict(device, "states")
        if not states:
            states = api._read_attr_sequence_strict(device, "output_statuses")
        return states

    _read_pdu_states_strict.__module__ = api.__name__
    _read_pdu_states_strict.__qualname__ = "_read_pdu_states_strict"

    def _wait_for_pdu_states(device, expected_states, attempts=6, delay=0.25):
        """Poll PDU state and confirm that readback matches requested states."""
        expected = [1 if api._as_int(value, 0) else 0 for value in expected_states]
        if not expected:
            return True, []

        observed = []
        for _ in range(max(1, attempts)):
            observed = api._read_pdu_states(device)
            if observed[: len(expected)] == expected:
                return True, observed
            api.time.sleep(delay)
        return False, observed

    _wait_for_pdu_states.__module__ = api.__name__
    _wait_for_pdu_states.__qualname__ = "_wait_for_pdu_states"

    def _as_bool(value, default=False):
        """Convert Tango/numpy/scalar values to bool in a predictable way."""
        if value is None:
            return default

        if isinstance(value, api.np.ndarray):
            if value.size == 0:
                return default
            if value.size == 1:
                return api._as_bool(value.item(), default)
            return api._as_bool(value.flat[0], default)

        if isinstance(value, (list, tuple)):
            if not value:
                return default
            return api._as_bool(value[0], default)

        if isinstance(value, (bool, api.np.bool_)):
            return bool(value)

        if isinstance(value, (int, float, api.np.integer, api.np.floating)):
            return bool(int(value))

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("1", "true", "yes", "y", "on", "running"):
                return True
            if normalized in ("0", "false", "no", "n", "off", "stopped"):
                return False
            return default

        return bool(value)

    _as_bool.__module__ = api.__name__
    _as_bool.__qualname__ = "_as_bool"

    def _read_camera_is_grabbing(device):
        try:
            raw_value = device.read_attribute("isgrabbing").value
        except Exception:
            return False
        return api._as_bool(raw_value, False)

    _read_camera_is_grabbing.__module__ = api.__name__
    _read_camera_is_grabbing.__qualname__ = "_read_camera_is_grabbing"

    def _wait_for_camera_grabbing(device, expected_state, attempts=10, delay=0.2):
        """Poll camera grabbing status and return observed state + whether target was reached."""
        observed = api._read_camera_is_grabbing(device)
        expected = bool(expected_state)

        for _ in range(max(1, attempts)):
            observed = api._read_camera_is_grabbing(device)
            if observed == expected:
                return observed, True
            api.time.sleep(delay)
        return observed, False

    _wait_for_camera_grabbing.__module__ = api.__name__
    _wait_for_camera_grabbing.__qualname__ = "_wait_for_camera_grabbing"

    def _resolve_command_name(device, candidates):
        """Find first available command name from a candidate list, case-insensitive."""
        try:
            available = {str(cmd_name).lower(): str(cmd_name) for cmd_name in device.get_command_list()}
        except Exception:
            available = {}

        for candidate in candidates:
            matched = available.get(str(candidate).lower())
            if matched:
                return matched

        # Fallback: try candidate names as-is even if command list failed.
        return str(candidates[0]) if candidates else None

    _resolve_command_name.__module__ = api.__name__
    _resolve_command_name.__qualname__ = "_resolve_command_name"

    def _safe_json_loads(value, default=None):
        if default is None:
            default = {}
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return api.json.loads(str(value))
        except Exception:
            return default

    _safe_json_loads.__module__ = api.__name__
    _safe_json_loads.__qualname__ = "_safe_json_loads"

    def _to_scalar_value(value):
        safe_value = api.make_json_safe(value)
        if isinstance(safe_value, list):
            if len(safe_value) == 1:
                return safe_value[0]
            return safe_value
        if isinstance(safe_value, dict):
            return safe_value
        return safe_value

    _to_scalar_value.__module__ = api.__name__
    _to_scalar_value.__qualname__ = "_to_scalar_value"

    def _list_device_commands_lower(device):
        try:
            return {str(name).lower(): str(name) for name in device.get_command_list()}
        except Exception:
            return {}

    _list_device_commands_lower.__module__ = api.__name__
    _list_device_commands_lower.__qualname__ = "_list_device_commands_lower"

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

    _read_daqmx_latest_payload.__module__ = api.__name__
    _read_daqmx_latest_payload.__qualname__ = "_read_daqmx_latest_payload"

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

    _normalize_daqmx_channels.__module__ = api.__name__
    _normalize_daqmx_channels.__qualname__ = "_normalize_daqmx_channels"

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

    _read_daqmx_device_info.__module__ = api.__name__
    _read_daqmx_device_info.__qualname__ = "_read_daqmx_device_info"

    def _is_owned_laser_flipper(role, camera_device):
        """Cam1 controls S1; Cam2 controls both upstream S1 and its own S2."""

        role_text = str(role or '')
        if not api.re.search(r'shutter|flipper', role_text, api.re.IGNORECASE):
            return False
        role_numbers = api.re.findall(r'\d+', role_text)
        if not role_numbers:
            return False
        camera_number = api._laser_camera_number(camera_device)
        role_number = int(role_numbers[0])
        if camera_number == 2:
            return role_number in (1, 2)
        return role_number == camera_number

    _is_owned_laser_flipper.__module__ = api.__name__
    _is_owned_laser_flipper.__qualname__ = "_is_owned_laser_flipper"

    def _to_float_or_none(value):
        try:
            return float(str(value))
        except Exception:
            return None

    _to_float_or_none.__module__ = api.__name__
    _to_float_or_none.__qualname__ = "_to_float_or_none"

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

    _normalize_psp_group.__module__ = api.__name__
    _normalize_psp_group.__qualname__ = "_normalize_psp_group"

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

    _parse_psp_payload.__module__ = api.__name__
    _parse_psp_payload.__qualname__ = "_parse_psp_payload"

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

    _normalize_psp_entry.__module__ = api.__name__
    _normalize_psp_entry.__qualname__ = "_normalize_psp_entry"

    return {
        "make_json_safe": make_json_safe,
        "_parse_controller_mapping": _parse_controller_mapping,
        "_read_selected_device_properties": _read_selected_device_properties,
        "_read_attr_sequence": _read_attr_sequence,
        "_sequence_from_value": _sequence_from_value,
        "_as_int": _as_int,
        "_is_delayed_tango_reconnect": _is_delayed_tango_reconnect,
        "_is_transient_tango_read_failure": _is_transient_tango_read_failure,
        "_with_tango_retry": _with_tango_retry,
        "_with_device_retry": _with_device_retry,
        "_coerce_binary_state_args": _coerce_binary_state_args,
        "_read_pdu_states": _read_pdu_states,
        "_is_missing_attribute_error": _is_missing_attribute_error,
        "_read_optional_attr_sequence_strict": _read_optional_attr_sequence_strict,
        "_read_pdu_states_strict": _read_pdu_states_strict,
        "_wait_for_pdu_states": _wait_for_pdu_states,
        "_as_bool": _as_bool,
        "_read_camera_is_grabbing": _read_camera_is_grabbing,
        "_wait_for_camera_grabbing": _wait_for_camera_grabbing,
        "_resolve_command_name": _resolve_command_name,
        "_safe_json_loads": _safe_json_loads,
        "_to_scalar_value": _to_scalar_value,
        "_list_device_commands_lower": _list_device_commands_lower,
        "_read_daqmx_latest_payload": _read_daqmx_latest_payload,
        "_normalize_daqmx_channels": _normalize_daqmx_channels,
        "_read_daqmx_device_info": _read_daqmx_device_info,
        "_is_owned_laser_flipper": _is_owned_laser_flipper,
        "_to_float_or_none": _to_float_or_none,
        "_normalize_psp_group": _normalize_psp_group,
        "_parse_psp_payload": _parse_psp_payload,
        "_normalize_psp_entry": _normalize_psp_entry,
    }
