"""Bounded RAM-only application view and asynchronous local lifecycle, Python 3.4.

Readers never enter the runtime's policy, filesystem or driver paths. A slow
capture ages visibly; it never turns old measurements into a fresh sample.
Only the local lifecycle dispatcher calls the explicitly named runtime methods.
"""
import copy
from collections import deque
import threading
import time


class ApplicationView(object):
    def __init__(self, runtime, period=.1, clock=None):
        self.runtime = runtime
        self.clock = clock or time.monotonic
        if not .02 <= period <= 1:
            raise ValueError("Bounded application snapshot period required")
        self.period = period
        self._lock = threading.Lock()
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._snapshot_worker = self._action_worker = None
        self._latest, self._captured_at = None, None
        self._generation = 0
        self._pending, self._active = deque(), None
        self._closing = False
        self._capture_error = self._action_error = ""

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    def start(self):
        if self._snapshot_worker is not None or self._stop.is_set():
            raise RuntimeError("Application view cannot be replaced or started twice")
        self._snapshot_worker = threading.Thread(target=self._capture_loop, name="ACQ-state-cache")
        self._action_worker = threading.Thread(target=self._action_loop, name="ACQ-local-lifecycle")
        self._snapshot_worker.daemon = self._action_worker.daemon = True
        self._snapshot_worker.start()
        self._action_worker.start()

    def capture_once(self):
        captured = self.clock()  # Include any blocked capture time in age.
        value = self.runtime.snapshot()  # Only this background worker may wait.
        with self._lock:
            self._latest, self._captured_at = value, captured
            self._generation += 1
            self._capture_error = ""

    def _capture_loop(self):
        while not self._stop.is_set():
            try:
                self.capture_once()
            except Exception as error:
                with self._lock:
                    self._capture_error = type(error).__name__ + ": " + str(error)[:300]
            self._stop.wait(self.period)

    def _cold_snapshot(self):
        # Identity is fixed at boot. Unknown means unknown, never a fake IDLE.
        return dict(self.runtime._identity, state="UNKNOWN", state_revision=-1,
                    error="Application metadata has not been captured", resource_count=0,
                    sequence=0, latest=None, age_seconds=None, stale=True,
                    everest_read_age_seconds=None,
                    control=dict(enabled=False, lease=None, capabilities={}),
                    stage_execution=dict(remote_commands_enabled=False),
                    recovery=dict(required=True, reason="METADATA_NOT_CURRENT"),
                    cooling_safety=dict(active=False, circuits=[], remaining_seconds=None,
                        stop_state="UNKNOWN", automatic_stop_available=False,
                        journal_error="Application metadata has not been captured"))

    def snapshot(self):
        with self._lock:
            value, at = self._latest, self._captured_at
            generation = self._generation
            capture_error = self._capture_error
        value = copy.deepcopy(value) if value is not None else self._cold_snapshot()
        age = None if at is None else max(0, self.clock() - at)
        current = age is not None and age < 2 and not capture_error
        if age is not None:
            for field in ("age_seconds", "everest_read_age_seconds", "software_state_age_seconds"):
                if type(value.get(field)) in (int, float):
                    value[field] += age
            alarm = value.get("cooling_safety", {})
            if alarm.get("active") and type(alarm.get("remaining_seconds")) in (int, float):
                alarm["remaining_seconds"] = max(0, alarm["remaining_seconds"] - age)
        value["stale"] = bool(value.get("stale", True) or not current
                              or type(value.get("age_seconds")) in (int, float)
                              and value["age_seconds"] >= 2)
        with self._condition:
            action = self._active or (self._pending[0][0] if self._pending else None)
            action_error = self._action_error
        value.update(application_view_current=current, application_view_age_seconds=age,
                     application_view_generation=generation,
                     application_view_error=capture_error, local_request_pending=action,
                     local_request_error=action_error)
        if not current or action:
            value.setdefault("control", {})["lease"] = None
            value["control"]["enabled"] = False
        if not current:
            value["software_state_current"] = False
            value["measurement_current"] = False
            value["control"]["enabled"] = False
            for capability in value["control"].get("capabilities", {}).values():
                capability.update(enabled=False, reason="APPLICATION_METADATA_NOT_CURRENT")
        return value

    def issue_command_lease(self, body):
        # A relative TTL computed by HTTP can be extended by descheduling.
        # Bind to this exact cached generation and its original absolute age.
        with self._lock:
            at, generation = self._captured_at, self._generation
        if at is None or body.get("application_view_generation") != generation:
            return None
        issuer = getattr(getattr(self.runtime, "broker", None), "issue_lease_nonblocking", None)
        if issuer is None:
            return None
        return issuer(session_id=body.get("session_id"), expected_revision=body.get("state_revision"),
                      view_deadline=at + 2, return_details=True)

    def note_everest_read(self):
        # Connection liveness is informational; never wait behind admission.
        if not self.runtime._lock.acquire(False):
            return False
        try:
            self.runtime._everest_seen = self.runtime._clock()
            return True
        finally:
            self.runtime._lock.release()

    def _submit(self, operation, **kwargs):
        with self._condition:
            if self._closing or self._action_worker is None or not self._action_worker.is_alive():
                raise RuntimeError("Local lifecycle dispatcher is closed")
            if self._pending or self._active:
                raise RuntimeError("A local lifecycle request is already pending")
            self._action_error = ""
            blocker = getattr(getattr(self.runtime, "broker", None), "block_local_lifecycle", None)
            if blocker is not None:
                blocker()
            self._pending.append((operation, kwargs))
            self._condition.notify_all()

    def initialize(self, startup_confirmed=False):
        self._submit("initialize", startup_confirmed=startup_confirmed)

    def initialize_after_handover(self, startup_confirmed=False, electrical_off_confirmed=False,
                                  confirmation=None, operator=None):
        self._submit("initialize_after_handover", startup_confirmed=startup_confirmed,
            electrical_off_confirmed=electrical_off_confirmed, confirmation=confirmation, operator=operator)

    def acknowledge_journal_history(self, operator=None, reason=None, expected_revision=None):
        self._submit("acknowledge_journal_history", operator=operator, reason=reason,
                     expected_revision=expected_revision)

    def deinitialize(self, electrical_off_confirmed=False):
        self._submit("deinitialize", electrical_off_confirmed=electrical_off_confirmed)

    def request_shutdown(self, electrical_off_confirmed=False):
        self._submit("request_shutdown", electrical_off_confirmed=electrical_off_confirmed)

    def recover_local(self, electrical_off_confirmed=False):
        self._submit("recover_local", electrical_off_confirmed=electrical_off_confirmed)

    def _action_loop(self):
        while True:
            with self._condition:
                while not self._pending and not self._closing:
                    self._condition.wait()
                if self._closing:
                    return
                operation, kwargs = self._pending.popleft()
                self._active = operation
            error = ""
            try:
                getattr(self.runtime, operation)(**kwargs)
            except Exception as caught:
                error = type(caught).__name__ + ": " + str(caught)[:300]
            with self._condition:
                self._action_error, self._active = error, None
                unblock = getattr(getattr(self.runtime, "broker", None), "finish_local_lifecycle", None)
                if unblock is not None:
                    unblock()

    def close(self, timeout=1):
        with self._condition:
            self._closing = True
            # Local requests have no replay and no replacement on shutdown.
            self._pending.clear()
            self._condition.notify_all()
        self._stop.set()
        for worker in (self._action_worker, self._snapshot_worker):
            if worker is not None:
                worker.join(timeout)
                if worker.is_alive():
                    raise RuntimeError("Application view worker still owned; replacement refused")


class ApplicationShutdown(object):
    """Resource joins run off Tk; the window stays open until confirmed exit."""
    def __init__(self, runtime, server, view, application_guard=None):
        self.runtime, self.server, self.view = runtime, server, view
        self.application_guard = application_guard
        self.worker, self.error, self.completed = None, "", False

    def start(self):
        if self.worker is not None and (self.worker.is_alive() or self.completed):
            return
        self.error = ""
        def run():
            try:
                if not self.runtime.join(0):
                    raise RuntimeError("NI owner still running; shutdown refused")
                publisher = getattr(self.runtime, "telemetry_publisher", None)
                if publisher is not None:
                    publisher.close()
                self.server.shutdown()
                self.server.server_close()
                cooling = getattr(self.runtime, "cooling", None)
                if cooling is not None and hasattr(cooling, "close") and cooling.close(timeout=1) is False:
                    raise RuntimeError("Alarm journal worker still owned; shutdown unfinished")
                self.view.close()
                if self.application_guard is not None:
                    self.application_guard.release()
                self.completed = True
            except Exception as error:
                self.error = type(error).__name__ + ": " + str(error)[:300]
        self.worker = threading.Thread(target=run, name="ACQ-application-shutdown")
        self.worker.daemon = False
        self.worker.start()


def cleanup_failed_start(runtime=None, server=None, view=None, publisher=None,
                         cooling=None, server_thread=None, application_guard=None, timeout=1):
    """Background-only cleanup; return errors and retain unfinished ownership."""
    errors = []
    def attempt(label, callback):
        try:
            return callback()
        except Exception as error:
            errors.append(label + ": " + type(error).__name__ + ": " + str(error))
            return False
    stopped = True
    if runtime is not None:
        attempt("request shutdown", runtime.request_shutdown)
        stopped = attempt("join NI owner", lambda: runtime.join(timeout))
        if not stopped:
            errors.append("NI owner still running; resources retained")
    if stopped:
        if publisher is not None:
            attempt("publisher", publisher.close)
        if server is not None:
            if server_thread is not None and server_thread.is_alive():
                attempt("HTTP shutdown", server.shutdown)
            attempt("HTTP close", server.server_close)
        if view is not None:
            attempt("application view", lambda: view.close(timeout))
        if cooling is not None and hasattr(cooling, "close"):
            # Adopt only already loaded RAM state; never wait for storage here.
            attempt("alarm metadata", cooling.snapshot)
            if attempt("alarm writer", lambda: cooling.close(timeout=timeout)) is False:
                errors.append("Alarm writer still owned; startup cleanup unfinished")
        if not errors and application_guard is not None:
            attempt("application guard", application_guard.release)
    return errors


class StartupCleanup(object):
    def __init__(self, **resources):
        self.resources = resources
        self.worker, self.errors, self.completed = None, [], False

    def start(self):
        if self.worker is not None and (self.worker.is_alive() or self.completed):
            return
        def run():
            self.errors = cleanup_failed_start(**self.resources)
            self.completed = not self.errors
        self.worker = threading.Thread(target=run, name="ACQ-failed-start-cleanup")
        self.worker.daemon = False
        self.worker.start()
