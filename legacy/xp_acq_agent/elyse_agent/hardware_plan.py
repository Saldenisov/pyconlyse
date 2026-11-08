"""Inert, Python 3.4-compatible reconstruction of ACQUISITION card setup.

This module imports no NI driver and never creates a task. Values are the
controller requests visible in the native LabVIEW VIs, not measurements of
electrical output. A plan is deliberately separate from executing it.
"""

from __future__ import division

import csv
import io
import math
import os

from .transforms import attenuator_voltage, dephaser_voltage, linear_calibration


AI_BANKS = (
    ("C1_NI6071E_AI", 1, 64),
    ("C2_NI6071E_AI", 2, 64),
    ("C11_NI6220_AI", 11, 16),
)

DI_BANKS = (
    ("C3_DIO96_DI", 3, 0, 6, 56),
    ("C4_DIO96_DI", 4, 0, 7, 64),
    ("C5_DIO96_DI", 5, 0, 6, 56),
)

DO_BANKS = (
    ("C3_DIO96_DO", 3, 7, 11, 40),
    ("C4_DIO96_DO", 4, 8, 11, 32),
    ("C5_DIO96_DO", 5, 7, 11, 40),
)

AO_BANKS = (
    ("C6NI6703", 6),
    ("C7NI6703", 7),
    ("C8NI6703", 8),
    ("C9NI6703", 9),
)

# Root VI initialization sequence frame 5 / subframe 0. These are logical
# values before 1_ACQ_WRITE_NI6703.vi converts them to AO volts.
STARTUP_AO_LOGICAL = {
    "C6NI6703": (0.0,) * 10,
    "C7NI6703": (0.0,) * 10,
    "C8NI6703": (0.0, 21.0, 27.9, 0.0, 0.0, 0.0, 360.0, 0.0, 0.0, 0.0),
    "C9NI6703": (6.5, 0.0, 4.755, 4.755, 2.126, 2.126, 2.126, 0.0, 0.0, 0.0),
}

# Saved root-VI Boolean constants traced to target banks by local-reference
# wires. The literal C3/C5 captions are swapped in the VI; see
# docs/ELYSE_ACQ_STARTUP_COMMAND_VECTOR_AUDIT_2026-09-29.md. Electrical
# polarity and physical transient behavior remain unverified.
STARTUP_DO_TRUE_BITS = {
    "C3_DIO96_DO": (1, 4),
    "C4_DIO96_DO": (1, 4, 6, 8, 17, 19),
    "C5_DIO96_DO": (33,),
}

COUNTERS_STARTED_ON_INIT = (0, 1, 2, 5, 6, 7)


def _data_path(filename, data_path=None):
    if data_path is None:
        data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    return os.path.join(data_path, filename)


def digital_startup_image():
    image = {}
    for name, _device, _first, _last, size in DO_BANKS:
        values = [False] * size
        for index in STARTUP_DO_TRUE_BITS[name]:
            if index < 0 or index >= size:
                raise ValueError("invalid startup DO bit: {0}[{1}]".format(name, index))
            values[index] = True
        image[name] = tuple(values)
    return image


def analog_startup_logical_image():
    return dict((name, tuple(STARTUP_AO_LOGICAL[name])) for name, _device in AO_BANKS)


def load_ao_calibration(data_path=None):
    """Return physical-order calibration rows; reject incomplete parser data."""
    rows = {}
    with io.open(_data_path("calibration_map.csv", data_path), "r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            group = row["group"]
            if group not in STARTUP_AO_LOGICAL:
                continue
            index = int(row["index"])
            device = int(group[1])
            key = (group, index)
            if key in rows or index not in range(10):
                raise ValueError("duplicate or invalid AO calibration index: {0}".format(key))
            expected_physical = "/{0}/ao{1}".format(device, index)
            if row["physical_channel"] != expected_physical:
                raise ValueError("AO physical-channel mismatch: {0}".format(key))
            rows[key] = {
                "physical_channel": expected_physical,
                "scale": float(row["scale"]),
                "offset": float(row["offset"]),
            }
    expected = set((name, index) for name, _device in AO_BANKS for index in range(10))
    if set(rows) != expected:
        raise ValueError("AO calibration table must cover all 40 physical channels")
    return rows


def logical_ao_to_volts(group, index, logical_value, calibration=None):
    """Apply the active NI6703 custom-VI conversion, then check DAQ bounds."""
    if calibration is None:
        calibration = load_ao_calibration()
    key = (group, int(index))
    if key not in calibration:
        raise ValueError("unknown AO channel: {0}".format(key))
    value = float(logical_value)
    if not math.isfinite(value):
        raise ValueError("AO logical value must be finite")
    if key == ("C8NI6703", 3):
        volts = dephaser_voltage(value)
    elif key == ("C8NI6703", 4):
        volts = attenuator_voltage(value)
    else:
        row = calibration[key]
        volts = linear_calibration(value, row["scale"], row["offset"])
    if not math.isfinite(volts) or not -10.0 <= volts <= 10.0:
        raise ValueError("AO request outside NI6703 ±10 V: {0}[{1}]".format(group, index))
    return volts


def analog_startup_voltage_image(data_path=None):
    calibration = load_ao_calibration(data_path)
    return dict(
        (group, tuple(logical_ao_to_volts(group, index, value, calibration)
                      for index, value in enumerate(STARTUP_AO_LOGICAL[group])))
        for group, _device in AO_BANKS
    )


def load_counter_timing(data_path=None):
    """Read corrected eight-counter plan; initial delay is zero, not low time."""
    result = []
    with io.open(_data_path("ni6602_timing.csv", data_path), "r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            output = int(row["output"])
            if output not in range(8):
                raise ValueError("invalid NI6602 output number")
            item = {
                "output": output,
                "physical_channel": row["physical_channel"],
                "high_ticks": int(row["high_ticks"]),
                "low_ticks": int(row["low_ticks"]),
                "initial_delay_ticks": int(row["initial_delay_ticks"]),
                "trigger": row["trigger"],
                "trigger_edge": row["trigger_edge"],
                "timebase": row["timebase"],
                "started_on_init": row["started_on_init"] == "True",
            }
            if item["physical_channel"] != "/10/ctr{0}".format(output):
                raise ValueError("NI6602 physical-channel mismatch")
            if item["timebase"] != "/10/PFI11" or item["trigger_edge"] not in ("rising", "falling"):
                raise ValueError("NI6602 timebase or edge mismatch")
            if item["high_ticks"] <= 0 or item["low_ticks"] <= 0 or item["initial_delay_ticks"] != 0:
                raise ValueError("invalid NI6602 pulse timing")
            result.append(item)
    result.sort(key=lambda item: item["output"])
    if [item["output"] for item in result] != list(range(8)):
        raise ValueError("NI6602 plan must contain all eight outputs exactly once")
    started = tuple(item["output"] for item in result if item["started_on_init"])
    if started != COUNTERS_STARTED_ON_INIT:
        raise ValueError("NI6602 startup selection mismatch")
    return result


def card_initialization_plan(data_path=None):
    """Describe all 11 cards without opening, reserving, or writing any card."""
    return {
        "device_numbers": tuple(range(1, 12)),
        "analog_input": AI_BANKS,
        "digital_input": DI_BANKS,
        "digital_output": DO_BANKS,
        "analog_output": AO_BANKS,
        "counter_output": load_counter_timing(data_path),
        "startup_analog_logical": analog_startup_logical_image(),
        "startup_analog_volts": analog_startup_voltage_image(data_path),
        "startup_digital": digital_startup_image(),
        "hardware_tasks_created": 0,
        "hardware_writes": False,
        "status": "INERT_PLAN_NOT_COMMISSIONED",
    }
