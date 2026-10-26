"""Everest-only vNext bridge. No automatic command retries or NI imports."""
import copy
import hmac
import json
import math
import threading
import time
import urllib.error
import urllib.request
import uuid

from .control_runtime_client import _NoRedirect, MAX_RUNTIME_BYTES, strict_runtime_json
from .control_runtime_health import INPUT_BANKS
from legacy.xp_acq_control.elyse_agent.acquisition_http import request_signature, response_signature
from legacy.xp_acq_control.elyse_agent.acquisition_remote import command_signature, validate_request, OPERATIONS
from legacy.xp_acq_control.elyse_agent.runtime_identity import valid_hex
from legacy.xp_acq_control.elyse_agent.standard_banks import fault_diagnostic_measurement_current


class ControlClient:
    def __init__(self, read_key, command_key=None, enabled=False, host="10.20.30.10", port=8772,
                 timeout=2.0, opener=None, clock=time.monotonic):
        if host not in ("10.20.30.10", "127.0.0.1") or type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Explicit XP endpoint required")
        if not isinstance(read_key, bytes) or len(read_key) < 32 or type(enabled) is not bool:
            raise ValueError("Read key and explicit command enablement required")
        if enabled and (not isinstance(command_key, bytes) or len(command_key) < 32 or command_key == read_key):
            raise ValueError("Separate command key required")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 5:
            raise ValueError("Bounded HTTP acceptance timeout required")
        self.read_key, self.command_key, self.enabled = read_key, command_key, enabled
        self.base = "http://{0}:{1}".format(host, port)
        self.timeout, self.clock = timeout, clock
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self._transport_lock = threading.Lock()

    def _exchange(self, path, body=None):
        nonce = uuid.uuid4().hex
        key = self.read_key if body is None else self.command_key
        signature = request_signature(key, path, nonce) if body is None else command_signature(key, nonce, body)
        request = urllib.request.Request(self.base + path, data=body, headers={
            "X-ACQ-Nonce": nonce, "X-ACQ-Signature": signature,
            "Content-Type": "application/json"})
        started = self.clock()
        # Exactly one HTTP attempt. Socket timeout is inactivity, not hard
        # cancellation; a late complete reply is rejected, never retried.
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_RUNTIME_BYTES + 1)
            elapsed = self.clock() - started
            if not 0 <= elapsed <= self.timeout:
                raise TimeoutError("Complete HTTP reply exceeded acceptance deadline")
            if not hmac.compare_digest(response_signature(key, nonce, raw),
                                       response.headers.get("X-ACQ-Response-Signature", "")):
                raise ValueError("Invalid authenticated XP response")
            result = strict_runtime_json(raw)
            if response.code != 200:
                raise RuntimeError(result.get("error", "XP request refused"))
        return result

    def _read(self):
        value = self._exchange("/snapshot")
        if (value.get("server_variant") != "acquisition_control_vnext"
                or value.get("control_policy_version") != 2
                or value.get("runtime_protocol_version") != 2
                or not valid_hex(value.get("session_id"), 32) or not valid_hex(value.get("build_id"), 64)
                or type(value.get("state_revision")) is not int or value["state_revision"] < 0
                or value.get("remote_initialization_enabled") is not False or value.get("auto_initialize") is not False
                or type(value.get("remote_setpoints_enabled")) is not bool
                or value.get("control", {}).get("protocol_version") != 1):
            raise ValueError("Incompatible control runtime; never fall back to LabVIEW or old runtime")
        capabilities = value["control"].get("capabilities")
        if (not isinstance(capabilities, dict) or set(capabilities) != set(OPERATIONS)
                or any(not isinstance(item, dict) or type(item.get("enabled")) is not bool
                       or not isinstance(item.get("reason"), str) for item in capabilities.values())):
            raise ValueError("Updated cooling/capability policy required before command transport")
        return value

    def read(self):
        with self._transport_lock:
            return self._read()

    def submit(self, request):
        request = validate_request(request)
        if not self.enabled:
            raise RuntimeError("TANGO_COMMANDS_DISABLED")
        with self._transport_lock:
            # A browser/Tango caller must name the boot/revision it observed.
            # A fresh read supplies a short-lived lease, not a silently updated
            # session/revision that could execute an old user intent.
            latest = self._read()
            if latest["session_id"] != request["session_id"] or latest["state_revision"] != request["expected_revision"]:
                raise RuntimeError("Observed runtime session/revision changed; request not sent")
            if latest["control"].get("enabled") is not True:
                raise RuntimeError("XP_COMMANDS_DISABLED")
            body = json.dumps(dict(request=request, lease=latest["control"].get("lease")),
                              allow_nan=False, separators=(",", ":")).encode("utf-8")
            try:
                result = self._exchange("/commands", body)
            except Exception as error:
                return dict(command_id=request["command_id"], session_id=request["session_id"],
                            operation=request["operation"], outcome="INDETERMINATE",
                            error=type(error).__name__ + ": " + str(error)[:300],
                            automatic_retry=False, hardware_acknowledged=False)
            if (result.get("command_id") != request["command_id"] or result.get("session_id") != request["session_id"]
                    or result.get("operation") != request["operation"] or result.get("hardware_acknowledged") is not False
                    or result.get("outcome") not in ("QUEUED", "EXECUTING", "COMPLETED", "FAILED", "REJECTED", "INTERRUPTED")):
                raise ValueError("Command receipt does not match submitted intent; result unknown")
            return result


class ControlBridge:
    """One polling owner, bounded retry for reads only; no process recovery."""
    def __init__(self, client, period=.25, clock=time.monotonic):
        if type(period) not in (int, float) or not math.isfinite(period) or not .05 <= period <= 10:
            raise ValueError("Bounded polling period required")
        self.client, self.period, self.clock = client, period, clock
        self.lock, self.stop_event = threading.RLock(), threading.Event()
        self.worker, self.latest, self.received = None, None, None
        self.error, self.failures, self.identity = "Waiting for XP control runtime", 0, None

    def poll_once(self):
        try:
            started = self.clock()
            value = self.client.read()
            with self.lock:
                if self.stop_event.is_set():
                    return self.period
                identity = (value["session_id"], value["build_id"], value["state_revision"])
                if self.identity and identity[0] == self.identity[0] and (
                        identity[1] != self.identity[1] or identity[2] < self.identity[2]):
                    raise ValueError("Build/revision changed inconsistently within boot")
                self.identity = identity
                self.latest, self.received = value, started
                self.error, self.failures = "", 0
            return self.period
        except Exception as error:
            with self.lock:
                self.latest = None
                self.error = type(error).__name__ + ": " + str(error)[:300]
                self.failures += 1
                return min(8, self.period * 2 ** min(6, self.failures))

    def start(self):
        if self.worker is not None or self.stop_event.is_set():
            raise RuntimeError("A bridge cannot be started/restarted twice")
        def run():
            while not self.stop_event.is_set():
                if self.stop_event.wait(self.poll_once()):
                    return
        self.worker = threading.Thread(target=run, name="ACQ-control-telemetry-reader", daemon=True)
        self.worker.start()

    def stop(self, timeout=3):
        self.stop_event.set()
        if self.worker is not None:
            self.worker.join(timeout)
        with self.lock:
            self.latest, self.error = None, "Reader stopped"
        return self.worker is None or not self.worker.is_alive()

    def snapshot(self):
        with self.lock:
            value = copy.deepcopy(self.latest)
            age = None if self.received is None else self.clock() - self.received
            transport = value is not None and age is not None and 0 <= age < 2 and not self.error
            fresh = bool(transport and value.get("state") == "RUNNING" and value.get("stale") is False
                         and not value.get("error") and type(value.get("age_seconds")) in (int, float)
                         and math.isfinite(value["age_seconds"]) and 0 <= value["age_seconds"] + age < 2)
            diagnostic = bool(transport and fault_diagnostic_measurement_current(value)
                              and 0 <= value["age_seconds"] + age < 2)
            latest = value.get("latest") if value else None
            banks = latest.get("banks", {}) if isinstance(latest, dict) else {}
            if fresh or diagnostic:
                valid = latest.get("source") == "python_daqmx_acquisition" and latest.get("simulated") is False
                for name, (kind, device, size) in INPUT_BANKS.items():
                    record = banks.get(name, {})
                    values = record.get("values")
                    valid = valid and record.get("kind") == kind and record.get("device") == device and isinstance(values, list) and len(values) == size
                    if valid:
                        valid = all(type(item) is bool for item in values) if kind == "digital_input" else all(
                            type(item) in (int, float) and math.isfinite(item) for item in values)
                fresh, diagnostic = fresh and valid, diagnostic and valid
            if value is not None and not (fresh or diagnostic):
                value["latest"] = None
            quality = "FRESH" if fresh else (value.get("state", "UNAVAILABLE") if transport else "UNAVAILABLE")
            if quality == "RUNNING":
                quality = "STALE"
            return dict(source="xp_python_acquisition_control", telemetry_schema="python_runtime_inputs_not_labview_27_banks",
                        quality=quality, bridge_age_seconds=age, bridge_error=self.error, runtime=value,
                        source_current=bool(fresh), diagnostic_source_current=bool(diagnostic),
                        measurements_hidden=not (fresh or diagnostic),
                        commands_enabled=self.client.enabled and bool(transport) and value.get("control", {}).get("enabled") is True,
                        automatic_command_retry=False)
