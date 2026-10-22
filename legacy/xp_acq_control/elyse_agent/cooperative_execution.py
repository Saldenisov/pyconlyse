"""Optional same-owner checkpoints during qualified noncritical waits.

Python 3.4 compatible. This scheduler creates no thread and never calls NI.
The caller must explicitly qualify each safe span. Observer time consumes the
original dwell; a slow callback may still overrun that dwell, so this is not a
hard real-time scheduler or a way to interrupt a native call.
"""
import math
import threading
import time


class CooperativeExecution(object):
    def __init__(self, observer=None, interval_seconds=.2, clock=None):
        if observer is not None and not callable(observer):
            raise ValueError("Execution observer must be callable or None")
        if (type(interval_seconds) not in (int, float)
                or not math.isfinite(interval_seconds) or interval_seconds <= 0):
            raise ValueError("Positive finite checkpoint interval required")
        self.observer = observer
        self.interval_seconds = interval_seconds
        self.clock = clock or time.monotonic
        self.owner_ident = None
        self.active = False
        self.checkpoint_count = 0
        self.observer_error_count = 0
        self.last_observer_error = None
        self.last_phase = None
        self.last_wait_overrun_seconds = 0.
        self.maximum_wait_overrun_seconds = 0.

    def snapshot(self):
        return dict(enabled=self.observer is not None,
                    checkpoint_count=self.checkpoint_count,
                    observer_error_count=self.observer_error_count,
                    last_observer_error=self.last_observer_error,
                    last_phase=dict(self.last_phase) if self.last_phase else None,
                    last_wait_overrun_seconds=self.last_wait_overrun_seconds,
                    maximum_wait_overrun_seconds=self.maximum_wait_overrun_seconds,
                    hardware_acknowledged=False)

    def wait(self, seconds, wait_seconds, safe_to_sample=False, phase=None):
        """Wait without changing the original effect order or critical dwell.

        Without an observer, or in a critical span, invoke the original wait
        exactly once. A safe observer is called on this caller's owner thread
        only, outside any scheduler lock. Exceptions are diagnostics: telemetry
        failure must not prevent a source pulse release or best-effort stop.
        Returning True from an Event.wait callback preserves early cancellation.
        """
        if self.observer is None or not safe_to_sample:
            return wait_seconds(seconds)
        if self.active:
            raise RuntimeError("Reentrant cooperative execution is forbidden")
        ident = threading.current_thread().ident
        if self.owner_ident is None:
            self.owner_ident = ident
        elif self.owner_ident != ident:
            raise RuntimeError("Cooperative checkpoints require the same NI owner")
        if (type(seconds) not in (int, float) or not math.isfinite(seconds)
                or seconds < 0):
            raise ValueError("Nonnegative finite source dwell required")
        deadline = self.clock() + seconds
        result = None
        self.active = True
        try:
            while True:
                remaining = deadline - self.clock()
                if remaining <= 0:
                    return result
                event = dict(phase or {})
                event.update(safe_to_sample=True, remaining_seconds=remaining,
                             minimum_next_action_deadline=deadline,
                             checkpoint_monotonic=self.clock(),
                             hardware_acknowledged=False)
                self.last_phase = event
                self.checkpoint_count += 1
                try:
                    self.observer(dict(event))
                except Exception as error:
                    self.observer_error_count += 1
                    self.last_observer_error = type(error).__name__ + ": " + str(error)
                remaining = deadline - self.clock()
                if remaining <= 0:
                    return result
                result = wait_seconds(min(self.interval_seconds, remaining))
                if result is True:
                    return result
        finally:
            self.last_wait_overrun_seconds = max(0., self.clock() - deadline)
            self.maximum_wait_overrun_seconds = max(
                self.maximum_wait_overrun_seconds, self.last_wait_overrun_seconds)
            self.active = False
