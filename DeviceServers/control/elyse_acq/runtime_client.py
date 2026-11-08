"""Latest-only authenticated reader for XP runtime. No mutation methods."""
import hmac
import json
import urllib.request
import uuid

from legacy.xp_acq_agent.elyse_agent.acquisition_http import request_signature, response_signature


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Acquisition runtime redirects are not allowed")


def read_runtime(key, host="10.20.30.10", port=8771, timeout=2.0):
    if host not in ("10.20.30.10", "127.0.0.1") or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid XP runtime endpoint")
    nonce = uuid.uuid4().hex
    path = "/snapshot"
    request = urllib.request.Request("http://{0}:{1}{2}".format(host, port, path), headers={
        "X-ACQ-Nonce": nonce, "X-ACQ-Signature": request_signature(key, path, nonce)})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError("Runtime snapshot exceeds limit")
        if not hmac.compare_digest(response_signature(key, nonce, raw),
                                   response.headers.get("X-ACQ-Response-Signature", "")):
            raise ValueError("Invalid acquisition response signature")
    result = json.loads(raw.decode("utf-8"))
    if (result.get("storage_mode") != "ram_latest" or result.get("auto_initialize") is not False
            or result.get("remote_initialization_enabled") is not False
            or result.get("remote_setpoints_enabled") is not False):
        raise ValueError("Unexpected runtime safety contract")
    return result
