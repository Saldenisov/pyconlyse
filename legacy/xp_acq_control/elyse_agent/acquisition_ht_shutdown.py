"""Explicit Python HT-stop extension, not original LabVIEW event 6.

No I/O on import. Only injected callbacks can actuate. Operator-requested
8-kV handoff differs from the saved outer-stop command threshold <6.6.
Fresh measured HT and supply feedback gate the remaining General sequence.
Defaults deliberately use exact zero, not an invented measurement tolerance.
This is a controlled stop, not independently qualified electrical protection.
"""

import math
import time

from .acquisition_procedures import GeneralStopError

HT_HANDOFF_KV = 8.0
HT_STEP_KV = 0.1
HT_STEP_SECONDS = 0.5
MAX_RAMP_STEPS = 200
MAX_SAMPLE_AGE_SECONDS = 2.0
HT_SUPPLY_STOP_FRAMES = (
    (0, "31696", ((19, False),), 150),
    (1, "31883", ((19, True),), 0),
    (2, "32123", (), 0),
    (3, "32374", (), 0),
    (4, "32729", (), 100),
)
HT_SUPPLY_STOP_EPS = ((45, False), (49, True))
HT_SUPPLY_STOP_DPS = ((17, False),)
PULSE_STOP_TASKS = (3, 4)
PULSE_STOP_EPS = ((52, False), (42, True))  # source event24, not EPS55
PULSE_STOP_DPS = ((19, False),)


def execute_ht_supply_stop(commit_c4, assign_status, wait_seconds):
    """Event21 pulse/status/waits; explicit writes replace local/PSP lanes."""
    failures, uncertain = [], False

    def attempt(label, callback, *args):
        try:
            callback(*args)
            return True
        except Exception as error:
            failures.append(label + ": " + type(error).__name__ + ": " + str(error))
            return False

    for index, _uid, assignments, milliseconds in HT_SUPPLY_STOP_FRAMES:
        for line, value in assignments:
            if not value:
                uncertain = True
            if attempt("C4[19] stop", commit_c4, line, value) and value:
                uncertain = False
        if index == 2:
            attempt(
                "HT source status",
                assign_status,
                HT_SUPPLY_STOP_EPS,
                HT_SUPPLY_STOP_DPS,
            )
        if milliseconds:
            attempt("HT source wait", wait_seconds, milliseconds / 1000.0)
    if uncertain:
        attempt("restore C4[19]=True", commit_c4, 19, True)
    if failures:
        raise GeneralStopError(failures)


def validate_policy(feedback_verified, zero_tolerance_kv, timeout_seconds):
    if type(feedback_verified) is not bool:
        raise ValueError("HT feedback verification must be explicit Boolean")
    if (
        type(zero_tolerance_kv) not in (int, float)
        or not math.isfinite(zero_tolerance_kv)
        or not 0 <= zero_tolerance_kv < HT_HANDOFF_KV
    ):
        raise ValueError("Explicit finite HT zero tolerance in [0, 8) kV required")
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError("HT feedback timeout must be in (0, 120] seconds")


def execute_ht_shutdown(
    command_kv,
    read_ht,
    lower_command,
    supply_stop,
    pulse_stop,
    wait_seconds,
    feedback_verified=False,
    zero_tolerance_kv=0.0,
    timeout_seconds=10.0,
    clock=None,
    observer=None,
):
    """Return only after observed zero + supply OFF + both pulse-stop ACKs.

    Ramp is skipped if a fresh measurement is already zero or the supply is
    already OFF. A command below8 is never raised. Successful output/task
    calls are software ACKs, not independent physical pulse measurements.
    Read/ramp faults still attempt HT/pulse stops, but never permit following
    General/stage shutdown. No cooling command or task release occurs here.
    Bounded loops do not impose a hard deadline on a blocked native call.
    """
    validate_policy(feedback_verified, zero_tolerance_kv, timeout_seconds)
    if feedback_verified is not True:
        raise ValueError(
            "HT feedback mapping/polarity/calibration must be verified "
            "before this extension"
        )
    if (
        type(command_kv) not in (int, float)
        or not math.isfinite(command_kv)
        or not 0 <= command_kv <= 20
    ):
        raise ValueError("Finite last-successful HT command in [0, 20] kV required")
    clock = clock or time.monotonic
    failures, sample, ramp_steps = [], None, 0

    def observe(stage):
        if observer is not None:
            try:
                observer(stage)
            except Exception as error:
                failures.append(
                    "HT observer: {0}: {1}".format(type(error).__name__, error)
                )

    def read():
        value = read_ht()
        if (
            not isinstance(value, dict)
            or type(value.get("supply_on")) is not bool
            or type(value.get("voltage_kv")) not in (int, float)
            or not math.isfinite(value["voltage_kv"])
            or value["voltage_kv"] < -zero_tolerance_kv
            or type(value.get("age_seconds")) not in (int, float)
            or not math.isfinite(value["age_seconds"])
            or not 0 <= value["age_seconds"] < MAX_SAMPLE_AGE_SECONDS
        ):
            raise ValueError(
                "Fresh valid measured HT and explicit supply feedback required"
            )
        return value

    def is_zero(value):
        return abs(value["voltage_kv"]) <= zero_tolerance_kv

    try:
        observe("observe_ht")
        sample = read()
        # Readback zero takes precedence over a nonzero legacy command image.
        # In particular startup command6.5 must never be raised to8.
        if not is_zero(sample) and sample["supply_on"]:
            observe("lower_ht_to_8kv")
            planned_steps = math.ceil(max(0.0, command_kv - HT_HANDOFF_KV) / HT_STEP_KV)
            deadline = clock() + planned_steps * HT_STEP_SECONDS + timeout_seconds
            polls = 0
            while sample["voltage_kv"] > HT_HANDOFF_KV:
                polls += 1
                if polls > MAX_RAMP_STEPS + int(math.ceil(timeout_seconds / 0.1)) + 2:
                    raise RuntimeError("HT ramp feedback iteration limit")
                if command_kv > HT_HANDOFF_KV:
                    if ramp_steps >= MAX_RAMP_STEPS:
                        raise RuntimeError("HT ramp iteration limit")
                    next_command = max(HT_HANDOFF_KV, command_kv - HT_STEP_KV)
                    # Enforce monotonic decrease independently of the adapter.
                    if not next_command < command_kv:
                        raise RuntimeError("HT ramp must never increase a command")
                    lower_command(next_command)
                    command_kv = next_command  # update only after write ACK
                    ramp_steps += 1
                    wait_seconds(HT_STEP_SECONDS)
                else:
                    wait_seconds(0.1)
                if clock() >= deadline:
                    raise RuntimeError("Measured HT did not reach 8 kV before deadline")
                sample = read()
                if is_zero(sample) or not sample["supply_on"]:
                    break
    except Exception as error:
        failures.append(
            "HT observation/ramp: {0}: {1}".format(type(error).__name__, error)
        )

    # Unknown feedback is not OFF: on a read/ramp failure still attempt both
    # dedicated stops. Subsequent General remains inhibited by the error.
    try:
        observe("stop_ht_supply")
        if failures or sample is None or sample["supply_on"]:
            supply_stop()
    except Exception as error:
        failures.append("HT supply stop: {0}: {1}".format(type(error).__name__, error))
    try:
        observe("stop_modulator_pulses")
        # Must acknowledge BOTH counters, even when measured HT was zero.
        pulse_stop()
    except Exception as error:
        failures.append(
            "Modulator pulse stop: {0}: {1}".format(type(error).__name__, error)
        )
    try:
        observe("verify_ht_off_and_zero")
        deadline = clock() + timeout_seconds
        for _attempt in range(int(math.ceil(timeout_seconds / 0.1)) + 2):
            sample = read()  # never reuse the pre-stop snapshot as an ACK
            if is_zero(sample) and sample["supply_on"] is False:
                break
            if clock() >= deadline:
                raise RuntimeError("HT zero / supply OFF feedback timeout")
            wait_seconds(0.1)
        else:
            raise RuntimeError("HT zero / supply OFF feedback iteration limit")
    except Exception as error:
        failures.append(
            "HT OFF verification: {0}: {1}".format(type(error).__name__, error)
        )
    if not failures:
        observe("ht_preamble_completed")
    if failures:
        raise GeneralStopError(failures)
    return dict(
        command_kv=command_kv,
        ramp_steps=ramp_steps,
        measured_zero_confirmed=True,
        supply_off_confirmed=True,
        pulse_stop_calls_acknowledged=True,
        physical_pulse_absence_independently_measured=False,
    )
