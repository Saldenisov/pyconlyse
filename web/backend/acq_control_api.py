"""Named web commands -> fixed Tango facade -> XP owner. No direct XP/NI I/O.

The durable dispatch fence is committed before Tango I/O. An uncertain result
is never retried automatically, including after a page/server restart.
"""
import json
import math
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError

import tango_gateway
from legacy.xp_acq_control.elyse_agent.acquisition_remote import OPERATIONS, validate_request, strict_json
from legacy.xp_acq_control.elyse_agent.runtime_identity import valid_hex
from mutation_auth import install_mutation_auth
from hardware_authorization import AuthorizationError, Operation, authorize_runtime_operation
from acq_contract import DEVICE, SOURCE_MODES, topology

MAX_BYTES = 2 * 1024 * 1024
api = Blueprint("acq_control_api", __name__, url_prefix="/api/elyse/acquisition/control")
install_mutation_auth(api, protected_get_endpoints=("get_control",))


def _json(raw):
    if not isinstance(raw, str) or not 0 < len(raw.encode("utf-8")) <= MAX_BYTES:
        raise ValueError("Bounded Tango control JSON required")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate Tango field")
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError("Nonfinite Tango data")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    json.dumps(value, allow_nan=False)
    return value


def read_view(allow_labview=False):
    proxy = tango_gateway.create_device_proxy(DEVICE)
    proxy.set_timeout_millis(2500)
    attr = proxy.read_attribute("runtime_json")
    if attr.has_failed:
        raise ValueError("Control telemetry unavailable")
    view = _json(attr.value)
    if allow_labview and view.get("source") == "labview_receive_only" and view.get("commands_enabled") is False:
        return proxy, view
    age = view.get("bridge_age_seconds")
    runtime = view.get("runtime")
    if (view.get("source") != "xp_python_acquisition_control" or view.get("bridge_error")
            or type(age) not in (float, int) or not math.isfinite(age) or not 0 <= age < 2
            or not isinstance(runtime, dict)
            or runtime.get("server_variant") != "acquisition_control_vnext"
            or runtime.get("runtime_protocol_version") != 2
            or runtime.get("control_policy_version") != 2
            or runtime.get("auto_initialize") is not False
            or runtime.get("remote_initialization_enabled") is not False
            or not valid_hex(runtime.get("session_id"), 32) or not valid_hex(runtime.get("build_id"), 64)
            or type(runtime.get("state_revision")) is not int or not 0 <= runtime["state_revision"] <= 2**53-1):
        raise ValueError("Current Python control runtime required; LabVIEW fallback forbidden")
    control = runtime.get("control", {})
    capabilities = control.get("capabilities")
    if (control.get("protocol_version") != 1 or type(capabilities) is not dict
            or set(capabilities) != set(OPERATIONS) or type(control.get("enabled")) is not bool
            or type(view.get("commands_enabled")) is not bool):
        raise ValueError("Updated named capability contract required")
    for item in capabilities.values():
        if (type(item) is not dict or set(item) != {"enabled", "reason"}
                or type(item["enabled"]) is not bool or not isinstance(item["reason"], str)
                or len(item["reason"]) > 300):
            raise ValueError("Invalid named capability")
    return proxy, view


def _database():
    path = current_app.config.get("ELYSE_CONTROL_STATE_DB", str(Path(current_app.instance_path) / "acq_control.sqlite3"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=3, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL)")
    return db


def _receipt(command, outcome, **extra):
    return dict(command_id=command["command_id"], session_id=command["session_id"], operation=command["operation"],
                outcome=outcome, hardware_acknowledged=False, automatic_retry=False, **extra)


def hardware_intent(command):
    """Bind manual approval to the exact actuator intent and observed boot.

    The random command ID is an at-most-once correlation token, not an extra
    actuator parameter. The separate approval nonce is consumed once before
    any command journal or Tango access. This does not authenticate arbitrary
    direct Tango callers: that existing transport requires a trusted ACL.
    """
    return Operation(method='POST', route_id='acquisition.command.' + command['operation'],
        action='execute', targets=({'device': DEVICE, 'command': 'ExecuteCommand'},),
        args={key: command[key] for key in ('operation', 'value', 'session_id', 'expected_revision')})


def _history(results=(), session=None):
    db = _database()
    try:
        # Only exact receipts for a locally dispatched intent may update it.
        for result in results:
            if not isinstance(result, dict) or result.get("session_id") != session:
                continue
            row = db.execute("SELECT request FROM commands WHERE id=?", (result.get("command_id"),)).fetchone()
            if row:
                command = json.loads(row[0])
                if (result.get("session_id") == command["session_id"] and result.get("operation") == command["operation"]
                        and result.get("hardware_acknowledged") is False and result.get("outcome") in
                        ("QUEUED", "EXECUTING", "COMPLETED", "FAILED", "REJECTED", "INTERRUPTED")):
                    safe = _receipt(command, result["outcome"], error=str(result.get("error", ""))[:300])
                    db.execute("UPDATE commands SET receipt=? WHERE id=?", (json.dumps(safe), command["command_id"]))
        return [json.loads(row[0]) for row in db.execute("SELECT receipt FROM commands ORDER BY rowid DESC LIMIT 30")]
    finally:
        db.close()


def public_view(view):
    runtime = view["runtime"]
    source_mode = runtime.get("telemetry_delivery", {}).get("source_mode")
    if source_mode not in SOURCE_MODES:
        source_mode = "UNKNOWN"
    history = _history(runtime["control"].get("results", []), runtime["session_id"])
    unknown = any(item["session_id"] == runtime["session_id"] and item["outcome"] == "INDETERMINATE" for item in history)
    enabled = (view.get("commands_enabled") is True
               and runtime["control"]["enabled"] is True and runtime.get("remote_setpoints_enabled") is True
               and source_mode == "PYTHON_NATIVE")
    capabilities = {name: dict(enabled=enabled and item["enabled"],
                              reason=item["reason"] or ("" if enabled else "PYTHON_CONTROL_SOURCE_NOT_ACTIVE"))
                    for name, item in runtime["control"]["capabilities"].items()}
    if unknown:
        for name, capability in capabilities.items():
            if name != "modulator.general.stop":
                capability.update(enabled=False, reason="UNRESOLVED_DISPATCH_DO_NOT_RESEND")
    return dict(schema_version=1, mode="XP_CONTROL", device=DEVICE,
                source_selected=source_mode == "PYTHON_NATIVE", source_mode=source_mode,
                topology=topology(),
                execution_allowed=any(item["enabled"] for item in capabilities.values()),
                session_id=runtime["session_id"], revision=runtime["state_revision"], build_id=runtime["build_id"],
                state=runtime["state"], quality=view.get("quality"), capabilities=capabilities,
                startup_phase=runtime.get("startup_phase"), current_operation=runtime.get("current_operation"),
                general_cooling_ready=runtime.get("general_cooling_ready") is True,
                synchronization=runtime.get("counter_timing_state", {}),
                commands=history,
                physical_acknowledgement=False, automatic_retry=False)


@api.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@api.get("")
def get_control():
    try:
        unused, view = read_view(allow_labview=True)
        if view.get("source") == "labview_receive_only":
            return jsonify(schema_version=1, mode="LABVIEW_READ_ONLY", execution_allowed=False,
                           source_selected=False, source_mode="LABVIEW_BRIDGE", topology=topology(),
                           state="DISABLED", capabilities={}, commands=_history())
        return jsonify(public_view(view))
    except Exception as error:
        current_app.logger.warning("ACQ control read unavailable: %s", type(error).__name__)
        return jsonify(schema_version=1, mode="XP_CONTROL", execution_allowed=False,
                       source_selected=False, state="UNAVAILABLE", capabilities={},
                       source_mode="UNKNOWN", topology=topology(),
                       commands=_history(), error="Device Server Python Acquisition indisponible."), 503


@api.post("/commands")
def post_command():
    # Live machine commands require authentication even on a development LAN.
    try:
        verify_jwt_in_request()
    except (JWTExtendedException, PyJWTError):
        return jsonify(error="Authentification requise pour commander Acquisition."), 401
    if request.mimetype != "application/json":
        return jsonify(error="application/json required"), 415
    try:
        command = validate_request(strict_json(request.stream.read(2049)))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as error:
        return jsonify(error=str(error)), 400
    try:
        authorize_runtime_operation(hardware_intent(command), request.headers.get('X-PYCONLYSE-HARDWARE-APPROVAL'), required=True)
    except AuthorizationError as error:
        # This validated, correlated attempt has not reached the command DB
        # or Tango. A caller may clear only its newly reserved local intent;
        # a lost transport reply or unrelated old intent remains unknown.
        return jsonify(schema_version=1, error=error.message, code=error.code,
            automatic_retry=False, receipt=_receipt(command, 'REJECTED',
                dispatch_attempted=False, error=error.message)), error.status_code
    encoded = json.dumps(command, sort_keys=True, separators=(",", ":"))
    db = _database()
    try:
        # Durable at-most-once *dispatch*: never reissue an unknown attempt.
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT request,receipt FROM commands WHERE id=?", (command["command_id"],)).fetchone()
        if row:
            db.execute("COMMIT")
            if row[0] != encoded:
                return jsonify(error="COMMAND_ID_REUSED_WITH_DIFFERENT_REQUEST"), 409
            return jsonify(schema_version=1, receipt=json.loads(row[1]), duplicate=True)
        if command["operation"] != "modulator.general.stop":
            for previous, receipt in db.execute("SELECT request,receipt FROM commands"):
                if (json.loads(previous)["session_id"] == command["session_id"]
                        and json.loads(receipt)["outcome"] == "INDETERMINATE"):
                    db.execute("ROLLBACK")
                    return jsonify(error="UNRESOLVED_DISPATCH_DO_NOT_RESEND"), 409
        try:
            proxy, view = read_view()
            runtime = view["runtime"]
            if (runtime["session_id"] != command["session_id"]
                    or runtime["state_revision"] != command["expected_revision"]):
                raise ValueError("Observed XP session/revision changed; refresh and confirm again")
            if (view.get("commands_enabled") is not True
                    or runtime["control"]["enabled"] is not True or runtime.get("remote_setpoints_enabled") is not True
                    or runtime.get("telemetry_delivery", {}).get("source_mode") != "PYTHON_NATIVE"
                    or runtime["control"]["capabilities"][command["operation"]]["enabled"] is not True):
                raise ValueError(runtime["control"]["capabilities"][command["operation"]]["reason"] or "COMMANDS_DISABLED")
        except Exception as error:
            db.execute("ROLLBACK")
            # Fresh first-attempt ID, no reservation/ExecuteCommand yet.
            # A source/boot/capability change is a refusal, not an unknown
            # actuation result. Existing-ID branches above never use this.
            message = str(error)[:300]
            return jsonify(schema_version=1, error=message,
                code="acquisition_pre_dispatch_rejected", automatic_retry=False,
                receipt=_receipt(command, "REJECTED", dispatch_attempted=False, error=message)), 409
        receipt = _receipt(command, "INDETERMINATE", error="Dispatch reserved; check XP receipt, never retry automatically")
        db.execute("INSERT INTO commands VALUES (?,?,?)", (command["command_id"], encoded, json.dumps(receipt)))
        db.execute("COMMIT")
        try:
            proxy.set_timeout_millis(5000)
            result = _json(proxy.command_inout("ExecuteCommand", json.dumps(command)))
            if (any(result.get(key) != command[key] for key in ("command_id", "session_id", "operation"))
                    or result.get("hardware_acknowledged") is not False or result.get("outcome") not in
                    ("QUEUED", "EXECUTING", "COMPLETED", "FAILED", "REJECTED", "INTERRUPTED", "INDETERMINATE")):
                raise ValueError("Command receipt mismatch; result unknown")
            receipt = _receipt(command, result["outcome"], error=str(result.get("error", ""))[:300])
        except Exception as error:
            receipt = _receipt(command, "INDETERMINATE", error=type(error).__name__ + ": " + str(error)[:200])
        db.execute("UPDATE commands SET receipt=? WHERE id=?", (json.dumps(receipt), command["command_id"]))
        return jsonify(schema_version=1, receipt=receipt, duplicate=False)
    finally:
        db.close()


def control_telemetry():
    """Compatibility helper: one standard attribute, no second projection."""
    from acq_telemetry_api import present_snapshot
    proxy = tango_gateway.create_device_proxy(DEVICE)
    proxy.set_timeout_millis(1500)
    state, value = proxy.read_attributes(["State", "telemetry_json"])
    if state.has_failed or value.has_failed:
        raise ValueError("Standard telemetry unavailable")
    return present_snapshot(value.value, str(state.value))
