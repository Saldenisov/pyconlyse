"""Fail-closed authorization for hardware-changing web operations.

Approvals are deliberately created outside the web application.  The service
only reads a trusted approval file and atomically records its one permitted
use before a caller can obtain a Tango proxy.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity


_NONCE_RE = re.compile(r"[0-9a-f]{64}\Z")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_MAX_APPROVAL_TTL_SECONDS = 300
_MAX_AUTH_JSON_BYTES = 1024 * 1024
_MAX_SCHEMA_ITEMS = 4096
_MAX_SCHEMA_STRING_LENGTH = 4096


class AuthorizationError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AuthorizationConfig:
    policy_path: Path
    approval_dir: Path
    consumed_dir: Path
    strict: bool = False
    require_readonly_approvals: bool = False

    @classmethod
    def from_environment(cls, environ=None, repository_root=None):
        environ = os.environ if environ is None else environ
        repository_root = Path(repository_root or _REPOSITORY_ROOT).resolve()
        names = {
            "policy_path": "PYCONLYSE_HARDWARE_POLICY_PATH",
            "approval_dir": "PYCONLYSE_HARDWARE_APPROVAL_DIR",
            "consumed_dir": "PYCONLYSE_HARDWARE_CONSUMED_DIR",
        }
        paths = {}
        for key, name in names.items():
            value = str(environ.get(name, "")).strip()
            if not value:
                raise AuthorizationError(403, "hardware_not_authorized", f"{name} is required")
            path = Path(value)
            if not path.is_absolute():
                raise AuthorizationError(403, "hardware_not_authorized", f"{name} must be absolute")
            resolved = path.resolve()
            try:
                resolved.relative_to(repository_root)
            except ValueError:
                paths[key] = resolved
                continue
            raise AuthorizationError(403, "hardware_not_authorized", f"{name} must be outside the repository")
        return cls(strict=True, **paths)


@dataclass(frozen=True)
class Operation:
    method: str
    route_id: str
    action: str
    targets: tuple[Mapping[str, str], ...]
    args: Any


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError(f"Non-finite JSON value: {value}")


def _load_json(path: Path) -> Any:
    try:
        return _read_regular_json(path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Authorization JSON is invalid") from exc


def _read_regular_json(path: Path, *, require_readonly: bool = False) -> Any:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or (require_readonly and os.access(path, os.W_OK)):
        raise ValueError("invalid authorization file")
    descriptor = os.open(str(path), flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or (before.st_dev, before.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError("invalid authorization file")
        if metadata.st_size < 0 or metadata.st_size > _MAX_AUTH_JSON_BYTES:
            raise ValueError("authorization file is too large")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(_MAX_AUTH_JSON_BYTES + 1)
        if len(raw) > _MAX_AUTH_JSON_BYTES:
            raise ValueError("authorization file is too large")
        return _parse_json(raw.decode("utf-8"))
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _parse_json(raw: str) -> Any:
    return json.loads(raw, object_pairs_hook=_reject_duplicates, parse_constant=_reject_nonfinite)


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Authorization values must be finite JSON") from exc


def _is_external_directory(path: Path) -> bool:
    try:
        path.resolve().relative_to(_REPOSITORY_ROOT)
    except ValueError:
        return path.is_absolute() and path.is_dir()
    return False


def _is_external_file(path: Path) -> bool:
    try:
        path.resolve().relative_to(_REPOSITORY_ROOT)
    except ValueError:
        return path.is_absolute() and path.is_file() and not path.is_symlink()
    return False


def authorization_required(environ=None) -> bool:
    environ = os.environ if environ is None else environ
    def enabled(name):
        return str(environ.get(name, "")).strip().lower() in {"1", "true", "yes", "y", "on"}
    return enabled("PYCONLYSE_PRODUCTION") or enabled("PYCONLYSE_ENFORCE_DEVICE_AUTH")


def authorization_config_from_environment(environ=None) -> AuthorizationConfig:
    environ = os.environ if environ is None else environ
    config = AuthorizationConfig.from_environment(environ)
    if not _is_external_file(config.policy_path):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy path must be an existing absolute file outside the repository")
    if not _is_external_directory(config.approval_dir):
        raise AuthorizationError(403, "hardware_not_authorized", "Approval directory must be an existing absolute directory outside the repository")
    if not _is_external_directory(config.consumed_dir) or config.consumed_dir.resolve() == config.approval_dir.resolve():
        raise AuthorizationError(403, "hardware_not_authorized", "Consumed directory must be a distinct existing absolute directory outside the repository")
    required = authorization_required(environ)
    if required and os.access(config.policy_path, os.W_OK):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy must not be writable by the web service")
    if required and os.access(config.policy_path.parent, os.W_OK):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy directory must not be writable by the web service")
    if required and os.access(config.approval_dir, os.W_OK):
        raise AuthorizationError(403, "hardware_not_authorized", "Approval directory must not be writable by the web service")
    if required and not os.access(config.consumed_dir, os.W_OK):
        raise AuthorizationError(403, "hardware_not_authorized", "Consumed directory must be writable by the web service")
    if required:
        try:
            approvals = tuple(config.approval_dir.iterdir())
        except OSError as exc:
            raise AuthorizationError(403, "hardware_not_authorized", "Approval directory is invalid") from exc
        for approval in approvals:
            if approval.is_symlink() or not approval.is_file() or os.access(approval, os.W_OK):
                raise AuthorizationError(403, "hardware_not_authorized", "Approval files must not be writable by the web service")
    load_policy(config.policy_path, strict=True)
    return AuthorizationConfig(
        policy_path=config.policy_path,
        approval_dir=config.approval_dir,
        consumed_dir=config.consumed_dir,
        strict=True,
        require_readonly_approvals=required,
    )


def load_policy(path: Path, *, strict: bool = False) -> Mapping[str, Any]:
    try:
        policy = _load_json(Path(path))
    except AuthorizationError as exc:
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy JSON is invalid") from exc
    if not isinstance(policy, dict) or not isinstance(policy.get("roles"), dict) or not isinstance(policy.get("operations"), list):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy must define roles and operations")
    if set(policy) - {"version", "subjects", "roles", "operations", "starter_servers"}:
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy contains unknown fields")
    if strict and (
        type(policy.get("version")) is not int
        or policy["version"] != 1
        or not isinstance(policy.get("subjects"), dict)
    ):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy must define version 1 and subjects")
    if strict:
        for subject, roles in policy["subjects"].items():
            values = roles.get("roles") if isinstance(roles, Mapping) else None
            if not isinstance(subject, str) or not subject.strip() or "*" in subject or not isinstance(roles, Mapping) or set(roles) != {"roles"} or not isinstance(values, list) or not values or not all(isinstance(role, str) and role.strip() and "*" not in role and role in policy["roles"] for role in values) or len(set(values)) != len(values):
                raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy subjects must define known server-side roles")
        for role, permissions in policy["roles"].items():
            if not isinstance(role, str) or not role.strip() or "*" in role or not isinstance(permissions, Mapping):
                raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy roles are invalid")
            for route_id, actions in permissions.items():
                if not isinstance(route_id, str) or not route_id.strip() or "*" in route_id or not isinstance(actions, list) or not actions or not all(isinstance(action, str) and action.strip() and "*" not in action for action in actions) or len(set(actions)) != len(actions):
                    raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy permissions are invalid")
        starter_servers = policy.get("starter_servers", {})
        if not isinstance(starter_servers, Mapping):
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware starter mapping is invalid")
        for server_name, starter_name in starter_servers.items():
            if not isinstance(server_name, str) or not server_name.strip() or "*" in server_name or not isinstance(starter_name, str) or not starter_name.strip() or "*" in starter_name or not starter_name.lower().startswith("tango/admin/"):
                raise AuthorizationError(403, "hardware_not_authorized", "Hardware starter mapping is invalid")
    signatures = set()
    for operation in policy["operations"]:
        if not isinstance(operation, dict):
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy operation must be an object")
        required = {"route_id", "action", "targets", "args"}
        if strict:
            required.add("method")
        if not required.issubset(operation):
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy operation is incomplete")
        if strict and set(operation) - {"method", "route_id", "action", "targets", "args", "roles"}:
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy operation contains unknown fields")
        if strict and (not isinstance(operation["method"], str) or operation["method"] not in {"POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"} or not isinstance(operation["route_id"], str) or not operation["route_id"].strip() or "*" in operation["route_id"] or not isinstance(operation["action"], str) or not operation["action"].strip() or "*" in operation["action"]):
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy operation identifiers are invalid")
        try:
            targets = _normalize_targets(operation.get("targets"))
        except AuthorizationError as exc:
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy targets are invalid") from exc
        if strict:
            roles = operation.get("roles")
            if not isinstance(roles, list) or not roles or not all(isinstance(role, str) and role.strip() and "*" not in role and role in policy["roles"] for role in roles) or len(set(roles)) != len(roles):
                raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy operation roles are invalid")
            signature = (operation["method"], operation["route_id"], operation["action"], _canonical(targets))
            if signature in signatures:
                raise AuthorizationError(403, "hardware_not_authorized", "Hardware policy contains ambiguous duplicate operations")
            signatures.add(signature)
        _validate_schema(operation.get("args"), strict=strict)
    return policy


def _normalize_targets(targets: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(targets, (list, tuple)) or not targets:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware targets must be a non-empty ordered list")
    normalized = []
    for target in targets:
        if not isinstance(target, Mapping) or set(target) != {"device", "command"}:
            raise AuthorizationError(409, "hardware_approval_invalid", "Each hardware target must contain exactly device and command")
        device, command = target["device"], target["command"]
        if not isinstance(device, str) or not isinstance(command, str) or not device.strip() or not command.strip() or "*" in device or "*" in command:
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware targets must be exact non-wildcard strings")
        normalized.append({"device": device, "command": command})
    return tuple(normalized)


def _validate_schema(schema: Any, *, strict: bool) -> None:
    if schema == {"kind": "none"} or schema is None:
        return
    if not isinstance(schema, Mapping):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware argument schema must be an object")
    if "type" not in schema:
        # Legacy concise object schema remains parseable for tests; production
        # policy requires the explicit closed-object form below.
        if strict:
            raise AuthorizationError(403, "hardware_not_authorized", "Hardware argument schema must declare type")
        for child in schema.values():
            _validate_schema(child, strict=False)
        return
    kind = schema["type"]
    if kind not in {"object", "array", "number", "integer", "string", "boolean"}:
        raise AuthorizationError(403, "hardware_not_authorized", "Unsupported hardware argument schema type")
    if kind == "object":
        if strict and set(schema) - {"type", "properties", "required", "additionalProperties"}:
            raise AuthorizationError(403, "hardware_not_authorized", "Object schema contains unknown fields")
        if schema.get("additionalProperties") is not False or not isinstance(schema.get("properties"), Mapping):
            raise AuthorizationError(403, "hardware_not_authorized", "Object schemas must be closed and define properties")
        properties = schema["properties"]
        if not all(isinstance(name, str) and name for name in properties):
            raise AuthorizationError(403, "hardware_not_authorized", "Object schema properties are invalid")
        required = schema.get("required", list(properties))
        if not isinstance(required, list) or not all(isinstance(name, str) and name in properties for name in required) or len(set(required)) != len(required):
            raise AuthorizationError(403, "hardware_not_authorized", "Object schema required keys are invalid")
        for child in properties.values():
            _validate_schema(child, strict=strict)
    elif kind == "array":
        if strict and set(schema) - {"type", "items", "min_items", "max_items"}:
            raise AuthorizationError(403, "hardware_not_authorized", "Array schema contains unknown fields")
        if not isinstance(schema.get("items"), Mapping) or not isinstance(schema.get("min_items"), int) or not isinstance(schema.get("max_items"), int):
            if strict:
                raise AuthorizationError(403, "hardware_not_authorized", "Array schemas require bounded items")
            _validate_schema(schema.get("items"), strict=False)
            return
        if schema["min_items"] < 0 or schema["max_items"] < schema["min_items"] or schema["max_items"] > _MAX_SCHEMA_ITEMS:
            raise AuthorizationError(403, "hardware_not_authorized", "Array schema bounds are invalid")
        _validate_schema(schema["items"], strict=strict)
    elif kind in {"number", "integer"}:
        if strict and set(schema) - {"type", "minimum", "maximum"}:
            raise AuthorizationError(403, "hardware_not_authorized", "Numeric schema contains unknown fields")
        if not all(isinstance(schema.get(name), (int, float)) and math.isfinite(float(schema[name])) for name in ("minimum", "maximum")):
            if strict:
                raise AuthorizationError(403, "hardware_not_authorized", "Numeric schemas require finite bounds")
            return
        if float(schema["maximum"]) < float(schema["minimum"]):
            raise AuthorizationError(403, "hardware_not_authorized", "Numeric schema bounds are invalid")
    elif kind == "string":
        if strict and set(schema) - {"type", "enum", "min_length", "max_length", "pattern"}:
            raise AuthorizationError(403, "hardware_not_authorized", "String schema contains unknown fields")
        enum = schema.get("enum")
        if enum is not None:
            if set(schema) - {"type", "enum"} or not isinstance(enum, list) or not enum or not all(isinstance(value, str) for value in enum) or len(set(enum)) != len(enum):
                raise AuthorizationError(403, "hardware_not_authorized", "String schemas require a non-empty enumeration")
        else:
            if not isinstance(schema.get("min_length"), int) or not isinstance(schema.get("max_length"), int) or schema["min_length"] < 0 or schema["max_length"] < schema["min_length"] or schema["max_length"] > _MAX_SCHEMA_STRING_LENGTH:
                raise AuthorizationError(403, "hardware_not_authorized", "String schema bounds are invalid")
            pattern = schema.get("pattern")
            if pattern is not None:
                if not isinstance(pattern, str) or not pattern or len(pattern) > 512:
                    raise AuthorizationError(403, "hardware_not_authorized", "String schema pattern is invalid")
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise AuthorizationError(403, "hardware_not_authorized", "String schema pattern is invalid") from exc
    elif strict and set(schema) != {"type"}:
        raise AuthorizationError(403, "hardware_not_authorized", "Boolean schema contains unknown fields")


def _normalize_args(value: Any, schema: Any, *, strict: bool) -> Any:
    if schema == {"kind": "none"} or schema is None:
        if value is not None:
            raise AuthorizationError(409, "hardware_approval_invalid", "This operation accepts no arguments")
        return None
    if not isinstance(schema, Mapping):
        raise AuthorizationError(409, "hardware_approval_invalid", "Invalid hardware argument schema")
    if "type" not in schema:
        if not isinstance(value, Mapping) or set(value) != set(schema):
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware arguments must contain exactly the approved keys")
        return {key: _normalize_args(value[key], child, strict=False) for key, child in schema.items()}
    kind = schema["type"]
    if kind == "object":
        properties = schema["properties"]
        required = set(schema.get("required", properties))
        if not isinstance(value, Mapping) or not required.issubset(value) or set(value) - set(properties):
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware arguments must contain exactly the approved keys")
        return {key: _normalize_args(value[key], properties[key], strict=strict) for key in value}
    if kind == "array":
        min_items, max_items = schema.get("min_items", 0), schema.get("max_items", len(value) if isinstance(value, list) else 0)
        if not isinstance(value, list) or not min_items <= len(value) <= max_items:
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware argument array is outside approved bounds")
        return [_normalize_args(item, schema["items"], strict=strict) for item in value]
    if kind == "boolean":
        if type(value) is not bool:
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware argument must be boolean")
        return value
    if kind == "string":
        if not isinstance(value, str):
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware string argument is not approved")
        enum = schema.get("enum")
        if enum is not None:
            if value not in enum:
                raise AuthorizationError(409, "hardware_approval_invalid", "Hardware string argument is not approved")
            return value
        if not schema["min_length"] <= len(value) <= schema["max_length"]:
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware string argument is not approved")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware string argument is not approved")
        return value
    if kind == "integer":
        if type(value) is not int or ("minimum" in schema and not schema["minimum"] <= value <= schema["maximum"]):
            raise AuthorizationError(409, "hardware_approval_invalid", "Hardware integer argument is outside approved bounds")
        return value
    if type(value) not in {int, float} or isinstance(value, bool) or not math.isfinite(float(value)) or ("minimum" in schema and not schema["minimum"] <= float(value) <= schema["maximum"]):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware number argument is outside approved bounds")
    return float(value)


def _matching_policy_operation(policy: Mapping[str, Any], role: str, operation: Operation, *, strict: bool) -> Mapping[str, Any]:
    targets = _normalize_targets(operation.targets)
    for entry in policy["operations"]:
        if entry.get("route_id") != operation.route_id or entry.get("action") != operation.action:
            continue
        if strict and entry.get("method") != operation.method:
            continue
        if _normalize_targets(entry.get("targets")) != targets:
            continue
        roles = entry.get("roles")
        if roles is not None and role not in roles:
            continue
        permissions = policy["roles"].get(role, {})
        if not isinstance(permissions, Mapping) or operation.action not in permissions.get(operation.route_id, []):
            continue
        normalized_args = _normalize_args(operation.args, entry["args"], strict=strict)
        return {**entry, "normalized_args": normalized_args}
    raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")


def _approval_path(config: AuthorizationConfig, nonce: str) -> Path:
    if not isinstance(nonce, str) or not _NONCE_RE.fullmatch(nonce):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval nonce is invalid")
    return config.approval_dir / f"{nonce}.json"


def _load_approval(config: AuthorizationConfig, nonce: str) -> Mapping[str, Any]:
    path = _approval_path(config, nonce)
    if not path.is_file() or path.is_symlink() or path.resolve().parent != config.approval_dir.resolve():
        raise AuthorizationError(428, "hardware_approval_required", "Hardware approval is required")
    try:
        approval = _read_regular_json(path, require_readonly=config.require_readonly_approvals)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval is invalid") from exc
    if not isinstance(approval, Mapping):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval must be an object")
    return approval


def _approval_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval time is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval time is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval time is invalid")
    return parsed


def consume_approval(config: AuthorizationConfig, nonce: str) -> bool:
    _approval_path(config, nonce)
    marker = config.consumed_dir / f"{nonce}.used"
    try:
        _write_and_sync_consumption_marker(marker, config.consumed_dir, nonce)
    except FileExistsError as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval was already used") from exc
    except OSError as exc:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval cannot be consumed") from exc
    return True


def _write_and_sync_consumption_marker(marker: Path, consumed_dir: Path, nonce: str) -> None:
    """Durably publish a consumed marker before a hardware side effect."""
    if _is_windows():
        _write_and_sync_windows_consumption_marker(marker, nonce)
        return
    _write_and_sync_posix_consumption_marker(marker, consumed_dir, nonce)


def _write_and_sync_posix_consumption_marker(marker: Path, consumed_dir: Path, nonce: str) -> None:
    marker_descriptor = os.open(
        str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    try:
        remaining = (nonce + "\n").encode("utf-8")
        while remaining:
            written = os.write(marker_descriptor, remaining)
            if written <= 0:
                raise OSError("Unable to write hardware approval marker")
            remaining = remaining[written:]
        os.fsync(marker_descriptor)
    finally:
        os.close(marker_descriptor)

    directory_descriptor = os.open(
        str(consumed_dir), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _windows_kernel32():
    """Load kernel32 lazily so non-Windows imports have no WinAPI dependency."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.WriteFile.argtypes = (
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    )
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _is_windows() -> bool:
    return os.name == "nt"


def _native_windows() -> bool:
    return os.name == "nt"


def _ctypes_last_error() -> int:
    import ctypes

    return int(ctypes.get_last_error())


def _windows_error(kernel32, message: str) -> OSError:
    # WinDLL(use_last_error=True) stores the call result in ctypes state. A
    # separate GetLastError call can overwrite or observe the wrong value.
    error_code = _ctypes_last_error() if _native_windows() else int(kernel32.GetLastError())
    return OSError(error_code, message)


def _write_and_sync_windows_consumption_marker(marker: Path, nonce: str) -> None:
    """Create and flush a CREATE_NEW marker before any hardware side effect.

    Windows has no portable parent-directory fsync equivalent. CREATE_NEW
    establishes the one-shot marker, and write-through plus FlushFileBuffers
    provides the durability primitive exposed by the Windows file API.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = _windows_kernel32()
    generic_write = 0x40000000
    create_new = 1
    file_attribute_normal = 0x00000080
    file_flag_write_through = 0x80000000
    invalid_handle_value = ctypes.c_void_p(-1).value
    handle = kernel32.CreateFileW(
        str(marker), generic_write, 0, None, create_new,
        file_attribute_normal | file_flag_write_through, None,
    )
    if handle in (None, -1, invalid_handle_value):
        raise _windows_error(kernel32, "Unable to create hardware approval marker")

    pending_error = None
    try:
        payload = (nonce + "\n").encode("utf-8")
        buffer = ctypes.create_string_buffer(payload)
        written = wintypes.DWORD()
        if not kernel32.WriteFile(handle, buffer, len(payload), ctypes.byref(written), None):
            raise _windows_error(kernel32, "Unable to write hardware approval marker")
        if written.value != len(payload):
            raise OSError("Unable to write complete hardware approval marker")
        if not kernel32.FlushFileBuffers(handle):
            raise _windows_error(kernel32, "Unable to flush hardware approval marker")
    except BaseException as exc:
        pending_error = exc
        raise
    finally:
        if not kernel32.CloseHandle(handle) and pending_error is None:
            raise _windows_error(kernel32, "Unable to close hardware approval marker")


def authorize_operation(config: AuthorizationConfig, *, subject: str, role: str, operation: Operation, nonce: str | None, before_side_effect: Callable[[], Any] | None = None, policy: Mapping[str, Any] | None = None, approval: Mapping[str, Any] | None = None) -> bool:
    policy = load_policy(config.policy_path, strict=config.strict) if policy is None else policy
    matched = _matching_policy_operation(policy, role, operation, strict=config.strict)
    if not nonce:
        raise AuthorizationError(428, "hardware_approval_required", "Hardware approval is required")
    approval = _load_approval(config, nonce) if approval is None else approval
    expected = {
        "subject": subject,
        "role": role,
        "route_id": operation.route_id,
        "action": operation.action,
        "targets": [dict(target) for target in _normalize_targets(operation.targets)],
        "args": matched["normalized_args"],
        "nonce": nonce,
    }
    if config.strict:
        expected["method"] = operation.method
    required = set(expected) | {"issued_at", "expires_at"}
    if config.strict:
        required |= {"version", "approved_by", "hardware_safe"}
    if set(approval) != required or any(_canonical(approval[key]) != _canonical(value) for key, value in expected.items()):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval does not match this operation")
    if config.strict and (
        type(approval["version"]) is not int
        or approval["version"] != 1
        or not isinstance(approval["approved_by"], str)
        or not approval["approved_by"].strip()
        or approval["hardware_safe"] is not True
    ):
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval safety fields are invalid")
    issued_at = _approval_time(approval["issued_at"])
    expires_at = _approval_time(approval["expires_at"])
    now = datetime.now(timezone.utc)
    if issued_at > now or expires_at <= now or expires_at <= issued_at or (expires_at - issued_at).total_seconds() > _MAX_APPROVAL_TTL_SECONDS:
        raise AuthorizationError(409, "hardware_approval_invalid", "Hardware approval is expired or has an invalid lifetime")
    consume_approval(config, nonce)
    if before_side_effect is not None:
        before_side_effect()
    return True


def _roles_for_subject(policy: Mapping[str, Any], subject: str) -> tuple[str, ...]:
    subjects = policy.get("subjects", {})
    entry = subjects.get(subject) if isinstance(subjects, Mapping) else None
    roles = entry.get("roles") if isinstance(entry, Mapping) else entry
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    return tuple(roles)


def trusted_starter_for_server(policy: Mapping[str, Any], server_name: str) -> str:
    if not isinstance(server_name, str) or not server_name.strip():
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    mapping = policy.get("starter_servers")
    if not isinstance(mapping, Mapping):
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    starter = mapping.get(server_name)
    if not isinstance(starter, str) or not starter.strip():
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    return starter


def authorize_runtime_operation(operation: Operation, nonce: str | None, *, subject: str | None = None) -> bool:
    if not authorization_required():
        return True
    config = authorization_config_from_environment()
    subject = subject if subject is not None else get_jwt_identity()
    if not isinstance(subject, str) or not subject:
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    policy = load_policy(config.policy_path, strict=True)
    subject_roles = _roles_for_subject(policy, subject)
    if not nonce:
        raise AuthorizationError(428, "hardware_approval_required", "Hardware approval is required")
    approval = _load_approval(config, nonce)
    approval_role = approval.get("role") if isinstance(approval, Mapping) else None
    if approval_role not in subject_roles:
        raise AuthorizationError(403, "hardware_not_authorized", "Hardware action is not authorized")
    return authorize_operation(
        config,
        subject=subject,
        role=approval_role,
        operation=operation,
        nonce=nonce,
        policy=policy,
        approval=approval,
    )


def require_http_hardware(action: str, targets: Sequence[Mapping[str, str]], args: Any, *, route_id: str | None = None, wrapper_fields: set[str] | frozenset[str] | None = None):
    if not authorization_required():
        return None
    try:
        raw = request.get_data(cache=True, as_text=True)
        payload = {} if not raw.strip() else _parse_json(raw)
        if not isinstance(payload, Mapping):
            raise ValueError("request must be an object")
        if wrapper_fields is not None and set(payload) - set(wrapper_fields):
            raise ValueError("unknown request field")
    except (TypeError, ValueError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "Hardware request is invalid", "code": "hardware_approval_invalid"}), 409
    operation = Operation(
        method=request.method,
        route_id=route_id or str(request.endpoint or ""),
        action=action,
        targets=tuple(dict(target) for target in targets),
        args=args,
    )
    try:
        authorize_runtime_operation(operation, request.headers.get("X-PYCONLYSE-HARDWARE-APPROVAL"))
    except AuthorizationError as exc:
        return jsonify({"success": False, "error": exc.message, "code": exc.code}), exc.status_code
    return None


def websocket_authorization_error(exc: AuthorizationError) -> dict[str, Any]:
    return {"error": exc.message, "success": False, "code": exc.code, "status": exc.status_code}


def authorize_websocket_command(config: AuthorizationConfig, *, subject: str, role: str, sid: str, device: str, command: str, args: Any, nonce: str | None, before_side_effect: Callable[[], Any] | None = None) -> bool:
    del sid
    return authorize_operation(
        config,
        subject=subject,
        role=role,
        operation=Operation("WEBSOCKET", "websocket.execute_command", "device.command", ({"device": device, "command": command},), args),
        nonce=nonce,
        before_side_effect=before_side_effect,
    )


def authorize_http_route(config: AuthorizationConfig, *, subject: str, role: str, route_id: str, method: str, path: str, payload: Any, nonce: str | None) -> bool:
    del path
    return authorize_operation(config, subject=subject, role=role, operation=Operation(method, route_id, "execute", ({"device": "route", "command": route_id},), payload), nonce=nonce)
