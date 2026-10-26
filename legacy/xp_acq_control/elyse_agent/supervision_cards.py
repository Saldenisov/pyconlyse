"""Deferred local SuperVision NI6602 owner. Python 3.4; no import-time I/O.

No device is reset or taken from LabVIEW. Source counter2's named-task
Stop/Clear/ClearErrors preamble is deliberately not applied to an unknown
task belonging to another client. Fresh-owned configuration follows source
ticks/routes/start ordering. A native failure retains every returned handle.
"""
import copy
import importlib
import math
import time

from .synchronization_profiles import supervision_counter_profile, synchronization_memory


class SupervisionCardError(RuntimeError):
    def __init__(self, message, owner):
        self.owner = owner
        RuntimeError.__init__(self, message)


class SupervisionCounterCard(object):
    def __init__(self, driver_factory=None, wait=None, clock=None):
        self.driver_factory = driver_factory
        self.wait, self.clock = wait or time.sleep, clock or time.monotonic
        self.tasks, self.channels = {}, {}
        self.plan = supervision_counter_profile()
        self.running, self.uncertain = set(), set()
        self.creation_uncertain = False
        self.initialized = False
        self.last_error = ""
        self.observer = None

    @property
    def resource_count(self):
        return len(self.tasks) + int(self.creation_uncertain)

    def set_execution_observer(self, observer):
        self.observer = observer

    def prepare_isolated_dependencies(self):
        """Inside accepted Initialize, before the Windows stdin pump; no Task."""
        if self.driver_factory is None:
            from .hardware_tasks import prepare_driver_dependencies, prepare_driver_runtime
            prepare_driver_dependencies(self.observer)
            prepare_driver_runtime(self.observer)

    def _call(self, name, callback, *args, **kwargs):
        def notice(phase):
            if self.observer is not None:
                try:
                    self.observer(dict(card="supervision.NI6602", call=name,
                        phase=phase, hardware_acknowledged=False, safe_to_sample=False))
                except Exception:
                    pass
        notice("ENTER")
        try:
            result = callback(*args, **kwargs)
        except Exception as error:
            self.last_error = type(error).__name__ + ": " + str(error)
            notice("RAISED")
            raise
        notice("RETURNED")
        return result

    def initialize(self, operator_confirmed=False, resources_released_confirmed=False, observer=None):
        if operator_confirmed is not True or resources_released_confirmed is not True:
            raise ValueError("Explicit local card release and synchronization-start confirmation required")
        if self.tasks or self.creation_uncertain or self.initialized:
            raise RuntimeError("Retained SuperVision NI6602 owner cannot be replaced")
        if observer is not None:
            self.observer = observer
        driver = self.driver_factory() if self.driver_factory is not None else importlib.import_module("nidaqmx")
        if self.driver_factory is None:
            constants = importlib.import_module("nidaqmx.constants")
        else:
            constants = driver.constants
        try:
            for row in self.plan:
                i, name = row["output"], row["task_name"]
                self.creation_uncertain = True
                task = self._call(name + ".Task", driver.Task, new_task_name=name)
                self.tasks[i] = task
                self.creation_uncertain = False
                self.uncertain.add(i)
                channel = self._call(name + ".add_co_pulse_chan_ticks",
                    task.co_channels.add_co_pulse_chan_ticks, row["physical_channel"], row["timebase"],
                    idle_state=constants.Level.LOW,
                    initial_delay=row["initial_delay_ticks"], low_ticks=row["low_ticks"],
                    high_ticks=row["high_ticks"])
                self.channels[i] = channel
                self._call(name + ".cfg_dig_edge_start_trig",
                    task.triggers.start_trigger.cfg_dig_edge_start_trig,
                    row["trigger"], trigger_edge=constants.Edge.RISING)
                self._call(name + ".retriggerable", setattr,
                           task.triggers.start_trigger, "retriggerable", True)
                self._call(name + ".co_pulse_idle_state", setattr,
                           channel, "co_pulse_idle_state", constants.Level.LOW)
                self._call(name + ".co_ctr_timebase_active_edge", setattr,
                           channel, "co_ctr_timebase_active_edge", constants.Edge.RISING)
                self._call(name + ".cfg_implicit_timing", task.timing.cfg_implicit_timing,
                    sample_mode=constants.AcquisitionType.FINITE, samps_per_chan=1)
                self._call(name + ".start", task.start)
                self.running.add(i)
                self.uncertain.discard(i)
        except Exception as error:
            raise SupervisionCardError("SuperVision NI6602 initialization failed: " + str(error), self)
        self.initialized = True
        return self.snapshot()

    def snapshot(self):
        return dict(resource_count=self.resource_count, initialized=self.initialized,
            synchronization=synchronization_memory(self.plan, sorted(self.running), sorted(self.uncertain)),
            creation_uncertain=self.creation_uncertain, last_error=self.last_error,
            source_named_counter2_cleanup="NOT_APPLIED_TO_UNOWNED_TASK",
            hardware_acknowledged=False, automatic_restart=False)

    def configure_timing(self, counter, delay_us, width_us, operator_confirmed=False,
                         timeout_seconds=2.0):
        if (operator_confirmed is not True or not self.initialized
                or type(counter) is not int or counter not in self.tasks
                or counter in self.uncertain):
            raise ValueError("Confirmed current known SuperVision counter required")
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not .01 <= timeout_seconds <= 10):
            raise ValueError("Bounded pulse-completion wait required")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
               or v * 20 > 2147483647 for v in (delay_us, width_us)):
            raise ValueError("Positive finite unsaturated timing values required")
        low, high = (int(round(v * 20.0)) for v in (delay_us, width_us))
        if min(low, high) <= 0:
            raise ValueError("Timing must encode positive ticks")
        task, channel = self.tasks[counter], self.channels[counter]
        deadline = self.clock() + timeout_seconds
        while True:
            done = channel.co_pulse_done
            if type(done) is not bool:
                raise TypeError("CO.PulseDone must be Boolean")
            self.wait(.001)
            if done:
                break
            if self.clock() >= deadline:
                raise TimeoutError("SuperVision CO.PulseDone wait exceeded Python deadline; no timing writes")
        self.uncertain.add(counter)
        try:
            self._call("counter.stop", task.stop)
            self.running.discard(counter)
            for name, value in (("co_pulse_ticks_initial_delay", low),
                                ("co_pulse_low_ticks", low), ("co_pulse_high_ticks", high)):
                self._call(name, setattr, channel, name, value)
            self._call("counter.start", task.start)
        except Exception as error:
            raise SupervisionCardError("SuperVision timing update outcome uncertain: " + str(error), self)
        self.running.add(counter)
        self.uncertain.discard(counter)
        self.plan[counter].update(initial_delay_ticks=low, low_ticks=low, high_ticks=high)
        return copy.deepcopy(self.plan[counter])

    def close(self):
        failures = []
        self.initialized = False
        for i, task in list(sorted(self.tasks.items(), reverse=True)):
            try:
                self._call("counter{0}.close".format(i), task.close)
            except Exception as error:
                failures.append(str(error))
            else:
                del self.tasks[i]
                self.channels.pop(i, None)
                self.running.discard(i)
                self.uncertain.discard(i)
        if failures or self.creation_uncertain:
            raise SupervisionCardError("NI6602 cleanup incomplete: " + "; ".join(failures), self)
