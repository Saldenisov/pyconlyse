"""One bounded worker owns REST I/O; Tango reads never wait on tuning or HTTP."""
from copy import deepcopy
from collections import OrderedDict
import math
import json
from threading import Event, Lock, Thread
import time
from uuid import uuid4

from .client import OutcomeUnknown, TopasError


class TopasMonitor:
    def __init__(self, client, interval_s=1, stale_after_s=5):
        if not math.isfinite(interval_s) or interval_s < .2:
            raise ValueError('Polling interval must be finite and at least 0.2 seconds')
        if not math.isfinite(stale_after_s) or stale_after_s <= interval_s:
            raise ValueError('Freshness limit must exceed the polling interval')
        self.client, self.interval, self.stale_after = client, interval_s, stale_after_s
        self.lock = Lock()
        self.wake, self.stop_event = Event(), Event()
        self.data, self.updated, self.received_at = None, None, None
        self.read_error = ''
        self.operation = None
        self.pending = None
        self.uncertain = False
        self.uncertain_operation = None
        self.thread = None
        self.requests = OrderedDict()

    def start(self):
        self.thread = Thread(target=self._run, name='topas-rest', daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                raise TopasError('TOPAS REST worker is still completing a bounded request; do not reuse it')
        else:
            self.client.close()

    def snapshot(self):
        with self.lock:
            age = None if self.updated is None else max(0, time.monotonic() - self.updated)
            fresh = age is not None and age <= self.stale_after and not self.read_error
            return deepcopy({'data': self.data, 'age_s': age, 'fresh': fresh, 'received_at': self.received_at,
                             'read_error': self.read_error, 'operation': self.operation, 'outcome_unknown': self.uncertain,
                             'uncertain_operation': self.uncertain_operation, 'stale_after_s': self.stale_after})

    def require_fresh(self):
        snapshot = self.snapshot()
        if not snapshot['fresh']:
            raise TopasError(snapshot['read_error'] or 'TOPAS telemetry is unavailable or stale')
        return snapshot['data']

    def submit(self, command, *args, request_id=None):
        if command not in {'set_wavelength', 'set_shutter', 'confirm_user_actions', 'stop_motors', 'set_motor_position'}:
            raise ValueError('Unsupported TOPAS operation')
        signature = json.dumps([command, args], sort_keys=True, allow_nan=False)
        with self.lock:
            if request_id is not None and request_id in self.requests:
                if self.requests[request_id] != signature:
                    raise ValueError('TOPAS request ID was reused with different arguments')
                return request_id
            if self.stop_event.is_set():
                raise TopasError('TOPAS REST worker is stopping')
            if self.pending or (self.operation and self.operation['status'] in {'queued', 'running'}):
                raise TopasError('A TOPAS request is already pending; inspect operation_json')
            if self.uncertain and not (command == 'set_shutter' and args == (False,)) and command != 'stop_motors':
                raise TopasError('Prior command outcome is unknown; verify TOPAS and explicitly acknowledge before retrying')
            operation = {'id': request_id or uuid4().hex, 'command': command, 'arguments': args,
                         'status': 'queued', 'error': '', 'submitted_at': time.time()}
            self.operation = operation
            self.pending = (operation['id'], command, args)
            self.requests[operation['id']] = signature
            while len(self.requests) > 128:
                self.requests.popitem(last=False)
        self.wake.set()
        return operation['id']

    def clear_error(self):
        data = self.require_fresh()
        with self.lock:
            if self.pending or (self.operation and self.operation['status'] in {'queued', 'running'}):
                raise TopasError('Wait for the current TOPAS request before acknowledging errors')
            if data['output']['IsWavelengthSettingInProgress'] or data['output']['IsWaitingForUserAction']:
                raise TopasError('TOPAS is still tuning or waiting for operator actions')
            if self.uncertain and data['shutter']['IsShutterOpen']:
                raise TopasError('Close and verify the TOPAS shutter before acknowledging an unknown outcome')
            self.uncertain = False
            self.uncertain_operation = None
            self.operation = None

    def refresh(self):
        observed = time.monotonic()
        try:
            data = self.client.read_snapshot()
            with self.lock:
                self.data, self.updated, self.received_at = data, observed, time.time()
                self.read_error = ''
        except Exception as exc:
            with self.lock:
                self.read_error = str(exc)

    def execute_pending(self):
        with self.lock:
            request = self.pending
            self.pending = None
            if request is None:
                return
            self.operation['status'] = 'running'
        _, command, args = request
        try:
            result = getattr(self.client, command)(*args)
            with self.lock:
                self.operation.update(status='accepted', result=result, finished_at=time.time())
        except Exception as exc:
            with self.lock:
                self.uncertain = self.uncertain or isinstance(exc, OutcomeUnknown)
                self.operation.update(status='failed', error=str(exc), finished_at=time.time())
                if isinstance(exc, OutcomeUnknown):
                    self.uncertain_operation = deepcopy(self.operation)

    def _run(self):
        try:
            while not self.stop_event.is_set():
                self.execute_pending()
                if self.stop_event.is_set():
                    break
                self.refresh()
                self.wake.wait(self.interval)
                self.wake.clear()
        finally:
            self.client.close()
