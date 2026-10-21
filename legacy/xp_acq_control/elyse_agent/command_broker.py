"""Bounded at-most-once command ledger and existing-owner admission."""
import copy
import time
import uuid

from .command_protocol import OPERATIONS, LEASE_SECONDS, validate_request

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
