"""Python NI owner -> standard 27 banks -> existing Everest signed sink.

Python 3.4, stdlib only. The publisher observes owner memory; it never reads
cards, changes outputs, initializes hardware, or waits for network on NI owner.
Unavailable banks carry null and an application error, never synthetic zeros.
"""
import copy
import datetime
import math
import json
import os

from .shared_state import BANKS, SNAPSHOT_PUBLICATION, validate_snapshot_packet

UNAVAILABLE = -80001  # Application code, not a claimed native NI error.
INPUTS = {
    "C1NI6071E": ("C1_NI6071E_AI", "analog_input", 1, 64, "legacy_scaled_values", "DBL"),
    "C2NI6071E": ("C2_NI6071E_AI", "analog_input", 2, 64, "legacy_scaled_values", "DBL"),
    "C3_IN_DIO96": ("C3_DIO96_DI", "digital_input", 3, 56, "values", "Boolean"),
    "C4_IN_DIO96": ("C4_DIO96_DI", "digital_input", 4, 64, "values", "Boolean"),
    "C5_IN_DIO96": ("C5_DIO96_DI", "digital_input", 5, 56, "values", "Boolean"),
}
COMMANDS = {
    "C3_OUT_DIO96": ("commanded_digital", "C3_DIO96_DO", 40, "Boolean"),
    "C4_OUT_DIO96": ("commanded_digital", "C4_DIO96_DO", 32, "Boolean"),
    "C5_OUT_DIO96": ("commanded_digital", "C5_DIO96_DO", 40, "Boolean"),
    "C6NI6703": ("commanded_analog_logical", "C6NI6703", 10, "DBL"),
    "C7NI6703": ("commanded_analog_logical", "C7NI6703", 10, "DBL"),
    "C8NI6703": ("commanded_analog_logical", "C8NI6703", 10, "DBL"),
    "C9NI6703": ("commanded_analog_logical", "C9NI6703", 10, "DBL"),
}
# These are Acquisition local-ref software images, not DI readback, permits,
# or a statement that an external supply acknowledged a command. The source
# root frame resets complete EPS/DPS images; reviewed event handlers mutate
# individual fields in those remembered images.
SOFTWARE_STATUSES = {"EPS": (77, "Boolean"), "DPS": (29, "Boolean")}
SOFTWARE_STATUS_SOURCE = "python_acquisition_software_memory"
_SCHEMA = None


def schemas():
    global _SCHEMA
    if _SCHEMA is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "standard_telemetry_schema.json")
        with open(path, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        if value.get("schema_version") != 1 or set(value.get("banks", {})) != set(BANKS):
            raise ValueError("Pinned 27-bank type descriptors required")
        _SCHEMA = value["banks"]
    return _SCHEMA


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _values(value, count, kind):
    return (isinstance(value, list) and len(value) == count and
            all(type(item) is bool if kind == "Boolean" else _finite(item) for item in value))


def _native_values(value, count, kind):
    # Owner IPC deliberately preserves tuples. Normalize only after the exact
    # native image has been checked; the public wire validator stays list-only.
    return isinstance(value, (list, tuple)) and _values(list(value), count, kind)


def _record(bank, values=None, kind=None, reason="PYTHON_BANK_NOT_YET_MIGRATED"):
    return dict(publication=bank, data=copy.deepcopy(list(values)) if values is not None else None,
        lv_type=copy.deepcopy(schemas()[bank]),
        error=dict(status=values is None, code=UNAVAILABLE if values is None else 0,
                   source=reason if values is None else ""))


def _measurement_current(runtime):
    """Only a genuine fresh owner sample, never an execution heartbeat."""
    latest = runtime.get("latest") or {}
    age = runtime.get("age_seconds")
    return (runtime.get("state") in ("RUNNING", "EXECUTING")
            and (runtime.get("state") != "EXECUTING"
                 or runtime.get("measurement_current") is True)
            and ("measurement_current" not in runtime
                 or runtime.get("measurement_current") is True)
            and runtime.get("stale") is False and not runtime.get("error")
            and runtime.get("telemetry_view_current") is not False
            and _finite(age) and 0 <= age < 2
            and latest.get("source") == "python_daqmx_acquisition"
            and latest.get("simulated") is False)


def fault_diagnostic_measurement_current(runtime):
    """Fresh readback from a settled FAULT owner, never permission to act.

    A procedure error does not invalidate a later successful input read. The
    explicit observation must match this owner, session and sample; old latest
    data or an idle HTTP heartbeat cannot supply the missing evidence.
    """
    value = runtime.get("fault_diagnostic_measurement")
    native = runtime.get("native_isolation")
    latest = runtime.get("latest") or {}
    age = runtime.get("age_seconds")
    sequence = runtime.get("sequence")
    if (runtime.get("state") != "FAULT"
            or runtime.get("telemetry_view_current") is False
            or runtime.get("application_view_current") is False
            or not isinstance(value, dict) or not isinstance(native, dict)):
        return False
    settled = (native.get("worker_state") == "IDLE_OWNED"
               and native.get("active_request_id") is None)
    reading = (value.get("read_in_progress") is True
               and native.get("worker_state") == "EXECUTING_READ_SNAPSHOT"
               and type(native.get("active_request_id")) is int
               and native["active_request_id"] > 0)
    return (value.get("current") is True
            and value.get("source") == "settled_fault_owner_readback"
            and value.get("command_admission") is False
            and isinstance(runtime.get("session_id"), str)
            and value.get("session_id") == runtime["session_id"]
            and type(sequence) is int and sequence > 0
            and type(value.get("sequence")) is int
            and value["sequence"] == sequence
            and _finite(age) and 0 <= age < 2
            and _finite(value.get("age_seconds"))
            and value["age_seconds"] == age
            and (settled or reading)
            and native.get("ownership_uncertain") is False
            and type(native.get("resource_count")) is int
            and native["resource_count"] > 0
            and isinstance(native.get("worker_generation"), str)
            and bool(native["worker_generation"])
            and value.get("worker_generation") == native["worker_generation"]
            and latest.get("source") == "python_daqmx_acquisition"
            and latest.get("simulated") is False)


def _software_status_image(runtime, measured_current):
    """Select independently attested current-owner memory or fresh sample.

    Literal software assignments persist until another assignment. Their
    change age is therefore not a two-second hardware-sample freshness test.
    The runtime must attest current owner/session validity on every projection;
    a fault, lifecycle transition, cancellation or missing attestation cannot
    revive status merely because its Boolean values are still in RAM.
    """
    if "software_state" in runtime:
        value = runtime.get("software_state")
        age = runtime.get("software_state_age_seconds")
        if (runtime.get("state") not in ("RUNNING", "EXECUTING")
                or runtime.get("error")
                or runtime.get("telemetry_view_current") is False
                or runtime.get("software_state_current") is not True
                or not _finite(age) or age < 0 or not isinstance(value, dict)
                or value.get("source") != SOFTWARE_STATUS_SOURCE
                or value.get("simulated") is not False
                or value.get("session_id") != runtime.get("session_id")
                or type(value.get("sequence")) is not int or value["sequence"] < 0
                or type(runtime.get("software_state_sequence")) is not int
                or value.get("sequence") != runtime.get("software_state_sequence")
                or type(value.get("source_revision")) is not int or value["source_revision"] < 0
                or value.get("hardware_acknowledged") is not False
                or value.get("psp_delivery_acknowledged") is not False):
            return {}
        image = value.get("local_banks")
        return image if isinstance(image, dict) else {}
    if measured_current:
        # Compatibility with a full genuine read_snapshot, which includes the
        # owner's local software image at that sample. Never use cached latest
        # for a status-only progress message or after a measurement expires.
        stage = (runtime.get("latest") or {}).get("stage_state") or {}
        if stage.get("software_status_valid") is not True:
            return {}
        image = stage.get("local_banks")
        return image if isinstance(image, dict) else {}
    return {}


def standard_packet(runtime, publication_sequence, now=None):
    """Same bank order/envelope as LabVIEW; honest source and per-bank errors."""
    latest = runtime.get("latest") or {}
    current = _measurement_current(runtime)
    diagnostic = fault_diagnostic_measurement_current(runtime)
    software = _software_status_image(runtime, current)
    records = []
    for bank in BANKS:
        value, kind = None, None
        reason = "PYTHON_BANK_NOT_YET_MIGRATED" if current else "PYTHON_INPUTS_NOT_CURRENT"
        if (current or diagnostic) and bank in INPUTS:
            source, native_kind, device, count, field, kind = INPUTS[bank]
            record = latest.get("banks", {}).get(source, {})
            candidate = record.get(field)
            if record.get("kind") == native_kind and record.get("device") == device and _native_values(candidate, count, kind):
                value = candidate
            else:
                reason = "PYTHON_INPUT_BANK_INVALID_OR_CALIBRATION_MISSING"
        elif current and bank in COMMANDS:
            section, source, count, kind = COMMANDS[bank]
            candidate = latest.get(section, {}).get(source)
            if _native_values(candidate, count, kind):
                value = candidate
            else:
                reason = "PYTHON_LAST_SUCCESSFUL_COMMAND_UNKNOWN"
        elif bank in SOFTWARE_STATUSES:
            count, kind = SOFTWARE_STATUSES[bank]
            candidate = software.get(bank)
            if _native_values(candidate, count, kind):
                value = candidate
            else:
                reason = "PYTHON_SOFTWARE_STATUS_UNKNOWN_OR_NOT_CURRENT"
        records.append(_record(bank, value, kind, reason))
    stamp = now or datetime.datetime.now(datetime.timezone.utc)
    packet = dict(session_id=runtime["session_id"], publication=SNAPSHOT_PUBLICATION,
        sequence=publication_sequence, source_seconds_1904=stamp.timestamp() + 2082844800,
        producer_kind="python_acquisition", source_site="python_ni_owner_standard_27_banks",
        error=dict(status=False, code=0, source=""),
        data=dict(snapshot_version=1, capture_kind="sequential_card_inputs_and_command_memory",
                  timestamp_origin="xp_runtime_snapshot_not_atomic", banks=records))
    validate_snapshot_packet(packet)
    return packet


def packet_age_seconds(runtime, packet):
    """Conservative age of populated categories in the fixed 27-bank frame.

    The unchanged wire envelope has one age, not independent per-bank clocks.
    Use the oldest populated source category: status progress cannot freshen
    an older AI/DI sample, and null/unknown hardware does not make a fresh
    software-memory observation look like a fresh hardware measurement.
    """
    ages = []
    records = packet.get("data", {}).get("banks", ())
    populated = set(record.get("publication") for record in records
                    if record.get("data") is not None
                    and record.get("error") == dict(status=False, code=0, source=""))
    if populated.intersection(set(INPUTS) | set(COMMANDS)):
        ages.append(runtime.get("age_seconds"))
    if populated.intersection(SOFTWARE_STATUSES):
        ages.append(runtime.get("software_state_age_seconds")
                    if "software_state" in runtime else runtime.get("age_seconds"))
    if any(not _finite(age) or age < 0 for age in ages):
        raise ValueError("Populated native telemetry requires finite nonnegative source ages")
    return max(ages) if ages else 0.


def validate_standard_packet(packet):
    encoded = validate_snapshot_packet(packet)
    if packet.get("producer_kind") != "python_acquisition":
        raise ValueError("Explicit Python producer required")
    for record in packet["data"]["banks"]:
        name, value, error = record["publication"], record["data"], record["error"]
        if record["lv_type"] != schemas()[name]:
            raise ValueError("Python publication changed standard LabVIEW type descriptor")
        if value is None:
            if error["status"] is not True or error["code"] != UNAVAILABLE or not error["source"]:
                raise ValueError("Unavailable bank must be null with explicit application error")
            continue
        if name in INPUTS:
            unused, unused_kind, unused_device, count, unused_field, kind = INPUTS[name]
        elif name in COMMANDS:
            unused_section, unused_source, count, kind = COMMANDS[name]
        elif name in SOFTWARE_STATUSES:
            count, kind = SOFTWARE_STATUSES[name]
        else:
            raise ValueError("Unmigrated Python bank cannot claim valid values")
        shape = record["lv_type"].get("contained_type") or {}
        if (not _values(value, count, kind) or error != dict(status=False, code=0, source="")
                or shape.get("type") != "Cluster" or shape.get("name") != name
                or len(shape.get("fields", [])) != count
                or any(item.get("type") != kind for item in shape["fields"])):
            raise ValueError("Invalid typed Python bank")
    return encoded
