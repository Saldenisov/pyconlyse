"""Tango readback normalization, retries and command discovery."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    # Helper function to convert numpy arrays to lists for JSON serialization
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


    def _read_attr_sequence(device, attr_name):
        """Best-effort read of an attribute as a Python list."""
        try:
            value = api.make_json_safe(device.read_attribute(attr_name).value)
        except Exception:
            return []

        return api._sequence_from_value(value)


    def _read_attr_sequence_strict(device, attr_name):
        """Read an attribute as a Python list, preserving Tango read errors for retry."""
        return api._sequence_from_value(api.make_json_safe(device.read_attribute(attr_name).value))


    def _sequence_from_value(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]


    def _as_int(value, fallback=0):
        try:
            return int(float(value))
        except Exception:
            return fallback


    def _is_delayed_tango_reconnect(exc):
        text = str(exc).lower()
        return (
            "connection request was delayed" in text
            or "last connection request was done less than" in text
            or "api_cantconnecttodevice" in text
            or "api_cantconnecttodatabase" in text
            or "transient_connectfailed" in text
        )


    def _is_transient_tango_read_failure(exc):
        """Return whether a read can safely be retried after Tango releases its monitor."""
        text = str(exc).lower()
        return api._is_delayed_tango_reconnect(exc) or (
            "api_commandtimedout" in text
            or "api_commandtimeout" in text
            or "not able to acquire serialization" in text
        )


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


    def _read_pdu_states(device):
        states = api._read_attr_sequence(device, "states")
        if not states:
            states = api._read_attr_sequence(device, "output_statuses")
        return [1 if api._as_int(raw_state, 0) else 0 for raw_state in states]


    def _is_missing_attribute_error(exc):
        """Return whether a Tango read error means this compatibility attribute is absent."""
        if isinstance(exc, KeyError):
            return True
        message = str(exc).lower()
        return any(
            marker in message
            for marker in ("api_attrnotfound", "attribute not found", "unknown attribute")
        )


    def _read_optional_attr_sequence_strict(device, attr_name):
        """Read an optional compatibility attribute without hiding real read failures."""
        try:
            return api._read_attr_sequence_strict(device, attr_name)
        except Exception as exc:
            if api._is_missing_attribute_error(exc):
                return []
            raise


    def _read_pdu_states_strict(device):
        """Read current PDU outputs, accepting the legacy ``output_statuses`` name.

        Connection and other read failures remain visible to the retry/error path.
        Only an absent ``states`` attribute activates the documented legacy fallback.
        """
        states = api._read_optional_attr_sequence_strict(device, "states")
        if not states:
            states = api._read_attr_sequence_strict(device, "output_statuses")
        return states


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


    def _read_camera_is_grabbing(device):
        try:
            raw_value = device.read_attribute("isgrabbing").value
        except Exception:
            return False
        return api._as_bool(raw_value, False)


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


    def _to_scalar_value(value):
        safe_value = api.make_json_safe(value)
        if isinstance(safe_value, list):
            if len(safe_value) == 1:
                return safe_value[0]
            return safe_value
        if isinstance(safe_value, dict):
            return safe_value
        return safe_value


    def _list_device_commands_lower(device):
        try:
            return {str(name).lower(): str(name) for name in device.get_command_list()}
        except Exception:
            return {}


    def _to_float_or_none(value):
        try:
            return float(str(value))
        except Exception:
            return None

    api.make_json_safe = make_json_safe
    api._parse_controller_mapping = _parse_controller_mapping
    api._read_selected_device_properties = _read_selected_device_properties
    api._read_attr_sequence = _read_attr_sequence
    api._read_attr_sequence_strict = _read_attr_sequence_strict
    api._sequence_from_value = _sequence_from_value
    api._as_int = _as_int
    api._is_delayed_tango_reconnect = _is_delayed_tango_reconnect
    api._is_transient_tango_read_failure = _is_transient_tango_read_failure
    api._with_tango_retry = _with_tango_retry
    api._with_device_retry = _with_device_retry
    api._coerce_binary_state_args = _coerce_binary_state_args
    api._read_pdu_states = _read_pdu_states
    api._is_missing_attribute_error = _is_missing_attribute_error
    api._read_optional_attr_sequence_strict = _read_optional_attr_sequence_strict
    api._read_pdu_states_strict = _read_pdu_states_strict
    api._wait_for_pdu_states = _wait_for_pdu_states
    api._as_bool = _as_bool
    api._read_camera_is_grabbing = _read_camera_is_grabbing
    api._wait_for_camera_grabbing = _wait_for_camera_grabbing
    api._resolve_command_name = _resolve_command_name
    api._safe_json_loads = _safe_json_loads
    api._to_scalar_value = _to_scalar_value
    api._list_device_commands_lower = _list_device_commands_lower
    api._to_float_or_none = _to_float_or_none
