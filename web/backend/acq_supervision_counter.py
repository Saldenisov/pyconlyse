"""Bounded read-only projection of the independent SuperVision counter memory."""
import math
import re

SESSION = re.compile(r"^[0-9a-f]{32}$")
SOURCES = {"PYTHON_NATIVE": "last_successful_counter_command_memory",
           "LABVIEW_BRIDGE": "observed_labview_control_memory"}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def project_counter(value):
    if (type(value) is not dict or value.get("owner") != "supervision"
            or type(value.get("available")) is not bool or value.get("read_only") is not True
            or value.get("hardware_acknowledged") is not False
            or value.get("physical_measurements_verified", False) is not False):
        raise ValueError("Read-only SuperVision counter contract required")
    available = value["available"]
    age, mode = value.get("age_seconds"), value.get("source_mode", "UNAVAILABLE")
    if age is not None and (not finite(age) or age < 0):
        raise ValueError("Finite nonnegative SuperVision counter age required")
    if mode not in ("UNAVAILABLE", "PYTHON_NATIVE", "LABVIEW_BRIDGE"):
        raise ValueError("Known SuperVision source mode required")
    values = value.get("values")
    session, sequence = value.get("session_id"), value.get("sequence")
    selector, pending = value.get("selector"), value.get("pending_selector")
    if (session is not None and (type(session) is not str or not SESSION.fullmatch(session))
            or sequence is not None and (type(sequence) is not int or not 1 <= sequence <= 2**53 - 1)
            or selector is not None and not finite(selector)
            or pending is not None and type(pending) is not bool
            or value.get("source") is not None and value["source"] not in SOURCES.values()):
        raise ValueError("Bounded counter observation metadata required")
    if available:
        if (age is None or value.get("stale") is not False
                or mode not in SOURCES or value.get("source") != SOURCES[mode]
                or type(values) is not list or len(values) != 16
                or any(not finite(item) for item in values)
                or not SESSION.fullmatch(session or "")
                or type(value.get("sequence")) is not int or not 1 <= value["sequence"] <= 2**53 - 1
                or not finite(value.get("selector")) or type(value.get("pending_selector")) is not bool
                or value["pending_selector"] is False and value["selector"] != -1):
            raise ValueError("Current independent16-value SuperVision memory required")
    elif values is not None:
        raise ValueError("Unavailable SuperVision memory cannot carry current values")
    identity = value.get("source_identity")
    if identity is not None and (type(identity) is not dict
            or set(identity) != {"source", "session_id", "sequence"}
            or identity["source"] != "labview_supervision_typed_local"
            or not SESSION.fullmatch(identity.get("session_id") or "")
            or type(identity.get("sequence")) is not int or not 1 <= identity["sequence"] <= 2**53 - 1):
        raise ValueError("Bounded SuperVision observation identity required")
    current = available and age < 2
    return dict(owner="supervision", source_host="10.20.30.2", available=current,
        stale=not current, age_seconds=age, values=list(values) if current else None,
        source=value.get("source"), source_mode=mode, session_id=value.get("session_id"),
        sequence=value.get("sequence"), selector=value.get("selector"),
        pending_selector=value.get("pending_selector"), source_identity=identity,
        read_only=True, hardware_acknowledged=False, physical_measurements_verified=False,
        stale_after_seconds=2,
        interpretation="Observed counter control memory, not hardware timing readback")
