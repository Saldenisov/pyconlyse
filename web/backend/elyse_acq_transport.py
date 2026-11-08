"""Authenticated bounded transport to the Python 3.4 ACQ simulation facade."""
import hmac
import os
import secrets
import socket
import struct
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from legacy.xp_acq_agent.elyse_agent.supervision_wire import (
    MAX_BYTES, json_bytes, request_mac, response_mac, strict_json, validate_key,
)


class AcqRejected(ValueError):
    """Authenticated, definite non-acceptance; explicit operator retry is safe."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ConnectionError("ACQ redirects are forbidden")


class HttpAcqPort:
    host = "10.20.30.10"
    mode = "SIMULATION"

    def __init__(self, endpoint, key, timeout=3, allow_loopback=False):
        parsed = urlsplit(endpoint)
        allowed = {self.host} | ({"127.0.0.1"} if allow_loopback else set())
        if (parsed.scheme not in ("http", "https") or parsed.hostname not in allowed
                or parsed.username or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.port is None or not 1 <= parsed.port <= 65535):
            raise ValueError("Explicit ACQ endpoint/port required; only 10.20.30.10 is allowed")
        if not 0 < timeout <= 10:
            raise ValueError("ACQ timeout must be in 0..10 seconds")
        self.endpoint = endpoint.rstrip("/")
        self.key = validate_key(key)
        self.timeout = timeout
        self._opener = build_opener(ProxyHandler({}), NoRedirect())

    def _request(self, method, path, payload=None):
        body = b"" if payload is None else json_bytes(payload)
        nonce = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        headers = {"X-ACQ-Timestamp": timestamp, "X-ACQ-Nonce": nonce,
                   "X-ACQ-Signature": request_mac(self.key, method, path, timestamp, nonce, body),
                   "Content-Type": "application/json"}
        request = Request(self.endpoint + path, data=body if method == "POST" else None,
                          headers=headers, method=method)
        try:
            response = self._opener.open(request, timeout=self.timeout)
        except HTTPError as failure:
            response = failure
        with response:
            status = response.code
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("ACQ response exceeds 65536 bytes")
            expected = response_mac(self.key, method, path, nonce, status, raw)
            signatures = response.headers.get_all("X-ACQ-Signature", [])
            if len(signatures) != 1 or not hmac.compare_digest(signatures[0], expected):
                raise ConnectionError("ACQ response authentication failed")
        value = strict_json(raw)
        if (type(value) is not dict or value.get("schema_version") != 1
                or value.get("execution_allowed") is not False
                or value.get("hardware_writes") is not False
                or value.get("physical_status") != "NOT_EXECUTED"):
            raise ValueError("ACQ simulation contract incompatible")
        if status == 409 and value.get("accepted") is False:
            raise AcqRejected(value.get("error", "ACQ request rejected"))
        if status != 200:
            raise ConnectionError(value.get("error", "ACQ HTTP {0}".format(status)))
        if "result" not in value:
            raise ValueError("ACQ result missing")
        return value["result"]

    def read_state(self):
        return self._request("GET", "/v1/state")

    def read_intent(self, intent_id):
        return self._request("GET", "/v1/intents/" + quote(intent_id, safe=""))

    def trace(self, intent_id):
        return self._request("GET", "/v1/trace/" + quote(intent_id, safe=""))

    def submit_procedure(self, *, intent_id, procedure, expected_revision, session_id):
        return self._request("POST", "/v1/intents", dict(intent_id=intent_id, procedure=procedure,
                                                       expected_revision=expected_revision, session_id=session_id))


class TcpAcqPort(HttpAcqPort):
    """Signed extension of the ORIGINAL four-byte length-prefixed agent protocol."""

    simulates_all_plans = True  # Logical stubs only; no physical adapter can be selected.
    simulates_setpoints = True
    simulates_lifecycle = True

    def read_lifecycle(self):
        return self._request("GET", "/v1/lifecycle")

    def read_observation(self):
        return self._request("GET", "/v1/observation")

    def __init__(self, endpoint, key, timeout=3, allow_loopback=False):
        parsed = urlsplit(endpoint)
        allowed = {self.host} | ({"127.0.0.1"} if allow_loopback else set())
        if (parsed.scheme != "tcp" or parsed.hostname not in allowed or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or parsed.port is None or not 1 <= parsed.port <= 65535):
            raise ValueError("Explicit ACQ TCP endpoint/port required; loopback needs local simulation opt-in")
        if not 0 < timeout <= 10:
            raise ValueError("ACQ timeout must be in 0..10 seconds")
        self.endpoint, self.address = endpoint.rstrip("/"), (parsed.hostname, parsed.port)
        self.key, self.timeout = validate_key(key), timeout

    @staticmethod
    def _receive(connection, count, deadline):
        chunks = []
        while count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ACQ TCP response deadline exceeded")
            connection.settimeout(remaining)
            chunk = connection.recv(count)
            if not chunk:
                raise ConnectionError("ACQ TCP response lost")
            chunks.append(chunk)
            count -= len(chunk)
        return b"".join(chunks)

    def _exchange(self, request):
        raw = json_bytes(request)
        if len(raw) > MAX_BYTES:
            raise ValueError("ACQ request exceeds 65536 bytes")
        deadline = time.monotonic() + self.timeout
        with socket.create_connection(self.address, timeout=self.timeout) as connection:
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            connection.sendall(struct.pack("!I", len(raw)) + raw)
            size = struct.unpack("!I", self._receive(connection, 4, deadline))[0]
            if not 0 < size <= MAX_BYTES:
                raise ValueError("ACQ response exceeds 65536 bytes or is empty")
            return strict_json(self._receive(connection, size, deadline))

    def _request(self, method, path, payload=None):
        raw = b"" if payload is None else json_bytes(payload)
        nonce, timestamp = secrets.token_hex(16), str(int(time.time()))
        request_id = "sup-" + secrets.token_hex(16)
        params = dict(method=method, path=path, payload=payload, timestamp=timestamp, nonce=nonce,
                      signature=request_mac(self.key, "RPC/" + method, path, timestamp, nonce, raw))
        response = self._exchange(dict(id=request_id, command="supervision", params=params))
        if (type(response) is not dict or set(response) != {"id", "ok", "result"}
                or response["id"] != request_id or response["ok"] is not True):
            raise ConnectionError("ACQ agent did not acknowledge signed supervision request")
        result = response["result"]
        if type(result) is not dict or set(result) != {"status", "body", "signature"}:
            raise ConnectionError("ACQ signed response missing")
        status, value, signature = result["status"], result["body"], result["signature"]
        if type(status) is not int or not 100 <= status <= 599 or not isinstance(signature, str):
            raise ConnectionError("ACQ signed response malformed")
        expected = response_mac(self.key, "RPC/" + method, path, nonce, status, json_bytes(value))
        if not hmac.compare_digest(signature, expected):
            raise ConnectionError("ACQ response authentication failed")
        if (type(value) is not dict or value.get("schema_version") != 1
                or value.get("execution_allowed") is not False or value.get("hardware_writes") is not False
                or value.get("physical_status") != "NOT_EXECUTED"):
            raise ValueError("ACQ simulation contract incompatible")
        if status == 409 and value.get("accepted") is False:
            raise AcqRejected(value.get("error", "ACQ request rejected"))
        if status != 200:
            raise ConnectionError(value.get("error", "ACQ RPC {0}".format(status)))
        if "result" not in value:
            raise ValueError("ACQ result missing")
        return value["result"]

    def outputs(self):
        return self._request("GET", "/v1/outputs")

    def read_setpoints(self):
        return self._request("GET", "/v1/setpoints")

    def submit_setpoint(self, *, intent_id, page, control, base_value, expected_revision, session_id):
        return self._request("POST", "/v1/setpoints", dict(intent_id=intent_id, page=page, control=control,
                            base_value=base_value, expected_revision=expected_revision, session_id=session_id))


def configured_acq(config):
    endpoint = config.get("ELYSE_ACQ_URL") or os.environ.get("ELYSE_ACQ_URL")
    if not endpoint:
        return None
    key_file = config.get("ELYSE_ACQ_SHARED_KEY_FILE") or os.environ.get("ELYSE_ACQ_SHARED_KEY_FILE")
    if key_file:
        with open(key_file, "rb") as stream:
            key = stream.read().strip()
    else:
        key = (config.get("ELYSE_ACQ_SHARED_KEY") or os.environ.get("ELYSE_ACQ_SHARED_KEY", "")).encode("utf-8")
    local = config.get("ELYSE_ACQ_LOCAL_SIMULATION", os.environ.get("ELYSE_ACQ_LOCAL_SIMULATION", "false"))
    allow_loopback = bool(config.get("TESTING", False)) or local is True or str(local).lower() == "true"
    adapter = TcpAcqPort if urlsplit(endpoint).scheme == "tcp" else HttpAcqPort
    return adapter(endpoint, key, allow_loopback=allow_loopback)
