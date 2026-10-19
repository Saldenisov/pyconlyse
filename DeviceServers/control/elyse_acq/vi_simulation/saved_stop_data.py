"""Explicit snapshot of four persisted stop-control values in the copied VI.

Selecting this fixture does not read LabVIEW's current controls, reset local
memory, restart a VI, or assert that persisted values were loaded at runtime.
No transport, adapter, hardware or file access exists in this module.
"""

from .stop_lifecycle import StopMemory


def saved_source_stop_snapshot():
    """Return source data only; never an implicit initialization/reset step."""
    return StopMemory(
        stop=False, tcp_ed=False, emergency_stop=False, general_stop=False
    )
