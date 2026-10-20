"""Read-only fixed Everest Tango runtime view. No XP HTTP or mutation path."""
import copy
import math
import threading

from flask import Blueprint, current_app, jsonify
import tango_gateway
from mutation_auth import install_mutation_auth
from acq_runtime_read_worker import DEVICE, RuntimeAttributeReader
from DeviceServers.control.elyse_acq.runtime_client import strict_runtime_json, MAX_RUNTIME_BYTES
from DeviceServers.control.elyse_acq.runtime_health import (
    BRIDGE_MAX_AGE_SECONDS, SOURCE_MAX_AGE_SECONDS, project_runtime_contract,
)


MAX_JSON_BYTES = MAX_RUNTIME_BYTES + 65536
_reader_creation_lock = threading.Lock()
_default_read_service = None
acq_runtime_api = Blueprint("acq_runtime_api", __name__, url_prefix="/api/elyse/acquisition/runtime")
install_mutation_auth(acq_runtime_api, protected_get_endpoints=("get_runtime",))


@acq_runtime_api.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _runtime_reader():
    # One process-local default owner, shared even if several Flask app
    # objects exist. Tests may inject an explicitly owned per-app service.
    global _default_read_service
    with _reader_creation_lock:
        service = current_app.extensions.get("acq_runtime_read_service")
        if service is None:
            if _default_read_service is None:
                _default_read_service = RuntimeAttributeReader(
                    lambda device: tango_gateway.create_device_proxy(device),
                    lambda: tango_gateway.tango.DevSource.DEV)
            service = _default_read_service
            current_app.extensions["acq_runtime_read_service"] = service
        return service


def _browser_values(value):
    if type(value) is int and abs(value) > 2**53 - 1:
        return {"integer_decimal": str(value)}
    if isinstance(value, list):
        return [_browser_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _browser_values(item) for key, item in value.items()}
    return value


def _base():
    return dict(schema_version=1, source="xp_python_acquisition_runtime",
                execution_allowed=False, hardware_writes=False,
                session_id=None, build_id=None, runtime_state=None,
                bridge_stale=True, bridge_age_seconds=None, source_stale=True,
                source_age_seconds=None, stale_after_seconds=SOURCE_MAX_AGE_SECONDS,
                source_stale_after_seconds=SOURCE_MAX_AGE_SECONDS,
                bridge_stale_after_seconds=BRIDGE_MAX_AGE_SECONDS)


def present_snapshot(raw, server_state, read_duration_seconds=0.0):
    """Independently rederive quality; never trust Tango ON or cached flags.

    The complete Tango read duration is a conservative age allowance. No host
    wall clocks are subtracted. The wrapper's raw XP age is used, not its
    already-adjusted source age, so bridge elapsed time is counted once.
    """
    value = strict_runtime_json(raw, max_bytes=MAX_JSON_BYTES)
    if (value.get("source") != "xp_python_acquisition_runtime"
            or value.get("storage_mode") != "ram_latest"
            or value.get("execution_allowed") is not False
            or value.get("hardware_writes") is not False):
        raise ValueError("Unexpected read-only runtime bridge contract")
    bridge_age = value.get("bridge_age_seconds")
    if (type(bridge_age) in (int, float) and math.isfinite(bridge_age) and bridge_age >= 0
            and type(read_duration_seconds) in (int, float)
            and math.isfinite(read_duration_seconds) and read_duration_seconds >= 0):
        bridge_age += read_duration_seconds
    else:
        bridge_age = None
    bridge_error = value.get("bridge_error")
    if not isinstance(bridge_error, str):
        bridge_error = "Invalid bridge error contract"
    if value.get("bridge_stale") is not False and not bridge_error:
        # Preserve stale classification without inventing a transport error.
        reader_started = True
    else:
        reader_started = value.get("runtime") is not None
    health = project_runtime_contract(
        value.get("runtime"), bridge_age, bridge_error, reader_started,
        value.get("read_duration_seconds", 0.0), value.get("session_changed") is True,
        value.get("bridge_protocol_error", ""))
    if value.get("bridge_stale") is not False:
        health.update(bridge_stale=True, source_stale=True, source_current=False)
        if health["quality"] not in ("UNAVAILABLE", "INCOMPATIBLE"):
            health["quality"] = "STALE"
    if str(server_state) in ("OFF", "DISABLE", "INIT", "UNKNOWN", "FAULT", "ALARM") and health["quality"] == "FRESH":
        health.update(quality="STALE", source_stale=True, source_current=False)
    snapshot = copy.deepcopy(value)
    hidden = health["quality"] != "FRESH"
    if hidden and isinstance(snapshot.get("runtime"), dict):
        snapshot["runtime"]["latest"] = None
    snapshot.pop("health", None)
    snapshot.update(measurements_hidden=hidden, quality=health["quality"],
                    bridge_stale=health["bridge_stale"], bridge_age_seconds=bridge_age,
                    source_stale=health["source_stale"], source_current=health["source_current"],
                    source_age_seconds=health["source_age_seconds"])
    result = _base()
    result.update(quality=health["quality"], session_id=health["session_id"],
                  build_id=health["build_id"], state_revision=health["state_revision"],
                  runtime_state=health["runtime_state"], server_state=str(server_state),
                  bridge_stale=health["bridge_stale"], bridge_age_seconds=bridge_age,
                  source_stale=health["source_stale"], source_age_seconds=health["source_age_seconds"],
                  protocol_error=health["protocol_error"], snapshot=_browser_values(snapshot))
    return result


@acq_runtime_api.get("")
def get_runtime():
    try:
        # Admission/auth happens first. COMPLETE factory + direct read is
        # single-flight and caller-bounded, including a hung proxy constructor.
        raw, server_state, elapsed = _runtime_reader().read()
        return jsonify(present_snapshot(raw, server_state, elapsed))
    except Exception as error:
        # Never fall back to LabVIEW telemetry, demo values, direct XP HTTP,
        # NI, another Tango device or any command-capable path.
        current_app.logger.warning("ACQ runtime read unavailable: %s", type(error).__name__)
        result = _base()
        result.update(quality="UNAVAILABLE", snapshot=None,
                      error="Python acquisition runtime unavailable.")
        return jsonify(result), 503
