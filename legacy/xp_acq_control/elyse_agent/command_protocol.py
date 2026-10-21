"""Strict command envelope and HMAC domains; Python 3.4, no I/O."""
import hashlib
import hmac
import json
import math

from .runtime_identity import valid_hex

OPERATIONS = (
    "cooling.start", "cooling.stop",
    "modulator.general.start", "modulator.general.stop",
    "chauffage.start", "chauffage.stop", "prema.start", "prema.stop",
    "focales.start", "focales.stop", "relays_ht.start", "relays_ht.stop",
    "alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset",
    "modulator.reset", "modulator_impulse.start", "modulator_impulse.stop",
    "ht_voltage.set",
)
FIELDS = frozenset(("command_id", "session_id", "expected_revision", "operation",
                    "operator_confirmed", "value"))
LEASE_SECONDS = 2.0
MAX_COMMAND_BYTES = 2048


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
    elif setting is not None:
        raise ValueError("This operation takes no setpoint")
    return dict(value)


def command_signature(key, nonce, body):
    if not valid_hex(nonce, 32) or not isinstance(body, bytes):
        raise ValueError("Exact nonce and encoded body required")
    return hmac.new(key, b"ACQ-CONTROL-1\nPOST\n/commands\n" + nonce.encode("ascii") + b"\n" + body,
                    hashlib.sha256).hexdigest()
