"""One camera read worker per web process; bounded latest-frame fan-out.

No device writes or image archive. Slow browsers never build a frame backlog.
The source is the fixed Everest telemetry DS, not XP or a camera directly.
"""
from contextlib import contextmanager, nullcontext
import copy
import json
import math
import threading
import time
import zlib


def camera_identity(value):
    frame = value.get('frame') or {}
    if not frame:
        return None
    return (frame.get('source_session_id') or value.get('session_id'),
            frame.get('capture_session_id'), frame.get('sequence'), frame.get('channel'))


def unavailable(reason='Camera source unavailable'):
    return dict(schema_version=1, owner='supervision', available=False, stale=True,
                frame=None, age_seconds=None, hardware_acknowledged=False, error=reason)


class CameraFrameBroker:
    def __init__(self, read_frame, read_channels, *, fps=25., clock=time.monotonic,
                 max_channels=8, max_subscribers=16, monitor_all=False):
        if fps not in (25., 12.5):
            raise ValueError('Camera display rate must be 25 or 12.5 Hz')
        self.read_frame, self.read_channels, self.fps, self.clock = read_frame, read_channels, fps, clock
        self.max_channels, self.max_subscribers = max_channels, max_subscribers
        self.monitor_all = monitor_all
        self.condition = threading.Condition()
        self.entries, self.demand, self.subscribers = {}, {}, {}
        self.metadata = dict(schema_version=1, owner='supervision', channel_ids=[], channels={}, selected_channel=None)
        self.metadata_at = None
        self.metadata_attempt_at, self.metadata_error, self.metadata_demand_until = None, False, 0.
        self.decorate = None
        self.stop = threading.Event()
        self.thread = None
        self.source_reads = self.source_errors = self.changed_frames = 0

    def start(self):
        with self.condition:
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name='supervision-camera-web', daemon=True)
                self.thread.start()

    def _touch(self, channel):
        if channel is not None and (type(channel) is not int or not 0 <= channel <= 4294967295):
            raise ValueError('Actual unsigned camera channel required')
        with self.condition:
            if channel not in self.demand and len(self.demand) >= self.max_channels:
                expired = [key for key, until in self.demand.items()
                           if until < self.clock() and not self.subscribers.get(key)]
                for key in expired:
                    self.demand.pop(key, None)
                    self.entries.pop(key, None)
            if channel not in self.demand and len(self.demand) >= self.max_channels:
                raise ValueError('Camera view capacity reached')
            self.demand[channel] = self.clock() + 2.
            self.condition.notify_all()
        self.start()

    @contextmanager
    def subscribe(self, channel):
        with self.condition:
            if sum(self.subscribers.values()) >= self.max_subscribers:
                raise ValueError('Camera subscriber capacity reached')
            self.subscribers[channel] = self.subscribers.get(channel, 0) + 1
        try:
            self._touch(channel)
            yield
        finally:
            with self.condition:
                self.subscribers[channel] -= 1
                if not self.subscribers[channel]:
                    self.subscribers.pop(channel, None)

    def publish(self, channel, value):
        """Worker-only publication. No source or database I/O under cache lock."""
        stamp = self.clock()
        value = copy.deepcopy(value)
        identity = camera_identity(value)
        with self.condition:
            if channel not in self.entries and len(self.entries) >= self.max_channels:
                victims = [key for key in self.entries if not self.subscribers.get(key)
                           and self.demand.get(key, 0) < stamp]
                if victims:
                    oldest = min(victims, key=lambda key: self.entries[key]['at'])
                    self.entries.pop(oldest)
                else:
                    raise ValueError('Camera cache capacity reached')
            prior = self.entries.get(channel)
            if prior and prior['identity'] == identity and identity is not None:
                prior_age = prior['value'].get('age_seconds')
                age = value.get('age_seconds')
                if type(prior_age) in (int, float) and type(age) in (int, float):
                    value['age_seconds'] = max(age, prior_age + max(0., stamp - prior['at']))
            version = (prior['version'] + 1 if prior else 1)
            changed = not prior or prior['identity'] != identity
            self.entries[channel] = dict(value=value, identity=identity, at=stamp, version=version)
            if changed and identity is not None:
                self.changed_frames += 1
            self.condition.notify_all()

    def snapshot(self, channel=None, *, wait=.25):
        self._touch(channel)
        deadline = time.monotonic() + wait
        with self.condition:
            while channel not in self.entries and wait > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.condition.wait(remaining)
            entry = self.entries.get(channel)
            if entry is None:
                return unavailable('Waiting for camera observation')
            value = copy.deepcopy(entry['value'])
            age = value.get('age_seconds')
            if type(age) in (int, float):
                value['age_seconds'] = age + max(0., self.clock() - entry['at'])
                diagnostics = value.get('diagnostics') or {}
                current = diagnostics.get('current') or {}
                if current:
                    current['age_seconds'] = value['age_seconds']
                    if value['age_seconds'] >= 2:
                        current.update(valid=False, quality='STALE', x=None, y=None)
                        diagnostics['offset'] = None
                        diagnostics['planner'] = dict(execution_allowed=False, state='BLOCKED',
                            reason='Camera observation expired', proposal=None)
                if value['age_seconds'] >= 2:
                    value.update(available=False, stale=True, frame=None)
            return value

    def channels(self):
        with self.condition:
            self.metadata_demand_until = self.clock() + 2.
        self.start()
        with self.condition:
            value = copy.deepcopy(self.metadata)
            elapsed = None if self.metadata_at is None else max(0., self.clock() - self.metadata_at)
            current = elapsed is not None and elapsed < 2 and not self.metadata_error
            for row in value.get('channels', {}).values():
                age = row.get('age_seconds')
                if type(age) in (int, float) and elapsed is not None:
                    row['age_seconds'] = age + elapsed
                    if row['age_seconds'] >= 2:
                        row.update(available=False, stale=True)
                if not current:
                    row.update(available=False, stale=True)
            return dict(value, metadata_current=current, metadata_age_seconds=elapsed,
                broker=dict(source_reads=self.source_reads,
                source_errors=self.source_errors, changed_frames=self.changed_frames,
                target_fps=self.fps, subscribers=sum(self.subscribers.values()),
                buffering='latest_per_channel', archive_images=False))

    def _run(self):
        while not self.stop.is_set():
            started = self.clock()
            with self.condition:
                channels = [key for key, until in self.demand.items()
                            if until >= started or self.subscribers.get(key)]
                if self.monitor_all:
                    channels = list(dict.fromkeys(channels + (self.metadata.get('channel_ids') or [None])))
            if not channels and self.metadata_demand_until < started:
                self.stop.wait(.1)
                continue
            if self.metadata_attempt_at is None or started - self.metadata_attempt_at >= 1:
                self.metadata_attempt_at = started
                try:
                    metadata = self.read_channels()
                    with self.condition:
                        self.metadata, self.metadata_at = metadata, self.clock()
                        self.metadata_error = False
                except Exception:
                    self.metadata_error = True
            selected = self.metadata.get('selected_channel')
            alias = None in channels and type(selected) is int
            if alias:
                channels = list(dict.fromkeys(selected if key is None else key for key in channels))
            any_current = False
            for channel in channels:
                if self.stop.is_set():
                    break
                try:
                    read_started = self.clock()
                    value = self.read_frame(channel)
                    self.source_reads += 1
                    elapsed = max(0., self.clock() - read_started)
                    if type(value.get('age_seconds')) in (int, float):
                        value = copy.deepcopy(value)
                        value['age_seconds'] += elapsed
                        if value.get('frame'):
                            value['frame']['source_age_seconds'] = max(
                                value['frame'].get('source_age_seconds', 0.), value['age_seconds'])
                    actual = (value.get('frame') or {}).get('channel', value.get('channel', channel))
                    analysis_started = self.clock()
                    if self.decorate and type(actual) is int:
                        try:
                            value = dict(value, diagnostics=self.decorate('ni1409:' + str(actual), value))
                        except Exception:
                            # Analysis/storage failures cannot erase a healthy image.
                            value = dict(value, diagnostics_error='Camera analysis unavailable')
                    elapsed = max(0., self.clock() - analysis_started)
                    if type(value.get('age_seconds')) in (int, float):
                        value['age_seconds'] += elapsed
                    self.publish(channel, value)
                    if alias and channel == selected:
                        self.publish(None, value)
                    any_current = any_current or value.get('available') is True
                except Exception as error:
                    self.source_errors += 1
                    self.publish(channel, unavailable(type(error).__name__ + ': camera read failed'))
                    if alias and channel == selected:
                        self.publish(None, unavailable(type(error).__name__ + ': camera read failed'))
            # An unavailable source needs no25Hz busy poll. The250ms backoff
            # excludes bounded source I/O; successful images have no1s limiter.
            period = 1. / self.fps if any_current else .25
            self.stop.wait(max(0., period - (self.clock() - started)))

    def events(self, channel=None, *, fps=25., duration=300., reserved=False):
        if fps not in (25., 12.5):
            raise ValueError('Camera display rate must be 25 or 12.5 Hz')
        with (nullcontext() if reserved else self.subscribe(channel)):
            deadline = self.clock() + duration
            previous, last_event = None, None
            while not self.stop.is_set() and self.clock() < deadline:
                started = self.clock()
                value = self.snapshot(channel, wait=.25)
                identity = camera_identity(value)
                marker = (identity, value.get('available'), value.get('stale'), value.get('error'))
                # No repeated pixel copies on owner heartbeats. Status refreshes
                # keep unavailable clients informed without faking fresh frames.
                if marker != previous or last_event is None or started - last_event >= 1:
                    event = 'frame' if value.get('available') else 'status'
                    yield ('event: ' + event + '\ndata: '
                           + json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n\n').encode()
                    previous, last_event = marker, started
                self.stop.wait(max(0., 1. / fps - (self.clock() - started)))

    def close(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread:
            self.thread.join(2)
        return self.thread is None or not self.thread.is_alive()


def gzip_events(events):
    """Flush each SSE event immediately; compression adds no frame batching."""
    compressor = zlib.compressobj(1, zlib.DEFLATED, 31)
    try:
        for event in events:
            yield compressor.compress(event) + compressor.flush(zlib.Z_SYNC_FLUSH)
    finally:
        close = getattr(events, 'close', None)
        if close:
            close()
