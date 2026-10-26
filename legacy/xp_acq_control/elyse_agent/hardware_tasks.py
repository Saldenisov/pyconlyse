"""Manual, gated NI-DAQmx adapter for the recovered eleven-card topology.

This is NOT the TCP backend. Importing it does nothing to hardware. Task
creation is itself potentially mutating on PCI-DIO-96 (8255 port resets), so
both gates must be passed explicitly by a supervised commissioning caller.
No service configuration or network command can reach this adapter.
"""

from __future__ import division

import time
import math
import importlib
from copy import deepcopy
from .acquisition_driver_diagnostics import describe_driver_exception
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
from .transforms import channel_last_samples, microseconds_to_20mhz_ticks


def prepare_driver_dependencies(observer=None):
    """Load dependencies only; never construct Task or call the NI driver.

    The isolated child calls this on its main thread BEFORE starting a blocking
    stdin reader. NumPy 1.15/Python 3.4 on Windows can otherwise hang loading
    multiarray. Importing this module or opening the GUI remains cold.
    """
    def note(phase, name):
        if observer is not None:
            try:
                observer(dict(phase=phase, call="import " + name,
                              hardware_acknowledged=False))
            except Exception:
                pass
    result = None
    for name in ("numpy", "nidaqmx"):
        note("ENTER", name)
        try:
            result = importlib.import_module(name)
        except Exception:
            note("RAISED", name)
            raise
        note("RETURNED", name)
    return result


def prepare_driver_runtime(observer=None, importer=None):
    """Warm lazy NI library/handle metadata before the child stdin pump.

    Python module import does not load nicaiu or resolve TaskHandle in the
    legacy binding. Task's constructor does both lazily. Version metadata is
    queried here inside confirmed Initialize, but no Task/channel/start/write
    is called. This is not a cold application-startup action.
    """
    if importer is None:
        from nidaqmx._lib import lib_importer
        importer = lib_importer
    def call(label, callback):
        def note(phase):
            if observer is not None:
                try:
                    observer(dict(phase=phase, call=label, hardware_acknowledged=False))
                except Exception:
                    pass
        note("ENTER")
        try:
            value = callback()
        except Exception:
            note("RAISED")
            raise
        note("RETURNED")
        return value
    library = call("load NI nicaiu library (no Task)", lambda: importer.windll)
    handle = call("resolve NI TaskHandle driver-version metadata (no Task)", lambda: importer.task_handle)
    call("resolve DAQmxCreateTask symbol (not invoked)", lambda: library.DAQmxCreateTask)
    return dict(task_handle_type=handle.__name__, tasks_created=0, driver_version_metadata_queried=True)


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
        self.last_counter_operation = None
        self.initialization_observer = None

    def _initialization_call(self, label, function, *args, **kwargs):
        def note(phase):
            if self.initialization_observer is not None:
                try:
                    self.initialization_observer(dict(phase=phase, call=label,
                                                      hardware_acknowledged=False))
                except Exception:
                    pass  # Diagnostics never skip a native call or cleanup.
        note("ENTER")
        try:
            result = function(*args, **kwargs)
        except Exception:
            note("RAISED")
            raise
        note("RETURNED")
        return result

    def get_counter_operation_report(self):
        """Return the latest bounded diagnostic snapshot, without driver I/O."""
        return deepcopy(self.last_counter_operation)

    def _new_counter_operation(self, operation, number, uid, properties=(), ticks=None):
        return {
            "operation": operation, "counter": number, "status": "ATTEMPTING",
            "source_node_uid": uid, "property_codes": list(properties),
            "requested_ticks": ticks, "returned_properties": [],
            "failed_property": None, "unattempted_properties": list(properties),
            "possibly_applied_effect": False, "driver_error": None,
            "pulse_done_observation_may_be_consumed": False,
            "hardware_acknowledged": False, "physical_readback": False,
            "resource_release_requested": False, "automatic_retry": False,
        }

    def _publish_counter_operation(self, report):
        # Published dictionaries are never mutated by the adapter. A reader
        # sees a complete boundary snapshot, even during a later setter call.
        self.last_counter_operation = deepcopy(report)

    def _counter_task_operation(self, number, operation, uid, method):
        task = self._counter_task(number)
        report = self._new_counter_operation(operation, number, uid)
        report["possibly_applied_effect"] = True
        self._publish_counter_operation(report)
        try:
            result = getattr(task, method)()
        except Exception as error:
            report["status"] = "RAISED"
            report["driver_error"] = describe_driver_exception(error)
            self._publish_counter_operation(report)
            raise
        report["status"] = "RETURNED"
        self._publish_counter_operation(report)
        return result

    def _task(self, name):
        if self.closed:
            raise RuntimeError("NI-DAQmx task set is closed")
        return self.tasks[name]

    def start_legacy_counters(self):
        """Starts only counters 0, 1, 2, 5, 6, 7, as LabVIEW does on init."""
        started = []
        for spec in self.plan["counter_output"]:
            if spec["started_on_init"]:
                name = "C10_NI6602_CO_{0}".format(spec["output"])
                self._initialization_call(name + ".start", self._task(name).start)
                started.append(spec["output"])
        return started

    def read_analog_latest(self, name, timeout_seconds=10.0):
        """Last sample per channel from the unchanged configured finite block.

        Read the whole block to preserve existing driver/trigger behavior.
        Do not average, change finite acquisition size, or fall back to a
        previous sample when the block/read is invalid.
        """
        if name not in dict((entry[0], True) for entry in AI_BANKS):
            raise ValueError("unknown analog input bank")
        count = AI_TIMING[name][2]
        if type(count) is not int or count <= 0:
            raise ValueError("Configured finite sample count must be a positive exact integer")
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
        return channel_last_samples(raw, expected_channels=expected, expected_samples=count)

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
            self._initialization_call(name + ".write_startup_image", self.write_digital_bank, name, digital[name])
        for group, _device in AO_BANKS:
            name = "{0}_AO".format(group)
            self._initialization_call(name + ".write_startup_image", self._task(name).write,
                                      list(analog[group]), auto_start=True)
        return {"digital": digital, "analog_volts": analog}

    def _counter_task(self, number):
        if type(number) is not int or number not in range(8):
            raise ValueError("physical NI6602 counter must be in 0..7")
        return self._task("C10_NI6602_CO_{0}".format(number))

    def start_counter(self, number):
        """Explicit start of a retained physical counter task, no new owner."""
        return self._counter_task_operation(number, "start_task", "3032", "start")

    def read_counter_pulse_done(self, number):
        """Read source CO.GénImpTerminée (property 6414), not task completion.

        A retriggerable task can remain active after its current pulse ends.
        Missing channel capability and non-Boolean responses fail closed;
        Task.is_task_done is intentionally never consulted.
        """
        self._counter_task(number)
        report = self._new_counter_operation("read_co_pulse_done", number, "3202", (6414,))
        report["unattempted_properties"] = []
        # The SDK documents a retriggerable query as resetting its Done flag.
        # A failed or ill-typed observation cannot safely be replayed.
        report["pulse_done_observation_may_be_consumed"] = True
        self._publish_counter_operation(report)
        try:
            done = self.counter_channels[number].co_pulse_done
            if type(done) is not bool:
                raise TypeError("NI6602 co_pulse_done must be an exact Boolean")
        except Exception as error:
            report["status"] = "RAISED"
            report["failed_property"] = 6414
            report["driver_error"] = describe_driver_exception(error)
            self._publish_counter_operation(report)
            raise
        report["status"] = "RETURNED"
        report["returned_properties"] = [6414]
        self._publish_counter_operation(report)
        return done

    def stop_counter(self, number):
        """Stop a retained counter task; a failure never removes its handle."""
        return self._counter_task_operation(number, "stop_task", "2976", "stop")

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
        report = self._new_counter_operation(
            "write_co_timing_properties", number, "3083", (664, 4465, 4457),
            {"initial_delay_ticks": initial_delay_ticks,
             "low_ticks": low_ticks, "high_ticks": high_ticks},
        )
        properties = ((664, "co_pulse_ticks_initial_delay", initial_delay_ticks),
                      (4465, "co_pulse_low_ticks", low_ticks),
                      (4457, "co_pulse_high_ticks", high_ticks))
        for index, (code, name, value) in enumerate(properties):
            report["unattempted_properties"] = [item[0] for item in properties[index + 1:]]
            report["possibly_applied_effect"] = True
            self._publish_counter_operation(report)
            try:
                setattr(channel, name, value)
            except Exception as error:
                report["status"] = "RAISED"
                report["failed_property"] = code
                report["driver_error"] = describe_driver_exception(error)
                self._publish_counter_operation(report)
                raise
            # This prefix records only setters returning without exception;
            # it is neither physical readback nor proof of applied outputs.
            report["returned_properties"].append(code)
            self._publish_counter_operation(report)
        report["status"] = "RETURNED"
        self._publish_counter_operation(report)
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


def create_legacy_card_tasks(authorized=False, outputs_commissioned=False, daqmx=None,
                             selected_devices=None, observer=None):
    """Configure all 11 cards, but neither start counters nor write outputs.

    Task creation may reconfigure PCI-DIO-96 directions and cause transients.
    Never call while LabVIEW owns cards or without independent safe-state proof.
    """
    if authorized is not True or outputs_commissioned is not True:
        raise HardwareWriteBlocked(
            "eleven-card task creation requires supervised commissioning; "
            "DIO-96 task creation can change output pin states"
        )
    if selected_devices is not None and (type(selected_devices) is not tuple
            or not selected_devices or any(type(item) is not int or item not in range(1, 12)
                                          for item in selected_devices)
            or len(set(selected_devices)) != len(selected_devices)):
        raise ValueError("Explicit unique card numbers 1..11 required")
    if observer is not None and not callable(observer):
        raise TypeError("Initialization boundary observer must be callable")
    selected = set(range(1, 12) if selected_devices is None else selected_devices)

    def note(phase, label):
        if observer is not None:
            try:
                observer(dict(phase=phase, call=label, hardware_acknowledged=False))
            except Exception:
                # Never lose a just-created handle, mask a native exception,
                # or skip cleanup because diagnostics failed. The supervised
                # probe separately refuses the next card on storage failure.
                pass

    def call(label, function, *args, **kwargs):
        note("ENTER", label)
        try:
            result = function(*args, **kwargs)
        except Exception:
            note("RAISED", label)
            raise
        note("RETURNED", label)
        return result

    plan = card_initialization_plan()
    plan["device_numbers"] = tuple(sorted(selected))
    if 10 not in selected:
        plan["counter_output"] = []
    if daqmx is None:
        note("ENTER", "import nidaqmx")
        import nidaqmx as daqmx
        note("RETURNED", "import nidaqmx")
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
            task = call(name + ".Task", daqmx.Task, new_task_name=name)
            tasks[name] = task
            channel = call(name + ".add_co_pulse_chan_ticks", task.co_channels.add_co_pulse_chan_ticks,
                spec["physical_channel"], spec["timebase"],
                idle_state=Level.LOW,
                initial_delay=spec["initial_delay_ticks"],
                low_ticks=spec["low_ticks"], high_ticks=spec["high_ticks"],
            )
            counter_channels[number] = channel
            call(name + ".co_ctr_timebase_active_edge", setattr, channel, "co_ctr_timebase_active_edge", Edge.RISING)
            call(name + ".cfg_dig_edge_start_trig", task.triggers.start_trigger.cfg_dig_edge_start_trig,
                spec["trigger"],
                trigger_edge=Edge.RISING if spec["trigger_edge"] == "rising" else Edge.FALLING,
            )
            call(name + ".retriggerable", setattr, task.triggers.start_trigger, "retriggerable", True)
            call(name + ".cfg_implicit_timing", task.timing.cfg_implicit_timing,
                sample_mode=AcquisitionType.FINITE, samps_per_chan=1
            )

        for name, device, _count in AI_BANKS[:2]:
            if device not in selected:
                continue
            task = call(name + ".Task", daqmx.Task, new_task_name=name)
            tasks[name] = task
            for physical, minimum, maximum in AI_CHANNEL_GROUPS[name]:
                call(name + ".add_ai_voltage_chan:" + physical, task.ai_channels.add_ai_voltage_chan,
                    physical, terminal_config=TerminalConfiguration.RSE,
                    min_val=minimum, max_val=maximum,
                )
            trigger, rate, samples = AI_TIMING[name]
            call(name + ".cfg_samp_clk_timing", task.timing.cfg_samp_clk_timing,
                rate, source="OnboardClock", active_edge=Edge.RISING,
                sample_mode=AcquisitionType.FINITE, samps_per_chan=samples,
            )
            call(name + ".cfg_dig_edge_start_trig", task.triggers.start_trigger.cfg_dig_edge_start_trig,
                 trigger, trigger_edge=Edge.RISING)
            # Original NI6071E initializer property codes 6410/6182:
            # 0x28B9 == CURRENT_READ_POSITION, Read.AutoStart == True.
            # No equivalent C11 property assignment is inferred here.
            call(name + ".read_relative_to", setattr, task.in_stream, "relative_to", ReadRelativeTo.CURRENT_READ_POSITION)
            call(name + ".read_auto_start", setattr, task.in_stream, "auto_start", True)

        for name, device, first, last, _size in DI_BANKS + DO_BANKS:
            if device not in selected:
                continue
            task = call(name + ".Task", daqmx.Task, new_task_name=name)
            tasks[name] = task
            lines = _physical_lines(device, first, last)
            collection = task.di_channels if name.endswith("_DI") else task.do_channels
            method = collection.add_di_chan if name.endswith("_DI") else collection.add_do_chan
            call(name + ".add_digital_channels", method, lines, line_grouping=LineGrouping.CHAN_PER_LINE)

        for group, device in AO_BANKS:
            if device not in selected:
                continue
            name = "{0}_AO".format(group)
            task = call(name + ".Task", daqmx.Task, new_task_name=name)
            tasks[name] = task
            for index in range(10):
                call(name + ".add_ao_voltage_chan:" + str(index), task.ao_channels.add_ao_voltage_chan,
                    "/{0}/ao{1}".format(device, index), min_val=-10.0, max_val=10.0
                )

        if 11 in selected:
            name = "C11_NI6220_AI"
            task = call(name + ".Task", daqmx.Task, new_task_name=name)
            tasks[name] = task
            for physical, minimum, maximum in AI_CHANNEL_GROUPS[name]:
                call(name + ".add_ai_voltage_chan:" + physical, task.ai_channels.add_ai_voltage_chan,
                    physical, terminal_config=TerminalConfiguration.RSE,
                    min_val=minimum, max_val=maximum,
                )
            trigger, rate, samples = AI_TIMING[name]
            call(name + ".cfg_samp_clk_timing", task.timing.cfg_samp_clk_timing,
                rate, source="OnboardClock", active_edge=Edge.RISING,
                sample_mode=AcquisitionType.FINITE, samps_per_chan=samples,
            )
            call(name + ".cfg_dig_edge_start_trig", task.triggers.start_trigger.cfg_dig_edge_start_trig,
                 trigger, trigger_edge=Edge.RISING)
        owner = LegacyCardTasks(daqmx, plan, tasks, counter_channels)
        owner.initialization_observer = observer
        return owner
    except Exception as cause:
        for name, task in reversed(list(tasks.items())):
            try:
                call(name + ".close_after_failure", task.close)
            except Exception:
                pass
            else:
                del tasks[name]
        if tasks:
            raise PartialTaskCreationError(
                cause, LegacyCardTasks(daqmx, plan, tasks, counter_channels)
            )
        raise
