"""Opt-in vNext command transport; Python 3.4, no native/device imports.

Separate command key, two-second single-use leases, boot/revision fencing and
bounded at-most-once ledger. A QUEUED receipt is not execution or hardware ACK.
Lifecycle stays local. Existing read-only RuntimeHTTPServer remains unchanged.
"""
import copy
import hashlib
import hmac
import json
import math
import time
import uuid

from .acquisition_http import RuntimeHTTPServer, _Handler
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


class CommandBroker(object):
    def __init__(self, runtime, enabled=False, clock=None, capacity=256):
        if type(enabled) is not bool or type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ValueError("Explicit enabled flag and bounded ledger required")
        self.runtime, self.enabled = runtime, enabled
        self.clock, self.capacity = clock or time.monotonic, capacity
        self.records, self.leases = {}, {}

    def snapshot(self, issue_lease=False):
        # One lock order throughout: runtime -> broker (the runtime RLock).
        with self.runtime._lock:
            lease = None
            now = self.clock()
            if (self.runtime._state in ("FAULT", "IDLE", "STOPPED", "RECOVERY_REQUIRED")
                    and self.runtime._pending is None and self.runtime._operation is None):
                for item in self.records.values():
                    if item["result"]["outcome"] == "QUEUED":
                        item["result"].update(outcome="INTERRUPTED",
                            error="Owner left queued operation before an observed callback; effects not inferred")
            self.leases = {key: end for key, end in self.leases.items() if end > now}
            if issue_lease and self.enabled and len(self.leases) < 64:
                lease = uuid.uuid4().hex
                self.leases[lease] = now + LEASE_SECONDS
            return dict(protocol_version=1, enabled=self.enabled, lease=lease,
                        lease_seconds=LEASE_SECONDS, operations=list(OPERATIONS),
                        initialization_local_only=True, automatic_command_retry=False,
                        ledger_size=len(self.records), ledger_capacity=self.capacity,
                        results=[copy.deepcopy(item["result"]) for item in self.records.values()],
                        interpretation="Procedure completion is software only, not physical acknowledgement")

    def submit(self, request, lease):
        request = validate_request(request)
        with self.runtime._lock:
            if not self.enabled:
                raise RuntimeError("REMOTE_CONTROL_DISABLED")
            if request["session_id"] != self.runtime._identity["session_id"]:
                raise RuntimeError("RUNTIME_SESSION_CHANGED")
            key = request["command_id"]
            previous = self.records.get(key)
            if previous is not None:
                if previous["request"] != request:
                    raise ValueError("COMMAND_ID_REUSED_WITH_DIFFERENT_REQUEST")
                return dict(copy.deepcopy(previous["result"]), duplicate=True)
            expiry = self.leases.pop(lease, None) if isinstance(lease, str) else None
            if expiry is None or self.clock() >= expiry:
                raise RuntimeError("COMMAND_LEASE_EXPIRED_OR_CONSUMED")
            if len(self.records) >= self.capacity:
                raise RuntimeError("COMMAND_LEDGER_FULL_LOCAL_CONTROL_REQUIRED")
            result = dict(command_id=key, session_id=request["session_id"],
                          operation=request["operation"], outcome="REJECTED", duplicate=False,
                          hardware_acknowledged=False)
            self.records[key] = dict(request=request, result=result)
            try:
                self.runtime.fenced_local_request(
                    request["session_id"], request["expected_revision"],
                    lambda: self.runtime.dispatch_remote(request["operation"], request["value"]))
            except Exception as error:
                result["error"] = str(error)[:300]
                result["error_type"] = type(error).__name__
            else:
                result["outcome"] = "QUEUED"
            return copy.deepcopy(result)

    def begin(self, operation):
        with self.runtime._lock:
            matches = [key for key, item in self.records.items()
                       if item["request"]["operation"] == operation and item["result"]["outcome"] == "QUEUED"]
            if not matches:
                return None
            key = matches[-1]
            self.records[key]["result"]["outcome"] = "EXECUTING"
            return key

    def finish(self, key, error=None):
        if key is None:
            return
        with self.runtime._lock:
            result = self.records[key]["result"]
            result["outcome"] = "FAILED" if error is not None else "COMPLETED"
            if error is not None:
                result["error_type"], result["error"] = type(error).__name__, str(error)[:300]

    def interrupt_queued(self):
        with self.runtime._lock:
            for item in self.records.values():
                if item["result"]["outcome"] == "QUEUED":
                    item["result"]["outcome"] = "INTERRUPTED"
                    item["result"]["error"] = "Superseded by local cleanup or General stop; effects not inferred"


class _ControlHandler(_Handler):
    def _reply(self, code, body):
        # All replies, including refused/failed commands, are authenticated.
        # The old reader uses its unchanged response-signature domain.
        if self.command != "POST":
            if code == 200 and self.path == "/snapshot" and "control" in body:
                body["control"]["lease"] = self.server.runtime.broker.snapshot(issue_lease=True)["lease"]
            return _Handler._reply(self, code, body)
        from .acquisition_http import response_signature
        encoded = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        for name, value in (("Content-Type", "application/json"), ("Content-Length", str(len(encoded))),
                            ("Cache-Control", "no-store"), ("Connection", "close")):
            self.send_header(name, value)
        nonce = self.headers.get("X-ACQ-Nonce", "")
        if valid_hex(nonce, 32) and self.server.command_key is not None:
            self.send_header("X-ACQ-Response-Signature", response_signature(self.server.command_key, nonce, encoded))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.client_address[0] not in self.server.allowed_peers:
            return self._reply(403, dict(error="peer_not_permitted"))
        if self.path != "/commands":
            return self._reply(404, dict(error="unknown_command_path"))
        if self.server.command_key is None or not self.server.runtime.broker.enabled:
            return self._reply(403, dict(error="remote_control_disabled"))
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if (len(lengths) != 1 or not lengths[0].isdigit() or self.headers.get("Transfer-Encoding")
                    or self.headers.get("Content-Type") != "application/json"):
                raise ValueError("Exact bounded JSON framing required")
            length = int(lengths[0])
            if not 0 < length <= MAX_COMMAND_BYTES:
                raise ValueError("Command body exceeds limit")
            body = self.rfile.read(length)
            expected = command_signature(self.server.command_key, self.headers.get("X-ACQ-Nonce", ""), body)
            if len(body) != length or not hmac.compare_digest(expected, self.headers.get("X-ACQ-Signature", "")):
                return self._reply(401, dict(error="command_authentication_required"))
            envelope = strict_json(body)
            if type(envelope) is not dict or set(envelope) != {"request", "lease"}:
                raise ValueError("Exact transport envelope required")
            result = self.server.runtime.broker.submit(envelope["request"], envelope["lease"])
            self._reply(200, result)
        except (ValueError, TypeError, RuntimeError) as error:
            self._reply(409, dict(error=str(error)[:300], hardware_acknowledged=False))


class ControlHTTPServer(RuntimeHTTPServer):
    def __init__(self, address, runtime, read_key, command_key=None):
        if runtime.broker.enabled and (not isinstance(command_key, bytes) or len(command_key) < 32
                                       or command_key == read_key):
            raise ValueError("Separate command key of at least 32 bytes required")
        RuntimeHTTPServer.__init__(self, address, runtime, read_key)
        self.command_key = command_key
        self.RequestHandlerClass = _ControlHandler
