"""Inert, bounded projections of beam-line event frame0.

Only explicit outer selector arms are executable. The saved outer selector
omits SelectDefaultCase; shared lvkit infers frame0, but that inference is
not promoted to an independently verified native default here. Property
nodes, reference casts and Variant To Data receive external fixtures, not
implementations. No UI, driver, PSP, global storage or sleep is used.
"""

from dataclasses import dataclass
from math import isfinite

FIELD_TYPES = (bool,) * 5 + (float,) * 2 + (bool,) * 4
CHANGE_MASK = 0x791
BUTTONS = (128, 256, 512, 1024)
EXPLICIT_MASKS = (0, 1, 16, *BUTTONS)


class UnverifiedOuterDefaultError(ValueError):
    """Combined change masks require independent native default evidence."""


@dataclass(frozen=True)
class ChangeSelection:
    masked_changes: tuple[int, ...]
    maximum: int
    selected_index: int
    apply_setpoints: bool


@dataclass(frozen=True)
class CellValueWritePlan:
    selected_index: int
    value: tuple
    wait_request_ms: int = 70
    property_name: str = "Value"
    error_handling: str = "saved property/cast/variant errors unwired"


def _event(event):
    if type(event) is not int or event not in (1, 2):
        raise ValueError("saved beam-line event1 or event2 required")


def _cell(cell):
    if (
        type(cell) is not tuple
        or len(cell) != 11
        or any(type(v) is not t for v, t in zip(cell, FIELD_TYPES))
    ):
        raise TypeError("explicit eleven-field Boolean/DBL device cell required")
    if not all(isfinite(cell[i]) for i in (5, 6)):
        raise ValueError("finite DBL fixture domain only; NaN/Inf not qualified")


def select_change(event, old_cells, new_cells):
    """Elementwise difference -> Boolean bit number -> mask -> first max index.

    Fields5/6 and status fields1/2/3 cannot set any retained change bit.
    Masks are not OR-ed across devices. A zero maximum still selects index0.
    The >=128 result is a change-class gate, never an interlock permission.
    """
    _event(event)
    count = 11 if event == 1 else 9
    for cells in (old_cells, new_cells):
        if type(cells) is not tuple or len(cells) != count:
            raise TypeError("complete event OldVal/NewVal cell tuples required")
        for cell in cells:
            _cell(cell)
    changes = tuple(
        sum((1 << i) for i, (a, b) in enumerate(zip(old, new)) if a != b) & CHANGE_MASK
        for old, new in zip(old_cells, new_cells)
    )
    maximum = max(changes)
    return ChangeSelection(changes, maximum, changes.index(maximum), maximum >= 128)


def adjustment_parameters(event, device_index, button):
    """Return (small step, large step, lower, upper), or nested default pass.

    Bounds are source software values, not independently proven physical
    units or safe operating limits. A True X1/X10 fixture selects large step.
    """
    _event(event)
    if (
        type(device_index) is not int
        or type(button) is not int
        or button not in BUTTONS
    ):
        raise TypeError("integer index and one explicit arrow-button mask required")
    coarse = button in (128, 1024)
    if event == 1:
        if device_index == 1:
            return (1.0, 10.0, 0.0, 120.0) if coarse else (0.1, 1.0, 0.0, 120.0)
        if device_index == 2:
            return (5.0, 50.0, 0.0, 180.0) if coarse else (1.0, 5.0, 0.0, 180.0)
        if device_index in (0, 7, 8):
            bound = 16.0
        elif device_index in (3, 4, 5, 6, 9, 10):
            bound = 5.0
        else:
            return None
    else:
        if device_index in (0, 1, 2, 3, 6):
            bound = 16.0
        elif device_index in (4, 5, 7, 8):
            bound = 5.0
        else:
            return None
    return (0.1, 1.0, -bound, bound) if coarse else (0.01, 0.1, -bound, bound)


def adjust_setpoint(event, device_index, button, current, x1_x10):
    if type(current) is not float or not isfinite(current) or type(x1_x10) is not bool:
        raise TypeError("finite DBL Consigne and explicit Boolean X1/X10 required")
    parameters = adjustment_parameters(event, device_index, button)
    if parameters is None:
        return current
    small, large, lower, upper = parameters
    step = large if x1_x10 else small
    requested = current - step if button in (128, 256) else current + step
    # Preserve the input DBL when already within bounds, including signed zero.
    return lower if requested < lower else upper if requested > upper else requested


def project_frame0(event, *, old_cells, new_cells, current_selected_cell):
    """Return change metadata and a Value-write plan after a requested70ms wait.

    current_selected_cell is the separate Value-read/Variant-to-Data result,
    not NewVal. Property/cast failure behavior is outside this fixture model.
    Frames1/2 require their own later local-read and publication snapshots.
    """
    selection = select_change(event, old_cells, new_cells)
    _cell(current_selected_cell)
    if selection.maximum not in EXPLICIT_MASKS:
        raise UnverifiedOuterDefaultError(
            f"mask {selection.maximum}: outer default not independently verified"
        )
    value = list(current_selected_cell)
    if selection.maximum in BUTTONS:
        value[5] = adjust_setpoint(
            event, selection.selected_index, selection.maximum, value[5], value[4]
        )
    value[7:] = [False] * 4
    return selection, CellValueWritePlan(selection.selected_index, tuple(value))
