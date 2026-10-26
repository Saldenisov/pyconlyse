"""Concurrent card configuration inside the retained NI child, without I/O.

Worker diagnostics only touch locked RAM. The coordinating thread publishes
events; a timed-out native call and its eventual owner remain reachable.
Compatible with the deployed Python 3.4 runtime.
"""
from __future__ import division

import math
import datetime
import threading
import time
from copy import deepcopy

from .acquisition_driver_diagnostics import describe_driver_exception
from .hardware_plan import card_initialization_plan
from .hardware_tasks import LegacyCardTasks, PartialTaskCreationError, TaskCleanupError


STATUS_KIND = "INITIALIZATION_CARD_STATUS_NOT_MEASUREMENT"
BOUNDARY_KIND = "INITIALIZATION_CALL_BOUNDARY_NOT_MEASUREMENT"


class ParallelCardPreparationError(PartialTaskCreationError):
    """Failed preparation retains every settled owner and pending worker."""

    def __init__(self, reason, owner):
        self.reason = reason
        self.card_status = owner.snapshot()
        PartialTaskCreationError.__init__(self, reason, owner)


class ParallelCardOwner(object):
    """Cleanup-only owner; never exposes start, write or measurement methods."""

    def __init__(self, create, cancel, devices, started):
        self.create, self.cancel = create, cancel
        self.devices, self.started = devices, started
        self.condition = threading.Condition()
        self.threads, self.owners, self.errors = {}, {}, {}
        self.events = []
        self.cards = dict((card, dict(state="QUEUED", current_call=None,
            phase=None, error=None, error_code=None, task_count=0, started=None, finished=None,
            timed_out=False, cancelled=False)) for card in devices)
        self.merged_owner = None
        self.cancelled = False
        self.closed = False

    def _boundary(self, card, phase, call, event=None):
        notice = dict(event or {})
        notice.update(kind=BOUNDARY_KIND, card=card, phase=phase,
            call=call, operation="initialize", safe_to_sample=False,
            hardware_acknowledged=False)
        notice.setdefault("utc", datetime.datetime.now(datetime.timezone.utc).isoformat())
        self.events.append(notice)

    def _notice(self, card, event):
        # Called by a card thread: never invoke the backend/scheduler observer.
        with self.condition:
            record = self.cards[card]
            record["current_call"] = event.get("call")
            record["phase"] = event.get("phase")
            self._boundary(card, record["phase"], record["current_call"], event)
            self.condition.notify_all()

    def _worker(self, card):
        with self.condition:
            record = self.cards[card]
            if self.cancel.is_set():
                record.update(state="CANCELLED_NOT_ENTERED", cancelled=True,
                              finished=time.monotonic())
                self.condition.notify_all()
                return
            record.update(state=("TIMED_OUT_UNKNOWN" if record["timed_out"]
                                 else "RUNNING"), started=time.monotonic(),
                          current_call="create_legacy_card_tasks", phase="ENTER")
            self._boundary(card, "ENTER", "create_legacy_card_tasks")
        result, error = None, None
        try:
            result = self.create(authorized=True, outputs_commissioned=True,
                selected_devices=(card,), observer=lambda event: self._notice(card, event))
            if result is None:
                raise TypeError("Card factory returned no task owner")
        except BaseException as cause:
            error = cause
            if isinstance(cause, PartialTaskCreationError):
                result = cause.owner
        with self.condition:
            if result is not None:
                self.owners[card] = result
                record["task_count"] = len(result.tasks)
            if error is not None:
                self.errors[card] = error
                record["error"] = describe_driver_exception(error)
                record["error_code"] = record["error"]["error_code"]
            record.update(state="FAILED" if error is not None else "READY",
                          phase="RAISED" if error is not None else "RETURNED",
                          finished=time.monotonic())
            self._boundary(card, record["phase"], "create_legacy_card_tasks")
            self.condition.notify_all()

    def launch(self):
        for card in self.devices:
            thread = threading.Thread(target=self._worker, args=(card,),
                                      name="NI-card-initialize-{0}".format(card))
            thread.daemon = True
            self.threads[card] = thread
            try:
                thread.start()
            except Exception as error:
                with self.condition:
                    self.errors[card] = error
                    self.cards[card].update(state="FAILED", phase="RAISED",
                        current_call="start initialization thread",
                        error=describe_driver_exception(error), finished=time.monotonic())
                    self._boundary(card, "RAISED", "start initialization thread")

    def _pending(self):
        return [card for card in self.devices if self.cards[card]["finished"] is None]

    @property
    def resource_count(self):
        with self.condition:
            if self.merged_owner is not None:
                return len(self.merged_owner.tasks)
            # Pending calls may own handles which have not yet been returned.
            return sum(len(owner.tasks) for owner in self.owners.values()) + len(self._pending())

    @property
    def tasks(self):
        with self.condition:
            if self.merged_owner is not None:
                return self.merged_owner.tasks
            tasks = {}
            for card in self.devices:
                if card not in self.owners:
                    continue
                for name, task in self.owners[card].tasks.items():
                    # Preserve both retained handles on an invalid duplicate.
                    key = name if name not in tasks else "card:{0}:{1}".format(card, name)
                    tasks[key] = task
            return tasks

    def snapshot(self):
        with self.condition:
            now, cards = time.monotonic(), {}
            for card in self.devices:
                record = self.cards[card]
                entry = dict((key, value) for key, value in record.items()
                             if key not in ("started", "finished"))
                entry["elapsed_seconds"] = (0.0 if record["started"] is None else
                    (record["finished"] or now) - record["started"])
                cards[card] = deepcopy(entry)
            return dict(kind=STATUS_KIND, operation="initialize", cards=cards,
                required_cards=list(self.devices), pending_cards=self._pending(),
                all_required_ready=self.merged_owner is not None,
                cancelled=self.cancelled, elapsed_seconds=now - self.started,
                safe_to_sample=False, hardware_acknowledged=False)

    def publish(self, observer):
        with self.condition:
            events, self.events = self.events, []
        if observer is not None:
            status = dict(kind=STATUS_KIND, initialization_cards=self.snapshot(),
                operation="initialize", hardware_acknowledged=False, safe_to_sample=False)
            for event in events + [status]:
                try:
                    observer(event)
                except Exception:
                    pass  # Diagnostics cannot discard ownership or skip work.

    def mark_unknown(self, cancelled=False):
        with self.condition:
            self.cancelled = cancelled
            for card in self._pending():
                self.cards[card].update(
                    state="CANCELLED_UNKNOWN" if cancelled else "TIMED_OUT_UNKNOWN")
                self.cards[card]["cancelled" if cancelled else "timed_out"] = True

    def merge(self, observer):
        with self.condition:
            tasks, counters = {}, {}
            for card in self.devices:
                owner = self.owners[card]
                if set(tasks).intersection(owner.tasks) or set(counters).intersection(owner.counter_channels):
                    raise ValueError("Duplicate task name or counter channel in card preparation")
                tasks.update(owner.tasks)
                counters.update(owner.counter_channels)
            first = self.owners[self.devices[0]]
            plan = card_initialization_plan()
            plan["device_numbers"] = self.devices
            if 10 not in self.devices:
                plan["counter_output"] = []
            merged = LegacyCardTasks(first.daqmx, plan, tasks, counters, first.sleep)
            merged.initialization_observer = observer
            merged.parallel_initialization = self
            self.merged_owner = merged
            # Transfer ownership, so cleanup has exactly one task dictionary.
            for owner in self.owners.values():
                owner.tasks.clear()
                owner.counter_channels.clear()
            return merged

    def close(self):
        with self.condition:
            if any(thread.is_alive() for thread in self.threads.values()):
                raise RuntimeError("Card initialization still pending; ownership retained")
            owners = ([self.merged_owner] if self.merged_owner is not None else
                      [self.owners[card] for card in reversed(self.devices) if card in self.owners])
        failures = []
        for index, owner in enumerate(owners):
            try:
                owner.close()
            except Exception as error:
                failures.append(("card owner {0}".format(index), error))
        self.closed = not self.resource_count
        if failures:
            raise TaskCleanupError(failures)


def prepare_parallel_cards(create, cancel, observer=None, timeout=30.0, devices=None):
    """Prepare all required cards once, with one total configuration deadline.

    No task start, output image, measurement, retry, or automatic cleanup occurs.
    Failure/cancellation/timeout returns retained ownership via the exception.
    """
    if not callable(create) or (observer is not None and not callable(observer)):
        raise TypeError("Card factory and optional initialization observer must be callable")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Initialization timeout must be finite and positive")
    devices = tuple(range(1, 12)) if devices is None else devices
    if (type(devices) is not tuple or not devices or
            any(type(card) is not int or card not in range(1, 12) for card in devices) or
            len(set(devices)) != len(devices)):
        raise ValueError("Explicit unique card numbers 1..11 required")
    owner = ParallelCardOwner(create, cancel, devices, time.monotonic())
    deadline = owner.started + timeout
    owner.publish(observer)
    owner.launch()
    reason = None
    while True:
        owner.publish(observer)
        with owner.condition:
            if cancel.is_set():
                reason = "Card preparation cancelled; ownership retained"
                owner.mark_unknown(cancelled=True)
                break
            if not owner._pending():
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "Card preparation deadline exceeded; pending calls have unknown outcomes"
                owner.mark_unknown()
                break
            owner.condition.wait(min(0.05, remaining))
    if reason is None and owner.errors:
        reason = "Card preparation failed for cards {0}".format(
            ", ".join(str(card) for card in sorted(owner.errors)))
    if reason is None:
        try:
            result = owner.merge(observer)
        except Exception as error:
            reason = str(error)
        else:
            owner.publish(observer)
            return result
    owner.publish(observer)
    raise ParallelCardPreparationError(reason, owner)
