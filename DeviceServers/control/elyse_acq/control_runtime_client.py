"""Latest-only authenticated reader for XP runtime. No mutation methods.

urllib timeout bounds socket inactivity, not drip-fed total response time.
Late complete replies are rejected. A blocked call remains owned until it
exits; the polling owner never abandons it or starts an overlapping reader.
"""
import hmac
import json
import math
import time
import urllib.request
import uuid

from legacy.xp_acq_control.elyse_agent.acquisition_http import request_signature, response_signature


MAX_RUNTIME_BYTES = 262144


def strict_runtime_json(raw, max_bytes=MAX_RUNTIME_BYTES):
    """Bounded, duplicate-free, finite JSON object; no trusted-source bypass."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if (type(max_bytes) is not int or not 0 < max_bytes <= 2 * MAX_RUNTIME_BYTES
            or not isinstance(raw, bytes) or len(raw) > max_bytes):
        raise ValueError("Runtime snapshot exceeds limit or has invalid type")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate runtime JSON key")
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError("Nonfinite runtime JSON token: " + value)
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError("Runtime JSON object required")
    def bounded(item, depth=0):
        if depth > 48:
            raise ValueError("Runtime JSON nesting limit exceeded")
        if isinstance(item, dict):
            for child in item.values():
                bounded(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                bounded(child, depth + 1)
        elif isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Nonfinite runtime JSON value")
    bounded(value)
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Acquisition runtime redirects are not allowed")


def read_runtime(key, host="10.20.30.10", port=8771, timeout=2.0):
    if host not in ("10.20.30.10", "127.0.0.1") or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid XP runtime endpoint")
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("Runtime shared key must contain at least 32 bytes")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
        raise ValueError("Runtime read timeout must be in (0, 5] seconds")
    nonce = uuid.uuid4().hex
    path = "/snapshot"
    request = urllib.request.Request("http://{0}:{1}{2}".format(host, port, path), headers={
        "X-ACQ-Nonce": nonce, "X-ACQ-Signature": request_signature(key, path, nonce)})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    started = time.monotonic()
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(MAX_RUNTIME_BYTES + 1)
        elapsed = time.monotonic() - started
        if elapsed < 0 or elapsed > timeout:
            raise TimeoutError("Runtime complete response exceeded total acceptance deadline")
        if len(raw) > MAX_RUNTIME_BYTES:
            raise ValueError("Runtime snapshot exceeds limit")
        if not hmac.compare_digest(response_signature(key, nonce, raw),
                                   response.headers.get("X-ACQ-Response-Signature", "")):
            raise ValueError("Invalid acquisition response signature")
    result = strict_runtime_json(raw)
    if (result.get("storage_mode") != "ram_latest" or result.get("auto_initialize") is not False
            or result.get("remote_initialization_enabled") is not False
            or result.get("remote_setpoints_enabled") is not False):
        raise ValueError("Unexpected runtime safety contract")
    return result
