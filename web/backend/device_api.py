# device_api.py - Enhanced Tango Device API for Browser Clients
from flask import Blueprint, jsonify, request
import os
import tango
import json
import traceback
from datetime import datetime
import threading
import time
import math
import numpy as np
from flask_jwt_extended import verify_jwt_in_request

device_api = Blueprint("device_api", __name__)

# Helper function to convert numpy arrays to lists for JSON serialization
def make_json_safe(value):
    """Convert numpy arrays and other non-JSON-serializable types to safe types"""
    if isinstance(value, np.ndarray):
        return [make_json_safe(item) for item in value.tolist()]
    elif isinstance(value, (float, np.float64, np.float32)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    elif isinstance(value, (np.int64, np.int32, np.int16, np.int8)):
        return int(value)
    elif isinstance(value, dict):
        return {key: make_json_safe(item) for key, item in value.items()}
    elif isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]
    elif isinstance(value, (set, frozenset)):
        return [make_json_safe(item) for item in sorted(value)]
    elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes, bytearray)):
        # Tango DB can return custom iterable containers (e.g. StdStringVector).
        try:
            return [make_json_safe(item) for item in list(value)]
        except Exception:
            return str(value)
    else:
        return value


def _read_attr_sequence(device, attr_name):
    """Best-effort read of an attribute as a Python list."""
    try:
        value = make_json_safe(device.read_attribute(attr_name).value)
    except Exception:
        return []

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


def _coerce_binary_state_args(args):
    """Return list[int] of 0/1 states when args is a scalar/list of numbers; otherwise None."""
    if isinstance(args, np.ndarray):
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
    states = _read_attr_sequence(device, "states")
    if not states:
        states = _read_attr_sequence(device, "output_statuses")
    return [1 if _as_int(raw_state, 0) else 0 for raw_state in states]


def _wait_for_pdu_states(device, expected_states, attempts=6, delay=0.25):
    """Poll PDU state and confirm that readback matches requested states."""
    expected = [1 if _as_int(value, 0) else 0 for value in expected_states]
    if not expected:
        return True, []

    observed = []
    for _ in range(max(1, attempts)):
        observed = _read_pdu_states(device)
        if observed[: len(expected)] == expected:
            return True, observed
        time.sleep(delay)
    return False, observed


def _as_bool(value, default=False):
    """Convert Tango/numpy/scalar values to bool in a predictable way."""
    if value is None:
        return default

    if isinstance(value, np.ndarray):
        if value.size == 0:
            return default
        if value.size == 1:
            return _as_bool(value.item(), default)
        return _as_bool(value.flat[0], default)

    if isinstance(value, (list, tuple)):
        if not value:
            return default
        return _as_bool(value[0], default)

    if isinstance(value, (bool, np.bool_)):
        return bool(value)

    if isinstance(value, (int, float, np.integer, np.floating)):
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
    return _as_bool(raw_value, False)


def _wait_for_camera_grabbing(device, expected_state, attempts=10, delay=0.2):
    """Poll camera grabbing status and return observed state + whether target was reached."""
    observed = _read_camera_is_grabbing(device)
    expected = bool(expected_state)

    for _ in range(max(1, attempts)):
        observed = _read_camera_is_grabbing(device)
        if observed == expected:
            return observed, True
        time.sleep(delay)
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


DAQMX_DEVICE_CLASSES = (
    "DS_DAQmx_ZMQ",
    "DS_PSP_SUPERVISION",
    "DS_PSP_Supervision",
    "DS_PSP",
)

PSP_GROUPS = (
    "timestamp",
    "cooling",
    "hf",
    "ht",
    "modulator",
    "vacuum",
    "magnets",
    "other",
)


def _safe_json_loads(value, default=None):
    if default is None:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _to_scalar_value(value):
    safe_value = make_json_safe(value)
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


def _read_daqmx_latest_payload(device):
    command_candidates = [
        "get_latest_values_json",
        "GetLatestValuesJson",
    ]
    attr_candidates = [
        "latest_values_json",
        "LatestValuesJson",
    ]

    for command_name in command_candidates:
        try:
            raw = device.command_inout(command_name)
            payload = _safe_json_loads(raw, default={})
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    for attr_name in attr_candidates:
        try:
            raw = device.read_attribute(attr_name).value
            payload = _safe_json_loads(raw, default={})
            if isinstance(payload, dict):
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
        channels.append({
            "name": str(channel_name),
            "value": _to_scalar_value(channel_value),
        })
    channels.sort(key=lambda item: item["name"])
    return channels


def _to_float_or_none(value):
    try:
        return float(str(value))
    except Exception:
        return None


def _normalize_psp_group(group_name):
    normalized = str(group_name or "").strip().lower()
    aliases = {
        "high_tension": "ht",
        "hightension": "ht",
        "magnet": "magnets",
        "time": "timestamp",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in PSP_GROUPS else "other"


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
        source_ts = _to_float_or_none(payload[second_colon + 1 :])

    parts = [part for part in str(channel).split("/") if part]
    group_raw = parts[1] if len(parts) >= 2 else ""
    group = _normalize_psp_group(group_raw)

    value_number = _to_float_or_none(value_raw)
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
        item = make_json_safe(raw_entry)
    else:
        item = {"payload": str(raw_entry)}

    payload = str(item.get("payload", ""))
    parsed = _parse_psp_payload(payload)

    channel = str(item.get("channel", parsed["channel"]))
    group = _normalize_psp_group(item.get("group", parsed["group"]))
    source_ts = item.get("source_ts", parsed["source_ts"])
    source_ts = _to_float_or_none(source_ts)
    recv_ts = _to_float_or_none(item.get("recv_ts"))
    msg_id = item.get("id")
    msg_id = _as_int(msg_id, 0) if msg_id is not None else None

    value = item.get("value", parsed["value"])
    if isinstance(value, (dict, list)):
        value = make_json_safe(value)
    else:
        value_number = _to_float_or_none(value)
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

        recv_ts = _to_float_or_none(item.get("recv_ts"))
        source_ts = _to_float_or_none(item.get("source_ts"))
        ts = recv_ts if recv_ts is not None else source_ts
        if ts is None:
            continue

        value = _to_float_or_none(item.get("value"))
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
    group = _normalize_psp_group(group_name)
    commands = _list_device_commands_lower(device)
    history_raw = []

    get_group_cmd = commands.get("get_group_history_json")
    if get_group_cmd:
        query = f"{group}|{max(0.0, float(seconds))}|{max(0, int(limit))}"
        raw = device.command_inout(get_group_cmd, query)
        payload = _safe_json_loads(raw, default={})
        if isinstance(payload, dict):
            history_raw = payload.get("history", [])
        elif isinstance(payload, list):
            history_raw = payload

    if not history_raw:
        get_history_cmd = commands.get("get_history_json")
        if get_history_cmd:
            raw = device.command_inout(get_history_cmd, max(0.0, float(seconds)))
            payload = _safe_json_loads(raw, default=[])
            if isinstance(payload, list):
                history_raw = payload

    normalized = [_normalize_psp_entry(item) for item in history_raw]
    normalized = [item for item in normalized if item.get("group") == group]
    if limit > 0:
        normalized = normalized[-int(limit) :]
    return normalized


def _write_daqmx_channel(device, channel, value):
    """
    Attempt to write DAQmx/PSP variable using any supported command signature.
    Raises Exception when no supported write command is found.
    """
    commands = _list_device_commands_lower(device)
    channel = str(channel)
    scalar_value = _to_scalar_value(value)

    json_payload_name_value = json.dumps({"name": channel, "value": scalar_value})
    json_payload_channel_value = json.dumps({"channel": channel, "value": scalar_value})
    eq_payload = f"{channel}={scalar_value}"

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

    raise Exception(
        "Device does not expose a supported write command "
        "(expected one of: write_variable*, set_variable_value*, set_channel_value*)"
    )


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _query_bool(name, default=False):
    value = request.args.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _maybe_require_auth():
    if _env_bool("PYCONLYSE_ENFORCE_DEVICE_AUTH", False):
        verify_jwt_in_request()

# Debug endpoint to test WebSocket monitoring
@device_api.route('/api/debug/monitor/<path:device_name>', methods=['GET'])
def debug_monitor_device(device_name):
    """Debug endpoint to manually trigger device monitoring"""
    try:
        from websocket_handler import monitor
        monitor.monitor_device(device_name, "debug_room")
        return jsonify({
            'message': f'Manual monitoring triggered for {device_name}',
            'success': True
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

# Global device proxy cache and monitoring
device_cache = {}
monitoring_threads = {}
monitoring_active = {}
_device_list_cache = {}

class DeviceManager:
    """Manages Tango device connections and operations"""
    
    @staticmethod
    def get_device(device_name):
        """Get or create device proxy with caching"""
        if device_name not in device_cache:
            try:
                device_cache[device_name] = tango.DeviceProxy(device_name)
            except Exception as e:
                raise Exception(f"Could not connect to device {device_name}: {str(e)}")
        return device_cache[device_name]

    @staticmethod
    def get_device_summary(device_name):
        device = DeviceManager.get_device(device_name)
        device_info = device.info()
        return {
            'name': device_name,
            'state': str(device.state()),
            'status': device.status(),
            'info': getattr(device_info, 'dev_class', ''),
            'server': getattr(device_info, 'server_id', ''),
            'connected': True,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def get_device_properties(device_name):
        properties = {}
        db = tango.Database()
        prop_list = db.get_device_property_list(device_name, '*')
        for prop_name in prop_list:
            try:
                prop_values = db.get_device_property(device_name, prop_name)
                properties[prop_name] = make_json_safe(prop_values.get(prop_name, []))
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
                    'value': make_json_safe(value),
                    'quality': str(attr.quality),
                    'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                    'writable': attr_config.writable != tango.AttrWriteType.READ,
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


def _get_starter_devices():
    db = tango.Database()
    devices = list(db.get_device_exported("*"))
    return [device_name for device_name in devices if str(device_name).startswith("tango/admin/")]


def _get_starter_server_lists(starter_name):
    starter = tango.DeviceProxy(starter_name)
    running = set(starter.command_inout('DevGetRunningServers', False))
    stopped = set(starter.command_inout('DevGetStopServers', False))
    return starter, running, stopped


def _find_starter_for_server(server_name):
    for starter_name in _get_starter_devices():
        try:
            starter, running, stopped = _get_starter_server_lists(starter_name)
        except Exception:
            continue
        if server_name in running or server_name in stopped:
            return starter_name, starter, running, stopped
    raise Exception(f"No Starter manages server {server_name}")


def _resolve_server_name(device_name):
    db = tango.Database()
    try:
        return DeviceManager.get_device(device_name).info().server_id
    except Exception:
        info = db.get_device_info(device_name)
        server_name = getattr(info, 'ds_full_name', None) or getattr(info, 'server', None)
        if not server_name:
            raise Exception(f"Could not resolve server for device {device_name}")
        return str(server_name)

@device_api.route('/api/devices', methods=['GET'])
def list_devices():
    """Get list of all available devices"""
    try:
        probe_state = _query_bool('probe_state', False)
        include_dserver = _query_bool('include_dserver', True)
        include_admin = _query_bool('include_admin', False)
        refresh = _query_bool('refresh', False)
        cache_ttl_s = float(os.environ.get('PYCONLYSE_DEVICE_LIST_CACHE_TTL', '4.0'))
        cache_key = (probe_state, include_dserver, include_admin)

        now = time.time()
        cached_entry = _device_list_cache.get(cache_key)
        if (
            not refresh
            and cached_entry
            and (now - cached_entry.get('ts', 0)) <= max(cache_ttl_s, 0.0)
        ):
            return jsonify({
                'devices': cached_entry.get('devices', []),
                'success': True,
                'cached': True,
                'probe_state': probe_state,
            })

        db = tango.Database()
        devices = db.get_device_exported("*")

        device_list = []
        for device_name in devices:
            device_name = str(device_name)
            lower_name = device_name.lower()
            if not include_dserver and lower_name.startswith('dserver/'):
                continue
            if not include_admin and lower_name.startswith('tango/admin/'):
                continue

            server_name = None
            dev_class = None
            state = 'UNKNOWN'
            available = True

            try:
                info = db.get_device_info(device_name)
                server_name = getattr(info, 'ds_full_name', None) or getattr(info, 'server', None)
                dev_class = getattr(info, 'class_name', None)
            except Exception:
                pass

            if probe_state:
                try:
                    device = tango.DeviceProxy(device_name)
                    state = str(device.state())
                    if not server_name or not dev_class:
                        info = device.info()
                        server_name = server_name or getattr(info, 'server_id', None)
                        dev_class = dev_class or getattr(info, 'dev_class', None)
                except Exception:
                    available = False

            device_list.append({
                'name': device_name,
                'state': state,
                'server': server_name,
                'class': dev_class,
                'available': available
            })

        device_list.sort(key=lambda item: str(item.get('name', '')))
        _device_list_cache[cache_key] = {'ts': now, 'devices': device_list}

        return jsonify({
            'devices': device_list,
            'success': True,
            'cached': False,
            'probe_state': probe_state,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/server/control', methods=['POST'])
def control_server():
    """Control a device server through its Starter."""
    try:
        _maybe_require_auth()
        data = request.get_json() or {}
        action = str(data.get('action', '')).strip().lower()
        server_name = data.get('server_name')
        device_name = data.get('device_name')

        if not server_name and device_name:
            server_name = _resolve_server_name(str(device_name))

        if not server_name:
            return jsonify({'error': 'server_name or device_name is required', 'success': False}), 400

        server_name = str(server_name)
        if action not in {'start', 'restart', 'hard_kill'}:
            return jsonify({'error': 'Unsupported action', 'success': False}), 400

        starter_name, starter, running_before, stopped_before = _find_starter_for_server(server_name)

        if action == 'start':
            if server_name not in running_before:
                starter.command_inout('DevStart', server_name)
                time.sleep(2)
        elif action == 'hard_kill':
            starter.command_inout('HardKillServer', server_name)
            time.sleep(2)
        elif action == 'restart':
            if server_name in running_before:
                try:
                    starter.command_inout('DevStop', server_name)
                    time.sleep(2)
                except Exception:
                    pass

                _, running_after_stop, _ = _get_starter_server_lists(starter_name)
                if server_name in running_after_stop:
                    starter.command_inout('HardKillServer', server_name)
                    time.sleep(2)

            starter.command_inout('DevStart', server_name)
            time.sleep(2)

        _, running_after, stopped_after = _get_starter_server_lists(starter_name)

        return jsonify({
            'success': True,
            'action': action,
            'server_name': server_name,
            'starter': starter_name,
            'running': server_name in running_after,
            'stopped': server_name in stopped_after,
            'running_count': len(running_after),
            'stopped_count': len(stopped_after),
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/info', methods=['GET'])
def get_device_info(device_name):
    """Get detailed device information"""
    try:
        include_properties = _query_bool('include_properties', True)
        include_attributes = _query_bool('include_attributes', True)
        include_commands = _query_bool('include_commands', True)

        info = DeviceManager.get_device_summary(device_name)
        device = DeviceManager.get_device(device_name)

        if include_properties:
            try:
                info['properties'] = DeviceManager.get_device_properties(device_name)
            except Exception as e:
                info['properties_error'] = str(e)

        if include_attributes:
            try:
                info['attributes'] = DeviceManager.get_device_attributes(device)
            except Exception as e:
                info['attributes_error'] = str(e)

        if include_commands:
            try:
                info['commands'] = DeviceManager.get_device_commands(device)
            except Exception as e:
                info['commands_error'] = str(e)

        return jsonify({'device_info': info, 'success': True})
    except Exception as e:
        return jsonify({
            'device_info': {
                'name': device_name,
                'connected': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            },
            'error': str(e),
            'success': False
        }), 500


@device_api.route('/api/device/<path:device_name>/summary', methods=['GET'])
def get_device_summary(device_name):
    """Get fast device summary for lazy UI loading."""
    try:
        summary = DeviceManager.get_device_summary(device_name)
        return jsonify({'device_info': summary, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/device/<path:device_name>/commands', methods=['GET'])
def get_device_commands(device_name):
    """Get device command list and input/output metadata."""
    try:
        device = DeviceManager.get_device(device_name)
        commands = DeviceManager.get_device_commands(device)
        return jsonify({'commands': commands, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/attributes', methods=['GET'])
def get_device_attributes(device_name):
    """Get all device attributes"""
    try:
        device = DeviceManager.get_device(device_name)
        attributes = DeviceManager.get_device_attributes(device)
        
        return jsonify({'attributes': attributes, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/attribute/<attr_name>', methods=['GET', 'POST'])
def handle_attribute(device_name, attr_name):
    """Read or write a specific attribute"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            attr = device.read_attribute(attr_name)
            return jsonify({
                'attribute': attr_name,
                'value': attr.value if hasattr(attr, 'value') else None,
                'quality': str(attr.quality),
                'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                'success': True
            })
        
        elif request.method == 'POST':
            _maybe_require_auth()
            data = request.get_json()
            value = data.get('value')
            
            if value is None:
                return jsonify({'error': 'No value provided', 'success': False}), 400
            
            device.write_attribute(attr_name, value)
            # Read back the attribute to confirm
            attr = device.read_attribute(attr_name)
            
            return jsonify({
                'attribute': attr_name,
                'value': attr.value if hasattr(attr, 'value') else None,
                'quality': str(attr.quality),
                'timestamp': attr.time.tv_sec if hasattr(attr, 'time') else None,
                'success': True
            })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/command/<command_name>', methods=['POST'])
def execute_command(device_name, command_name):
    """Execute a device command"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json() or {}
        args = data.get('args')
        
        if args is not None:
            result = device.command_inout(command_name, args)
        else:
            result = device.command_inout(command_name)

        # DS_Netio_pdu can return "success" even when hardware state does not change.
        # For set_channels_states, verify readback and surface mismatch as an API error.
        verified_states = None
        if str(command_name).lower() == "set_channels_states":
            requested_states = _coerce_binary_state_args(args)
            if requested_states is not None:
                matched, observed_states = _wait_for_pdu_states(device, requested_states)
                if not matched:
                    return jsonify({
                        'error': (
                            f"Command {command_name} executed, but readback states do not "
                            "match requested values."
                        ),
                        'command': command_name,
                        'requested_states': requested_states,
                        'observed_states': observed_states,
                        'success': False
                    }), 409
                verified_states = observed_states
        
        return jsonify({
            'command': command_name,
            'result': result,
            'verified_states': verified_states,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/state', methods=['GET'])
def get_device_state(device_name):
    """Get device state and status"""
    try:
        device = DeviceManager.get_device(device_name)
        return jsonify({
            'device': device_name,
            'state': str(device.state()),
            'status': device.status(),
            'timestamp': datetime.now().isoformat(),
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/<path:device_name>/properties', methods=['GET'])
def get_device_properties(device_name):
    """Get raw Tango device properties as a flat JSON object."""
    try:
        properties = DeviceManager.get_device_properties(device_name)

        properties['success'] = True
        return jsonify(properties)
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/device/<path:device_name>/pdu/outputs', methods=['GET'])
def get_pdu_outputs(device_name):
    """Read NETIO/PDU output table using normalized output objects."""
    try:
        device = DeviceManager.get_device(device_name)

        ids = _read_attr_sequence(device, 'ids')
        names = _read_attr_sequence(device, 'names')
        states = _read_attr_sequence(device, 'states')
        if not states:
            states = _read_attr_sequence(device, 'output_statuses')

        output_count = max(len(ids), len(names), len(states), 4)
        if not ids:
            ids = list(range(1, output_count + 1))

        outputs = []
        for idx in range(output_count):
            raw_id = ids[idx] if idx < len(ids) else idx + 1
            output_id = _as_int(raw_id, idx + 1)
            output_name = (
                str(names[idx])
                if idx < len(names) and names[idx] not in (None, "")
                else f"Output {output_id}"
            )
            raw_state = states[idx] if idx < len(states) else 0
            output_state = 1 if _as_int(raw_state, 0) else 0
            outputs.append({
                'id': output_id,
                'name': output_name,
                'state': output_state,
            })

        return jsonify({
            'device': device_name,
            'state': str(device.state()),
            'outputs': outputs,
            'success': True,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Device-specific endpoints for common PYCONLYSE devices
@device_api.route('/api/device/ds_itest_psu/<path:device_name>/slots', methods=['GET'])
def get_ds_itest_psu_slots(device_name):
    """Get all DS iTest PSU slot information"""
    try:
        device = DeviceManager.get_device(device_name)
        
        # Read all slot data including real slot IDs
        names = list(device.read_attribute('names').value)
        states = list(device.read_attribute('states').value)
        currents_meas = list(device.read_attribute('currents_meas').value)
        currents_setpoint = list(device.read_attribute('currents_setpoint').value)
        ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int for JSON serialization
        
        slots = []
        for i in range(len(names)):
            # Use actual slot ID instead of counter
            slot_id = ids[i] if i < len(ids) else i + 1
            slots.append({
                'id': slot_id,  # Real slot ID
                'index': i,     # Array index for reference
                'name': names[i] if i < len(names) else f'Slot {slot_id}',
                'state': bool(states[i]) if i < len(states) else False,
                'current_measured': make_json_safe(currents_meas[i]) if i < len(currents_meas) else 0.0,
                'current_setpoint': make_json_safe(currents_setpoint[i]) if i < len(currents_setpoint) else 0.0
            })
        
        return jsonify({
            'slots': slots,
            'slot_count': len(names),
            'available_slot_ids': ids,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/ds_itest_psu/<path:device_name>/tab_config', methods=['GET'])
def get_ds_itest_psu_tab_config(device_name):
    """Get tab configuration from Tango DB property 'tab_config'"""
    try:
        db = tango.Database()
        
        # Default configuration
        default_config = {
            'V0': {'slots': [], 'defaults': {}, 'enabled': True},
            'VD2': {'slots': [], 'defaults': {}, 'enabled': True},
            'REF': {'slots': [], 'defaults': {}, 'enabled': True},
            'ALL': {'slots': [], 'defaults': {}, 'enabled': True}
        }
        key_aliases = {
            'V0': 'V0',
            'VD': 'V0',
            'VD2': 'VD2',
            'REF': 'REF',
            'RF': 'REF',
            'ALL': 'ALL',
        }
        
        try:
            # Read tab_config property from Tango DB
            # Expected format: JSON string like:
            # {
            #   "V0": {"slots": [1, 2, 3], "defaults": {"1": 0.5, "2": 1.0}},
            #   "VD2": {"slots": [4, 5], "defaults": {"4": 2.0}},
            #   "REF": {"slots": [6, 7, 8], "defaults": {"6": 0.1}}
            # }
            prop_values = db.get_device_property(device_name, 'tab_config')
            
            if 'tab_config' in prop_values and prop_values['tab_config']:
                # Handle both single-line and multi-line property values
                raw_value = prop_values['tab_config']
                if isinstance(raw_value, (list, tuple)) or hasattr(raw_value, '__iter__'):
                    try:
                        # Multi-line property: join all lines (works for list, tuple, StdStringVector)
                        config_str = ''.join(line for line in raw_value)
                    except (TypeError, AttributeError):
                        config_str = str(raw_value)
                else:
                    config_str = str(raw_value)
                
                if config_str:
                    raw_config = json.loads(config_str)
                    normalized = {
                        tab_name: {
                            'slots': [],
                            'defaults': {},
                            'enabled': default_config[tab_name]['enabled'],
                        }
                        for tab_name in default_config
                    }

                    for raw_tab_name, tab_payload in raw_config.items():
                        canonical = key_aliases.get(str(raw_tab_name).upper())
                        if not canonical or not isinstance(tab_payload, dict):
                            continue

                        slots = []
                        for slot_id in tab_payload.get('slots', []):
                            parsed_slot = _as_int(slot_id, None)
                            if parsed_slot is not None and parsed_slot not in slots:
                                slots.append(parsed_slot)

                        defaults = {}
                        for slot_key, slot_value in (tab_payload.get('defaults', {}) or {}).items():
                            normalized_key = str(_as_int(slot_key, slot_key))
                            defaults[normalized_key] = slot_value

                        normalized[canonical] = {
                            'slots': slots,
                            'defaults': defaults,
                            'enabled': bool(tab_payload.get('enabled', True)),
                        }

                    return jsonify({'tab_configs': normalized, 'success': True})
        except Exception as e:
            print(f"Warning: Could not read tab_config property: {e}")
        
        # Return default config if property doesn't exist or is invalid
        return jsonify({'tab_configs': default_config, 'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/itest/<path:device_name>/all_slots', methods=['GET'])
def get_itest_all_slots(device_name):
    """Get all slot data for iTest PSU device"""
    try:
        device = DeviceManager.get_device(device_name)
        
        # Read all attributes
        ids = make_json_safe(device.read_attribute('ids').value)
        names = make_json_safe(device.read_attribute('names').value)
        states = make_json_safe(device.read_attribute('states').value)
        currents_setpoint = make_json_safe(device.read_attribute('currents_setpoint').value)
        currents_meas = make_json_safe(device.read_attribute('currents_meas').value)
        current_limits = make_json_safe(device.read_attribute('current_limits').value)
        
        return jsonify({
            'ids': ids,
            'names': names,
            'states': states,
            'currents_setpoint': currents_setpoint,
            'currents_meas': currents_meas,
            'current_limits': current_limits,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/output', methods=['POST'])
def set_itest_slot_output(device_name, slot_id):
    """Set output state for specific iTest PSU slot"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json()
        state = int(data.get('state', 0))
        
        # Use set_output_state command with [slot_id, state]
        device.command_inout('set_output_state', [int(slot_id), state])
        
        return jsonify({
            'slot_id': slot_id,
            'state': state,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/current', methods=['POST'])
def set_ds_itest_psu_current(device_name, slot_id):
    """Set current for specific DS iTest PSU slot with limit validation"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json()
        current_value = float(data.get('current', 0.0))
        
        # Get slot array index for validation
        ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int
        try:
            array_idx = ids.index(slot_id)
        except ValueError:
            return jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404
        
        # Validate current limits before setting
        try:
            limits_array = list(device.read_attribute('current_limits').value)
            if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                limits_idx = array_idx * 2
                min_limit = float(limits_array[limits_idx])
                max_limit = float(limits_array[limits_idx + 1])
                
                if current_value < min_limit or current_value > max_limit:
                    return jsonify({
                        'error': f'Current value {current_value}A is outside limits [{min_limit}, {max_limit}]A for slot {slot_id}',
                        'limits': {'min': min_limit, 'max': max_limit},
                        'slot_id': slot_id,
                        'success': False
                    }), 400
        except Exception as e:
            print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")
        
        # Use set_current command with [slot_id, value] - slot_id is the real slot ID
        device.command_inout('set_current', [float(slot_id), current_value])
        
        # Read back the setpoint array to confirm
        currents_setpoint = list(device.read_attribute('currents_setpoint').value)
        
        try:
            actual_value = currents_setpoint[array_idx] if array_idx < len(currents_setpoint) else current_value
        except ValueError:
            # Slot ID not found, return the requested value
            actual_value = current_value
        
        return jsonify({
            'slot_id': slot_id,
            'current_setpoint': actual_value,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/ds_itest_psu/<path:device_name>/slot/<int:slot_id>/state', methods=['POST'])
def set_ds_itest_psu_state(device_name, slot_id):
    """Set output state for specific DS iTest PSU slot"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json()
        enabled = bool(data.get('enabled', False))
        
        # Use set_output_state command with [slot_id, state] - slot_id is the real slot ID
        device.command_inout('set_output_state', [int(slot_id), int(1 if enabled else 0)])
        
        # Read back the states array to confirm - need to find array index
        ids = [int(x) for x in device.read_attribute('ids').value]  # Convert int64 to int
        states = list(device.read_attribute('states').value)
        
        try:
            array_idx = ids.index(slot_id)
            actual_state = bool(states[array_idx]) if array_idx < len(states) else enabled
        except ValueError:
            # Slot ID not found, return the requested state
            actual_state = enabled
        
        return jsonify({
            'slot_id': slot_id,
            'state': actual_state,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/itest/<path:device_name>/current', methods=['GET', 'POST'])
def handle_itest_current(device_name):
    """Handle iTest PSU current operations (legacy endpoint)"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            setpoint = device.read_attribute('CurrentSetpoint').value
            measured = device.read_attribute('MeasuredCurrent').value
            voltage = device.read_attribute('MeasuredVoltage').value
            
            # Try to get current limits if available
            limits = None
            try:
                limits_array = device.read_attribute('current_limits').value
                if limits_array and len(limits_array) >= 2:
                    # Assuming single channel device, take first pair
                    limits = {'min': float(limits_array[0]), 'max': float(limits_array[1])}
            except:
                # Fallback to default limits if attribute doesn't exist
                limits = {'min': -5.0, 'max': 15.0}
            
            return jsonify({
                'current_setpoint': make_json_safe(setpoint),
                'measured_current': make_json_safe(measured),
                'measured_voltage': make_json_safe(voltage),
                'current_limits': limits,
                'success': True
            })
        
        elif request.method == 'POST':
            _maybe_require_auth()
            data = request.get_json()
            action = data.get('action')
            value = data.get('value')
            
            # For set action, validate limits first
            if action == 'set' and value is not None:
                try:
                    limits_array = device.read_attribute('current_limits').value
                    if limits_array and len(limits_array) >= 2:
                        min_limit = float(limits_array[0])
                        max_limit = float(limits_array[1])
                        
                        if value < min_limit or value > max_limit:
                            return jsonify({
                                'error': f'Current value {value}A is outside limits [{min_limit}, {max_limit}]A',
                                'limits': {'min': min_limit, 'max': max_limit},
                                'success': False
                            }), 400
                except Exception as e:
                    # If we can't read limits, log but continue (fallback behavior)
                    print(f"Warning: Could not read current limits for {device_name}: {e}")
            
            if action == 'set':
                device.write_attribute('CurrentSetpoint', value)
            elif action == 'inc_fine':
                device.command_inout('IncCurrentFine')
            elif action == 'dec_fine':
                device.command_inout('DecCurrentFine')
            elif action == 'inc_coarse':
                device.command_inout('IncCurrentCoarse')
            elif action == 'dec_coarse':
                device.command_inout('DecCurrentCoarse')
            else:
                return jsonify({'error': 'Unknown action', 'success': False}), 400
            
            # Read back current value
            setpoint = device.read_attribute('CurrentSetpoint').value
            return jsonify({'current_setpoint': setpoint, 'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/itest/<path:device_name>/slot/<int:slot_id>/current', methods=['GET', 'POST'])
def handle_itest_slot_current(device_name, slot_id):
    """Handle iTest PSU current operations for specific slot with proper limits"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            # Read multi-slot arrays
            ids = [int(x) for x in device.read_attribute('ids').value]
            currents_setpoint = list(device.read_attribute('currents_setpoint').value)
            currents_meas = list(device.read_attribute('currents_meas').value)
            
            # Try to read voltage (may not be available on all devices)
            voltage = 0.0
            try:
                voltages = list(device.read_attribute('voltages_meas').value)
                array_idx = ids.index(slot_id)
                voltage = make_json_safe(voltages[array_idx]) if array_idx < len(voltages) else 0.0
            except:
                voltage = 0.0  # Default if voltage not available
            
            # Find array index for this slot
            try:
                array_idx = ids.index(slot_id)
            except ValueError:
                return jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404
            
            # Get current values for this slot
            current_setpoint = make_json_safe(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
            measured_current = make_json_safe(currents_meas[array_idx]) if array_idx < len(currents_meas) else 0.0
            
            # Get current limits for this slot
            limits = {'min': -5.0, 'max': 15.0}  # Default
            try:
                limits_array = list(device.read_attribute('current_limits').value)
                if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                    # Limits are stored as [min1, max1, min2, max2, ...]
                    limits_idx = array_idx * 2
                    limits = {
                        'min': float(limits_array[limits_idx]),
                        'max': float(limits_array[limits_idx + 1])
                    }
            except Exception as e:
                print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")
            
            return jsonify({
                'slot_id': slot_id,
                'current_setpoint': current_setpoint,
                'measured_current': measured_current,
                'measured_voltage': make_json_safe(voltage),
                'current_limits': limits,
                'success': True
            })
        
        elif request.method == 'POST':
            _maybe_require_auth()
            data = request.get_json() or {}
            action = data.get('action')
            value = data.get('value')
            if value is None and data.get('current') is not None:
                value = data.get('current')
            if action is None and value is not None:
                action = 'set'
            
            # Get slot array index
            ids = [int(x) for x in device.read_attribute('ids').value]
            try:
                array_idx = ids.index(slot_id)
            except ValueError:
                return jsonify({'error': f'Slot {slot_id} not found', 'success': False}), 404
            
            # For set action, validate limits first
            if action == 'set' and value is not None:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    return jsonify({'error': 'value must be numeric', 'success': False}), 400
                try:
                    limits_array = list(device.read_attribute('current_limits').value)
                    if limits_array and len(limits_array) >= (array_idx + 1) * 2:
                        limits_idx = array_idx * 2
                        min_limit = float(limits_array[limits_idx])
                        max_limit = float(limits_array[limits_idx + 1])
                        
                        if value < min_limit or value > max_limit:
                            return jsonify({
                                'error': f'Current value {value}A is outside limits [{min_limit}, {max_limit}]A for slot {slot_id}',
                                'limits': {'min': min_limit, 'max': max_limit},
                                'slot_id': slot_id,
                                'success': False
                            }), 400
                except Exception as e:
                    print(f"Warning: Could not read current limits for {device_name} slot {slot_id}: {e}")
            
            if action == 'set':
                # Use set_current command with [slot_id, value]
                device.command_inout('set_current', [float(slot_id), float(value)])
            elif action == 'inc_fine':
                # Get current setpoint and increment by 0.01A
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                new_val = current_val + 0.01
                device.command_inout('set_current', [float(slot_id), new_val])
            elif action == 'dec_fine':
                # Get current setpoint and decrement by 0.01A
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                new_val = current_val - 0.01
                device.command_inout('set_current', [float(slot_id), new_val])
            elif action == 'inc_coarse':
                # Get current setpoint and increment by 0.1A
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                new_val = current_val + 0.1
                device.command_inout('set_current', [float(slot_id), new_val])
            elif action == 'dec_coarse':
                # Get current setpoint and decrement by 0.1A
                currents_setpoint = list(device.read_attribute('currents_setpoint').value)
                current_val = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
                new_val = current_val - 0.1
                device.command_inout('set_current', [float(slot_id), new_val])
            else:
                return jsonify({'error': 'Unknown action', 'success': False}), 400
            
            # Read back current value for this slot
            currents_setpoint = list(device.read_attribute('currents_setpoint').value)
            current_setpoint = float(currents_setpoint[array_idx]) if array_idx < len(currents_setpoint) else 0.0
            
            return jsonify({
                'slot_id': slot_id,
                'current_setpoint': current_setpoint,
                'success': True
            })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/device/camera/<path:device_name>/capture', methods=['POST'])
def camera_capture(device_name):
    """Trigger camera capture"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json() or {}
        
        exposure_time = data.get('exposure_time', 1.0)
        
        # Set exposure time if provided
        if 'exposure_time' in data:
            device.write_attribute('ExposureTime', exposure_time)
        
        # Trigger capture
        result = device.command_inout('StartAcquisition')
        
        return jsonify({
            'command': 'StartAcquisition',
            'exposure_time': exposure_time,
            'result': result,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# DAQmx / Supervision endpoints
@device_api.route('/api/daqmx/devices', methods=['GET'])
def list_daqmx_devices():
    """List DAQmx-related Tango devices (ZMQ reader and PSP supervision readers)."""
    try:
        db = tango.Database()
        seen = set()
        devices = []
        probe_state = _query_bool('probe_state', True)

        for class_name in DAQMX_DEVICE_CLASSES:
            try:
                class_devices = db.get_device_name('*', class_name)
            except Exception:
                continue

            for device_name in class_devices:
                device_name = str(device_name)
                if device_name in seen:
                    continue
                seen.add(device_name)

                state = 'UNKNOWN'
                available = True
                if probe_state:
                    try:
                        state = str(DeviceManager.get_device(device_name).state())
                    except Exception:
                        available = False

                devices.append({
                    'name': device_name,
                    'class': class_name,
                    'state': state,
                    'available': available,
                })

        devices.sort(key=lambda item: item['name'])
        return jsonify({'devices': devices, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/psp/devices', methods=['GET'])
def list_psp_devices():
    """List DS_PSP devices available in Tango DB."""
    try:
        db = tango.Database()
        probe_state = _query_bool('probe_state', True)
        names = []
        try:
            names = db.get_device_name('*', 'DS_PSP')
        except Exception:
            names = []

        devices = []
        for device_name in names:
            device_name = str(device_name)
            state = 'UNKNOWN'
            available = True
            if probe_state:
                try:
                    state = str(DeviceManager.get_device(device_name).state())
                except Exception:
                    available = False

            devices.append({
                'name': device_name,
                'class': 'DS_PSP',
                'state': state,
                'available': available,
            })

        devices.sort(key=lambda item: item['name'])
        return jsonify({'devices': devices, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/psp/device/<path:device_name>/group/<group_name>/history', methods=['GET'])
def get_psp_group_history(device_name, group_name):
    """Read PSP FIFO history for one group and return graph-ready series."""
    try:
        device = DeviceManager.get_device(device_name)
        seconds = max(0.0, float(request.args.get('seconds', 1800.0)))
        limit = max(1, int(request.args.get('limit', 5000)))
        group = _normalize_psp_group(group_name)

        history = _read_psp_group_history(device, group, seconds, limit)
        series, latest = _build_psp_series(history)

        return jsonify({
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
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/psp/device/<path:device_name>/commands/pending', methods=['GET'])
def get_psp_pending_commands(device_name):
    """Read pending outbound commands queued for LabVIEW bridge."""
    try:
        device = DeviceManager.get_device(device_name)
        commands = _list_device_commands_lower(device)
        limit = max(1, int(request.args.get('limit', 200)))
        pop = _query_bool('pop', False)

        cmd_name = commands.get('pop_pending_commands_json') if pop else commands.get('get_pending_commands_json')
        if not cmd_name:
            return jsonify({'error': 'Device does not support pending command queue', 'success': False}), 400

        raw = device.command_inout(cmd_name, limit)
        payload = _safe_json_loads(raw, default={})
        if not isinstance(payload, dict):
            payload = {}

        items = payload.get('items', [])
        if not isinstance(items, list):
            items = []
        pending_count = _as_int(payload.get('pending_count'), len(items))

        return jsonify({
            'device': device_name,
            'pending_count': pending_count,
            'items': make_json_safe(items),
            'popped': bool(pop),
            'success': True,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/psp/device/<path:device_name>/commands/ack', methods=['POST'])
def acknowledge_psp_command(device_name):
    """Store LabVIEW execution acknowledgment for one queued command."""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        commands = _list_device_commands_lower(device)
        cmd_name = commands.get('acknowledge_command_json')
        if not cmd_name:
            return jsonify({'error': 'Device does not support command acknowledgments', 'success': False}), 400

        data = request.get_json() or {}
        raw = device.command_inout(cmd_name, json.dumps(data))
        payload = _safe_json_loads(raw, default={})
        if not isinstance(payload, dict):
            payload = {'raw': make_json_safe(raw)}

        return jsonify({'device': device_name, **make_json_safe(payload), 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/daqmx/device/<path:device_name>/latest', methods=['GET'])
def get_daqmx_latest(device_name):
    """Get latest DAQmx/PSP data payload and normalized channel list."""
    try:
        device = DeviceManager.get_device(device_name)
        payload = _read_daqmx_latest_payload(device)
        channels = _normalize_daqmx_channels(payload)

        return jsonify({
            'device': device_name,
            'state': str(device.state()),
            'latest': payload,
            'channels': channels,
            'channel_count': len(channels),
            'success': True,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/daqmx/device/<path:device_name>/history', methods=['GET'])
def get_daqmx_history(device_name):
    """Get DAQmx history if the device supports get_history_json(seconds)."""
    try:
        device = DeviceManager.get_device(device_name)
        seconds = float(request.args.get('seconds', 10.0))
        commands = _list_device_commands_lower(device)
        cmd = commands.get('get_history_json')
        if not cmd:
            return jsonify({
                'error': 'History is not supported by this device',
                'success': False,
            }), 400

        raw = device.command_inout(cmd, seconds)
        history = _safe_json_loads(raw, default=[])
        if not isinstance(history, list):
            history = []

        return jsonify({
            'device': device_name,
            'seconds': seconds,
            'history': history,
            'sample_count': len(history),
            'success': True,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500


@device_api.route('/api/daqmx/device/<path:device_name>/write', methods=['POST'])
def write_daqmx_channel(device_name):
    """Write one channel/variable value via DAQmx/PSP write command."""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        data = request.get_json() or {}
        channel = data.get('channel') or data.get('name') or data.get('variable')
        value = data.get('value')

        if channel in (None, ''):
            return jsonify({'error': 'channel is required', 'success': False}), 400
        if value is None:
            return jsonify({'error': 'value is required', 'success': False}), 400

        result = _write_daqmx_channel(device, channel, value)
        return jsonify({
            'device': device_name,
            'channel': str(channel),
            'value': _to_scalar_value(value),
            'result': make_json_safe(result),
            'success': True,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Camera-specific endpoints
@device_api.route('/api/cameras', methods=['GET'])
def list_cameras():
    """Get list of all available camera devices - fast query from Tango DB"""
    try:
        db = tango.Database()
        
        # Query Tango DB for camera device classes directly (much faster!)
        camera_classes = ['DS_Basler_camera', 'DS_ANDOR_CCD', 'DS_AVANTES_CCD']
        camera_list = []
        
        for dev_class in camera_classes:
            try:
                # Get all devices of this class from Tango DB
                device_list = db.get_device_name('*', dev_class)
                
                for device_name in device_list:
                    try:
                        device = tango.DeviceProxy(device_name)
                        state = str(device.state())
                        
                        camera_info = {
                            'name': device_name,
                            'state': state,
                            'class': dev_class,
                            'available': True
                        }
                        
                        # Try to get camera-specific info (non-blocking)
                        try:
                            camera_info['serial_number'] = str(device.read_attribute('camera_serial_number').value)
                        except:
                            pass
                        
                        try:
                            camera_info['model_name'] = str(device.read_attribute('camera_model_name').value)
                        except:
                            pass
                        
                        try:
                            camera_info['friendly_name'] = str(device.read_attribute('device_friendly_name').value)
                        except:
                            pass
                        
                        camera_list.append(camera_info)
                    except Exception as e:
                        # Device exists in DB but may not be running
                        camera_list.append({
                            'name': device_name,
                            'state': 'UNKNOWN',
                            'class': dev_class,
                            'available': False,
                            'error': str(e)
                        })
            except Exception as e:
                # Class not found or other error
                print(f"No devices found for class {dev_class}: {e}")
        
        return jsonify({'cameras': camera_list, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/info', methods=['GET'])
def get_camera_info(device_name):
    """Get detailed camera information"""
    try:
        device = DeviceManager.get_device(device_name)
        
        info = {
            'name': device_name,
            'state': str(device.state()),
            'status': device.status(),
        }
        
        # Camera-specific attributes
        camera_attrs = [
            'camera_serial_number', 'camera_model_name', 'device_friendly_name',
            'exposure_time', 'exposure_min', 'exposure_max',
            'gain', 'gain_min', 'gain_max',
            'width', 'width_min', 'width_max',
            'height', 'height_min', 'height_max',
            'offsetX', 'offsetY',
            'format_pixel', 'framerate', 'isgrabbing',
            'binning_horizontal', 'binning_vertical',
            'trigger_mode', 'trigger_delay',
            'cg', 'number_kinetics', 'track_count',
            'wavelengths_axis', 'temperature_current',
            'temperature_target', 'temperature_status',
            'cooler_on', 'linked_spectrograph_device'
        ]
        
        for attr_name in camera_attrs:
            try:
                attr = device.read_attribute(attr_name)
                info[attr_name] = make_json_safe(attr.value)
            except:
                pass
        
        return jsonify({'camera_info': info, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/parameters', methods=['GET', 'POST'])
def handle_camera_parameters(device_name):
    """Get or set camera parameters"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            parameters = {}
            param_names = ['exposure_time', 'gain', 'width', 'height', 'offsetX', 'offsetY', 
                          'format_pixel', 'trigger_mode', 'trigger_delay', 'binning_horizontal', 'binning_vertical',
                          'number_kinetics']
            
            for param in param_names:
                try:
                    attr = device.read_attribute(param)
                    parameters[param] = make_json_safe(attr.value)
                except:
                    pass
            
            return jsonify({'parameters': parameters, 'success': True})
        
        elif request.method == 'POST':
            _maybe_require_auth()
            data = request.get_json()
            results = {}
            
            for param_name, param_value in data.items():
                try:
                    device.write_attribute(param_name, param_value)
                    # Read back to confirm
                    attr = device.read_attribute(param_name)
                    results[param_name] = {'success': True, 'value': make_json_safe(attr.value)}
                except Exception as e:
                    results[param_name] = {'success': False, 'error': str(e)}
            
            return jsonify({'results': results, 'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/grabbing', methods=['GET', 'POST'])
def handle_camera_grabbing(device_name):
    """Control camera grabbing (start/stop)"""
    try:
        device = DeviceManager.get_device(device_name)
        
        if request.method == 'GET':
            is_grabbing = _read_camera_is_grabbing(device)
            return jsonify({
                'grabbing': is_grabbing,
                'success': True
            })
        
        elif request.method == 'POST':
            _maybe_require_auth()
            data = request.get_json()
            action = data.get('action')  # 'start' or 'stop'
            
            if action == 'start':
                command_name = _resolve_command_name(
                    device,
                    ['start_grabbing', 'startgrabbing', 'StartGrabbing', 'start', 'on']
                )
                device.command_inout(command_name)
                expected_grabbing = True
                message = f'Grabbing start command sent ({command_name})'
            elif action == 'stop':
                command_name = _resolve_command_name(
                    device,
                    ['stop_grabbing', 'stopgrabbing', 'StopGrabbing', 'stop', 'off']
                )
                device.command_inout(command_name)
                expected_grabbing = False
                message = f'Grabbing stop command sent ({command_name})'
            else:
                return jsonify({'error': 'Invalid action. Use "start" or "stop"', 'success': False}), 400
            
            # Confirm status with short polling to avoid stale immediate readback.
            is_grabbing, state_confirmed = _wait_for_camera_grabbing(
                device,
                expected_state=expected_grabbing,
            )
            
            return jsonify({
                'message': message,
                'grabbing': is_grabbing,
                'expected_grabbing': expected_grabbing,
                'state_confirmed': state_confirmed,
                'success': True
            })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/image', methods=['GET'])
def get_camera_image(device_name):
    """Get the last captured image from camera"""
    try:
        device = DeviceManager.get_device(device_name)
        
        # Read image attribute
        image_attr = device.read_attribute('image')
        image_data = image_attr.value
        
        if image_data is None:
            return jsonify({'error': 'No image available', 'success': False}), 404
        
        # Get center of gravity if available
        cg_position = None
        try:
            cg_str = str(device.read_attribute('cg').value)
            import ast
            cg_position = ast.literal_eval(cg_str)
        except:
            pass
        
        return jsonify({
            'image': make_json_safe(image_data),
            'cg_position': cg_position,
            'timestamp': image_attr.time.tv_sec if hasattr(image_attr, 'time') else None,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrographs', methods=['GET'])
def list_spectrographs():
    """Get list of Andor spectrograph devices directly from Tango DB."""
    try:
        db = tango.Database()
        spectro_classes = ['DS_ANDOR_SPECTROGRAPH']
        spectrograph_list = []

        for dev_class in spectro_classes:
            try:
                device_list = db.get_device_name('*', dev_class)
                for device_name in device_list:
                    try:
                        device = tango.DeviceProxy(device_name)
                        info = {
                            'name': device_name,
                            'state': str(device.state()),
                            'class': dev_class,
                            'available': True,
                        }
                        try:
                            info['friendly_name'] = str(device.read_attribute('device_friendly_name').value)
                        except Exception:
                            pass
                        try:
                            info['serial_number'] = str(device.read_attribute('serial_number').value)
                        except Exception:
                            pass
                        spectrograph_list.append(info)
                    except Exception as exc:
                        spectrograph_list.append({
                            'name': device_name,
                            'state': 'UNKNOWN',
                            'class': dev_class,
                            'available': False,
                            'error': str(exc),
                        })
            except Exception as exc:
                print(f"No devices found for class {dev_class}: {exc}")

        return jsonify({'spectrographs': spectrograph_list, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrograph/<path:device_name>/info', methods=['GET'])
def get_spectrograph_info(device_name):
    """Get detailed spectrograph information."""
    try:
        device = DeviceManager.get_device(device_name)
        info = {
            'name': device_name,
            'state': str(device.state()),
            'status': device.status(),
        }

        attr_names = [
            'device_friendly_name', 'serial_number', 'wavelength_nm',
            'grating', 'gratings_number', 'pixel_number_attr',
            'pixel_width_um_attr', 'input_side_slit_um',
            'output_side_slit_um', 'input_direct_slit_um',
            'output_direct_slit_um', 'calibration',
            'lines_per_mm', 'blaze_wavelength_nm',
        ]
        for attr_name in attr_names:
            try:
                attr = device.read_attribute(attr_name)
                info[attr_name] = make_json_safe(attr.value)
            except Exception:
                pass

        return jsonify({'spectrograph_info': info, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/spectrograph/<path:device_name>/parameters', methods=['GET', 'POST'])
def handle_spectrograph_parameters(device_name):
    """Get or set spectrograph parameters."""
    try:
        device = DeviceManager.get_device(device_name)

        if request.method == 'GET':
            parameters = {}
            attr_names = [
                'wavelength_nm', 'grating', 'pixel_number_attr',
                'pixel_width_um_attr', 'input_side_slit_um',
                'output_side_slit_um', 'input_direct_slit_um',
                'output_direct_slit_um',
            ]
            for attr_name in attr_names:
                try:
                    attr = device.read_attribute(attr_name)
                    parameters[attr_name] = make_json_safe(attr.value)
                except Exception:
                    pass
            return jsonify({'parameters': parameters, 'success': True})

        _maybe_require_auth()
        data = request.get_json()
        results = {}
        for param_name, param_value in data.items():
            try:
                device.write_attribute(param_name, param_value)
                attr = device.read_attribute(param_name)
                results[param_name] = {'success': True, 'value': make_json_safe(attr.value)}
            except Exception as exc:
                results[param_name] = {'success': False, 'error': str(exc)}

        return jsonify({'results': results, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@device_api.route('/api/camera/<path:device_name>/trigger', methods=['POST'])
def trigger_camera(device_name):
    """Trigger camera software trigger"""
    try:
        _maybe_require_auth()
        device = DeviceManager.get_device(device_name)
        
        # Execute software trigger if supported
        try:
            device.command_inout('TriggerSoftware')
            message = 'Software trigger executed'
        except:
            # Fallback to generic trigger
            device.command_inout('Trigger')
            message = 'Trigger executed'
        
        return jsonify({
            'message': message,
            'success': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

# Error handling
@device_api.errorhandler(Exception)
def handle_device_error(error):
    """Global error handler for device API"""
    return jsonify({
        'error': str(error),
        'traceback': traceback.format_exc(),
        'success': False
    }), 500
