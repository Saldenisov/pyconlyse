from __future__ import division

import copy
import datetime
import math
import threading
import time

from .daqmx_backend import AI_TASK_SPECS, DI_TASK_SPECS, BLOCKED_OUTPUT_SPECS
from .errors import CommandError, HardwareWriteBlocked
from .psp_format import PspSupervisionEncoder


SCENARIOS = ("idle", "beam_ready", "fault")

DIGITAL_OUTPUT_COUNTS = {
    "C3_DIO96_DO": 40,
    "C4_DIO96_DO": 32,
    "C5_DIO96_DO": 40,
}

ANALOG_OUTPUT_COUNTS = dict(
    ("C{0}_NI6703_AO".format(device), 10) for device in (6, 7, 8, 9)
)

COUNTER_OUTPUT_COUNT = 8


def _utc_now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _wave(channel_count, phase, offset, amplitude, channel_phase):
    return [
        round(offset + amplitude * math.sin(phase + index * channel_phase), 9)
        for index in range(channel_count)
    ]


class SimulatedBackend(object):
    """Deterministic, thread-safe model of ACQUISITION.vi data flow."""

    def __init__(self):
        self._lock = threading.RLock()
        self._initialized = False
        self._scenario = "idle"
        self._simulated_seconds = 0.0
        self._last_clock = time.monotonic()
        self._sequence = 0
        self._discovery_count = 0
        self._output_revision = 0
        self.supervision = None
        self._psp_encoder = PspSupervisionEncoder()
        self._psp_messages_emitted = 0
        self._digital_outputs = dict(
            (name, [False] * count) for name, count in DIGITAL_OUTPUT_COUNTS.items()
        )
        self._analog_outputs = dict(
            (name, [0.0] * count) for name, count in ANALOG_OUTPUT_COUNTS.items()
        )
        self._counter_outputs = [
            {"delay_seconds": 0.0, "width_seconds": 0.0, "enabled": False}
            for unused in range(COUNTER_OUTPUT_COUNT)
        ]

    def initialize(self):
        with self._lock:
            if not self._initialized:
                self._initialized = True
                self._simulated_seconds = 0.0
                self._last_clock = time.monotonic()
                self._sequence = 0
                self._psp_messages_emitted = 0
            return {
                "initialized": True,
                "mode": "simulation",
                "scenario": self._scenario,
                "hardware_tasks_created": 0,
                "hardware_writes": False,
                "channel_counts": {
                    "C1_NI6071E_AI": 64,
                    "C2_NI6071E_AI": 64,
                    "C11_NI6220_AI": 16,
                    "C3_DIO96_DI": 56,
                    "C4_DIO96_DI": 64,
                    "C5_DIO96_DI": 56,
                    "C3_DIO96_DO": 40,
                    "C4_DIO96_DO": 32,
                    "C5_DIO96_DO": 40,
                    "C6_NI6703_AO": 10,
                    "C7_NI6703_AO": 10,
                    "C8_NI6703_AO": 10,
                    "C9_NI6703_AO": 10,
                    "C10_NI6602_CO": 8,
                },
            }

    def discover(self):
        with self._lock:
            self._discovery_count += 1
            return {
                "driver_version": "SIMULATED",
                "devices": [
                    {"name": str(index), "product_type": product}
                    for index, product in (
                        (1, "PCI-6071E"),
                        (2, "PCI-6071E"),
                        (3, "PCI-DIO-96"),
                        (4, "PCI-DIO-96"),
                        (5, "PCI-DIO-96"),
                        (6, "PCI-6703"),
                        (7, "PCI-6703"),
                        (8, "PCI-6703"),
                        (9, "PCI-6703"),
                        (10, "PCI-6602"),
                        (11, "PCI-6220"),
                    )
                ],
                "read_only": True,
                "tasks_created": 0,
                "discovery_count": self._discovery_count,
            }

    def set_scenario(self, name):
        name = str(name)
        if name not in SCENARIOS:
            raise CommandError("unknown simulation scenario: {0}".format(name))
        with self._lock:
            self._scenario = name
            return {"scenario": self._scenario}

    def assert_procedure_ready(self):
        with self._lock:
            self._require_initialized()
            if self._scenario == "fault":
                raise CommandError("Simulated equipment fault: vacuum/interlock not ready")

    def advance(self, seconds):
        value = float(seconds)
        if not math.isfinite(value) or value < 0.0 or value > 60.0:
            raise CommandError("seconds must be finite and in 0..60")
        with self._lock:
            self._require_initialized()
            self._simulated_seconds += value
            self._last_clock = time.monotonic()
            return self._snapshot_locked()

    def set_simulated_digital_output(self, task, index, value):
        with self._lock:
            self._require_initialized()
            if task not in self._digital_outputs:
                raise CommandError("unknown simulated digital output task: {0}".format(task))
            index = self._validate_index(index, len(self._digital_outputs[task]))
            if not isinstance(value, bool):
                raise CommandError("digital output value must be boolean")
            self._digital_outputs[task][index] = value
            self._output_revision += 1
            return self._output_ack("digital", task, index, value)

    def set_simulated_analog_output(self, task, index, value_volts):
        with self._lock:
            self._require_initialized()
            if task not in self._analog_outputs:
                raise CommandError("unknown simulated analog output task: {0}".format(task))
            index = self._validate_index(index, len(self._analog_outputs[task]))
            if isinstance(value_volts, bool):
                raise CommandError("analog output value_volts must be numeric")
            value_volts = float(value_volts)
            if not math.isfinite(value_volts) or value_volts < -10.0 or value_volts > 10.0:
                raise CommandError("analog output value_volts must be finite and in -10..10")
            self._analog_outputs[task][index] = value_volts
            self._output_revision += 1
            return self._output_ack("analog", task, index, value_volts)

    def set_simulated_counter_output(self, counter, delay_seconds, width_seconds, enabled):
        with self._lock:
            self._require_initialized()
            counter = self._validate_index(counter, COUNTER_OUTPUT_COUNT)
            if isinstance(delay_seconds, bool) or isinstance(width_seconds, bool):
                raise CommandError("counter delay and width must be numeric")
            delay_seconds = float(delay_seconds)
            width_seconds = float(width_seconds)
            if not math.isfinite(delay_seconds) or delay_seconds < 0.0 or delay_seconds > 60.0:
                raise CommandError("counter delay_seconds must be finite and in 0..60")
            if not math.isfinite(width_seconds) or width_seconds < 0.0 or width_seconds > 60.0:
                raise CommandError("counter width_seconds must be finite and in 0..60")
            if not isinstance(enabled, bool):
                raise CommandError("counter enabled must be boolean")
            value = {
                "delay_seconds": delay_seconds,
                "width_seconds": width_seconds,
                "enabled": enabled,
            }
            self._counter_outputs[counter] = value
            self._output_revision += 1
            return self._output_ack("counter", "C10_NI6602_CO", counter, value)

    def reset_simulated_outputs(self):
        with self._lock:
            self._require_initialized()
            for values in self._digital_outputs.values():
                for index in range(len(values)):
                    values[index] = False
            for values in self._analog_outputs.values():
                for index in range(len(values)):
                    values[index] = 0.0
            for index in range(len(self._counter_outputs)):
                self._counter_outputs[index] = {
                    "delay_seconds": 0.0,
                    "width_seconds": 0.0,
                    "enabled": False,
                }
            self._output_revision += 1
            return {
                "simulated": True,
                "hardware_writes": False,
                "output_revision": self._output_revision,
            }

    def get_snapshot(self):
        with self._lock:
            self._require_initialized()
            now = time.monotonic()
            elapsed = max(0.0, now - self._last_clock)
            self._last_clock = now
            self._simulated_seconds += elapsed
            return self._snapshot_locked()

    def get_psp_catalog(self):
        with self._lock:
            return self._psp_encoder.catalog()

    def get_psp_snapshot(self):
        with self._lock:
            self._require_initialized()
            now = time.monotonic()
            elapsed = max(0.0, now - self._last_clock)
            self._last_clock = now
            self._simulated_seconds += elapsed
            snapshot = self._snapshot_locked()
            result = self._psp_encoder.encode(snapshot, time.time())
            self._psp_messages_emitted += result["messages_in_batch"]
            result["messages_received"] = self._psp_messages_emitted
            return result

    def _require_initialized(self):
        if not self._initialized:
            raise CommandError("simulation is not initialized")

    @staticmethod
    def _validate_index(index, count):
        if isinstance(index, bool) or not isinstance(index, int):
            raise CommandError("output index must be an integer")
        if index < 0 or index >= count:
            raise CommandError("output index must be in 0..{0}".format(count - 1))
        return index

    def _output_ack(self, kind, task, index, value):
        return {
            "simulated": True,
            "hardware_writes": False,
            "kind": kind,
            "task": task,
            "index": index,
            "value": copy.deepcopy(value),
            "output_revision": self._output_revision,
        }

    def _snapshot_locked(self):
        self._sequence += 1
        phase = 2.0 * math.pi * (self._simulated_seconds % 10.0) / 10.0
        scenario = self._scenario
        beam_offset = 0.025 if scenario == "beam_ready" else 0.0
        fault_offset = 0.15 if scenario == "fault" else 0.0

        c3 = [False] * 56
        c4 = [False] * 64
        c5 = [False] * 56
        if scenario == "beam_ready":
            for index in (0, 3, 9, 11, 15, 17, 21, 23, 27, 29):
                if index < len(c3):
                    c3[index] = True
            for index in (0, 3, 5, 7, 16):
                c4[index] = True
        if scenario == "fault":
            c5[0] = True
            c5[1] = True

        pressures = {
            "TPG300_1_mbar": 2.0e-7 if scenario != "fault" else 8.0e-4,
            "TPG300_2_mbar": 3.5e-7 if scenario != "fault" else 1.2e-3,
        }
        alarms = []
        if scenario == "fault":
            alarms = ["SIMULATED_VACUUM_FAULT", "SIMULATED_INTERLOCK_OPEN"]

        result = {
            "sequence": self._sequence,
            "timestamp_utc": _utc_now(),
            "simulation_time_seconds": round(self._simulated_seconds, 6),
            "scenario": scenario,
            "acquisition_state": "FAULT" if alarms else "READY",
            "analog_inputs": {
                "C1_NI6071E_AI": _wave(64, phase, beam_offset, 0.01, 0.13),
                "C2_NI6071E_AI": _wave(64, phase, fault_offset, 0.02, 0.09),
                "C11_NI6220_AI": _wave(16, phase, beam_offset, 0.005, 0.17),
            },
            "digital_inputs": {
                "C3_DIO96_DI": c3,
                "C4_DIO96_DI": c4,
                "C5_DIO96_DI": c5,
            },
            "digital_outputs": copy.deepcopy(self._digital_outputs),
            "analog_outputs_volts": copy.deepcopy(self._analog_outputs),
            "counter_outputs": copy.deepcopy(self._counter_outputs),
            "output_revision": self._output_revision,
            "outputs_simulated": True,
            "environment": pressures,
            "alarms": alarms,
            "hardware_tasks_created": 0,
            "hardware_writes": False,
        }
        if self.supervision:
            image = self.supervision.outputs.snapshot()
            # Project exact recovered digital aliases into the legacy telemetry.
            # Analog plan values are native logical values, NOT calibrated volts.
            for target, value in image["digital"].items():
                group, index = target.rsplit(".", 1)
                task = group.replace("_OUT_DIO96", "_DIO96_DO")
                if task in result["digital_outputs"]:
                    result["digital_outputs"][task][int(index)] = value
            for target, state in image["counters"].items():
                if target.startswith("C10_NI6602.ctr"):
                    result["counter_outputs"][int(target.split("ctr")[-1])]["enabled"] = state == "RUNNING"
            result["supervision"] = self.supervision.read_state()
            result["procedure_outputs"] = image
            result["procedure_output_units"] = "LEGACY_LOGICAL_SIMULATION"
        return result

    def describe_legacy_tasks(self):
        return copy.deepcopy(
            {
                "analog_input": list(AI_TASK_SPECS),
                "digital_input": list(DI_TASK_SPECS),
                "blocked_outputs": BLOCKED_OUTPUT_SPECS,
            }
        )

    def write(self, *args, **kwargs):
        raise HardwareWriteBlocked("simulation exposes no hardware mutation command")
