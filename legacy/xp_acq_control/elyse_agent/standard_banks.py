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
    return type(value) in (int, float) and math.isfinite(value)


def _values(value, count, kind):
    return (isinstance(value, list) and len(value) == count and
            all(type(item) is bool if kind == "Boolean" else _finite(item) for item in value))


def _record(bank, values=None, kind=None, reason="PYTHON_BANK_NOT_YET_MIGRATED"):
    return dict(publication=bank, data=copy.deepcopy(values),
        lv_type=copy.deepcopy(schemas()[bank]),
        error=dict(status=values is None, code=UNAVAILABLE if values is None else 0,
                   source=reason if values is None else ""))


def standard_packet(runtime, publication_sequence, now=None):
    """Same bank order/envelope as LabVIEW; honest source and per-bank errors."""
    latest = runtime.get("latest") or {}
    age = runtime.get("age_seconds")
    current = (runtime.get("state") == "RUNNING" and runtime.get("stale") is False
               and not runtime.get("error") and _finite(age) and 0 <= age < 2
               and latest.get("source") == "python_daqmx_acquisition" and latest.get("simulated") is False)
    records = []
    for bank in BANKS:
        value, kind = None, None
        reason = "PYTHON_BANK_NOT_YET_MIGRATED" if current else "PYTHON_INPUTS_NOT_CURRENT"
        if current and bank in INPUTS:
            source, native_kind, device, count, field, kind = INPUTS[bank]
            record = latest.get("banks", {}).get(source, {})
            candidate = record.get(field)
            if record.get("kind") == native_kind and record.get("device") == device and _values(candidate, count, kind):
                value = candidate
            else:
                reason = "PYTHON_INPUT_BANK_INVALID_OR_CALIBRATION_MISSING"
        elif current and bank in COMMANDS:
            section, source, count, kind = COMMANDS[bank]
            candidate = latest.get(section, {}).get(source)
            if _values(candidate, count, kind):
                value = candidate
            else:
                reason = "PYTHON_LAST_SUCCESSFUL_COMMAND_UNKNOWN"
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
        else:
            raise ValueError("Unmigrated Python bank cannot claim valid values")
        shape = record["lv_type"].get("contained_type") or {}
        if (not _values(value, count, kind) or error != dict(status=False, code=0, source="")
                or shape.get("type") != "Cluster" or shape.get("name") != name
                or len(shape.get("fields", [])) != count
                or any(item.get("type") != kind for item in shape["fields"])):
            raise ValueError("Invalid typed Python bank")
    return encoded
