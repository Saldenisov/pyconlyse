"""Explicit original-source measurement fixture, not live startup/restart state.

Seven DSINIT/DCO/DFDS associations are independently checked by
tools/validate_acq_saved_measurement_data.py. Nothing consumes this snapshot
automatically; no control, driver, transport or reset runs here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SavedMeasurementSnapshot:
    bank59: tuple[float, ...]
    bank62: int
    bank63: int
    bank65: tuple[float, ...]
    bank66: tuple[float, ...]
    bank67: tuple[float, ...]
    bank68: int


def saved_source_measurement_snapshot() -> SavedMeasurementSnapshot:
    return SavedMeasurementSnapshot((), 0, 0, (), (), (), 0)
