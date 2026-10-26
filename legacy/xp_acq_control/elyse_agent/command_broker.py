"""Bounded at-most-once command ledger and existing-owner admission."""
import copy
import math
import threading
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
        self._lifecycle_pending = threading.Event()
        self._lifecycle_epoch = 0

    def block_local_lifecycle(self):
        # Local GUI intent never waits for runtime policy or disk I/O. One
        # lifecycle dispatcher owns epoch changes; old leases stay revoked.
        self._lifecycle_pending.set()
        self._lifecycle_epoch += 1

    def finish_local_lifecycle(self):
        self._lifecycle_pending.clear()

    def _lease_record(self, now, session_id=None, expected_revision=None, seconds=LEASE_SECONDS):
        return dict(expires=now + seconds,
                    lifecycle_epoch=self._lifecycle_epoch,
                    session_id=self.runtime._identity["session_id"] if session_id is None else session_id,
                    expected_revision=getattr(self.runtime, "_state_revision", None)
                        if expected_revision is None else expected_revision)

    def issue_lease_nonblocking(self, session_id=None, expected_revision=None, view_remaining_seconds=None,
                              view_deadline=None, return_details=False):
        """A read reply may offer a lease, but never wait behind policy/disk."""
        if not self.runtime._lock.acquire(False):
            return None
        try:
            now = self.clock()
            self.leases = {key: record for key, record in self.leases.items() if record["expires"] > now}
            if not self.enabled or self._lifecycle_pending.is_set() or len(self.leases) >= 64:
                return None
            if (session_id is not None and session_id != self.runtime._identity["session_id"]
                    or expected_revision is not None
                    and expected_revision != getattr(self.runtime, "_state_revision", None)):
                return None
            seconds = LEASE_SECONDS
            if view_deadline is not None:
                if type(view_deadline) not in (int, float) or not math.isfinite(view_deadline):
                    return None
                seconds = min(seconds, view_deadline - now)
                if seconds <= 0:
                    return None
            if view_remaining_seconds is not None:
                if (type(view_remaining_seconds) not in (int, float)
                        or not math.isfinite(view_remaining_seconds) or view_remaining_seconds <= 0):
                    return None
                seconds = min(seconds, view_remaining_seconds)
            lease = uuid.uuid4().hex
            self.leases[lease] = self._lease_record(now, session_id, expected_revision, seconds)
            return (dict(lease=lease, lease_seconds=max(0, self.leases[lease]["expires"] - self.clock()))
                    if return_details else lease)
        finally:
            self.runtime._lock.release()

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
            self.leases = {key: record for key, record in self.leases.items() if record["expires"] > now}
            if issue_lease and self.enabled and not self._lifecycle_pending.is_set() and len(self.leases) < 64:
                lease = uuid.uuid4().hex
                self.leases[lease] = self._lease_record(now)
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
            if self._lifecycle_pending.is_set():
                raise RuntimeError("LOCAL_LIFECYCLE_PENDING")
            record = self.leases.pop(lease, None) if isinstance(lease, str) else None
            if record is None or self.clock() >= record["expires"]:
                raise RuntimeError("COMMAND_LEASE_EXPIRED_OR_CONSUMED")
            if (record["session_id"] != request["session_id"]
                    or record["lifecycle_epoch"] != self._lifecycle_epoch
                    or record["expected_revision"] is not None
                    and record["expected_revision"] != request["expected_revision"]):
                raise RuntimeError("COMMAND_LEASE_CONTEXT_CHANGED")
            if len(self.records) >= self.capacity:
                raise RuntimeError("COMMAND_LEDGER_FULL_LOCAL_CONTROL_REQUIRED")
            result = dict(command_id=key, session_id=request["session_id"],
                          operation=request["operation"], outcome="REJECTED", duplicate=False,
                          hardware_acknowledged=False)
            self.records[key] = dict(request=request, result=result)
            try:
                def dispatch():
                    if self._lifecycle_pending.is_set():
                        raise RuntimeError("LOCAL_LIFECYCLE_PENDING")
                    return self.runtime.dispatch_remote(request["operation"], request["value"])
                dispatched = self.runtime.fenced_local_request(
                    request["session_id"], request["expected_revision"],
                    dispatch)
            except Exception as error:
                result["error"] = str(error)[:300]
                result["error_type"] = type(error).__name__
            else:
                if (request["operation"] == "cooling.confirm_circulation"
                        and isinstance(dispatched, dict)
                        and dispatched.get("completed_without_hardware") is True
                        and dispatched.get("confirmed_incident_ids") == request["value"]["incident_ids"]):
                    result.update(outcome="COMPLETED", operator_confirmation_only=True,
                        hardware_writes=False,
                        confirmed_incident_ids=list(dispatched["confirmed_incident_ids"]))
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
