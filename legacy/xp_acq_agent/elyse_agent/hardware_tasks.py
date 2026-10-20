"""Manual, gated NI-DAQmx adapter for the recovered eleven-card topology.

This is NOT the TCP backend. Importing it does nothing to hardware. Task
creation is itself potentially mutating on PCI-DIO-96 (8255 port resets), so
both gates must be passed explicitly by a supervised commissioning caller.
No service configuration or network command can reach this adapter.
"""

from __future__ import division

import time
import math

from .errors import HardwareWriteBlocked
from .hardware_plan import (
    AI_BANKS,
    AO_BANKS,
    DI_BANKS,
    DO_BANKS,
    analog_startup_voltage_image,
    card_initialization_plan,
    digital_startup_image,
    load_ao_calibration,
    logical_ao_to_volts,
)
from .input_tasks import AI_CHANNEL_GROUPS, AI_TIMING
from .transforms import channel_means, microseconds_to_20mhz_ticks


class TaskCleanupError(RuntimeError):
    def __init__(self, failures):
        self.failures = failures
        RuntimeError.__init__(self, "; ".join("{0}: {1}".format(name, error)
                                             for name, error in failures))


class PartialTaskCreationError(RuntimeError):
    def __init__(self, cause, owner):
        self.owner = owner
        RuntimeError.__init__(self, "Task creation failed: {0}; cleanup incomplete".format(cause))


def _physical_lines(device, first_port, last_port):
    return ",".join(
        "/{0}/port{1}/line0:7".format(device, port)
        for port in range(first_port, last_port + 1)
    )


class LegacyCardTasks(object):
    """Task owner; explicit method calls are the only write/start paths."""

    def __init__(self, daqmx, plan, tasks, counter_channels, sleep=None):
        self.daqmx = daqmx
        self.plan = plan
        self.tasks = tasks
        self.counter_channels = counter_channels
        self.sleep = sleep or time.sleep
        self.calibration = load_ao_calibration()
        self.closed = False

    def _task(self, name):
        if self.closed:
            raise RuntimeError("NI-DAQmx task set is closed")
        return self.tasks[name]

    def start_legacy_counters(self):
        """Starts only counters 0, 1, 2, 5, 6, 7, as LabVIEW does on init."""
        started = []
        for spec in self.plan["counter_output"]:
            if spec["started_on_init"]:
                self._task("C10_NI6602_CO_{0}".format(spec["output"])).start()
                started.append(spec["output"])
        return started

    def read_analog_means(self, name, samples_per_channel=10, timeout_seconds=10.0):
        if name not in dict((entry[0], True) for entry in AI_BANKS):
            raise ValueError("unknown analog input bank")
        count = samples_per_channel
        if type(count) is not int or not 0 < count <= AI_TIMING[name][2]:
            raise ValueError("samples_per_channel requires a positive exact integer within configured finite samples")
        if type(timeout_seconds) not in (int, float):
            raise ValueError("timeout_seconds requires a finite positive number")
        try:
            timeout = float(timeout_seconds)
        except (OverflowError, ValueError):
            raise ValueError("timeout_seconds requires a finite positive number")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds requires a finite positive number")
        raw = self._task(name).read(number_of_samples_per_channel=count,
                                    timeout=timeout)
        expected = dict((entry[0], entry[2]) for entry in AI_BANKS)[name]
        return channel_means(raw, expected_channels=expected, expected_samples=count)

    def read_digital_bank(self, name):
        if name not in dict((entry[0], True) for entry in DI_BANKS):
            raise ValueError("unknown digital input bank")
        return self._task(name).read()

    def write_digital_bank(self, name, values):
        """Write one complete bank; partial line writes are intentionally absent."""
        sizes = dict((entry[0], entry[4]) for entry in DO_BANKS)
        if name not in sizes:
            raise ValueError("unknown digital output bank")
        vector = list(values)
        if len(vector) != sizes[name] or any(type(value) is not bool for value in vector):
            raise ValueError("digital output requires a complete Boolean bank")
        return self._task(name).write(vector, auto_start=True)

    def write_analog_logical_bank(self, group, logical_values):
        """Convert LabVIEW logical commands, then write ten AO volts."""
        names = dict((entry[0], True) for entry in AO_BANKS)
        if group not in names:
            raise ValueError("unknown analog output bank")
        values = list(logical_values)
        if len(values) != 10:
            raise ValueError("analog output requires a complete ten-channel bank")
        volts = [logical_ao_to_volts(group, index, value, self.calibration)
                 for index, value in enumerate(values)]
        task_name = "{0}_AO".format(group)
        self._task(task_name).write(volts, auto_start=True)
        return tuple(volts)

    def write_initial_images(self):
        """Explicitly apply recovered startup outputs; NEVER called by setup."""
        digital = digital_startup_image()
        analog = analog_startup_voltage_image()
        for name, _device, _first, _last, _size in DO_BANKS:
            self.write_digital_bank(name, digital[name])
        for group, _device in AO_BANKS:
            self._task("{0}_AO".format(group)).write(list(analog[group]), auto_start=True)
        return {"digital": digital, "analog_volts": analog}

    def _counter_task(self, number):
        if type(number) is not int or number not in range(8):
            raise ValueError("physical NI6602 counter must be in 0..7")
        return self._task("C10_NI6602_CO_{0}".format(number))

    def start_counter(self, number):
        """Explicit start of a retained physical counter task, no new owner."""
        return self._counter_task(number).start()

    def read_counter_pulse_done(self, number):
        """Read source CO.GénImpTerminée (property 6414), not task completion.

        A retriggerable task can remain active after its current pulse ends.
        Missing channel capability and non-Boolean responses fail closed;
        Task.is_task_done is intentionally never consulted.
        """
        self._counter_task(number)
        done = self.counter_channels[number].co_pulse_done
        if type(done) is not bool:
            raise TypeError("NI6602 co_pulse_done must be an exact Boolean")
        return done

    def stop_counter(self, number):
        """Stop a retained counter task; a failure never removes its handle."""
        return self._counter_task(number).stop()

    def write_counter_ticks(self, number, initial_delay_ticks, low_ticks, high_ticks):
        """Apply source NI6602 properties in order, without task lifecycle work.

        All arguments are validated before the first property write. Zero is a
        valid U32 source representation, not a claim that the driver accepts it.
        A property failure may leave earlier properties applied; the exception
        propagates while this owner retains every task and channel handle.
        """
        if type(number) is not int or number not in range(8):
            raise ValueError("physical NI6602 counter must be in 0..7")
        ticks = (initial_delay_ticks, low_ticks, high_ticks)
        if any(type(value) is not int or not 0 <= value <= 0xffffffff
               for value in ticks):
            raise ValueError("NI6602 ticks require exact U32 integers")
        self._counter_task(number)
        channel = self.counter_channels[number]
        channel.co_pulse_ticks_initial_delay = initial_delay_ticks
        channel.co_pulse_low_ticks = low_ticks
        channel.co_pulse_high_ticks = high_ticks
        return {"counter": number, "initial_delay_ticks": initial_delay_ticks,
                "low_ticks": low_ticks, "high_ticks": high_ticks}

    def update_counter_microseconds(self, number, delay_us, width_us):
        """Manual policy for 1_ACQ_WRITE_NI6602.vi's three properties.

        Saved-VI parent mapping pairs commands 1..16 onto physical ctr0..7;
        this manual method accepts the physical zero-based counter directly.
        Pulse-done property matches source 6414. Conversion and 22-attempt
        polling remain manual policy, not established source timing parity.
        """
        task = self._counter_task(number)
        low_and_initial = microseconds_to_20mhz_ticks(delay_us)
        high = microseconds_to_20mhz_ticks(width_us)
        if low_and_initial <= 0 or high <= 0:
            raise ValueError("counter low/high time must be positive")
        for _attempt in range(22):
            if self.read_counter_pulse_done(number):
                break
            self.sleep(0.001)
        task.stop()
        channel = self.counter_channels[number]
        channel.co_pulse_ticks_initial_delay = low_and_initial
        channel.co_pulse_low_ticks = low_and_initial
        channel.co_pulse_high_ticks = high
        task.start()
        return {"counter": number, "initial_delay_ticks": low_and_initial,
                "low_ticks": low_and_initial, "high_ticks": high}

    def close(self):
        if self.closed:
            return
        failures = []
        for name, task in reversed(list(self.tasks.items())):
            try:
                task.close()
            except Exception as error:
                failures.append((name, error))
            else:
                del self.tasks[name]
        self.closed = not self.tasks
        if failures:
            raise TaskCleanupError(failures)


def create_legacy_card_tasks(authorized=False, outputs_commissioned=False, daqmx=None):
    """Configure all 11 cards, but neither start counters nor write outputs.

    Task creation may reconfigure PCI-DIO-96 directions and cause transients.
    Never call while LabVIEW owns cards or without independent safe-state proof.
    """
    if authorized is not True or outputs_commissioned is not True:
        raise HardwareWriteBlocked(
            "eleven-card task creation requires supervised commissioning; "
            "DIO-96 task creation can change output pin states"
        )
    plan = card_initialization_plan()
    if daqmx is None:
        import nidaqmx as daqmx
    from nidaqmx.constants import (
        AcquisitionType, Edge, Level, LineGrouping, ReadRelativeTo,
        TerminalConfiguration,
    )

    tasks = {}
    counter_channels = {}
    try:
        for spec in plan["counter_output"]:
            number = spec["output"]
            name = "C10_NI6602_CO_{0}".format(number)
            task = daqmx.Task(new_task_name=name)
            tasks[name] = task
            channel = task.co_channels.add_co_pulse_chan_ticks(
                spec["physical_channel"], spec["timebase"],
                idle_state=Level.LOW,
                initial_delay=spec["initial_delay_ticks"],
                low_ticks=spec["low_ticks"], high_ticks=spec["high_ticks"],
            )
            counter_channels[number] = channel
            channel.co_ctr_timebase_active_edge = Edge.RISING
            task.triggers.start_trigger.cfg_dig_edge_start_trig(
                spec["trigger"],
                trigger_edge=Edge.RISING if spec["trigger_edge"] == "rising" else Edge.FALLING,
            )
            task.triggers.start_trigger.retriggerable = True
            task.timing.cfg_implicit_timing(
                sample_mode=AcquisitionType.FINITE, samps_per_chan=1
            )

        for name, device, _count in AI_BANKS[:2]:
            task = daqmx.Task(new_task_name=name)
            tasks[name] = task
            for physical, minimum, maximum in AI_CHANNEL_GROUPS[name]:
                task.ai_channels.add_ai_voltage_chan(
                    physical, terminal_config=TerminalConfiguration.RSE,
                    min_val=minimum, max_val=maximum,
                )
            trigger, rate, samples = AI_TIMING[name]
            task.timing.cfg_samp_clk_timing(
                rate, source="OnboardClock", active_edge=Edge.RISING,
                sample_mode=AcquisitionType.FINITE, samps_per_chan=samples,
            )
            task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger, trigger_edge=Edge.RISING)
            # Original NI6071E initializer property codes 6410/6182:
            # 0x28B9 == CURRENT_READ_POSITION, Read.AutoStart == True.
            # No equivalent C11 property assignment is inferred here.
            task.in_stream.relative_to = ReadRelativeTo.CURRENT_READ_POSITION
            task.in_stream.auto_start = True

        for name, device, first, last, _size in DI_BANKS + DO_BANKS:
            task = daqmx.Task(new_task_name=name)
            tasks[name] = task
            lines = _physical_lines(device, first, last)
            collection = task.di_channels if name.endswith("_DI") else task.do_channels
            method = collection.add_di_chan if name.endswith("_DI") else collection.add_do_chan
            method(lines, line_grouping=LineGrouping.CHAN_PER_LINE)

        for group, device in AO_BANKS:
            name = "{0}_AO".format(group)
            task = daqmx.Task(new_task_name=name)
            tasks[name] = task
            for index in range(10):
                task.ao_channels.add_ao_voltage_chan(
                    "/{0}/ao{1}".format(device, index), min_val=-10.0, max_val=10.0
                )

        name = "C11_NI6220_AI"
        task = daqmx.Task(new_task_name=name)
        tasks[name] = task
        for physical, minimum, maximum in AI_CHANNEL_GROUPS[name]:
            task.ai_channels.add_ai_voltage_chan(
                physical, terminal_config=TerminalConfiguration.RSE,
                min_val=minimum, max_val=maximum,
            )
        trigger, rate, samples = AI_TIMING[name]
        task.timing.cfg_samp_clk_timing(
            rate, source="OnboardClock", active_edge=Edge.RISING,
            sample_mode=AcquisitionType.FINITE, samps_per_chan=samples,
        )
        task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger, trigger_edge=Edge.RISING)
        return LegacyCardTasks(daqmx, plan, tasks, counter_channels)
    except Exception as cause:
        for name, task in reversed(list(tasks.items())):
            try:
                task.close()
            except Exception:
                pass
            else:
                del tasks[name]
        if tasks:
            raise PartialTaskCreationError(
                cause, LegacyCardTasks(daqmx, plan, tasks, counter_channels)
            )
        raise
