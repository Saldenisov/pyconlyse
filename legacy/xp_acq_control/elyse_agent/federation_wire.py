"""Typed owner-scoped telemetry, stdlib/Python 3.4; import performs no I/O.

The existing signed relay envelope carries these frames. The receiver binds
the declared owner to a DIFFERENT configured key for each host. IP addresses
are only a network allowlist, never evidence of ownership. Source ages are
captured in each record; the relay body's age is queue/delivery age only.
"""
import copy
import datetime
import json
import math
import base64
import binascii

from .shared_state import BANKS
from .standard_banks import INPUTS, COMMANDS, SOFTWARE_STATUSES, schemas, UNAVAILABLE


PUBLICATION = "ELYSE_OWNER_SNAPSHOT"
ROLES = ("acquisition", "supervision")
OWNED_BANKS = {
    "acquisition": tuple(name for name in BANKS
                         if name in INPUTS or name in COMMANDS or name in SOFTWARE_STATUSES),
    "supervision": ("C12NI1409",),
}
MAX_OWNER_FRAME_BYTES = 900 * 1024
MAX_CAMERA_STRING_CHARS = 4096  # Existing C12 is a String, not an image array.
MAX_VIDEO_RAW_BYTES = 512 * 1024
COUNTER_SOURCES = ("last_successful_counter_command_memory", "observed_labview_control_memory")


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (ValueError, OverflowError):
        return False


def hex_id(value):
    return (isinstance(value, str) and len(value) == 32
            and all(c in "0123456789abcdef" for c in value))


def _error(error, available):
    if (type(error) is not dict or set(error) != {"status", "code", "source"}
            or type(error["status"]) is not bool or type(error["code"]) is not int
            or not -(2 ** 31) <= error["code"] < 2 ** 31
            or not isinstance(error["source"], str) or len(error["source"]) > 4096):
        raise ValueError("Exact bounded owner-bank error required")
    if available and error != dict(status=False, code=0, source=""):
        raise ValueError("Available owner bank cannot carry a read failure")
    if not available and (error["status"] is not True or not error["source"]):
        raise ValueError("Unavailable owner bank needs an explicit failure")


def _typed_value(name, value):
    if name == "C12NI1409":
        return isinstance(value, str) and len(value) <= MAX_CAMERA_STRING_CHARS
    if name in INPUTS:
        unused, unused_kind, unused_device, count, unused_field, kind = INPUTS[name]
    elif name in COMMANDS:
        unused_section, unused_source, count, kind = COMMANDS[name]
    elif name in SOFTWARE_STATUSES:
        count, kind = SOFTWARE_STATUSES[name]
    else:
        return False
    return (type(value) is list and len(value) == count
            and all(type(v) is bool if kind == "Boolean" else finite(v) for v in value))


def validate_counter_part(value):
    if value is None:
        return
    if (type(value) is not dict or set(value) != {
            "values", "source_age_seconds", "source", "selector", "pending_selector"}
            or type(value["values"]) is not list or len(value["values"]) != 16
            or any(not finite(v) for v in value["values"])
            or not finite(value["source_age_seconds"]) or value["source_age_seconds"] < 0
            or value["source"] not in COUNTER_SOURCES
            or type(value["pending_selector"]) is not bool
            or not finite(value["selector"])):
        raise ValueError("Explicit 16-value owner counter-memory part required")
    if value["pending_selector"] is False and value["selector"] != -1:
        raise ValueError("No-pending selector requires the explicitly observed -1 value")


def validate_video_frame(value):
    """Bounded NI1409 raw U8 capture; no decoding/rescaling into a new image."""
    if value is None:
        return
    if type(value) is not dict or set(value) != {
            "source", "simulated", "sequence", "sequence_interpretation", "capture_session_id",
            "observed_utc", "sample_elapsed_seconds", "width", "height", "pixel_type",
            "encoding", "data", "channel", "processing", "hardware_acknowledged", "source_age_seconds"}:
        raise ValueError("Exact independently identified video frame required")
    if (value["source"] != "python_supervision_ni1409" or value["simulated"] is not False
            or value["hardware_acknowledged"] is not False or not hex_id(value["capture_session_id"])
            or type(value["sequence"]) is not int or not 1 <= value["sequence"] <= 9007199254740991
            or value["sequence_interpretation"] != "software grab observation, not hardware frame counter"
            or not finite(value["sample_elapsed_seconds"]) or value["sample_elapsed_seconds"] < 0
            or not finite(value["source_age_seconds"]) or value["source_age_seconds"] < 0
            or type(value["width"]) is not int or type(value["height"]) is not int
            or not 1 <= value["width"] <= MAX_VIDEO_RAW_BYTES
            or not 1 <= value["height"] <= MAX_VIDEO_RAW_BYTES
            or value["width"] * value["height"] > MAX_VIDEO_RAW_BYTES
            or value["pixel_type"] != "U8" or value["encoding"] != "base64_raw_row_major"
            or type(value["channel"]) is not int or not 0 <= value["channel"] <= 3
            or value["processing"] != "raw_grab_before_legacy_interlace_bcg_profiles"
            or not isinstance(value["observed_utc"], str) or len(value["observed_utc"]) > 40
            or not value["observed_utc"].endswith("+00:00")
            or not isinstance(value["data"], str)
            or len(value["data"]) > 4 * ((MAX_VIDEO_RAW_BYTES + 2) // 3)):
        raise ValueError("Invalid bounded raw U8 video metadata")
    try:
        raw = base64.b64decode(value["data"].encode("ascii"), validate=True)
        stamp = value["observed_utc"][:-6]
        datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%f" if "." in stamp else "%Y-%m-%dT%H:%M:%S")
    except (UnicodeEncodeError, ValueError, binascii.Error):
        raise ValueError("Malformed raw video base64 or UTC observation time")
    if len(raw) != value["width"] * value["height"]:
        raise ValueError("Raw video byte count does not match its geometry")


def validate_owner_frame(frame):
    if type(frame) is not dict or set(frame) != {
            "schema_version", "publication", "owner", "session_id", "sequence",
            "source_mode", "source_seconds_1904", "banks", "counter_part", "video_frame"}:
        raise ValueError("Exact owner telemetry frame required")
    role = frame["owner"]
    if (type(frame["schema_version"]) is not int or frame["schema_version"] != 1
            or frame["publication"] != PUBLICATION or role not in ROLES
            or not hex_id(frame["session_id"])
            or type(frame["sequence"]) is not int or not 1 <= frame["sequence"] <= 9007199254740991
            or frame["source_mode"] not in ("PYTHON_NATIVE", "LABVIEW_BRIDGE", "UNAVAILABLE")
            or not finite(frame["source_seconds_1904"]) or frame["source_seconds_1904"] < 0
            or type(frame["banks"]) is not list
            or len(frame["banks"]) != len(OWNED_BANKS[role])):
        raise ValueError("Invalid owner telemetry identity or source metadata")
    for record, name in zip(frame["banks"], OWNED_BANKS[role]):
        if (type(record) is not dict or set(record) != {
                "publication", "data", "lv_type", "error", "source_age_seconds"}
                or record["publication"] != name or record["lv_type"] != schemas()[name]
                or not finite(record["source_age_seconds"]) or record["source_age_seconds"] < 0):
            raise ValueError("Foreign, reordered or ill-typed owner bank")
        value = record["data"]
        _error(record["error"], value is not None)
        if value is not None and (frame["source_mode"] == "UNAVAILABLE" or not _typed_value(name, value)):
            raise ValueError("Invalid typed value or unavailable source claiming data")
    validate_counter_part(frame["counter_part"])
    validate_video_frame(frame["video_frame"])
    if frame["video_frame"] is not None and (role != "supervision" or frame["source_mode"] != "PYTHON_NATIVE"):
        raise ValueError("Raw NI1409 frames belong only to the native SuperVision owner")
    if frame["source_mode"] == "UNAVAILABLE" and frame["counter_part"] is not None:
        raise ValueError("Unavailable source cannot publish current counter memory")
    raw = json.dumps(frame, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    if len(raw) > MAX_OWNER_FRAME_BYTES:
        raise ValueError("Owner frame exceeds the bounded relay contract")
    return raw


def owner_frame(owner, session_id, sequence, records=None, source_mode="UNAVAILABLE",
                counter_part=None, now=None, video_frame=None):
    """Build complete owned subset. Missing banks stay null, never zero-filled.

    ``records`` is a map containing ONLY that owner's publications. Callers
    forwarding a legacy 27-bank frame must select the explicit owner subset.
    This helper does not turn timestamps/heartbeats into available bank data.
    """
    if owner not in ROLES or records is not None and type(records) is not dict:
        raise ValueError("Known owner and explicit record map required")
    records = records or {}
    if set(records) - set(OWNED_BANKS[owner]):
        raise ValueError("Owner cannot forward a foreign bank, even as unavailable")
    result = []
    for name in OWNED_BANKS[owner]:
        record = records.get(name)
        if record is None:
            record = dict(publication=name, data=None, lv_type=copy.deepcopy(schemas()[name]),
                          error=dict(status=True, code=UNAVAILABLE, source="OWNER_BANK_NOT_AVAILABLE"),
                          source_age_seconds=0.)
        result.append(copy.deepcopy(record))
    stamp = now or datetime.datetime.now(datetime.timezone.utc)
    frame = dict(schema_version=1, publication=PUBLICATION, owner=owner,
                 session_id=session_id, sequence=sequence, source_mode=source_mode,
                 source_seconds_1904=stamp.timestamp() + 2082844800,
                 banks=result, counter_part=copy.deepcopy(counter_part), video_frame=copy.deepcopy(video_frame))
    validate_owner_frame(frame)
    return frame


def expand_owner_frame(frame):
    """Expand authenticated frame for archive/projection; no freshness inference."""
    validate_owner_frame(frame)
    result = {}
    for record in frame["banks"]:
        result[record["publication"]] = dict(
            session_id=frame["session_id"], publication=record["publication"],
            sequence=frame["sequence"], source_seconds_1904=frame["source_seconds_1904"],
            producer_kind="python_" + frame["owner"], source_site="owner_scoped_orchestrator",
            owner=frame["owner"], source_mode=frame["source_mode"],
            data=copy.deepcopy(record["data"]), lv_type=copy.deepcopy(record["lv_type"]),
            error=copy.deepcopy(record["error"]), source_age_seconds=record["source_age_seconds"],
            timestamp_origin="owner_sample_age_plus_relay_delivery_age",
            capture_kind="independent_owner_snapshot_not_atomic")
    return result
