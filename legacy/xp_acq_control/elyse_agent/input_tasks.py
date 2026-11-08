"""Recovered AI/DI initialization, kept behind an explicit resource gate.

Creating even an input task can reserve NI-DAQmx resources. Nothing in the
network service calls this module. Native LabVIEW AI-Voltage diagrams wire
terminal configuration 10083 (RSE) for cards 1, 2, and 11. Earlier Python
diagnostics deliberately used a DIFFERENTIAL/RSE split; that was a probe,
not the LabVIEW acquisition configuration.
"""

from __future__ import print_function

from .errors import AgentError
from .transforms import channel_means


class InputTaskCreationBlocked(AgentError):
    code = "input_task_creation_blocked"


AI_CHANNEL_GROUPS = {
    "C1_NI6071E_AI": (
        ("/1/ai0:1", -10.0, 10.0),
        ("/1/ai2", -0.05, 0.05),
        ("/1/ai3:4", -1.0, 1.0),
        ("/1/ai5:63", -10.0, 10.0),
    ),
    "C2_NI6071E_AI": (("/2/ai0:63", -10.0, 10.0),),
    "C11_NI6220_AI": (
        ("/11/ai0:3", -0.2, 0.2),
        ("/11/ai4:7", -10.0, 10.0),
        ("/11/ai8:15", -0.2, 0.2),
    ),
}


AI_TIMING = {
    "C1_NI6071E_AI": ("/1/PFI0", 5000.0, 10),
    "C2_NI6071E_AI": ("/2/PFI0", 5000.0, 10),
    "C11_NI6220_AI": ("/11/PFI0", 5000.0, 10),
}


DI_PORTS = {
    "C3_DIO96_DI": (3, 7),
    "C4_DIO96_DI": (4, 8),
    "C5_DIO96_DI": (5, 7),
}


class InputTaskSet(object):
    def __init__(self, tasks):
        self.tasks = dict(tasks)

    def close(self):
        first_error = None
        for task in self.tasks.values():
            try:
                task.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
        self.tasks = {}
        if first_error is not None:
            raise first_error

    def read_analog_means(self, task_name, timeout_seconds=10.0):
        task = self.tasks[task_name]
        sample_count = AI_TIMING[task_name][2]
        samples = task.read(
            number_of_samples_per_channel=sample_count,
            timeout=float(timeout_seconds),
        )
        expected_channels = 16 if task_name == "C11_NI6220_AI" else 64
        return channel_means(samples, expected_channels, sample_count)


def create_legacy_input_tasks(authorized=False):
    if authorized is not True:
        raise InputTaskCreationBlocked(
            "input task creation is disabled because it may reserve hardware used by LabVIEW"
        )

    import nidaqmx
    from nidaqmx.constants import AcquisitionType, LineGrouping, TerminalConfiguration

    tasks = {}
    try:
        for task_name in sorted(AI_CHANNEL_GROUPS):
            task = nidaqmx.Task(new_task_name=task_name)
            tasks[task_name] = task
            for physical_channels, minimum, maximum in AI_CHANNEL_GROUPS[task_name]:
                task.ai_channels.add_ai_voltage_chan(
                    physical_channels,
                    terminal_config=TerminalConfiguration.RSE,
                    min_val=minimum,
                    max_val=maximum,
                )
            trigger, rate, samples = AI_TIMING[task_name]
            task.timing.cfg_samp_clk_timing(
                rate,
                sample_mode=AcquisitionType.FINITE,
                samps_per_chan=samples,
            )
            task.triggers.start_trigger.cfg_dig_edge_start_trig(trigger)

        for task_name in sorted(DI_PORTS):
            device, port_count = DI_PORTS[task_name]
            task = nidaqmx.Task(new_task_name=task_name)
            tasks[task_name] = task
            for port in range(port_count):
                task.di_channels.add_di_chan(
                    "/{0}/port{1}/line0:7".format(device, port),
                    line_grouping=LineGrouping.CHAN_PER_LINE,
                )
        return InputTaskSet(tasks)
    except Exception:
        for task in tasks.values():
            try:
                task.close()
            except Exception:
                pass
        raise
