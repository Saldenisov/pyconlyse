"""Strict command envelope and HMAC domains; Python 3.4, no I/O."""
import hashlib
import hmac
import json
import math

from .runtime_identity import valid_hex
from .acquisition_counter_timing import validate_remote_timing

OPERATIONS = (
    "cooling.start", "cooling.stop", "cooling.confirm_circulation",
    "modulator.general.start", "modulator.general.stop",
    "chauffage.start", "chauffage.stop", "prema.start", "prema.stop",
    "focales.start", "focales.stop", "relays_ht.start", "relays_ht.stop",
    "alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset",
    "modulator.reset", "modulator_impulse.start", "modulator_impulse.stop",
    "ht_voltage.set",
    "counter_timing.set",
    "faraday_1.en_pulse", "faraday_3.en_pulse",
    "laser_mirror.en_pulse", "laser_mirror.hors_pulse",
)
FIELDS = frozenset(("command_id", "session_id", "expected_revision", "operation",
                    "operator_confirmed", "value"))
LEASE_SECONDS = 2.0
MAX_COMMAND_BYTES = 2048


def validate_circulation_confirmation(value):
    if type(value) is not dict or set(value) != {"incident_ids"}:
        raise ValueError("Exact current circulation incident IDs required")
    ids = value["incident_ids"]
    if (type(ids) is not list or not 1 <= len(ids) <= 2
            or any(not valid_hex(item, 32) for item in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("One or two distinct current circulation incident IDs required")
    return dict(incident_ids=list(ids))


def strict_json(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_COMMAND_BYTES:
        raise ValueError("Bounded command JSON required")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate command field")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON forbidden")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def validate_request(value):
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("Exact named command fields required")
    if not valid_hex(value["command_id"], 32) or not valid_hex(value["session_id"], 32):
        raise ValueError("Exact command and boot IDs required")
    if type(value["expected_revision"]) is not int or value["expected_revision"] < 0:
        raise ValueError("Exact nonnegative revision required")
    if value["operation"] not in OPERATIONS or value["operator_confirmed"] is not True:
        raise ValueError("Named operation and operator confirmation required")
    setting = value["value"]
    if value["operation"] == "ht_voltage.set":
        if type(setting) not in (int, float) or not math.isfinite(setting) or not 0 <= setting <= 20:
            raise ValueError("Finite HT command in [0,20] kV required")
    elif value["operation"] == "counter_timing.set":
        setting = validate_remote_timing(setting)
    elif value["operation"] == "cooling.confirm_circulation":
        setting = validate_circulation_confirmation(setting)
    elif setting is not None:
        raise ValueError("This operation takes no setpoint")
    return dict(value, value=setting)


def command_signature(key, nonce, body):
    if not valid_hex(nonce, 32) or not isinstance(body, bytes):
        raise ValueError("Exact nonce and encoded body required")
    return hmac.new(key, b"ACQ-CONTROL-1\nPOST\n/commands\n" + nonce.encode("ascii") + b"\n" + body,
                    hashlib.sha256).hexdigest()
