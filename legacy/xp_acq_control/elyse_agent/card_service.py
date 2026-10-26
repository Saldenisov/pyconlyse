"""One process owns one physical Acquisition card. Import is cold; Python 3.4.

Only the existing isolated-worker main thread calls this service. A private
trusted factory is an offline-test seam, never a field accepted from HTTP.
No device reset, reconnect, output replay or automatic restart occurs here.
"""
import copy
import importlib
import math
import time

from .hardware_plan import AI_BANKS, DI_BANKS
from .input_tasks import AI_TIMING
from .hardware_tasks import (create_legacy_card_tasks, prepare_driver_dependencies,
                             prepare_driver_runtime)


class CardService(object):
    def __init__(self, device, read_timeout=.5, trusted_factory=None):
        if type(device) is not int or device not in range(1, 12):
            raise ValueError("An exact Acquisition device 1..11 is required")
        if (type(read_timeout) not in (int, float) or not math.isfinite(read_timeout)
                or not .01 <= read_timeout <= 2):
            raise ValueError("Bounded card input timeout required")
        self.device, self.read_timeout = device, read_timeout
        self.owner, self.observer = None, None
        if trusted_factory is not None and (type(trusted_factory) is not str
                or trusted_factory.count(":") != 1):
            raise ValueError("Trusted local factory name required")
        self.trusted_factory = trusted_factory
        self.started = []
        self.legacy_start_attempted = self.legacy_start_completed = False

    @property
    def resource_count(self):
        return len(self.owner.tasks) if self.owner is not None else 0

    def set_execution_observer(self, observer):
        self.observer = observer

    def prepare_isolated_dependencies(self):
        if self.trusted_factory is None:
            prepare_driver_dependencies(self._notice)
            prepare_driver_runtime(self._notice)

    def _notice(self, event):
        if self.observer is not None:
            self.observer(dict(event, card=self.device, safe_to_sample=False,
                kind="INITIALIZATION_CALL_BOUNDARY_NOT_MEASUREMENT", operation="initialize"))

    def _native(self, label, callback, *arguments, **keywords):
        def notice(phase):
            if self.observer is not None:
                try:
                    self.observer(dict(kind="CARD_NATIVE_CALL_BOUNDARY_NOT_MEASUREMENT",
                        card=self.device, call=label, phase=phase, safe_to_sample=False,
                        hardware_acknowledged=False))
                except Exception:
                    pass  # Diagnostics never skip a stop or discard a handle.
        notice("ENTER")
        try:
            result = callback(*arguments, **keywords)
        except Exception:
            notice("RAISED")
            raise
        notice("RETURNED")
        return result

    def initialize(self, cancel, startup_confirmed=False):
        if startup_confirmed is not True or self.owner is not None or cancel.is_set():
            raise RuntimeError("One explicitly confirmed card initialization required")
        factory = create_legacy_card_tasks
        if self.trusted_factory is not None:
            module, name = self.trusted_factory.split(":")
            if not name.isidentifier() or not all(p.isidentifier() for p in module.split(".")):
                raise ValueError("Trusted importable factory required")
            factory = getattr(importlib.import_module(module), name)
        try:
            self.owner = factory(authorized=True, outputs_commissioned=True,
                selected_devices=(self.device,), observer=self._notice)
        except Exception as error:
            self.owner = getattr(error, "owner", None)
            raise
        return dict(device=self.device, tasks=sorted(self.owner.tasks),
                    started_counters=list(self.started), hardware_acknowledged=False)

    def read_snapshot(self, cancel):
        if self.owner is None or cancel.is_set():
            raise RuntimeError("Existing current card owner required")
        banks, started = {}, time.monotonic()
        for name, device, count in AI_BANKS:
            if device != self.device:
                continue
            task = self.owner.tasks[name]
            self._native(name + ".start", task.start)
            try:
                values = list(self._native(name + ".read_analog_latest",
                    self.owner.read_analog_latest, name, self.read_timeout))
            finally:
                self._native(name + ".stop", task.stop)
            if len(values) != count or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
                raise ValueError("Invalid raw analog input bank")
            banks[name] = dict(kind="analog_input", device=device, values=values,
                software_averaging=False, samples_per_channel_acquired=AI_TIMING[name][2],
                selected_sample_index=AI_TIMING[name][2] - 1)
        for name, device, first, last, count in DI_BANKS:
            if device == self.device:
                values = list(self._native(name + ".read", self.owner.tasks[name].read,
                                          timeout=self.read_timeout))
                if len(values) != count or any(type(v) is not bool for v in values):
                    raise ValueError("Invalid digital input bank")
                banks[name] = dict(kind="digital_input", device=device, values=values)
        return dict(device=self.device, banks=banks,
                    sample_elapsed_seconds=time.monotonic() - started,
                    hardware_acknowledged=False)

    def card_call(self, request, cancel):
        if (type(request) is not dict or set(request) != {"action", "arguments"}
                or type(request["arguments"]) not in (tuple, list)):
            raise ValueError("Exact private card request required")
        if self.owner is None or cancel.is_set():
            raise RuntimeError("Current card owner required")
        action, arguments = request["action"], tuple(request["arguments"])
        methods = {"write_digital_bank": 2, "write_analog_logical_bank": 2,
                   "read_counter_pulse_done": 1, "start_counter": 1, "stop_counter": 1,
                   "write_counter_ticks": 4}
        if action == "start_legacy_counters" and not arguments:
            if self.device != 10:
                raise ValueError("Legacy counter startup requires Acquisition card10")
            if self.legacy_start_attempted and not self.legacy_start_completed:
                raise RuntimeError("Earlier counter startup may be partial; replay refused")
            if not self.legacy_start_completed:
                self.legacy_start_attempted = True
                self.started = list(self._native("start_legacy_counters", self.owner.start_legacy_counters))
                self.legacy_start_completed = True
            result = list(self.started)
        elif action in ("task.start", "task.stop"):
            if (self.device != 10 or len(arguments) != 1
                    or arguments[0] not in self.owner.tasks
                    or not arguments[0].startswith("C10_NI6602_CO_")):
                raise ValueError("Only an owned counter lifecycle may be addressed")
            result = self._native(arguments[0] + "." + action.split(".")[1],
                                 getattr(self.owner.tasks[arguments[0]], action.split(".")[1]))
        elif action in methods and len(arguments) == methods[action]:
            if "counter" in action and self.device != 10:
                raise ValueError("Counter operation requires the Acquisition NI6602")
            # The adapter validates names/shapes before any write. A foreign
            # bank cannot be redirected to another process by this service.
            if action == "write_digital_bank" and arguments[0] not in self.owner.tasks:
                raise ValueError("Digital bank is not owned by this card")
            if action == "write_analog_logical_bank" and arguments[0] + "_AO" not in self.owner.tasks:
                raise ValueError("Analog bank is not owned by this card")
            try:
                result = self._native(action, getattr(self.owner, action), *arguments)
            except Exception as error:
                report = getattr(self.owner, "get_counter_operation_report", lambda: None)()
                if report is not None and not hasattr(error, "report"):
                    error.report = copy.deepcopy(report)
                raise
        else:
            raise ValueError("Card operation is not on the private allowlist")
        report = getattr(self.owner, "get_counter_operation_report", lambda: None)()
        return dict(value=result, driver_report=copy.deepcopy(report))

    def close(self):
        if self.owner is not None:
            self._native("close card tasks", self.owner.close)
            self.owner = None
