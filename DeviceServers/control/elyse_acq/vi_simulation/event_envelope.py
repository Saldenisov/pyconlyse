"""Procedure event entry only: a supplied event is not an equipment permission."""

from dataclasses import dataclass

from legacy.xp_acq_agent.elyse_agent.saved_requests import procedure_entry_values


@dataclass(frozen=True)
class ProcedureEntry:
    event_index: int
    enters_sequence: bool
    duration_argument: int | None
    registration_flags: int


def procedure_entry(event_index, *, new_value):
    """Every saved procedure event3..25 gates its sequence on BooleanNewVal.

    OldVal is not used at this entry gate. The special event25 registration
    high bit is preserved without interpreting its scheduling/locking role.
    Duration is a wired U32 entry argument, not a proven physical pulse.
    """
    return ProcedureEntry(*procedure_entry_values(event_index, new_value))
