"""Bounded read-only camera phase diagnostics, compatible with Python 3.4.

No pixels, disk writes, driver calls, or clock-based frame identities. Sampling
never waits for the diagnostic lock. Durations use perf_counter on XP, whose
monotonic clock alone can quantize short phases to 10--16 ms.
"""
from collections import deque
import threading


class CameraIngressMetrics:
    FIELDS = ('receive_seconds', 'ingest_seconds', 'reply_seconds',
              'source_age_at_receive_seconds', 'source_copy_seconds')

    def __init__(self, capacity=256):
        if type(capacity) is not int or not 1 <= capacity <= 1024:
            raise ValueError('Bounded diagnostic sample capacity required')
        self.lock = threading.Lock()
        self.samples = deque(maxlen=capacity)
        self.completed = self.rejected = self.connections = 0
        self.skipped_busy = 0
        self.last_arrival = None
        self.first_arrival = None
        self.errors = {}

    def connection(self):
        if not self.lock.acquire(False):
            self.skipped_busy += 1
            return
        try:
            self.connections += 1
        finally:
            self.lock.release()

    def record(self, arrival, receive, ingest, reply, accepted,
               source_age=None, source_copy=None, error=''):
        if not self.lock.acquire(False):
            self.skipped_busy += 1
            return
        try:
            row = dict(zip(self.FIELDS, (receive, ingest, reply, source_age, source_copy)))
            row['arrival'] = arrival
            self.samples.append(row)
            self.completed += 1
            self.rejected += int(not accepted)
            self.last_arrival = arrival
            if self.first_arrival is None:
                self.first_arrival = arrival
            if error:
                # Fixed categories avoid unbounded per-frame numeric error strings.
                category = ('source_clock' if 'clock' in error or 'stale' in error
                            or 'future' in error else 'owner_busy' if 'BUSY' in error
                            else 'other')
                self.errors[category] = self.errors.get(category, 0) + 1
        finally:
            self.lock.release()

    @staticmethod
    def summarize(values):
        values = sorted(value for value in values if value is not None)
        if not values:
            return None
        return dict(count=len(values), mean=sum(values) / len(values),
                    p50=values[(len(values) - 1) // 2],
                    p95=values[int((len(values) - 1) * .95)], maximum=values[-1])

    def snapshot(self):
        if not self.lock.acquire(False):
            return dict(available=False, reason='DIAGNOSTIC_SNAPSHOT_BUSY')
        try:
            rows = list(self.samples)
            result = dict(available=True, completed=self.completed, rejected=self.rejected,
                connections=self.connections, skipped_busy=self.skipped_busy,
                errors=dict(self.errors), retained_samples=len(rows),
                sample_capacity=self.samples.maxlen, pixels_retained=False,
                clock='perf_counter', interpretation='Software ingress phases, not camera acquisition FPS')
        finally:
            self.lock.release()
        result['phases'] = {field: self.summarize(row[field] for row in rows) for field in self.FIELDS}
        arrivals = sorted(row['arrival'] for row in rows)
        result['arrival_intervals_seconds'] = self.summarize(
            right - left for left, right in zip(arrivals, arrivals[1:]))
        elapsed = arrivals[-1] - arrivals[0] if len(arrivals) > 1 else 0
        result['completed_window_hz'] = (len(arrivals) - 1) / elapsed if elapsed > 0 else None
        return result
