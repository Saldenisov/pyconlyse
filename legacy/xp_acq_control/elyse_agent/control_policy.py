"""Named command admission, independent of browser and Tango; Python 3.4.

These gates are additional Python policy, not recovered hardware interlocks.
Commissioning flags must be established locally, never from an HTTP request.
"""
import math


def command_capabilities(value):
    from .acquisition_remote import OPERATIONS
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
        if value.get("remote_setpoints_enabled") is not True:
            reason = "REMOTE_CONTROL_DISABLED"
        elif recovery.get("required") is not False or recovery.get("protection_active") is not True:
            reason = "LOCAL_OWNERSHIP_RECOVERY_REQUIRED"
        elif not value.get("resource_count"):
            reason = "INITIALIZE_LOCALLY_ON_XP"
        elif operation == "modulator.general.stop":
            if state not in ("RUNNING", "FAULT", "EXECUTING") or (
                    state == "EXECUTING" and value.get("current_operation") in
                    ("modulator.general.stop", "acq.outer.controlled_stop", "acq.timeout.cooling_trip")):
                reason = "STOP_OR_CLEANUP_ALREADY_IN_PROGRESS"
        elif state not in (("RUNNING", "FAULT") if stopping else ("RUNNING",)):
            reason = "OWNER_BUSY_OR_NOT_RUNNING"
        elif not stopping and not current:
            reason = "FRESH_PYTHON_INPUTS_REQUIRED"
        if not reason and operation != "modulator.general.stop":
            if stage.get("commissioned") is not True:
                reason = "STAGE_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("alimentation_ht.") and stage.get("ht_commissioned") is not True:
                reason = "HT_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("focales.") and stage.get("focal_commissioned") is not True:
                reason = "CHROMA_CONTROLS_NOT_COMMISSIONED"
            elif operation.startswith("modulator_impulse.") and stage.get("counter_commissioned") is not True:
                reason = "COUNTER_CONTROLS_NOT_COMMISSIONED"
            elif operation == "ht_voltage.set" and stage.get("ht_voltage_commissioned") is not True:
                reason = "HT_VOLTAGE_NOT_COMMISSIONED"
            elif operation == "cooling.stop":
                reason = "COOLING_STOP_REQUIRES_LOCAL_COOLDOWN_VERIFICATION"
            elif not stopping:
                if value.get("full_stop_commissioned") is not True:
                    reason = "HT_CHROMA_COOLING_SHUTDOWN_NOT_COMMISSIONED"
                elif operation == "modulator.general.start":
                    if value.get("general_stop_required") is not False:
                        reason = "GENERAL_ALREADY_STARTED_OR_STOP_REQUIRED"
                elif operation != "cooling.start" and value.get("general_cooling_ready") is not True:
                    reason = "GENERAL_AND_CONFIRMED_COOLING_REQUIRED"
                elif operation != "cooling.start" and value.get("cooling_permit_current") is not True:
                    reason = "FRESH_NORMAL_CANON_SECTION_COOLING_REQUIRED"
        results[operation] = dict(enabled=not reason, reason=reason)
    return results


def require_command(value, operation):
    capability = command_capabilities(value).get(operation)
    if capability is None or not capability["enabled"]:
        raise RuntimeError(capability["reason"] if capability else "UNKNOWN_NAMED_OPERATION")

