from __future__ import print_function

from .errors import HardwareWriteBlocked


AI_TASK_SPECS = (
    {
        "name": "C1_NI6071E_AI",
        "physical_channels": "/1/ai0:63",
        "trigger": "/1/PFI0",
        "recovery_trigger": "/1/20MHzTimebase",
        "rate_hz": 5000.0,
        "samples_per_channel": 10,
        "terminal_configuration": "RSE",
        "ranges": {"2": [-0.05, 0.05], "3:4": [-1.0, 1.0], "default": [-10.0, 10.0]},
    },
    {
        "name": "C2_NI6071E_AI",
        "physical_channels": "/2/ai0:63",
        "trigger": "/2/PFI0",
        "recovery_trigger": "/2/20MHzTimebase",
        "rate_hz": 5000.0,
        "samples_per_channel": 10,
        "terminal_configuration": "RSE",
        "ranges": {"default": [-10.0, 10.0]},
    },
    {
        "name": "C11_NI6220_AI",
        "physical_channels": "/11/ai0:15",
        "trigger": "/11/PFI0",
        "rate_hz": 5000.0,
        "samples_per_channel": 10,
        "terminal_configuration": "RSE",
        "ranges": {"0:3": [-0.2, 0.2], "4:7": [-10.0, 10.0], "8:15": [-0.2, 0.2]},
    },
)


DI_TASK_SPECS = (
    {"name": "C3_DIO96_DI", "physical_channels": "/3/port0:6", "line_count": 56},
    {"name": "C4_DIO96_DI", "physical_channels": "/4/port0:7", "line_count": 64},
    {"name": "C5_DIO96_DI", "physical_channels": "/5/port0:6", "line_count": 56},
)


BLOCKED_OUTPUT_SPECS = {
    "digital": (
        {"name": "C3_DIO96_DO", "physical_channels": "/3/port7:11", "line_count": 40},
        {"name": "C4_DIO96_DO", "physical_channels": "/4/port8:11", "line_count": 32},
        {"name": "C5_DIO96_DO", "physical_channels": "/5/port7:11", "line_count": 40},
    ),
    "analog": tuple(
        {"name": "C{0}_NI6703_AO".format(device), "physical_channels": "/{0}/ao0:9".format(device), "range_v": [-10.0, 10.0]}
        for device in (6, 7, 8, 9)
    ),
    "counter": {
        "physical_channels": "/10/ctr0:7",
        "timebase": "/10/PFI11",
        "retriggerable": True,
        "idle_state": "LOW",
    },
}


def _channel_names(collection):
    return [channel.name for channel in collection]


class DaqmxBackend(object):
    """NI-DAQmx inventory access. This release never creates output tasks."""

    def __init__(self, allow_hardware_writes=False):
        if allow_hardware_writes:
            raise HardwareWriteBlocked("hardware writes are not commissioned")
        self._last_discovery = None

    def initialize(self):
        self._last_discovery = self.discover()
        return {
            "initialized": True,
            "mode": "discover_only",
            "hardware_tasks_created": 0,
            "hardware_writes": False,
            "discovery": self._last_discovery,
        }

    def discover(self):
        from nidaqmx.system import System

        system = System.local()
        version = system.driver_version
        devices = []
        for device in system.devices:
            devices.append(
                {
                    "name": device.name,
                    "product_type": device.product_type,
                    "ai": _channel_names(device.ai_physical_chans),
                    "ao": _channel_names(device.ao_physical_chans),
                    "di": _channel_names(device.di_lines),
                    "do": _channel_names(device.do_lines),
                    "ci": _channel_names(device.ci_physical_chans),
                    "co": _channel_names(device.co_physical_chans),
                }
            )
        result = {
            "driver_version": "{0}.{1}.{2}".format(
                version.major_version, version.minor_version, version.update_version
            ),
            "devices": devices,
            "read_only": True,
            "tasks_created": 0,
        }
        self._last_discovery = result
        return result

    def get_snapshot(self):
        return {
            "acquisition_state": "DISCOVERY_ONLY",
            "last_discovery": self._last_discovery,
            "hardware_tasks_created": 0,
            "hardware_writes": False,
        }

    def set_scenario(self, name):
        raise HardwareWriteBlocked("simulation scenarios are unavailable in discover_only mode")

    def advance(self, seconds):
        raise HardwareWriteBlocked("simulation clock is unavailable in discover_only mode")

    def set_simulated_digital_output(self, task, index, value):
        raise HardwareWriteBlocked("simulated outputs are unavailable in discover_only mode")

    def set_simulated_analog_output(self, task, index, value_volts):
        raise HardwareWriteBlocked("simulated outputs are unavailable in discover_only mode")

    def set_simulated_counter_output(self, counter, delay_seconds, width_seconds, enabled):
        raise HardwareWriteBlocked("simulated outputs are unavailable in discover_only mode")

    def reset_simulated_outputs(self):
        raise HardwareWriteBlocked("simulated outputs are unavailable in discover_only mode")

    def describe_legacy_tasks(self):
        return {
            "analog_input": list(AI_TASK_SPECS),
            "digital_input": list(DI_TASK_SPECS),
            "blocked_outputs": BLOCKED_OUTPUT_SPECS,
        }

    def write(self, *args, **kwargs):
        raise HardwareWriteBlocked(
            "all DAQmx writes are blocked pending polarity, safe-state, wiring, and interlock commissioning"
        )
