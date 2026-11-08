"""Hardware-free motion planning from ``Moteurs SdC GoTo.vi``.

This is deliberately not a CmdLib adapter.  It only reconstructs selector and
button-mask decisions visible in the expanded LabVIEW diagrams.  Invalid masks
are rejected instead of inheriting the legacy ``1, Default`` forward-X branch.
That explicit fail-closed boundary prevents an incomplete UI state from being
converted into a motion command during later integration.
"""

from dataclasses import dataclass
from enum import Enum


class Axis(str, Enum):
    X = "x"
    Y = "y"


class Direction(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True)
class MotorPair:
    """X/Y motor numbers selected by the legacy laser selector."""

    x_motor: int
    y_motor: int


@dataclass(frozen=True)
class RelativeMovePlan:
    """A pure plan; no class in this module can send a motor command."""

    laser_selector: int
    button_mask: int
    axis: Axis
    direction: Direction
    motor_index: int
    motor_number: int
    signed_steps: int


@dataclass(frozen=True)
class MotionTermination:
    """The evidenced while-loop stop and abort decision, without side effects."""

    terminate: bool
    abort_requested: bool


def motor_pair_for_laser(laser_selector: int) -> MotorPair:
    """Return only the two evidenced selector cases: 1 -> [3, 4], 2 -> [1, 2]."""

    if (
        isinstance(laser_selector, bool)
        or not isinstance(laser_selector, int)
        or laser_selector not in (1, 2)
    ):
        raise ValueError("laser_selector must be exactly 1 or 2")
    return MotorPair(3, 4) if laser_selector == 1 else MotorPair(1, 2)


def legacy_default_motor_pair_for_laser(laser_selector: int) -> MotorPair:
    """Explicit compatibility helper for the VI's selector-2/default branch.

    This helper is not used by the strict planner.  It documents, rather than
    silently imports, the legacy default behavior.
    """

    return MotorPair(3, 4) if laser_selector == 1 else MotorPair(1, 2)


def _motion_from_mask(button_mask: int) -> tuple[Axis, Direction, int]:
    mapping = {
        1: (Axis.X, Direction.FORWARD, 0),
        2: (Axis.X, Direction.REVERSE, 0),
        4: (Axis.Y, Direction.FORWARD, 1),
        8: (Axis.Y, Direction.REVERSE, 1),
    }
    if isinstance(button_mask, bool) or not isinstance(button_mask, int):
        raise ValueError("button_mask must be an integer one-hot mask")
    try:
        return mapping[button_mask]
    except KeyError as error:
        raise ValueError(
            "button_mask must be exactly one of 1, 2, 4, or 8; invalid and multiple masks fail closed"
        ) from error


def plan_relative_move(
    laser_selector: int, button_mask: int, relative_steps: int
) -> RelativeMovePlan:
    """Make an evidenced relative-motion plan without contacting CmdLib.

    The diagrams negate ``Relative Steps`` only for masks 2 and 8.  Requiring a
    non-negative magnitude here prevents a double-negative request from being
    silently reinterpreted as the opposite direction.
    """

    if isinstance(relative_steps, bool) or not isinstance(relative_steps, int):
        raise ValueError("relative_steps must be an integer magnitude")
    if not 0 <= relative_steps <= 2**31 - 1:
        raise ValueError("relative_steps must be within the I32 non-negative magnitude range")
    axis, direction, motor_index = _motion_from_mask(button_mask)
    pair = motor_pair_for_laser(laser_selector)
    motor_number = (pair.x_motor, pair.y_motor)[motor_index]
    signed_steps = -relative_steps if direction is Direction.REVERSE else relative_steps
    return RelativeMovePlan(
        laser_selector=laser_selector,
        button_mask=button_mask,
        axis=axis,
        direction=direction,
        motor_index=motor_index,
        motor_number=motor_number,
        signed_steps=signed_steps,
    )


def decide_motion_termination(
    *, motion_done: bool, error_status: bool, stop_motor: bool
) -> MotionTermination:
    """Mirror the loop's observed OR chain and the stop-motor abort case."""

    return MotionTermination(
        terminate=motion_done or error_status or stop_motor,
        abort_requested=stop_motor,
    )
