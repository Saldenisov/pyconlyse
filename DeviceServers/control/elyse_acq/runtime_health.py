"""Pure health projection for the read-only XP runtime view.

A responsive authenticated HTTP service is not proof of fresh NI input data.
Tango state names are returned as strings so this module needs no Tango, NI,
network, clock or device imports. Thresholds match the existing two boundaries:
the XP runtime marks input snapshots stale after 2 s; the bridge after 3 s.
"""

import math


SOURCE_MAX_AGE_SECONDS = 2.0
BRIDGE_MAX_AGE_SECONDS = 3.0
STANDBY_RUNTIME_STATES = frozenset(("IDLE", "INITIALIZING", "DEINITIALIZING", "STOPPED"))


def _valid_age(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def project_runtime_health(runtime, bridge_age_seconds, bridge_error="", reader_started=True,
                           read_duration_seconds=0.0):
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
        source_stale=not source_current,
        source_age_seconds=source_age if _valid_age(source_age) else None,
        source_reported_age_seconds=reported_age if _valid_age(reported_age) else None,
        runtime_state=state,
    )
