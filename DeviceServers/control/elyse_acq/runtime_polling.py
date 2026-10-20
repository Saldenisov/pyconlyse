"""Single-flight, latest-only runtime reader; no workers start on import.

Only the injected reader may access HTTP. Its socket inactivity timeout does
not guarantee a total cancellation deadline against drip-fed replies; late
complete replies are rejected. There are no redirects or write API. Retry
delays are interruptible, bounded exponential backoff. An in-flight read cannot
overlap another read or publish after stop. A stop timeout retains its live
owner; restarting is refused until the previous thread actually exits.
"""
import copy
import math
import threading
import time

from .runtime_client import read_runtime
from .runtime_health import project_runtime_contract, validate_runtime_identity


class RuntimePollingWorker:
    def __init__(self, key, port=8771, reader=read_runtime, period=1.0, timeout=2.0,
                 max_backoff=8.0, clock=time.monotonic, stop_event=None):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Runtime shared key must contain at least 32 bytes")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid XP runtime port")
        for value in (period, timeout, max_backoff):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Positive finite polling bounds required")
        if timeout > 5 or period < 0.05 or max_backoff < period or max_backoff > 60:
            raise ValueError("Invalid bounded polling policy")
        if not callable(reader) or not callable(clock):
            raise ValueError("Explicit runtime reader and monotonic clock required")
        self._key, self._port, self._reader = key, port, reader
        self._period, self._timeout, self._max_backoff = period, timeout, max_backoff
        self._clock = clock
        self._stop = stop_event if stop_event is not None else threading.Event()
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        self._worker = None
        self._started = False
        self._runtime = None
        self._received = None
        self._duration = 0.0
        self._error = "Waiting for XP runtime"
        self._protocol_error = ""
        self._identity = None
        self._session_changed = False
        self._failures = 0
        self._overlap_skipped = 0

    def start(self):
        with self._lock:
            if self._started or self._worker is not None or self._stop.is_set():
                raise RuntimeError("Runtime reader cannot be started or restarted twice")
            self._started = True
            self._worker = threading.Thread(target=self.run, name="ACQ-runtime-reader", daemon=True)
            self._worker.start()

    def is_alive(self):
        return self._worker is not None and self._worker.is_alive()

    def stop(self, join_timeout=3.0):
        self._stop.set()
        with self._lock:
            self._runtime = None
            self._error = "Runtime reader stopped"
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(join_timeout)
        return not self.is_alive()

    def poll_once(self):
        """Return retry delay; fake readers/clocks allow deterministic tests."""
        if self._stop.is_set():
            return self._period
        if not self._poll_lock.acquire(blocking=False):
            with self._lock:
                self._overlap_skipped += 1
            return self._period
        try:
            with self._lock:
                self._started = True
            try:
                started = self._clock()
                value = self._reader(self._key, port=self._port, timeout=self._timeout)
                received = self._clock()
                duration = received - started
                if not math.isfinite(duration) or duration < 0 or not isinstance(value, dict):
                    raise ValueError("Invalid runtime read duration or payload")
                protocol_error = ""
                try:
                    identity = validate_runtime_identity(value)
                except ValueError as error:
                    identity, protocol_error = None, str(error)
                with self._lock:
                    if self._stop.is_set():
                        return self._period  # Discard an in-flight late reply.
                    previous = self._identity
                    changed = bool(identity and previous
                                   and identity["session_id"] != previous["session_id"])
                    if identity and previous and not changed:
                        if identity["build_id"] != previous["build_id"]:
                            protocol_error = "Runtime build changed within one session"
                        elif identity["state_revision"] < previous["state_revision"]:
                            protocol_error = "Runtime state revision moved backwards within one session"
                    # Complete replacement only: never merge an earlier
                    # session's banks/commands into a new response.
                    self._runtime = copy.deepcopy(value)
                    if protocol_error:
                        # Retain identity/error diagnostics, never rejected
                        # session/build/revision measurements even internally.
                        self._runtime["latest"] = None
                    self._received, self._duration = received, duration
                    self._error, self._protocol_error = "", protocol_error
                    self._session_changed = changed
                    if identity and not protocol_error:
                        self._identity = identity
                    self._failures = 0
                return self._period
            except Exception as error:
                with self._lock:
                    self._runtime = None  # Never serve cached measurements on failure.
                    self._error = type(error).__name__ + ": " + str(error)[:500]
                    self._protocol_error = ""
                    self._session_changed = False
                    self._failures += 1
                    return min(self._max_backoff, self._period * 2**min(self._failures, 20))
        finally:
            self._poll_lock.release()

    def run(self):
        while not self._stop.is_set():
            delay = self.poll_once()
            if self._stop.wait(delay):
                break

    def snapshot(self):
        with self._lock:
            age = None if self._received is None else self._clock() - self._received
            health = project_runtime_contract(
                self._runtime, age, self._error, self._started and not self._stop.is_set(),
                self._duration, self._session_changed, self._protocol_error)
            runtime = copy.deepcopy(self._runtime)
            hidden = health["quality"] != "FRESH"
            if hidden and isinstance(runtime, dict):
                runtime["latest"] = None
            return dict(
                source="xp_python_acquisition_runtime", storage_mode="ram_latest",
                execution_allowed=False, hardware_writes=False, runtime=runtime,
                bridge_stale=health["bridge_stale"], bridge_age_seconds=age,
                bridge_error=self._error, bridge_protocol_error=self._protocol_error,
                read_duration_seconds=self._duration, source_current=health["source_current"],
                source_stale=health["source_stale"], source_age_seconds=health["source_age_seconds"],
                source_reported_age_seconds=health["source_reported_age_seconds"],
                runtime_state=health["runtime_state"], quality=health["quality"],
                session_changed=self._session_changed, measurements_hidden=hidden,
                overlapping_polls_skipped=self._overlap_skipped, health=health)
