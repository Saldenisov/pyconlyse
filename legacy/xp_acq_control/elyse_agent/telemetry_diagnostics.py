"""Bounded, best-effort transport events; never a hardware/command journal."""
import collections
import datetime
import json
import os
import queue
import threading
import time
import uuid


class TelemetryDiagnostics(object):
    def __init__(self, session_id=None, path=None, capacity=64):
        self.session_id = session_id or uuid.uuid4().hex
        self.path = path
        self._queue = queue.Queue(maxsize=capacity)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._sequence = self._written = self._dropped = 0
        self._error = ''
        self._history = collections.deque(maxlen=16)
        self._last_kind = {}

    def emit(self, kind, throttle=0, **fields):
        now = time.monotonic()
        with self._lock:
            if throttle and now - self._last_kind.get(kind, float('-inf')) < throttle:
                return
            self._last_kind[kind] = now
            self._sequence += 1
            row = dict(fields, kind=kind, event_sequence=self._sequence,
                       session_id=self.session_id,
                       observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            self._history.append(row)
        if self.path:
            try:
                self._queue.put_nowait(row)
            except queue.Full:
                with self._lock:
                    self._dropped += 1

    def start(self):
        if self._thread is not None:
            raise RuntimeError('Diagnostic writer already started')
        if self.path:
            self._thread = threading.Thread(target=self._run, name='ACQ-telemetry-diagnostics')
            self._thread.daemon = True
            try:
                self._thread.start()
            except Exception as error:
                self._thread = None
                with self._lock:
                    self._error = type(error).__name__ + ': ' + str(error)[:300]
                    self._dropped += 1

    def _write(self, row):
        folder = os.path.dirname(os.path.abspath(self.path))
        if not os.path.isdir(folder):
            os.makedirs(folder)
        if os.path.isfile(self.path) and os.path.getsize(self.path) >= 2 * 1024 * 1024:
            os.replace(self.path, self.path + '.1')
        with open(self.path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + '\n')

    def _run(self):
        while not self._stop.is_set() or not self._queue.empty():
            try:
                row = self._queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                self._write(row)
                with self._lock:
                    self._written += 1
                    self._error = ''
            except Exception as error:
                with self._lock:
                    self._error = type(error).__name__ + ': ' + str(error)[:300]
                    self._dropped += 1
            finally:
                self._queue.task_done()

    def close(self, timeout=.25):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        # A stuck filesystem must not turn this diagnostic into a stop gate.

    def snapshot(self):
        with self._lock:
            return dict(event_sequence=self._sequence, written=self._written,
                        dropped=self._dropped, last_write_error=self._error,
                        pending=self._queue.qsize(), recent_events=list(self._history),
                        writer_alive=bool(self._thread and self._thread.is_alive()),
                        required_for_telemetry=False, durable=False)
