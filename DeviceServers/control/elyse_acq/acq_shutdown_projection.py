"""Pure projections of verified saved Acquisition shutdown-control wires.

These functions do not call PSP, DAQmx, Tango, serial devices, or hardware.
They are not instructions for operating or stopping the installation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple


HT_RAMP_EXIT_BELOW = 6.6
HT_RAMP_DECREMENT = 0.1
HT_RAMP_WAIT_S = 0.5
HT_RAMP_AUX_PARAM50_VALUE = 6.0
CONTROLLED_STOP_PHASE_MARKERS = (6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0)
PULSE_POLL_INDEX_EXIT_ABOVE = 40
PULSE_POLL_WAIT_S = 0.001
PULSE_STOP_POST_WAIT_S = 1.0
PULSE_STOP_TASK_FIELDS = (3, 4)
MAGNET_STOP_C6_ZERO_FIELDS = (0, 1, 2, 3, 4, 5, 6, 7, 9)
MAGNET_STOP_C7_ZERO_FIELDS = (0, 1, 3, 4, 5, 6, 7, 8, 9)
MAGNET_STOP_C3_FALSE_FIELDS = (
    9, 11, 15, 17, 21, 23, 25, 27, 29,
    31, 32, 33, 34, 35, 36, 37, 38, 39,
)
MAGNET_STOP_FRAME_WAITS_S = (None, 1.0, None, 1.0)
STAGE_STOP_C4_PULSE_FIELDS = (8, 17, 6, 4, 1)
STAGE_STOP_INTERSTAGE_WAITS_S = (1.0, 1.0, 1.0, 2.0, 1.0)
COOLING_STOP_C3_PULSE_FIELDS = (1, 4)
COOLING_STOP_EPS_FIELD_VALUES = ((3, False), (2, False), (5, True), (1, False))
COOLING_STOP_DPS_FIELD_VALUES = ((1, False),)
COOLING_STOP_EXPLICIT_WAITS_S = (0.4, 0.1)


@dataclass(frozen=True)
class AcqPspErrorStopAssignment:
    """Assignments in one selected PSP-error Case arm, not execution state."""

    stop: bool
    tcp_ed: bool
    general_stop_assignment: Optional[bool]


def project_acq_psp_error_stop_assignment(
    operation: str,
) -> AcqPspErrorStopAssignment:
    """Transcribe checked PSP read/write error arms without actuating.

    The saved root has two checked PSP-write error arms assigning both
    True, but its checked PSP-read error arm assigns both False. None
    of these arms assigns Arrêt général. This function does not model
    any other concurrent writer, PSP outcome, or front-panel control.
    """

    if operation == "write":
        return AcqPspErrorStopAssignment(True, True, None)
    if operation == "read":
        return AcqPspErrorStopAssignment(False, False, None)
    raise ValueError("operation must be 'read' or 'write'")


def controlled_stop_pulse_poll_exits(pulse_complete: bool, loop_index: int) -> bool:
    """Saved phase-1 loop predicate for either task; no DAQmx operation.

    A True result means the saved loop proceeds to a Stop Task call, not
    that pulse generation or task stopping succeeded.
    """

    if type(pulse_complete) is not bool:
        raise ValueError("pulse_complete must be a Boolean")
    if type(loop_index) is not int or loop_index < 0:
        raise ValueError("loop_index must be a nonnegative integer")
    return pulse_complete or loop_index > PULSE_POLL_INDEX_EXIT_ABOVE


@dataclass(frozen=True)
class ControlledStopHtSupplyFrame:
    """One ordered LabVIEW frame; nodes inside the frame are not ordered."""

    frame_index: int
    c4_field19_write: Optional[bool]
    wait_s: Optional[float]


CONTROLLED_STOP_HT_SUPPLY_FRAMES = (
    ControlledStopHtSupplyFrame(0, False, 0.150),
    ControlledStopHtSupplyFrame(1, True, None),
    ControlledStopHtSupplyFrame(2, None, 1.0),
)


@dataclass(frozen=True)
class ControlledStopHtRampIteration:
    """One logical loop iteration, without ordering concurrent diagram nodes."""

    observed_c9_field0: float
    local_param48_mirror: float
    local_param50_assignment: float
    c9_field0_write: Optional[float]
    wait_s: Optional[float]
    exits_loop: bool


def project_controlled_stop_ht_ramp(
    initial_c9_field0: float, *, max_iterations: int = 10000
) -> Tuple[ControlledStopHtRampIteration, ...]:
    """Project the saved outer-frame-3 HT command loop, not measured HT.

    The copied VI exits when the current logical C9[0] command is < 6.6;
    otherwise it subtracts 0.1, writes local C9[0], waits 500 ms, and
    rechecks. It also mirrors the current value to local param 48 and
    assigns 6.0 to local param 50 on each iteration. The meanings of those
    two numeric locals are not independently established. Strict finite
    input and the iteration cap are Python-only safeguards: the saved loop
    has no analogous limit on the traced stop-condition wire.
    """

    if type(initial_c9_field0) not in (int, float) or not math.isfinite(initial_c9_field0):
        raise ValueError("initial C9[0] command must be finite numeric")
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    current = float(initial_c9_field0)
    steps = []
    for _ in range(max_iterations):
        exits = current < HT_RAMP_EXIT_BELOW
        next_value = None if exits else current - HT_RAMP_DECREMENT
        steps.append(ControlledStopHtRampIteration(
            observed_c9_field0=current,
            local_param48_mirror=current,
            local_param50_assignment=HT_RAMP_AUX_PARAM50_VALUE,
            c9_field0_write=next_value,
            wait_s=None if exits else HT_RAMP_WAIT_S,
            exits_loop=exits,
        ))
        if exits:
            return tuple(steps)
        current = next_value
    raise ValueError("Python projection iteration cap reached before saved exit condition")
