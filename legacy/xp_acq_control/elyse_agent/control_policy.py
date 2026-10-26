"""Named command admission, independent of browser and Tango; Python 3.4.

These gates are additional Python policy, not recovered hardware interlocks.
Commissioning flags must be established locally, never from an HTTP request.
"""
import math
from .acquisition_beamline import BEAMLINE_OPERATIONS
from .acquisition_counter_timing import validate_remote_timing
from .supervised_test import controls_permitted, supervised_allowed
from .command_protocol import validate_circulation_confirmation
from .runtime_identity import valid_hex


def known_ht_command(sequence):
    """A retained software command is not measured HT or a physical permit."""
    if type(sequence) is not dict or sequence.get("owner_current") is not True:
        return None
    command = sequence.get("current_command_kv")
    if (sequence.get("command_known") is not True or type(command) not in (int, float)
            or not math.isfinite(command) or not -20 <= command <= 20):
        return None
    return command


def require_ht_value(sequence, requested):
    """Additional Python sequence gate for increases, never a VI interlock.

    Known-command decreases do not require the two completed start sequences.
    Dedicated stop/HT-discharge procedures do not call this scalar admission.
    """
    current = known_ht_command(sequence)
    if current is None:
        raise RuntimeError("CURRENT_OWNER_HT_COMMAND_UNKNOWN")
    if type(requested) not in (int, float) or not math.isfinite(requested):
        raise ValueError("FINITE_HT_REQUEST_VALUE_REQUIRED")
    if requested > current and (sequence.get("supply_sequence_completed") is not True
                                or sequence.get("pulses_sequence_completed") is not True):
        raise RuntimeError("HT_INCREASE_REQUIRES_CURRENT_OWNER_SUPPLY_AND_PULSE_SEQUENCES")


def _confirmation_candidates(value):
    rows = value.get("cooling_safety", {}).get("confirmation_candidates", ())
    if type(rows) is not list:
        return set()
    return {row["incident_id"] for row in rows if type(row) is dict
        and valid_hex(row.get("incident_id"), 32)
        and type(row.get("remaining_seconds")) in (int, float)
        and math.isfinite(row["remaining_seconds"]) and row["remaining_seconds"] > 0}


def _circulation_confirmation_reason(value):
    """Software incident decision only; never a water or energy-start permit."""
    age = value.get("application_view_age_seconds")
    if (value.get("application_view_current") is False or value.get("telemetry_view_current") is False
            or value.get("application_view_error") or value.get("local_request_pending")
            or ("application_view_age_seconds" in value and (type(age) not in (int, float)
                or not math.isfinite(age) or not 0 <= age < 2))):
        return "APPLICATION_METADATA_NOT_CURRENT"
    operation = value.get("current_operation")
    stopping = (operation in ("modulator.general.stop", "acq.outer.controlled_stop", "acq.timeout.cooling_trip")
        or isinstance(operation, str) and operation.startswith("acq.stage.") and operation.endswith(".stop"))
    if (stopping or value.get("pending_operation") in ("close", "general_stop", "outer_stop")
            or value.get("shutdown_requested") is True or value.get("cancellation_requested") is True):
        return "STOP_OR_CLEANUP_ALREADY_IN_PROGRESS"
    if value.get("state") not in ("RUNNING", "EXECUTING", "FAULT"):
        return "CURRENT_OWNER_REQUIRED_FOR_CIRCULATION_CONFIRMATION"
    native = value.get("native_isolation")
    if (not isinstance(native, dict) or native.get("ownership_uncertain") is not False
            or type(native.get("resource_count")) is not int or native["resource_count"] <= 0
            or not isinstance(native.get("worker_generation"), str) or not native["worker_generation"]):
        return "CURRENT_OWNER_UNCERTAIN"
    worker_state, request = native.get("worker_state"), native.get("active_request_id", "UNKNOWN")
    if not ((worker_state == "IDLE_OWNED" and request is None)
            or isinstance(worker_state, str) and worker_state.startswith("EXECUTING_")
            and type(request) is int and request > 0
            and worker_state not in ("EXECUTING_GENERAL_STOP", "EXECUTING_OUTER_CONTROLLED_STOP", "EXECUTING_CLOSE")):
        return "CURRENT_OWNER_UNCERTAIN"
    alarm = value.get("cooling_safety", {})
    if alarm.get("active") is not True or alarm.get("stop_state") != "NONE":
        return "NO_PENDING_CIRCULATION_CONFIRMATION"
    if value.get("state") == "FAULT":
        from .standard_banks import fault_diagnostic_measurement_current
        if not fault_diagnostic_measurement_current(value):
            return "FRESH_FAULT_DIAGNOSTIC_INPUTS_REQUIRED"
    if not _confirmation_candidates(value):
        return "NO_UNEXPIRED_CIRCULATION_CONFIRMATION"
    return ""


def command_capabilities(value):
    from .command_protocol import OPERATIONS
    stage = value.get("stage_execution", {})
    state = value.get("state")
    recovery = value.get("recovery", {})
    age = value.get("age_seconds")
    latest = value.get("latest") or {}
    current = (state == "RUNNING" and value.get("stale") is False
               and type(age) in (int, float) and math.isfinite(age) and 0 <= age < 2
               and latest.get("source") == "python_daqmx_acquisition"
               and latest.get("simulated") is False and not value.get("error"))
    results = {}
    for operation in OPERATIONS:
        reason = ""
        stopping = operation.endswith(".stop")
        supervised = (supervised_allowed(value, operation)
                      and value.get("operator_test_cold_attested") is True)
        permissions = dict(stage, operator_supervised_test=supervised,
                           operator_cold_water_only=value.get("operator_cold_water_only") is True)
        if value.get("remote_setpoints_enabled") is not True:
            reason = "REMOTE_CONTROL_DISABLED"
        elif (value.get("startup_complete") is False
              or supervised and value.get("startup_complete") is not True):
            reason = "ALL_REQUIRED_CARDS_AND_STARTUP_NOT_READY"
        elif recovery.get("required") is not False or recovery.get("protection_active") is not True:
            reason = "LOCAL_OWNERSHIP_RECOVERY_REQUIRED"
        elif not value.get("resource_count"):
            reason = "INITIALIZE_LOCALLY_ON_XP"
        elif ("ownership_uncertain" in value.get("native_isolation", {})
              and value["native_isolation"].get("ownership_uncertain") is not False):
            reason = "CURRENT_OWNER_UNCERTAIN"
        elif operation == "cooling.confirm_circulation":
            if value.get("startup_complete") is not True:
                reason = "ALL_REQUIRED_CARDS_AND_STARTUP_NOT_READY"
            else:
                reason = _circulation_confirmation_reason(value)
        elif operation == "modulator.general.stop":
            if state not in ("RUNNING", "FAULT", "EXECUTING") or (
                    state == "EXECUTING" and value.get("current_operation") in
                    ("modulator.general.stop", "acq.outer.controlled_stop", "acq.timeout.cooling_trip")):
                reason = "STOP_OR_CLEANUP_ALREADY_IN_PROGRESS"
        elif state not in (("RUNNING", "FAULT") if stopping else ("RUNNING",)):
            reason = "OWNER_BUSY_OR_NOT_RUNNING"
        elif not stopping and not current:
            reason = "FRESH_PYTHON_INPUTS_REQUIRED"
        if not reason and operation not in ("modulator.general.stop", "cooling.confirm_circulation"):
            if not controls_permitted(permissions, "commissioned", operation):
                reason = "STAGE_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("alimentation_ht.") and stage.get("ht_commissioned") is not True:
                reason = "HT_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("focales.") and not controls_permitted(permissions, "focal_commissioned", operation):
                reason = "CHROMA_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("modulator_impulse.") and stage.get("counter_commissioned") is not True:
                reason = "COUNTER_CONTROLS_NOT_COMMISSIONED"
            elif operation == "ht_voltage.set" and stage.get("ht_voltage_commissioned") is not True:
                reason = "HT_VOLTAGE_NOT_COMMISSIONED"
            elif operation == "counter_timing.set" and stage.get("counter_timing_commissioned") is not True:
                reason = "COUNTER_TIMING_NOT_COMMISSIONED"
            elif operation in BEAMLINE_OPERATIONS and stage.get("beamline_commissioned") is not True:
                reason = "BEAMLINE_CONTROLS_NOT_COMMISSIONED"
            elif operation == "ht_voltage.set" and known_ht_command(value.get("ht_sequence_state")) is None:
                reason = "CURRENT_OWNER_HT_COMMAND_UNKNOWN"
            elif operation == "cooling.stop" and not supervised:
                reason = "COOLING_STOP_REQUIRES_LOCAL_COOLDOWN_VERIFICATION"
            elif not stopping:
                if value.get("full_stop_commissioned") is not True and not supervised:
                    reason = "HT_CHROMA_COOLING_SHUTDOWN_NOT_COMMISSIONED"
                elif operation == "modulator.general.start":
                    if value.get("general_stop_required") is not False:
                        reason = "GENERAL_ALREADY_STARTED_OR_STOP_REQUIRED"
                elif (operation == "cooling.start" and supervised
                      and value.get("operator_test_general_epoch_current") is not True):
                    reason = "GENERAL_REQUIRED_BEFORE_OPERATOR_WATER"
                elif operation != "cooling.start" and value.get("general_cooling_ready") is not True:
                    reason = "GENERAL_AND_CONFIRMED_COOLING_REQUIRED"
                elif operation != "cooling.start" and value.get("cooling_permit_current") is not True:
                    reason = "FRESH_NORMAL_CANON_SECTION_COOLING_REQUIRED"
        results[operation] = dict(enabled=not reason, reason=reason)
    return results


def require_command(value, operation, command_value=None):
    capability = command_capabilities(value).get(operation)
    if capability is None or not capability["enabled"]:
        raise RuntimeError(capability["reason"] if capability else "UNKNOWN_NAMED_OPERATION")
    if operation == "ht_voltage.set":
        require_ht_value(value.get("ht_sequence_state"), command_value)
    elif operation == "counter_timing.set":
        timing = validate_remote_timing(command_value)
        running = value.get("counter_timing_state", {}).get("running_counters", [])
        if timing["counter"] not in running:
            raise RuntimeError("COUNTER_TIMING_REQUIRES_ALREADY_RUNNING_COUNTER")
    elif operation == "cooling.confirm_circulation":
        confirmation = validate_circulation_confirmation(command_value)
        if not set(confirmation["incident_ids"]).issubset(_confirmation_candidates(value)):
            raise RuntimeError("CIRCULATION_CONFIRMATION_INCIDENT_CHANGED_OR_EXPIRED")

