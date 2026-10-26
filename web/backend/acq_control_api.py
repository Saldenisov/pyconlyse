"""Named web commands -> fixed Tango facade -> XP owner. No direct XP/NI I/O.

The durable dispatch fence is committed before Tango I/O. An uncertain result
is never retried automatically, including after a page/server restart.
"""
import json
import copy
import math
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError

import tango_gateway
from legacy.xp_acq_control.elyse_agent.command_protocol import OPERATIONS, validate_request, strict_json
from legacy.xp_acq_control.elyse_agent.runtime_identity import valid_hex
from mutation_auth import install_mutation_auth, mutation_auth_required
from hardware_authorization import (AuthorizationError, Operation, authorize_runtime_operation,
                                    authorization_required as hardware_approval_required)
from acq_local_console import LocalConsoleError, local_subject, issue_approval, consume_approval
from acq_contract import DEVICE, SOURCE_MODES, topology

MAX_BYTES = 2 * 1024 * 1024
OWNERS = ("acquisition", "supervision")
OWNER_HOSTS = dict(acquisition="10.20.30.10", supervision="10.20.30.2")
api = Blueprint("acq_control_api", __name__, url_prefix="/api/elyse/acquisition/control")
install_mutation_auth(api, protected_get_endpoints=("get_control",))


def _local_settings():
    names = ("ACQ_LOCAL_CONSOLE_ORIGIN", "ACQ_LOCAL_CONSOLE_KEY_FILE", "ACQ_LOCAL_CONSOLE_DB_FILE")
    value = {name: current_app.config.get(name, os.environ.get(name)) for name in names}
    enabled = current_app.config.get("ACQ_LOCAL_CONSOLE_ENABLED", os.environ.get("ACQ_LOCAL_CONSOLE_ENABLED", "false"))
    value["ACQ_LOCAL_CONSOLE_ENABLED"] = enabled is True or (type(enabled) is str and enabled.lower() == "true")
    value["ACQ_LOCAL_CONSOLE_TTL_SECONDS"] = 30
    return value


def _local_subject(read_only=False):
    return local_subject(request, _local_settings(), mutation_auth_required() or hardware_approval_required(),
                         require_origin=not read_only)


def _request_owner():
    supplied = request.args.getlist("owner")
    if len(supplied) > 1 or supplied and supplied[0] not in OWNERS:
        raise ValueError("One exact owner=acquisition or owner=supervision required")
    return supplied[0] if supplied else "acquisition"


def _owner_operation(command, owner):
    if owner not in OWNERS or owner == "supervision" and command["operation"] != "counter_timing.set":
        raise ValueError("Operation is not owned by the selected orchestrator")


def _ledger_id(command_id, owner):
    return command_id if owner == "acquisition" else "supervision:" + command_id


def _stored_request(encoded):
    value = json.loads(encoded)
    if type(value) is dict and set(value) == {"owner", "request"}:
        if value["owner"] != "supervision" or type(value["request"]) is not dict:
            raise ValueError("Invalid owner dispatch journal entry")
        return "supervision", value["request"]
    return "acquisition", value


def _approval_intent(command, owner="acquisition"):
    return dict(operation=command["operation"], value=command["value"], session_id=command["session_id"],
                expected_revision=command["expected_revision"], device=DEVICE, method="POST",
                route=owner + ".command." + command["operation"])


def _check_current_command(command, view, owner="acquisition"):
    _owner_operation(command, owner)
    runtime = view["runtime"]
    if owner == "supervision" and (view.get("owner_state_current") is not True
                                   or view.get("telemetry_source_current") is not True):
        raise ValueError("SUPERVISION_OWNER_STATE_NOT_CURRENT")
    if runtime["session_id"] != command["session_id"] or runtime["state_revision"] != command["expected_revision"]:
        raise ValueError("Observed XP session/revision changed; refresh and confirm again")
    if (view.get("commands_enabled") is not True or runtime["control"]["enabled"] is not True
            or runtime.get("remote_setpoints_enabled") is not True
            or runtime.get("telemetry_delivery", {}).get("source_mode") != "PYTHON_NATIVE"
            or runtime["control"]["capabilities"][command["operation"]]["enabled"] is not True):
        raise ValueError(runtime["control"]["capabilities"][command["operation"]]["reason"] or "COMMANDS_DISABLED")


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


def read_view(allow_labview=False, owner="acquisition"):
    if owner not in OWNERS:
        raise ValueError("Unknown orchestrator owner")
    proxy = tango_gateway.create_device_proxy(DEVICE)
    proxy.set_timeout_millis(2500)
    attr = proxy.read_attribute("runtime_json" if owner == "acquisition" else "orchestrators_json")
    if attr.has_failed:
        raise ValueError("Control telemetry unavailable")
    view = _json(attr.value)
    if owner == "supervision":
        if (type(view) is not dict or view.get("federated") is not True
                or type(view.get("owners")) is not dict
                or type(view["owners"].get(owner)) is not dict):
            raise ValueError("Explicit SuperVision orchestrator metadata required")
        view = view["owners"][owner]
        if view.get("owner") != owner:
            raise ValueError("SuperVision runtime owner binding mismatch")
    if allow_labview and view.get("source") == "labview_receive_only" and view.get("commands_enabled") is False:
        return proxy, view
    age = view.get("bridge_age_seconds")
    runtime = view.get("runtime")
    if (view.get("source") != "xp_python_" + owner + "_control" or view.get("bridge_error")
            or type(age) not in (float, int) or not math.isfinite(age) or not 0 <= age < 2
            or not isinstance(runtime, dict)
            or runtime.get("server_variant") != owner + "_control_vnext"
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
    if owner == "supervision":
        if (type(view.get("owner_state_current")) is not bool
                or type(view.get("telemetry_source_current")) is not bool):
            raise ValueError("Explicit SuperVision owner-state freshness required")
        if view["owner_state_current"]:
            latest = runtime.get("latest") or {}
            sample_age = runtime.get("age_seconds")
            if (type(latest) is not dict or latest.get("source") != "python_supervision_card_processes"
                    or latest.get("simulated") is not False
                    or runtime.get("card_health", {}).get("all_required_ready") is not True
                    or type(sample_age) not in (int, float) or not math.isfinite(sample_age)
                    or not 0 <= sample_age + age < 2):
                raise ValueError("Current SuperVision card-owner memory required")
    return proxy, view


def _database():
    path = current_app.config.get("ELYSE_CONTROL_STATE_DB", str(Path(current_app.instance_path) / "acq_control.sqlite3"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=3, isolation_level=None)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, request TEXT NOT NULL, receipt TEXT NOT NULL)")
    return db


def _receipt(command, outcome, owner="acquisition", **extra):
    value = dict(command_id=command["command_id"], session_id=command["session_id"], operation=command["operation"],
                outcome=outcome, hardware_acknowledged=False, automatic_retry=False, **extra)
    if owner != "acquisition":
        value["owner"] = owner
    return value


def hardware_intent(command, owner="acquisition"):
    """Bind manual approval to the exact actuator intent and observed boot.

    The random command ID is an at-most-once correlation token, not an extra
    actuator parameter. The separate approval nonce is consumed once before
    any command journal or Tango access. This does not authenticate arbitrary
    direct Tango callers: that existing transport requires a trusted ACL.
    """
    args = {key: command[key] for key in ('operation', 'value', 'session_id', 'expected_revision')}
    if owner != "acquisition":
        args["owner"] = owner
    return Operation(method='POST', route_id=owner + '.command.' + command['operation'],
        action='execute', targets=({'device': DEVICE, 'command':
                                  'ExecuteCommand' if owner == 'acquisition' else 'ExecuteOwnerCommand'},), args=args)


def _history(results=(), session=None, owner="acquisition"):
    db = _database()
    try:
        # Only exact receipts for a locally dispatched intent may update it.
        for result in results:
            if not isinstance(result, dict) or result.get("session_id") != session:
                continue
            row = db.execute("SELECT request FROM commands WHERE id=?",
                             (_ledger_id(str(result.get("command_id", "")), owner),)).fetchone()
            if row:
                stored_owner, command = _stored_request(row[0])
                if (stored_owner == owner and result.get("session_id") == command["session_id"] and result.get("operation") == command["operation"]
                        and result.get("hardware_acknowledged") is False and result.get("outcome") in
                        ("QUEUED", "EXECUTING", "COMPLETED", "FAILED", "REJECTED", "INTERRUPTED")):
                    safe = _receipt(command, result["outcome"], owner=owner, error=str(result.get("error", ""))[:300])
                    db.execute("UPDATE commands SET receipt=? WHERE id=?",
                               (json.dumps(safe), _ledger_id(command["command_id"], owner)))
        predicate = "LIKE" if owner == "supervision" else "NOT LIKE"
        return [json.loads(row[0]) for row in db.execute(
            "SELECT receipt FROM commands WHERE id " + predicate + " 'supervision:%' ORDER BY rowid DESC LIMIT 30")]
    finally:
        db.close()


def public_view(view, owner="acquisition"):
    runtime = view["runtime"]
    source_mode = runtime.get("telemetry_delivery", {}).get("source_mode")
    if source_mode not in SOURCE_MODES:
        source_mode = "UNKNOWN"
    history = _history(runtime["control"].get("results", []), runtime["session_id"], owner=owner)
    unknown = any(item["session_id"] == runtime["session_id"] and item["outcome"] == "INDETERMINATE" for item in history)
    enabled = (view.get("commands_enabled") is True
               and runtime["control"]["enabled"] is True and runtime.get("remote_setpoints_enabled") is True
               and source_mode == "PYTHON_NATIVE")
    if owner == "supervision":
        enabled = enabled and view.get("owner_state_current") is True and view.get("telemetry_source_current") is True
    capabilities = {name: dict(enabled=enabled and item["enabled"],
                              reason=item["reason"] or ("" if enabled else "PYTHON_CONTROL_SOURCE_NOT_ACTIVE"))
                    for name, item in runtime["control"]["capabilities"].items()}
    if owner == "supervision":
        for name, capability in capabilities.items():
            if name != "counter_timing.set":
                capability.update(enabled=False, reason="OPERATION_NOT_OWNED_BY_SUPERVISION")
    if unknown:
        for name, capability in capabilities.items():
            if name != "modulator.general.stop":
                capability.update(enabled=False, reason="UNRESOLVED_DISPATCH_DO_NOT_RESEND")
    cooling = copy.deepcopy(runtime.get("cooling_safety", {}))
    bridge_age = view.get("bridge_age_seconds", 0.)
    if type(bridge_age) in (int, float) and math.isfinite(bridge_age) and bridge_age >= 0:
        for item in [cooling] + cooling.get("circuits", []) + cooling.get("confirmation_candidates", []):
            remaining = item.get("remaining_seconds")
            if type(remaining) in (int, float):
                item["remaining_seconds"] = max(0, remaining - bridge_age)
        if cooling.get("policy_version") == 2:
            cooling["confirmation_candidates"] = [row for row in cooling.get("confirmation_candidates", [])
                if type(row.get("remaining_seconds")) in (int, float) and row["remaining_seconds"] > 0]
            cooling["confirmation_required"] = bool(cooling["confirmation_candidates"]
                and cooling.get("stop_state") == "NONE")
            name = "cooling.confirm_circulation"
            reason = "" if cooling["confirmation_required"] else "NO_UNEXPIRED_CIRCULATION_CONFIRMATION"
            cache_age = runtime.get("application_view_age_seconds")
            if type(cache_age) in (int, float) and cache_age + bridge_age >= 2:
                reason = "APPLICATION_METADATA_NOT_CURRENT"
            if runtime.get("state") == "FAULT":
                diagnostic = runtime.get("fault_diagnostic_measurement") or {}
                diagnostic_age = diagnostic.get("age_seconds")
                if (diagnostic.get("current") is not True or type(diagnostic_age) not in (int, float)
                        or diagnostic_age + bridge_age >= 2):
                    reason = "FRESH_FAULT_DIAGNOSTIC_INPUTS_REQUIRED"
            if name in capabilities and reason:
                capabilities[name] = dict(enabled=False, reason=reason)
    owner_topology = topology()
    if owner != "acquisition":
        owner_topology.update(xp_host=OWNER_HOSTS[owner], orchestrator_owner=owner)
    return dict(schema_version=1, mode="XP_CONTROL", device=DEVICE, owner=owner, source_host=OWNER_HOSTS[owner],
                source_selected=source_mode == "PYTHON_NATIVE", source_mode=source_mode,
                topology=owner_topology,
                execution_allowed=any(item["enabled"] for item in capabilities.values()),
                session_id=runtime["session_id"], revision=runtime["state_revision"], build_id=runtime["build_id"],
                state=runtime["state"], quality=view.get("quality"), capabilities=capabilities,
                startup_phase=runtime.get("startup_phase"), current_operation=runtime.get("current_operation"),
                operator_supervised_test=runtime.get("operator_supervised_test") is True,
                operator_test_admission=runtime.get("operator_test_admission"),
                approval_mode="LOCAL_CONSOLE" if _local_subject(read_only=True) else "JWT_APPROVAL",
                general_cooling_ready=runtime.get("general_cooling_ready") is True,
                cooling_safety=cooling,
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
        owner = _request_owner()
    except ValueError as error:
        return jsonify(error=str(error), execution_allowed=False), 400
    try:
        unused, view = read_view(allow_labview=True, owner=owner)
        if view.get("source") == "labview_receive_only":
            return jsonify(schema_version=1, mode="LABVIEW_READ_ONLY", execution_allowed=False,
                           source_selected=False, source_mode="LABVIEW_BRIDGE", topology=topology(),
                           state="DISABLED", capabilities={}, commands=_history(owner=owner),
                           owner=owner, source_host=OWNER_HOSTS[owner])
        return jsonify(public_view(view, owner=owner))
    except Exception as error:
        current_app.logger.warning("ACQ control read unavailable: %s", type(error).__name__)
        return jsonify(schema_version=1, mode="XP_CONTROL", execution_allowed=False,
                       source_selected=False, state="UNAVAILABLE", capabilities={},
                       source_mode="UNKNOWN", topology=topology(),
                       commands=_history(owner=owner), owner=owner, source_host=OWNER_HOSTS[owner],
                       error=("Device Server Python Acquisition indisponible." if owner == "acquisition"
                              else "Device Server Python SuperVision indisponible.")), 503


@api.post("/approvals")
def local_approval():
    """Local console confirmation only; performs a read, never dispatches."""
    try:
        subject = _local_subject()
        if subject is None:
            return jsonify(error="Explicit local console approval mode required"), 403
        if request.mimetype != "application/json":
            return jsonify(error="application/json required"), 415
        command = validate_request(strict_json(request.stream.read(2049)))
        owner = _request_owner()
        _owner_operation(command, owner)
        unused, view = read_view(owner=owner)
        _check_current_command(command, view, owner=owner)
        nonce = issue_approval(_approval_intent(command, owner), subject, _local_settings())
        return jsonify(schema_version=1, nonce=nonce, expires_in_seconds=30,
                       dispatch_attempted=False, hardware_writes=False)
    except LocalConsoleError as error:
        return jsonify(error=error.message, code=error.code, dispatch_attempted=False), error.status_code
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as error:
        return jsonify(error=str(error)[:300], dispatch_attempted=False), 409
    except Exception:
        current_app.logger.warning("Local console approval unavailable")
        return jsonify(error="Local console approval unavailable", dispatch_attempted=False), 503


@api.post("/commands")
def post_command():
    # Live machine commands require authentication even on a development LAN.
    try:
        subject = _local_subject()
        if subject is None:
            verify_jwt_in_request()
    except LocalConsoleError as error:
        return jsonify(error=error.message, code=error.code), error.status_code
    except (JWTExtendedException, PyJWTError):
        return jsonify(error="Authentification requise pour commander Acquisition."), 401
    if request.mimetype != "application/json":
        return jsonify(error="application/json required"), 415
    try:
        command = validate_request(strict_json(request.stream.read(2049)))
        owner = _request_owner()
        _owner_operation(command, owner)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError) as error:
        return jsonify(error=str(error)), 400
    try:
        nonce = request.headers.get('X-PYCONLYSE-HARDWARE-APPROVAL')
        if subject is not None:
            consume_approval(_approval_intent(command, owner), subject, nonce, _local_settings())
        else:
            authorize_runtime_operation(hardware_intent(command, owner), nonce, required=True)
    except (AuthorizationError, LocalConsoleError) as error:
        # This validated, correlated attempt has not reached the command DB
        # or Tango. A caller may clear only its newly reserved local intent;
        # a lost transport reply or unrelated old intent remains unknown.
        return jsonify(schema_version=1, error=error.message, code=error.code,
            automatic_retry=False, receipt=_receipt(command, 'REJECTED', owner=owner,
                dispatch_attempted=False, error=error.message)), error.status_code
    encoded = json.dumps(command if owner == "acquisition" else dict(owner=owner, request=command),
                         sort_keys=True, separators=(",", ":"))
    ledger_id = _ledger_id(command["command_id"], owner)
    db = _database()
    try:
        # Durable at-most-once *dispatch*: never reissue an unknown attempt.
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT request,receipt FROM commands WHERE id=?", (ledger_id,)).fetchone()
        if row:
            db.execute("COMMIT")
            if row[0] != encoded:
                return jsonify(error="COMMAND_ID_REUSED_WITH_DIFFERENT_REQUEST"), 409
            return jsonify(schema_version=1, receipt=json.loads(row[1]), duplicate=True)
        if command["operation"] != "modulator.general.stop":
            for previous, receipt in db.execute("SELECT request,receipt FROM commands"):
                previous_owner, previous_command = _stored_request(previous)
                if (previous_owner == owner and previous_command["session_id"] == command["session_id"]
                        and json.loads(receipt)["outcome"] == "INDETERMINATE"):
                    db.execute("ROLLBACK")
                    return jsonify(error="UNRESOLVED_DISPATCH_DO_NOT_RESEND"), 409
        try:
            proxy, view = read_view(owner=owner)
            runtime = view["runtime"]
            _check_current_command(command, view, owner=owner)
        except Exception as error:
            db.execute("ROLLBACK")
            # Fresh first-attempt ID, no reservation/ExecuteCommand yet.
            # A source/boot/capability change is a refusal, not an unknown
            # actuation result. Existing-ID branches above never use this.
            message = str(error)[:300]
            return jsonify(schema_version=1, error=message,
                code=owner + "_pre_dispatch_rejected", automatic_retry=False,
                receipt=_receipt(command, "REJECTED", owner=owner, dispatch_attempted=False, error=message)), 409
        receipt = _receipt(command, "INDETERMINATE", owner=owner,
                           error="Dispatch reserved; check XP receipt, never retry automatically")
        db.execute("INSERT INTO commands VALUES (?,?,?)", (ledger_id, encoded, json.dumps(receipt)))
        db.execute("COMMIT")
        try:
            proxy.set_timeout_millis(5000)
            method = "ExecuteCommand" if owner == "acquisition" else "ExecuteOwnerCommand"
            payload = command if owner == "acquisition" else dict(owner=owner, request=command)
            result = _json(proxy.command_inout(method, json.dumps(payload)))
            if (any(result.get(key) != command[key] for key in ("command_id", "session_id", "operation"))
                    or result.get("hardware_acknowledged") is not False or result.get("outcome") not in
                    ("QUEUED", "EXECUTING", "COMPLETED", "FAILED", "REJECTED", "INTERRUPTED", "INDETERMINATE")):
                raise ValueError("Command receipt mismatch; result unknown")
            receipt = _receipt(command, result["outcome"], owner=owner, error=str(result.get("error", ""))[:300])
        except Exception as error:
            receipt = _receipt(command, "INDETERMINATE", owner=owner, error=type(error).__name__ + ": " + str(error)[:200])
        db.execute("UPDATE commands SET receipt=? WHERE id=?", (json.dumps(receipt), ledger_id))
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
