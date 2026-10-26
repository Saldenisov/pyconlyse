"""Pure health projection for the read-only XP runtime view.

A responsive authenticated HTTP service is not proof of fresh NI input data.
Tango state names are returned as strings. Projection performs no Tango, NI,
network, clock or device calls. Thresholds match the existing two boundaries:
the XP runtime marks input snapshots stale after 2 s; the bridge after 3 s.
"""

import math
import re

from legacy.xp_acq_control.elyse_agent.standard_banks import fault_diagnostic_measurement_current


SOURCE_MAX_AGE_SECONDS = 2.0
BRIDGE_MAX_AGE_SECONDS = 3.0
STANDBY_RUNTIME_STATES = frozenset(("IDLE", "INITIALIZING", "DEINITIALIZING", "STOPPED"))
RUNTIME_PROTOCOL_VERSION = 2
RUNTIME_STATES = STANDBY_RUNTIME_STATES | frozenset(("RUNNING", "EXECUTING", "FAULT", "RECOVERY_REQUIRED"))
INPUT_BANKS = {
    "C1_NI6071E_AI": ("analog_input", 1, 64),
    "C2_NI6071E_AI": ("analog_input", 2, 64),
    "C11_NI6220_AI": ("analog_input", 11, 16),
    "C3_DIO96_DI": ("digital_input", 3, 56),
    "C4_DIO96_DI": ("digital_input", 4, 64),
    "C5_DIO96_DI": ("digital_input", 5, 56),
}


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _valid_age(value):
    return _finite_number(value) and value >= 0


def project_runtime_health(runtime, bridge_age_seconds, bridge_error="", reader_started=True,
                           read_duration_seconds=0.0, session_changed=False, protocol_error=""):
    """Separate transport freshness, source freshness and lifecycle activity.

    EXECUTING deliberately marks the XP input snapshot stale while its single
    NI owner performs a procedure. Represent that activity as MOVING, not a
    fresh acquisition RUNNING claim. IDLE and other inactive lifecycle states
    remain STANDBY even though they normally have no current input snapshot.
    Add cached bridge elapsed time and the whole signed HTTP read duration to
    the XP-reported age. The latter is a conservative transport allowance,
    not a subtraction between unsynchronised host clocks.
    """
    bridge_stale = (not reader_started or bool(bridge_error)
                    or not _valid_age(bridge_age_seconds)
                    or bridge_age_seconds > BRIDGE_MAX_AGE_SECONDS)
    value = runtime if isinstance(runtime, dict) else {}
    raw_state = value.get("state")
    state = raw_state if isinstance(raw_state, str) else None
    reported_age = value.get("age_seconds")
    latest = value.get("latest")
    source_age = (reported_age + bridge_age_seconds + read_duration_seconds
                  if all(_valid_age(age) for age in
                         (reported_age, bridge_age_seconds, read_duration_seconds)) else None)
    source_current = (not bridge_stale and state == "RUNNING"
                      and value.get("stale") is False and not value.get("error")
                      and _valid_age(source_age) and source_age <= SOURCE_MAX_AGE_SECONDS
                      and isinstance(latest, dict)
                      and latest.get("source") == "python_daqmx_acquisition"
                      and latest.get("simulated") is False)
    diagnostic_current = _diagnostic_current(value, bridge_stale, source_age,
                                             session_changed, protocol_error)
    prefix = "XP runtime: {0}".format(state if state is not None else "unknown")
    if not reader_started:
        tango_state = "FAULT"
        status = "XP runtime reader unavailable: " + str(bridge_error)
    elif bridge_stale:
        tango_state = "UNKNOWN"
        status = "No current authenticated XP runtime snapshot: " + str(bridge_error)
    elif state == "FAULT":
        tango_state = "FAULT"
        status = prefix + "; " + str(value.get("error") or "NI runtime fault")
        if diagnostic_current:
            status += "; fresh diagnostic NI input readback during FAULT"
    elif state in STANDBY_RUNTIME_STATES:
        tango_state = "STANDBY"
        status = prefix + "; no current NI acquisition data expected"
    elif state == "EXECUTING":
        tango_state = "MOVING"
        status = prefix + "; procedure active; current NI input acquisition not confirmed"
    elif source_current:
        tango_state = "RUNNING"
        status = prefix + "; current NI input snapshot"
    else:
        tango_state = "UNKNOWN"
        status = prefix + "; NI input snapshot stale, missing or invalid"
    return dict(
        tango_state=tango_state,
        status=status + "; no remote controls enabled",
        bridge_stale=bridge_stale,
        source_current=source_current,
        diagnostic_source_current=diagnostic_current,
        diagnostic_source_age_seconds=(source_age if _valid_age(source_age)
            and isinstance(value.get("fault_diagnostic_measurement"), dict) else None),
        source_stale=not source_current,
        source_age_seconds=source_age if _valid_age(source_age) else None,
        source_reported_age_seconds=reported_age if _valid_age(reported_age) else None,
        runtime_state=state,
    )


def validate_runtime_identity(runtime):
    """Protocol identity is mandatory at the new web/bridge contract boundary.

    build_id fingerprints source files; it is not a signed deployment or Git
    attestation. protection_active=False does not fabricate bad NI readings.
    """
    if not isinstance(runtime, dict):
        raise ValueError("Missing Python runtime object")
    if (type(runtime.get("runtime_protocol_version")) is not int
            or runtime["runtime_protocol_version"] != RUNTIME_PROTOCOL_VERSION):
        raise ValueError("Python runtime protocol version 2 required")
    for name, length in (("session_id", 32), ("build_id", 64)):
        value = runtime.get(name)
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{" + str(length) + "}", value):
            raise ValueError("Invalid Python runtime " + name)
    revision = runtime.get("state_revision")
    if type(revision) is not int or revision < 0 or revision > 2**53 - 1:
        raise ValueError("Invalid Python runtime state revision")
    recovery = runtime.get("recovery")
    if (not isinstance(recovery, dict) or type(recovery.get("required")) is not bool
            or type(recovery.get("protection_active")) is not bool
            or not isinstance(recovery.get("reason"), str) or len(recovery["reason"]) > 2048):
        raise ValueError("Invalid Python runtime recovery contract")
    if not isinstance(runtime.get("state"), str) or runtime["state"] not in RUNTIME_STATES:
        raise ValueError("Unknown Python runtime lifecycle state")
    if type(runtime.get("stale")) is not bool or not isinstance(runtime.get("error"), str):
        raise ValueError("Invalid Python runtime freshness/error contract")
    if (runtime.get("storage_mode") != "ram_latest" or runtime.get("auto_initialize") is not False
            or runtime.get("remote_initialization_enabled") is not False
            or runtime.get("remote_setpoints_enabled") is not False):
        raise ValueError("Unexpected Python runtime safety contract")
    return dict(session_id=runtime["session_id"], build_id=runtime["build_id"],
                state_revision=revision, recovery=dict(recovery))


def _complete_input_banks(latest):
    banks = latest.get("banks") if isinstance(latest, dict) else None
    if not isinstance(banks, dict) or set(banks) != set(INPUT_BANKS):
        return False
    for name, (kind, device, count) in INPUT_BANKS.items():
        bank = banks[name]
        if (not isinstance(bank, dict) or bank.get("kind") != kind
                or type(bank.get("device")) is not int or bank["device"] != device):
            return False
        values = bank.get("values")
        if not isinstance(values, list) or len(values) != count:
            return False
        if kind == "digital_input":
            if any(type(value) is not bool for value in values):
                return False
        elif any(not _finite_number(value) for value in values):
            return False
        scaled = bank.get("legacy_scaled_values")
        if scaled is not None and (not isinstance(scaled, list) or len(scaled) != count or any(
                not _finite_number(value) for value in scaled)):
            return False
    return True


def _diagnostic_current(runtime, bridge_stale, source_age, session_changed, protocol_error):
    """Independent settled-FAULT input observation, never lifecycle recovery."""
    if (bridge_stale or session_changed or protocol_error
            or not _valid_age(source_age) or source_age >= SOURCE_MAX_AGE_SECONDS
            or runtime.get("stale") is not True or runtime.get("measurement_current") is not False
            or not runtime.get("error") or not _complete_input_banks(runtime.get("latest"))):
        return False
    try:
        identity = validate_runtime_identity(runtime)
    except ValueError:
        return False
    return (identity["recovery"]["required"] is False
            and fault_diagnostic_measurement_current(runtime))


def project_runtime_contract(runtime, bridge_age_seconds, bridge_error="", reader_started=True,
                             read_duration_seconds=0.0, session_changed=False, protocol_error=""):
    """Strict protocol-v2 observation. No command permission is ever derived.

    Transport errors take precedence and invalidate cached observations. A
    changed session requires another consistent poll before measurements are
    considered fresh. Every poll revalidates identity, source kind, six input
    banks and independent source/bridge age; cached Tango ON is insufficient.
    """
    health = project_runtime_health(runtime, bridge_age_seconds, bridge_error, reader_started,
                                    read_duration_seconds, session_changed, protocol_error)
    health.update(quality="UNAVAILABLE", session_id=None, build_id=None,
                  state_revision=None, recovery=None, protocol_error="",
                  execution_allowed=False, hardware_writes=False)
    if not reader_started or bridge_error or runtime is None:
        health.update(source_current=False, source_stale=True, diagnostic_source_current=False)
        return health
    try:
        identity = validate_runtime_identity(runtime)
        if protocol_error:
            raise ValueError(str(protocol_error)[:1000])
    except ValueError as error:
        health.update(quality="INCOMPATIBLE", tango_state="UNKNOWN", source_current=False,
                      source_stale=True, diagnostic_source_current=False,
                      protocol_error=str(error), status=str(error))
        return health
    health.update(identity)
    if health["bridge_stale"]:
        quality = "STALE"
    elif identity["recovery"]["required"] or runtime["state"] == "RECOVERY_REQUIRED":
        quality = "RECOVERY_REQUIRED"
        health.update(tango_state="FAULT", status="XP runtime recovery required; no remote controls enabled")
    elif runtime["state"] == "FAULT":
        quality = "FAULT"
    elif runtime["state"] in STANDBY_RUNTIME_STATES:
        quality = "IDLE" if runtime["state"] in ("IDLE", "STOPPED") else "EXECUTING"
    elif runtime["state"] == "EXECUTING":
        quality = "EXECUTING"
    elif session_changed or not health["source_current"] or not _complete_input_banks(runtime.get("latest")):
        quality = "STALE"
    else:
        quality = "FRESH"
    health["quality"] = quality
    if quality != "FRESH":
        health.update(source_current=False, source_stale=True)
        if quality == "STALE":
            health.update(tango_state="UNKNOWN", status="XP runtime observations stale or revalidating session")
    return health
