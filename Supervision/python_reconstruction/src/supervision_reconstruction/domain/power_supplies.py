"""Pure fault topology from ``3_SUP_en_défaut_alims.vi``.

The full-screen LabVIEW diagram shows each ordinary channel as
``(command XOR running) OR (command AND fault)``.  It also visibly routes the
H4 command bit into the H5 branch and contains the note ``Attention H4 mis une
deuxième fois pour H5``.  The anomaly is modelled explicitly; it is never
silently corrected or hidden in an external field map.
"""

from dataclasses import dataclass
from enum import Enum


class H5CommandSource(str, Enum):
    """Select the documented legacy H5 command routing explicitly."""

    LEGACY_H4 = "legacy_h4"
    INTENDED_H5 = "intended_h5"


@dataclass(frozen=True)
class PowerSupplyFault:
    """Pure evaluation result including the command source actually used."""

    command_used: bool
    running: bool
    fault_feedback: bool
    fault_active: bool


def evaluate_power_supply_fault(
    command: bool, running: bool, fault_feedback: bool
) -> PowerSupplyFault:
    """Evaluate the confirmed per-channel boolean topology."""

    return PowerSupplyFault(
        command_used=command,
        running=running,
        fault_feedback=fault_feedback,
        fault_active=(command != running) or (command and fault_feedback),
    )


def evaluate_h5_fault(
    *,
    h4_command: bool,
    h5_running: bool,
    h5_fault_feedback: bool,
    command_source: H5CommandSource,
    h5_command: bool | None = None,
) -> PowerSupplyFault:
    """Evaluate H5 while making the legacy H4-command defect selectable.

    ``LEGACY_H4`` must be selected explicitly even though it is the observed VI
    wiring. ``INTENDED_H5`` is an analysis mode only and requires a separately
    supplied H5 command value; it is not evidence that such a production mapping
    exists.
    """

    if command_source is H5CommandSource.LEGACY_H4:
        if h5_command is not None:
            raise ValueError("LEGACY_H4 mode does not accept h5_command")
        command = h4_command
    elif command_source is H5CommandSource.INTENDED_H5:
        if h5_command is None:
            raise ValueError("INTENDED_H5 mode requires an explicitly supplied h5_command")
        command = h5_command
    else:
        raise ValueError(f"unsupported H5 command source: {command_source!r}")
    return evaluate_power_supply_fault(command, h5_running, h5_fault_feedback)
