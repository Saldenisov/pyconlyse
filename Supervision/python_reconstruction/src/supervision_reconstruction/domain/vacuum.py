"""Semantics reconstructed from ``2_SUP_marche_defaut_VIDE.vi``.

Evidence: full-screen LabVIEW block diagram and an independent lvkit parsing
pass.  The VI passes the chamber-preparation running signal through unchanged
and calculates each of the other six outputs as ``fault and not running``.
Channel names are intentionally supplied by callers: the captured evidence
establishes the repeated logic but is not an authoritative I/O name map.
"""

from dataclasses import dataclass
from typing import Mapping


PAIRED_VACUUM_CHANNEL_COUNT = 6


@dataclass(frozen=True)
class VacuumPairedState:
    """Running and fault feedback for one non-preparation vacuum channel."""

    running: bool
    fault: bool


@dataclass(frozen=True)
class VacuumStatus:
    """Outputs of the evidenced vacuum-status VI."""

    chamber_preparation: bool
    paired_channels: Mapping[str, bool]


def evaluate_vacuum_status(
    chamber_preparation_running: bool,
    paired_states: Mapping[str, VacuumPairedState],
) -> VacuumStatus:
    """Evaluate the boolean topology visible in the legacy VI.

    ``paired_states`` is copied into a new mapping so a later caller mutation
    cannot change this result.  This function performs no hardware I/O.
    """

    if len(paired_states) != PAIRED_VACUUM_CHANNEL_COUNT:
        raise ValueError(
            "paired_states must contain exactly the six evidenced non-preparation vacuum channels"
        )
    return VacuumStatus(
        chamber_preparation=chamber_preparation_running,
        paired_channels={
            channel: state.fault and not state.running
            for channel, state in paired_states.items()
        },
    )
