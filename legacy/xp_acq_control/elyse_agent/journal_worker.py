"""Bounded asynchronous alarm persistence; Python 3.4 stdlib only.

The worker alone calls storage methods. Queue/receipt locks never enclose I/O.
An accepted item remains inflight until append returns a durable commit ACK.
"""
import copy
import collections
import threading
import uuid


class JournalWorker(object):
    def __init__(self, storage_factory, validate_loaded=None, capacity=64,
                 retry_seconds=.25):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Journal capacity must be a positive integer")
        self._factory, self._validate = storage_factory, validate_loaded
        self._capacity, self._retry = capacity, retry_seconds
        self._condition = threading.Condition()
        self._queue, self._inflight = collections.deque(), None
        self._initial, self._ready, self._adopted = None, False, False
        self._submitted = self._committed = self._overflow = 0
        self._load_error = self._write_error = self._recovery_error = ""
        self._reconciling = 0
        self._closing = self._stopped = False
        self._thread = threading.Thread(target=self._run, name="ACQ-alarm-journal")
        # An unfinished writer must retain process ownership, not disappear
        # when Tk closes. The composition root must explicitly drain/join it.
        self._thread.daemon = False
        self._thread.start()

    def append(self, state, event):
        # Detach caller-owned mutable state before admission. No filesystem,
        # JSON encoding or SQLite work occurs on the observer's thread.
        state, event = copy.deepcopy(state), copy.deepcopy(event)
        event["journal_event_id"] = uuid.uuid4().hex
        with self._condition:
            size = len(self._queue) + (1 if self._inflight is not None else 0)
            if self._closing or self._stopped or size >= self._capacity:
                self._overflow += 1
                return None
            self._submitted += 1
            self._queue.append((self._submitted, state, event, "append"))
            self._condition.notify_all()
            return self._submitted

    def reconcile(self, state, event):
        state, event = copy.deepcopy(state), copy.deepcopy(event)
        event["journal_event_id"] = uuid.uuid4().hex
        with self._condition:
            if (not self._ready or not self._adopted or not self._recovery_error
                    or self._load_error or self._write_error or self._overflow
                    or self._queue or self._inflight is not None
                    or self._closing or self._stopped or self._reconciling):
                raise RuntimeError("Reconciliation requires loaded history gap and healthy idle journal writer")
            self._submitted += 1
            self._reconciling = self._submitted
            self._queue.append((self._submitted, state, event, "reconcile"))
            self._condition.notify_all()
            return self._submitted

    def loaded(self):
        with self._condition:
            return copy.deepcopy(self._initial) if self._ready else None

    def adopt_loaded(self, state):
        """Release writes only after the observer has merged persisted alarms.

        Pre-load events retain their identities/order, but their state image
        must include prior incidents instead of overwriting them with RAM-only
        startup observations. The journal stores latest state, not state history.
        """
        state = copy.deepcopy(state)
        with self._condition:
            if not self._ready or self._adopted:
                return False
            self._queue = collections.deque((seq, copy.deepcopy(state), event, operation)
                                            for seq, unused, event, operation in self._queue)
            self._adopted = True
            self._condition.notify_all()
            return True

    def status(self):
        with self._condition:
            pending = len(self._queue) + (1 if self._inflight is not None else 0)
            errors = []
            if not self._ready or not self._adopted:
                errors.append(self._load_error or "Alarm journal initial load pending")
            if self._write_error:
                errors.append(self._write_error)
            if self._recovery_error:
                errors.append(self._recovery_error)
            if self._overflow:
                errors.append("Alarm journal event admission failed: {0}".format(self._overflow))
            return dict(ready=self._ready, pending=pending,
                        submitted=self._submitted, committed=self._committed,
                        overflow=self._overflow, load_error=self._load_error,
                        write_error=self._write_error,
                        recovery_error=self._recovery_error,
                        reconciling=bool(self._reconciling),
                        error="; ".join(errors), closing=self._closing,
                        stopped=self._stopped,
                        durable=self._ready and self._adopted and not errors and not pending)

    def close(self, timeout=0):
        with self._condition:
            self._closing = True
            self._condition.notify_all()
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _pause(self):
        # Closing is not permission to drop pending data. Retry the same item;
        # the caller sees close(False) while persistence remains unfinished.
        with self._condition:
            self._condition.wait(self._retry)

    def _run(self):
        storage = None
        while True:
            try:
                if storage is None:
                    storage = self._factory()
                saved, events = storage.load(), storage.events()
                if self._validate is not None:
                    self._validate(saved, events)
                warning = storage.begin_session() if hasattr(storage, "begin_session") else ""
                with self._condition:
                    self._initial, self._ready = (saved, events), True
                    self._load_error, self._recovery_error = "", warning
                    self._condition.notify_all()
                break
            except Exception as error:
                with self._condition:
                    self._load_error = "Alarm journal load failed: " + str(error)
                    # No observations can be written before a trustworthy load.
                    # With no pending data it is safe to close, still unhealthy.
                    may_close = self._closing and not self._queue
                if may_close:
                    if storage is not None:
                        try:
                            storage.close()
                        except Exception as close_error:
                            with self._condition:
                                self._write_error = "Alarm journal close failed: " + str(close_error)
                            self._pause()
                            continue
                    with self._condition:
                        self._stopped = True
                    return
                self._pause()

        while True:
            with self._condition:
                while not self._adopted and not (self._closing and not self._queue):
                    self._condition.wait()
                while self._inflight is None and not self._queue and not self._closing:
                    self._condition.wait()
                if self._inflight is None and self._queue:
                    self._inflight = self._queue.popleft()
                item = self._inflight
                closing = self._closing
            if item is None and closing:
                try:
                    status = self.status()
                    # Historical uncertainty must persist, but it does not
                    # make this successfully drained writer an unclean owner.
                    clean = bool(self._ready and self._adopted
                                 and not status["load_error"] and not status["write_error"])
                    uncertainty = ("Alarm journal event admission failed: {0}".format(status["overflow"])
                                   if status["overflow"] else "")
                    if hasattr(storage, "end_session"):
                        storage.end_session(clean, uncertainty)
                    storage.close()
                    with self._condition:
                        self._stopped = True
                    return
                except Exception as error:
                    with self._condition:
                        self._write_error = "Alarm journal close failed: " + str(error)
                    self._pause()
                    continue
            try:
                if item[3] == "reconcile":
                    storage.reconcile(item[1], item[2])
                else:
                    storage.append(item[1], item[2])
                with self._condition:
                    self._committed = item[0]
                    self._inflight = None
                    self._write_error = ""
                    if item[3] == "reconcile":
                        self._recovery_error = ""
                        self._reconciling = 0
                    self._condition.notify_all()
            except Exception as error:
                with self._condition:
                    self._write_error = "Alarm journal write failed: " + str(error)
                self._pause()
