"""Pure, non-actuating decoder for the saved Acquisition NI6602 request path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CounterRequest:
    owner: str
    command_number: int
    counter_index: int
    task_name: str
    delay_field_index: int
    width_field_index: int
    delay_microseconds: float
    width_microseconds: float


def decode_counter_request(number: int, timing_fields: Sequence[float]) -> CounterRequest:
    """Map integer command 1..16 to one of eight tasks and a C10 timing pair.

    This models the saved VI's integer path only. LabVIEW's visible guard is
    merely ``0 < number < 17``; noninteger coercion remains unverified and is
    therefore rejected here. No DAQmx operation or PSP acknowledgement occurs.
    """
    if type(number) is not int or not 1 <= number <= 16:
        raise ValueError("counter command number must be an integer in 1..16")
    if len(timing_fields) < 16:
        raise ValueError("C10-11 bank needs at least 16 C10 timing fields")
    index = (number - 1) // 2
    delay_index = 2 * index
    width_index = delay_index + 1
    return CounterRequest(
        owner="acquisition",
        command_number=number,
        counter_index=index,
        task_name=f"C10_NI6602.ctr{index}",
        delay_field_index=delay_index,
        width_field_index=width_index,
        delay_microseconds=float(timing_fields[delay_index]),
        width_microseconds=float(timing_fields[width_index]),
    )


def decode_supervision_counter_request(number: int, timing_fields: Sequence[float]) -> CounterRequest:
    """Map integer command 17..32 to Supervision's local Dev1 counter bank.

    The saved Supervision VI guards only ``number > 16``. This decoder rejects
    numbers above 32 because the eight-task array has no proven such mapping.
    ``timing_fields`` must be the Supervision local timing cluster, not assumed
    to be an atomic/fresh PSP read.
    """
    if type(number) is not int or not 17 <= number <= 32:
        raise ValueError("Supervision counter command number must be an integer in 17..32")
    if len(timing_fields) < 32:
        raise ValueError("C10-11 bank needs 32 timing fields for Supervision")
    index = (number - 17) // 2
    delay_index = 16 + 2 * index
    width_index = delay_index + 1
    return CounterRequest(
        owner="supervision",
        command_number=number,
        counter_index=index,
        task_name=f"SUPERVISION.Dev1/ctr{index}",
        delay_field_index=delay_index,
        width_field_index=width_index,
        delay_microseconds=float(timing_fields[delay_index]),
        width_microseconds=float(timing_fields[width_index]),
    )


def changed_timing_commands(before: Sequence[float], after: Sequence[float]) -> tuple[int, ...]:
    """Return one-based selectors emitted by the Supervision field-delta loop.

    This models the loop's changed-field selection only. Its separate outer
    case guard and PSP timing/overwrites are not simulated by this function.
    """
    if len(before) != 33 or len(after) != 33:
        raise ValueError("Supervision timing page requires 32 timing fields plus selector")
    return tuple(index + 1 for index, (old, new) in enumerate(zip(before, after)) if new - old != 0)
