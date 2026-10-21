"""Non-waiting telemetry projection; never takes command/journal paths."""
import copy
import threading
import time


class TelemetryView(object):
    def __init__(self, runtime):
        self.runtime = runtime
        self.clock = getattr(runtime, '_clock', time.monotonic)
        self._lock = threading.Lock()
        self._latest, self._captured_at = None, None
        self.busy_reads = 0

    def snapshot(self):
        capture = getattr(self.runtime, 'try_telemetry_snapshot', None)
        if capture is None:
            # Compatibility for simple driver-free publishers. The production
            # control runtime always implements the non-waiting capture API.
            return self.runtime.snapshot()
        value = capture()
        now = self.clock()
        with self._lock:
            if value is not None:
                version = (value.get('state_revision', -1), value.get('sequence', -1))
                previous = self._latest or {}
                if version >= (previous.get('state_revision', -1), previous.get('sequence', -1)):
                    self._latest, self._captured_at = copy.deepcopy(value), now
                return value
            self.busy_reads += 1
            value = copy.deepcopy(self._latest)
            if value is None:
                value = dict(self.runtime._identity, state='UNKNOWN', sequence=0,
                             state_revision=-1, latest=None, age_seconds=None,
                             resource_count=0, telemetry_bridge_mode=False)
            elif value.get('age_seconds') is not None:
                value['age_seconds'] += max(0, now - self._captured_at)
            # A contended command/lifecycle lock cannot turn cached values into
            # a current image. Native packets become null/unavailable instead.
            value.update(stale=True, error='OWNER_STATE_BUSY', telemetry_view_current=False)
            return value

    def status(self):
        with self._lock:
            return dict(busy_reads=self.busy_reads, owner_lock_waiting=False)
