"""Eleven independently retained card processes behind a LegacyCardTasks facade.

Import is cold. Explicit factory admission starts one dispatcher per physical
card; each dispatcher alone owns its isolated RPC client. Input polling is
independent, and all public status methods use locked RAM only. No helper
automatically restarts a dead owner, resets a device, replays an uncertain
mutation or interprets process death as physical OFF. Python 3.4, stdlib only.
"""
import copy
import collections
import math
import queue
import threading
import time

from .card_service import CardService
from .hardware_plan import (AI_BANKS, AO_BANKS, DI_BANKS, DO_BANKS,
    COUNTERS_STARTED_ON_INIT, analog_startup_logical_image,
    analog_startup_voltage_image, digital_startup_image, card_initialization_plan)
from .hardware_tasks import PartialTaskCreationError, TaskCleanupError
from .isolated_backend import IsolatedCardBackend, IsolatedBackendUncertain


INPUT_DEVICES = tuple(sorted(set(row[1] for row in AI_BANKS + DI_BANKS)))


def _bounded(value, minimum, maximum, label):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not minimum <= value <= maximum):
        raise ValueError("Finite bounded " + label + " required")
    return float(value)


def _task_names(device):
    names = [row[0] for row in AI_BANKS + DI_BANKS + DO_BANKS if row[1] == device]
    names += [row[0] + "_AO" for row in AO_BANKS if row[1] == device]
    if device == 10:
        names += ["C10_NI6602_CO_{0}".format(number) for number in range(8)]
    return tuple(sorted(names))


class CardRequestTimeout(RuntimeError):
    """No retry permission: an entered mutation may already have applied."""


class _Request(object):
    def __init__(self, action, arguments, timeout):
        self.action, self.arguments = action, copy.deepcopy(tuple(arguments))
        self.deadline = time.monotonic() + timeout
        self.condition = threading.Condition()
        self.entered = self.abandoned = self.complete = False
        self.value, self.error = None, None

    def enter(self):
        with self.condition:
            if self.abandoned or time.monotonic() >= self.deadline:
                self.error = CardRequestTimeout("Queued card request expired before dispatch; no effect inferred")
                self.complete = True
                self.condition.notify_all()
                return False
            self.entered = True
            return True

    def finish(self, value=None, error=None):
        with self.condition:
            self.value, self.error, self.complete = value, error, True
            self.condition.notify_all()

    def wait(self):
        with self.condition:
            while not self.complete:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    self.abandoned = True
                    raise CardRequestTimeout("Card request deadline exceeded; {0}; do not resend".format(
                        "entered outcome UNKNOWN" if self.entered else "not entered"))
                self.condition.wait(min(.05, remaining))
            if self.error is not None:
                raise self.error
            return copy.deepcopy(self.value)


class CardProcessEndpoint(object):
    """Reusable private card endpoint; local factories only, no public RPC port."""
    def __init__(self, device, read_timeout=.5, period=.2, rpc_timeout=3., initialize_timeout=30.,
                 close_timeout=5., trusted_factory=None, client_factory=None, observer=None,
                 service_factory=CardService, service_options=None, expected_tasks=None,
                 expected_started_counters=None):
        if (type(device) is not int and (type(device) is not str or not device or len(device) > 64)):
            raise ValueError("Explicit local card identity required")
        self.device = device
        self.read_timeout = _bounded(read_timeout, .01, 2, "read timeout")
        self.period = _bounded(period, .02, 10, "poll period")
        self.rpc_timeout = _bounded(rpc_timeout, .05, 30, "card RPC timeout")
        self.initialize_timeout = _bounded(initialize_timeout, .05, 120, "initialization timeout")
        self.close_timeout = _bounded(close_timeout, .05, 30, "close timeout")
        self.trusted_factory, self.client_factory = trusted_factory, client_factory
        self.service_factory = service_factory
        self.service_options = (dict(device=device, read_timeout=read_timeout, trusted_factory=trusted_factory)
                                if service_options is None else copy.deepcopy(service_options))
        self.expected_tasks = (_task_names(device) if expected_tasks is None else tuple(sorted(expected_tasks)))
        self.expected_started_counters = (() if expected_started_counters is None
                                          else tuple(expected_started_counters))
        if (type(self.service_options) is not dict or not self.expected_tasks
                or len(set(self.expected_tasks)) != len(self.expected_tasks)
                or any(type(name) is not str or not name for name in self.expected_tasks)):
            raise ValueError("Exact trusted service configuration and task inventory required")
        self.observer = observer
        self.lock = threading.RLock()
        self.incoming = queue.Queue(maxsize=2)
        self.client = None
        self.ready, self.finished = threading.Event(), threading.Event()
        self.state, self.error, self.input_error = "QUEUED", "", ""
        self.current_call, self.phase, self.error_code = None, None, None
        self.task_names, self.started_counters = (), ()
        self.latest, self.sample_started_at, self.sample_sequence = None, None, 0
        self.last_driver_report = None
        self.started_at = self.finished_initialization_at = None
        self.unresolved_request = False
        self.thread = threading.Thread(target=self._run, name="ACQ-card-dispatch-{0}".format(device))
        self.thread.daemon = True  # Native owners remain separate retained processes.

    def start(self):
        self.thread.start()

    initialize_async = start

    def call(self, action, arguments=(), timeout=None):
        request = self.submit(action, arguments, timeout)
        try:
            return request.wait()
        except CardRequestTimeout:
            with request.condition:
                entered = request.entered
            if entered:
                with self.lock:
                    self.unresolved_request = True
                    self.error = "Caller abandoned an entered card request; ownership retained"
            raise

    def fresh_input(self):
        value = self.call("fresh_input")
        value["age_seconds"] = max(0., time.monotonic() - value.pop("request_started_monotonic"))
        native = self.status()["native"]
        value.update(card_generation=native.get("worker_generation"), card_process_pid=native.get("worker_pid"))
        return value

    def input_snapshot(self):
        status = self.status()
        return dict(sample=status["sample"] if status["input_current"] else None,
                    age_seconds=status["sample_age_seconds"], current=status["input_current"],
                    card_generation=status["native"].get("worker_generation"),
                    sample_sequence=status["sample_sequence"], device=self.device)

    def close(self):
        with self.lock:
            if self.state == "CLOSED_JOINED":
                return dict(cleanup_confirmed=True)
            if self.thread.ident is None and self.client is None:
                self.state = "CLOSED_JOINED"
                self.finished.set()
                return dict(cleanup_confirmed=True)
        deadline = time.monotonic() + min(30., 2 * self.close_timeout + self.rpc_timeout + 2)
        value = self.call("close", timeout=max(.01, deadline - time.monotonic()))
        self.thread.join(max(0., deadline - time.monotonic()))
        status = self.status()
        if self.thread.is_alive() or status["native"].get("cleanup_confirmed") is not True:
            raise RuntimeError("Card cleanup and dispatcher join unconfirmed")
        return value

    def restart(self, affected_outputs_off_confirmed=False, expected_generation=None):
        """Return a new endpoint only after this one's clean close and join.

        The owner must replace its own reference with the returned object. A
        failed or crashed endpoint is never converted into a new owner here.
        """
        state = self.status()
        if affected_outputs_off_confirmed is not True:
            raise ValueError("Explicit affected-card physical OFF confirmation required")
        if (not expected_generation or expected_generation != state["native"].get("worker_generation")
                or state["state"] != "READY" or state["unresolved_request"]
                or state["native"].get("ownership_uncertain") is not False):
            raise RuntimeError("Changed or uncertain card ownership cannot be restarted")
        self.close()
        replacement = CardProcessEndpoint(self.device, self.read_timeout, self.period,
            self.rpc_timeout, self.initialize_timeout, self.close_timeout,
            self.trusted_factory, self.client_factory, self.observer,
            self.service_factory, self.service_options, self.expected_tasks,
            self.expected_started_counters)
        replacement.start()
        return replacement

    def _progress(self, event):
        with self.lock:
            self.current_call = event.get("call", self.current_call)
            self.phase = event.get("phase", self.phase)
        if self.observer is not None:
            try:
                self.observer(dict(event, card=self.device))
            except Exception:
                pass  # Status delivery cannot discard a returned owner.

    def _read(self):
        started = time.monotonic()
        value = self.client.read_snapshot(threading.Event())
        if (type(value) is not dict or value.get("device") != self.device
                or type(value.get("banks")) is not dict
                or not math.isfinite(value.get("sample_elapsed_seconds", float("nan")))):
            raise ValueError("Invalid per-card input result")
        with self.lock:
            self.latest, self.sample_started_at = copy.deepcopy(value), started
            self.sample_sequence += 1
            self.input_error = ""
        return value, started

    def _execute(self, request):
        if not request.enter():
            return False
        value, error, closed = None, None, False
        try:
            if request.action == "close":
                if self.client is not None:
                    self.client.close()
                closed = True
                value = dict(cleanup_confirmed=True)
            elif request.action == "fresh_input":
                sample, started = self._read()
                value = dict(sample=sample, request_started_monotonic=started)
            else:
                with self.lock:
                    self.last_driver_report = None
                value = self.client.card_call(dict(action=request.action, arguments=request.arguments))
                with self.lock:
                    self.last_driver_report = copy.deepcopy(value.get("driver_report"))
                value = value.get("value")
                if request.action == "start_legacy_counters":
                    with self.lock:
                        self.started_counters = tuple(value)
        except Exception as caught:
            error = caught
            with self.lock:
                if hasattr(caught, "report"):
                    self.last_driver_report = copy.deepcopy(caught.report)
                self.error = type(caught).__name__ + ": " + str(caught)
        with request.condition:
            abandoned_entered = request.abandoned and request.entered
        with self.lock:
            if abandoned_entered:
                # Even a late successful native return must be reconciled by
                # an explicit clean close before another mutation/replacement.
                self.unresolved_request = True
                self.error = "Caller abandoned an entered card request; ownership retained"
            if closed:
                self.state, self.error = "CLOSED_JOINED", ""
            elif self.client is not None and self.client.isolation_snapshot().get("ownership_uncertain") is True:
                self.state = "OWNERSHIP_UNCERTAIN"
        request.finish(value, error)
        return closed

    def _run(self):
        with self.lock:
            self.state, self.started_at = "INITIALIZING", time.monotonic()
            self.current_call, self.phase = "construct isolated card client", "ENTER"
        try:
            factory = self.client_factory or IsolatedCardBackend
            self.client = factory(backend_options=self.service_options, backend_factory=self.service_factory,
                rpc_timeout=self.rpc_timeout, initialize_timeout=self.initialize_timeout,
                close_timeout=self.close_timeout, progress_observer=self._progress)
            with self.lock:
                self.current_call, self.phase = "initialize isolated card client", "ENTER"
            result = self.client.initialize(threading.Event(), startup_confirmed=True)
            if (type(result) is not dict or result.get("device") != self.device
                    or tuple(result.get("tasks", ())) != self.expected_tasks
                    or tuple(result.get("started_counters", ())) !=
                    self.expected_started_counters):
                raise ValueError("Card initialized with an unexpected task/counter inventory")
            with self.lock:
                self.task_names = tuple(result["tasks"])
                self.started_counters = tuple(result["started_counters"])
                self.state, self.phase = "READY", "RETURNED"
                self.current_call = "initialize isolated card client"
        except Exception as error:
            with self.lock:
                self.state, self.error = "INITIALIZATION_FAILED_RETAINED", type(error).__name__ + ": " + str(error)
                self.error_code = getattr(error, "error_code", getattr(error, "code", None))
                self.phase = "RAISED"
        finally:
            with self.lock:
                self.finished_initialization_at = time.monotonic()
            self.ready.set()
        next_read = time.monotonic()
        try:
            while True:
                try:
                    request = self.incoming.get(timeout=min(.05, max(0., next_read - time.monotonic())))
                except queue.Empty:
                    request = None
                if request is not None:
                    if self._execute(request):
                        return
                    # A command always has priority over the next idle poll.
                    continue
                with self.lock:
                    eligible = self.state == "READY" and not self.unresolved_request
                if eligible and time.monotonic() >= next_read:
                    # Output-only owners still answer a RAM-only liveness RPC;
                    # no property reads or pulse-done queries are invented.
                    try:
                        self._read()
                    except Exception as error:
                        with self.lock:
                            self.input_error = type(error).__name__ + ": " + str(error)
                            if self.client.isolation_snapshot().get("ownership_uncertain") is True:
                                self.state = "OWNERSHIP_UNCERTAIN"
                    next_read = time.monotonic() + self.period
                elif not eligible:
                    next_read = time.monotonic() + self.period
        finally:
            self.finished.set()

    def submit(self, action, arguments=(), timeout=None):
        timeout = self.rpc_timeout + 1 if timeout is None else timeout
        timeout = _bounded(timeout, .01, 600., "card request timeout")
        request = _Request(action, arguments, timeout)
        with self.lock:
            if self.finished.is_set() or self.state == "CLOSED_JOINED":
                raise RuntimeError("Card owner is already closed")
            if action != "close" and (self.state != "READY" or self.unresolved_request):
                raise RuntimeError("Card owner is not ready; no automatic replay/restart")
            try:
                self.incoming.put_nowait(request)
            except queue.Full:
                raise RuntimeError("Bounded card queue full; request not submitted")
        return request

    def status(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            native = self.client.isolation_snapshot() if self.client is not None else dict(
                worker_generation=None, worker_pid=None, ownership_uncertain=False,
                cleanup_confirmed=self.state == "CLOSED_JOINED", resource_count=0,
                worker_state="NOT_SPAWNED")
            age = None if self.sample_started_at is None else max(0., now - self.sample_started_at)
            result = dict(device=self.device, state=self.state, error=self.error,
                current_call=self.current_call, phase=self.phase, error_code=self.error_code,
                task_count=len(self.task_names),
                input_error=self.input_error, tasks=list(self.task_names),
                started_counters=list(self.started_counters), native=native,
                sample_age_seconds=age, sample_sequence=self.sample_sequence,
                sample=copy.deepcopy(self.latest), queue_depth=self.incoming.qsize(),
                unresolved_request=self.unresolved_request,
                elapsed_seconds=(0. if self.started_at is None else
                    (self.finished_initialization_at or now) - self.started_at),
                automatic_restart=False, hardware_acknowledged=False)
        result["input_current"] = bool(result["state"] == "READY" and not result["input_error"]
            and not result["unresolved_request"] and native.get("ownership_uncertain") is False
            and age is not None and age < 2 and result["sample"] is not None)
        return result


class _CounterTaskProxy(object):
    def __init__(self, owner, name, generation):
        self.owner, self.name, self.generation = owner, name, generation

    def start(self):
        if not self.name.startswith("C10_NI6602_CO_"):
            raise RuntimeError("Input polling owns its AI lifecycle; use input_snapshot/fresh_input")
        return self.owner._call(10, "start_counter", (int(self.name.rsplit("_", 1)[1]),),
                                expected_generation=self.generation)

    def stop(self):
        if not self.name.startswith("C10_NI6602_CO_"):
            raise RuntimeError("Input polling owns its AI lifecycle; use input_snapshot/fresh_input")
        return self.owner._call(10, "stop_counter", (int(self.name.rsplit("_", 1)[1]),),
                                expected_generation=self.generation)


class CardProcessTasks(object):
    def __init__(self, devices=None, read_timeout=.5, period=.2, rpc_timeout=3.,
                 initialize_timeout=30., close_timeout=5., trusted_factory=None,
                 client_factory=None, observer=None):
        devices = tuple(range(1, 12)) if devices is None else devices
        if (type(devices) is not tuple or not devices or len(set(devices)) != len(devices)
                or any(type(v) is not int or v not in range(1, 12) for v in devices)):
            raise ValueError("Exact unique card tuple required")
        self.devices = devices
        self.read_timeout = _bounded(read_timeout, .01, 2, "read timeout")
        self.period = _bounded(period, .02, 10, "poll period")
        self.rpc_timeout = _bounded(rpc_timeout, .05, 30, "card RPC timeout")
        self.initialize_timeout = _bounded(initialize_timeout, .05, 120, "initialization timeout")
        self.close_timeout = _bounded(close_timeout, .05, 30, "close timeout")
        self.trusted_factory, self.client_factory, self.observer = trusted_factory, client_factory, observer
        self.dispatchers, self.closed = {}, False
        self.event_lock, self.events = threading.Lock(), collections.deque(maxlen=256)
        self.lifecycle = threading.RLock()
        self.last_counter_operation = None
        self._legacy_starts_attempted = False
        self.plan = card_initialization_plan()
        self.plan["device_numbers"] = devices

    def _new_dispatcher(self, device):
        return CardProcessEndpoint(device, self.read_timeout, self.period, self.rpc_timeout,
            self.initialize_timeout, self.close_timeout, self.trusted_factory,
            self.client_factory, self._notice)

    def _notice(self, event):
        with self.event_lock:
            self.events.append(copy.deepcopy(event))

    def _publish(self):
        with self.event_lock:
            events, self.events = list(self.events), collections.deque(maxlen=256)
        if self.observer is not None:
            for event in events:
                try:
                    self.observer(event)
                except Exception:
                    pass

    def initialize(self, cancel):
        if self.dispatchers or self.closed:
            raise RuntimeError("A retained card owner cannot initialize twice")
        for device in self.devices:
            dispatcher = self._new_dispatcher(device)
            self.dispatchers[device] = dispatcher
            try:
                dispatcher.start()
            except Exception as error:
                with dispatcher.lock:
                    dispatcher.state = "DISPATCH_THREAD_FAILED"
                    dispatcher.error = type(error).__name__ + ": " + str(error)
                dispatcher.ready.set()
                dispatcher.finished.set()
        deadline = time.monotonic() + self.initialize_timeout + 1
        while not all(v.ready.is_set() for v in self.dispatchers.values()):
            self._publish()
            if cancel.is_set() or time.monotonic() >= deadline:
                raise PartialTaskCreationError("Per-card preparation pending/cancelled; owners retained", self)
            cancel.wait(.02)
        self._publish()
        if any(v.status()["state"] != "READY" for v in self.dispatchers.values()):
            raise PartialTaskCreationError("One or more card processes failed initialization; owners retained", self)
        return self

    @property
    def tasks(self):
        result = {}
        for dispatcher in tuple(self.dispatchers.values()):
            state = dispatcher.status()
            if state["state"] != "CLOSED_JOINED":
                for name in state["tasks"]:
                    result[name] = _CounterTaskProxy(self, name, state["native"].get("worker_generation"))
        return result

    @property
    def resource_count(self):
        total = 0
        for dispatcher in tuple(self.dispatchers.values()):
            state = dispatcher.status()
            if state["state"] != "CLOSED_JOINED":
                total += max(1, state["native"].get("resource_count", 0))
        return total

    def snapshot(self):
        now = time.monotonic()
        cards = dict((str(device), dispatcher.status(now)) for device, dispatcher in
                     tuple(self.dispatchers.items()))
        return dict(kind="PER_CARD_PROCESS_STATUS_NOT_ATOMIC", cards=cards,
            required_cards=list(self.devices),
            pending_cards=[device for device, dispatcher in tuple(self.dispatchers.items())
                           if not dispatcher.ready.is_set()],
            generation_vector=[(device, cards[str(device)]["native"].get("worker_generation"))
                               for device in self.devices],
            all_required_ready=bool(cards and all(v["state"] == "READY" and
                v["native"].get("ownership_uncertain") is False and not v["unresolved_request"]
                for v in cards.values())),
            automatic_restart=False, hardware_acknowledged=False)

    def input_snapshot(self):
        status, banks = self.snapshot(), {}
        for device, card in status["cards"].items():
            if not card["input_current"]:
                continue
            for name, record in card["sample"]["banks"].items():
                value = copy.deepcopy(record)
                value.update(age_seconds=card["sample_age_seconds"],
                    card_generation=card["native"]["worker_generation"],
                    card_process_pid=card["native"]["worker_pid"],
                    sample_sequence=card["sample_sequence"], quality="FRESH")
                banks[name] = value
        required = [v for v in self.devices if v in INPUT_DEVICES]
        current = status["all_required_ready"] and all(
            status["cards"][str(v)]["input_current"] for v in required)
        return dict(banks=banks, cards=status["cards"], all_current=bool(current),
            generation_vector=status["generation_vector"],
            required_input_cards=required, sample_kind="independent_card_processes_not_atomic")

    def _call(self, device, action, arguments=(), timeout=None, expected_generation=None):
        if type(device) is not int or device not in self.dispatchers:
            raise ValueError("Card is not owned by this orchestrator")
        dispatcher = self.dispatchers[device]
        if (expected_generation is not None and expected_generation !=
                dispatcher.status()["native"].get("worker_generation")):
            raise RuntimeError("Task proxy belongs to a replaced card generation")
        try:
            value = dispatcher.call(action, arguments, timeout)
        except Exception:
            with dispatcher.lock:
                self.last_counter_operation = copy.deepcopy(dispatcher.last_driver_report)
            raise
        with dispatcher.lock:
            self.last_counter_operation = copy.deepcopy(dispatcher.last_driver_report)
        return value

    def fresh_input(self, device):
        # The request only returns a read that BEGAN on this dispatcher's
        # owner thread after this request entered; idle cache is never used.
        if type(device) is not int or device not in self.dispatchers:
            raise ValueError("Card is not owned by this orchestrator")
        return self.dispatchers[device].fresh_input()

    def start_legacy_counters(self):
        if 10 not in self.dispatchers:
            return []
        state = self.dispatchers[10].status()
        if state["state"] != "READY" or self.snapshot()["all_required_ready"] is not True:
            raise RuntimeError("All required cards must be prepared before startup effects")
        if tuple(state["started_counters"]) == COUNTERS_STARTED_ON_INIT:
            return list(state["started_counters"])  # Never replay source starts.
        if self._legacy_starts_attempted:
            raise RuntimeError("Earlier clock startup may be partial; replay refused")
        self._legacy_starts_attempted = True
        result = self._call(10, "start_legacy_counters")
        if tuple(result) != COUNTERS_STARTED_ON_INIT:
            raise RuntimeError("Unexpected source synchronization counter startup result")
        return list(result)

    def write_digital_bank(self, name, values):
        mapping = dict((v[0], v[1]) for v in DO_BANKS)
        if name not in mapping:
            raise ValueError("Unknown digital bank")
        return self._call(mapping[name], "write_digital_bank", (name, tuple(values)))

    def write_analog_logical_bank(self, name, values):
        mapping = dict(AO_BANKS)
        if name not in mapping:
            raise ValueError("Unknown analog bank")
        return self._call(mapping[name], "write_analog_logical_bank", (name, tuple(values)))

    def write_initial_images(self):
        digital, analog = digital_startup_image(), analog_startup_voltage_image()
        logical = analog_startup_logical_image()
        for name, device, first, last, count in DO_BANKS:
            if device in self.devices:
                self.write_digital_bank(name, digital[name])
        for name, device in AO_BANKS:
            if device in self.devices:
                self.write_analog_logical_bank(name, logical[name])
        return dict(digital=dict((n, v) for n, v in digital.items() if int(n[1]) in self.devices),
                    analog_volts=dict((n, v) for n, v in analog.items() if int(n[1]) in self.devices))

    def read_counter_pulse_done(self, number):
        return self._call(10, "read_counter_pulse_done", (number,))

    def start_counter(self, number):
        return self._call(10, "start_counter", (number,))

    def stop_counter(self, number):
        return self._call(10, "stop_counter", (number,))

    def write_counter_ticks(self, number, initial_delay_ticks, low_ticks, high_ticks):
        return self._call(10, "write_counter_ticks", (number, initial_delay_ticks, low_ticks, high_ticks))

    def get_counter_operation_report(self):
        return copy.deepcopy(self.last_counter_operation)

    def restart_card(self, device, affected_outputs_off_confirmed=False, expected_generation=None):
        if affected_outputs_off_confirmed is not True:
            raise ValueError("Explicit affected-card physical OFF confirmation required")
        with self.lifecycle:
            if device not in self.dispatchers or self.closed:
                raise ValueError("Existing current card required")
            previous = self.dispatchers[device]
            state = previous.status()
            if (not expected_generation or expected_generation != state["native"].get("worker_generation")
                    or state["native"].get("ownership_uncertain") is not False
                    or state["state"] != "READY" or state["unresolved_request"]):
                raise RuntimeError("Uncertain or changed card owner cannot be replaced")
            previous.close()
            if previous.thread.is_alive() or previous.status()["native"].get("cleanup_confirmed") is not True:
                raise RuntimeError("Prior card close and process join unconfirmed; replacement refused")
            replacement = self._new_dispatcher(device)
            self.dispatchers[device] = replacement
            replacement.start()
            if not replacement.ready.wait(self.initialize_timeout + 1) or replacement.status()["state"] != "READY":
                raise PartialTaskCreationError("Replacement card failed; new owner retained", self)
            if device == 10:
                self._legacy_starts_attempted = False
                self.start_legacy_counters()
            # Only this card's startup image is restored, never another card
            # or the synchronization process. No previous uncertain command is replayed.
            for name, owner_device, first, last, count in DO_BANKS:
                if owner_device == device:
                    self.write_digital_bank(name, digital_startup_image()[name])
            for name, owner_device in AO_BANKS:
                if owner_device == device:
                    self.write_analog_logical_bank(name, analog_startup_logical_image()[name])
            return dict(device=device, old_generation=expected_generation,
                new_generation=replacement.status()["native"]["worker_generation"],
                synchronization_interrupted=device == 10, hardware_acknowledged=False)

    def close(self):
        # Admit all closes first. An unresolved read on one physical card must
        # not prevent the remaining cards from attempting their own cleanup.
        requests, failures = [], []
        with self.lifecycle:
            deadline = time.monotonic() + min(30., 2 * self.close_timeout + self.rpc_timeout + 2)
            for device, dispatcher in tuple(self.dispatchers.items()):
                if dispatcher.status()["state"] == "CLOSED_JOINED":
                    continue
                if dispatcher.client is None and dispatcher.finished.is_set():
                    with dispatcher.lock:
                        dispatcher.state = "CLOSED_JOINED"
                    continue  # Dispatcher never constructed a native client.
                try:
                    requests.append((device, dispatcher, dispatcher.submit("close",
                        timeout=max(.01, deadline - time.monotonic()))))
                except Exception as error:
                    failures.append(("card {0}".format(device), error))
            for device, dispatcher, request in requests:
                try:
                    request.wait()
                    dispatcher.thread.join(max(0., deadline - time.monotonic()))
                    if dispatcher.thread.is_alive():
                        raise RuntimeError("Dispatcher join unconfirmed")
                except Exception as error:
                    failures.append(("card {0}".format(device), error))
            self.closed = self.resource_count == 0
        if failures:
            raise TaskCleanupError(failures)


def create_card_process_tasks(authorized=False, outputs_commissioned=False, cancel=None,
                              observer=None, owner_created=None, **options):
    if authorized is not True or outputs_commissioned is not True:
        raise ValueError("Explicit local NI ownership and startup admission required")
    if owner_created is not None and not callable(owner_created):
        raise TypeError("Trusted local owner publication callback must be callable")
    owner = CardProcessTasks(observer=observer, **options)
    if owner_created is not None:
        # Publish the strong owner reference before a dispatcher/process can
        # start. A failed callback has no card/process effects to reconcile.
        owner_created(owner)
    return owner.initialize(cancel or threading.Event())
