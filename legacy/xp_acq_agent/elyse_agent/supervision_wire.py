"""Python 3.4 stdlib-only authenticated JSON wire contract (no hardware)."""
from __future__ import print_function

import hashlib
import hmac
import json
import math
import re
import threading
import time

MAX_BYTES = 65536


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-finite JSON constant")

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        if isinstance(value, dict):
            for part in value.values():
                finite(part)
        elif isinstance(value, list):
            for part in value:
                finite(part)

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    finite(value)
    return value


def validate_key(key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("ACQ shared key requires at least 32 bytes")
    return key


def _mac(key, fields, body):
    message = "\n".join(fields + [hashlib.sha256(body).hexdigest()]).encode("utf-8")
    return hmac.new(validate_key(key), message, hashlib.sha256).hexdigest()


def request_mac(key, method, path, timestamp, nonce, body):
    return _mac(key, ["ACQ-REQUEST-1", method, path, timestamp, nonce], body)


def response_mac(key, method, path, nonce, status, body):
    return _mac(key, ["ACQ-RESPONSE-1", method, path, nonce, str(status)], body)


class RequestGuard(object):
    """Bounded nonce cache; signatures never contain or transmit the secret key."""
    def __init__(self, key, clock=time.time, max_skew_seconds=30, max_nonces=4096):
        self.key = validate_key(key)
        self.clock = clock
        self.max_skew = max_skew_seconds
        self.max_nonces = max_nonces
        self._seen = {}
        self._lock = threading.Lock()

    def verify(self, method, path, timestamp, nonce, signature, body):
        if not re.match(r"^[0-9]{1,12}\Z", timestamp or ""):
            raise ValueError("Invalid authentication timestamp")
        if not re.match(r"^[a-f0-9]{32}\Z", nonce or ""):
            raise ValueError("Invalid authentication nonce")
        if not re.match(r"^[a-f0-9]{64}\Z", signature or ""):
            raise ValueError("Invalid authentication signature")
        now = self.clock()
        if abs(now - int(timestamp)) > self.max_skew:
            raise ValueError("Authentication timestamp expired")
        expected = request_mac(self.key, method, path, timestamp, nonce, body)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid authentication signature")
        with self._lock:
            self._seen = dict((value, expiry) for value, expiry in self._seen.items() if expiry >= now)
            if nonce in self._seen:
                raise ValueError("Authentication nonce already used")
            if len(self._seen) >= self.max_nonces:
                raise ValueError("Authentication nonce capacity reached")
            self._seen[nonce] = now + self.max_skew * 2
