"""One bounded command-admission worker, separate from telemetry and NI.

Only the existing broker can admit an operation to the NI owner. HTTP receipt
timeout never retries or claims cancellation of an admission already in flight.
"""
from collections import deque
import copy
import threading
import time

from .command_protocol import validate_request


class CommandDispatcher(object):
    def __init__(self, broker, capacity=1, reply_timeout=1.0):
        if type(capacity) is not int or not 1 <= capacity <= 16 or not 0 < reply_timeout <= 1.5:
            raise ValueError('Bounded command queue and reply deadline required')
        self.broker, self.capacity, self.reply_timeout = broker, capacity, reply_timeout
        self._condition = threading.Condition()
        self._pending, self._urgent, self._active = deque(), deque(), None
        self._closing, self._worker = False, None

    def start(self):
        with self._condition:
            if self._worker is not None or self._closing:
                raise RuntimeError('Command dispatcher cannot start twice')
            self._worker = threading.Thread(target=self._run, name='ACQ-command-admission')
            self._worker.daemon = True
            try:
                self._worker.start()
            except Exception:
                self._worker = None
                self._closing = True
                raise

    def submit(self, request, lease):
        value = validate_request(request)
        job = dict(request=copy.deepcopy(value), lease=lease, done=threading.Event(),
                   result=None, error=None, started=False,
                   deadline=time.monotonic() + self.reply_timeout)
        with self._condition:
            if self._closing or self._worker is None or not self._worker.is_alive():
                raise RuntimeError('COMMAND_ADMISSION_CLOSED')
            # Reserved intent channel, not a bypass of broker/session/policy.
            # An in-flight admission is not forcibly interrupted or replaced.
            queue = self._urgent if value['operation'] == 'modulator.general.stop' else self._pending
            capacity = 1 if queue is self._urgent else self.capacity
            if len(queue) >= capacity:
                raise RuntimeError('COMMAND_ADMISSION_BUSY_NOT_SUBMITTED')
            queue.append(job)
            self._condition.notify_all()
        job['done'].wait(self.reply_timeout)
        with self._condition:
            if not job['done'].is_set():
                if not job['started']:
                    queue.remove(job)
                    raise RuntimeError('COMMAND_ADMISSION_EXPIRED_NOT_SUBMITTED')
                raise RuntimeError('COMMAND_ADMISSION_REPLY_TIMEOUT_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY')
            if job['error'] is not None:
                raise job['error']
            return copy.deepcopy(job['result'])

    def _run(self):
        while True:
            with self._condition:
                while not self._pending and not self._urgent and not self._closing:
                    self._condition.wait()
                if self._closing:
                    return
                job = (self._urgent if self._urgent else self._pending).popleft()
                if time.monotonic() >= job['deadline']:
                    job['error'] = RuntimeError('COMMAND_ADMISSION_EXPIRED_NOT_SUBMITTED')
                    job['done'].set()
                    continue
                job['started'], self._active = True, job
            result, error = None, None
            try:
                result = self.broker.submit(job['request'], job['lease'])
            except Exception as caught:
                error = caught
            with self._condition:
                job['result'], job['error'] = result, error
                self._active = None
                job['done'].set()

    def close(self, timeout=3):
        with self._condition:
            self._closing = True
            while self._pending or self._urgent:
                job = (self._urgent if self._urgent else self._pending).popleft()
                job['error'] = RuntimeError('COMMAND_ADMISSION_CLOSED_NOT_SUBMITTED')
                job['done'].set()
            self._condition.notify_all()
            worker = self._worker
        if worker is not None:
            worker.join(timeout)
            if worker.is_alive():
                raise RuntimeError('Command admission still owned; replacement refused')

    def status(self):
        with self._condition:
            return dict(pending=len(self._pending) + len(self._urgent), capacity=self.capacity,
                        urgent_pending=len(self._urgent), urgent_capacity=1,
                        active=self._active is not None, closing=self._closing,
                        worker_alive=self._worker is not None and self._worker.is_alive(),
                        automatic_retry=False)
