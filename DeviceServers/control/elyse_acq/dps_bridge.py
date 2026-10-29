"""Pure legacy DPS request-to-procedure bridge; no PSP or hardware calls.

The zero-based bank indices are from the copied Supervision DPS cluster. ACQ's
legacy dispatcher uses one-based selector numbers; they are not ACQ event case
numbers. The source/handler crosswalk is in
``Supervision/integration_analysis/SUP_ACQ_DPS_FIELD_CROSSWALK_2026-09-29.csv``.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from .contracts import ProcedurePlan
from .plans import PROCEDURE_PLANS
from legacy.xp_acq_agent.elyse_agent import saved_dispatch as _shared

replay_saved_dispatch = _shared.replay_saved_dispatch


class UnsupportedDpsIntent(ValueError):
    """A visible DPS field has no corresponding ACQ procedure handler."""


# Index 22 (one-based dispatcher selector 23) is magnet PT: dispatched by the
# copied VI but has no recovered ACQ event handler. It must never be guessed.
DPS_ACQ_EVENT_CASES: Tuple[Optional[int], ...] = (
    3, 4, 5, 6, 12, 7, 13, 8, 14, 9, 15, 10,
    11, 18, 19, 20, 22, 21, 23, 24, 16, 25, None, 17,
)

_PLANS_BY_CASE = {plan.legacy_event_case: plan for plan in PROCEDURE_PLANS.values()}
if len(DPS_ACQ_EVENT_CASES) != 24:
    raise RuntimeError("expected 24 DPS procedure-dispatch fields")
if {case for case in DPS_ACQ_EVENT_CASES if case is not None} != set(range(3, 26)):
    raise RuntimeError("DPS bridge must cover exactly ACQ event cases 3..25")
DPS_FIELD_BY_ACQ_EVENT_CASE = {
    case: index for index, case in enumerate(DPS_ACQ_EVENT_CASES)
    if case is not None
}


def resolve_dps_request(index: int, asserted: bool) -> Optional[ProcedurePlan]:
    """Decode one DPS field without executing or acknowledging it.

    ``False`` is no request. ``True`` returns the matching immutable plan,
    except for the orphaned PT field, which fails closed. This function does
    not implement request arbitration, clear an asserted flag, or claim that
    the corresponding hardware procedure has completed.
    """

    if type(index) is not int or not 0 <= index < len(DPS_ACQ_EVENT_CASES):
        raise ValueError(f"unsupported DPS bank index: {index!r}")
    if type(asserted) is not bool:
        raise ValueError("DPS request value must be Boolean")
    if not asserted:
        return None
    case = DPS_ACQ_EVENT_CASES[index]
    if case is None:
        raise UnsupportedDpsIntent(
            "DPS[22] Alimentation aimant = PT has no ACQ event handler"
        )
    return _PLANS_BY_CASE[case]


def first_asserted_dps_request(flags: Sequence[bool]) -> Optional[ProcedurePlan]:
    """Decode the first true procedure flag, as the legacy timeout scan does.

    The copied ACQ timeout frame uses ``Search 1D Array(True)`` and increments
    its result before selecting dispatcher cases 0..24. Thus an all-false
    snapshot selects no procedure, while simultaneous true flags select the
    lowest bank index. This is a *single-snapshot* reference model: it does not
    clear flags, schedule later requests, or acknowledge completion. The five
    other DPS schema fields are outside this 24-field procedure slice.
    """

    if len(flags) != len(DPS_ACQ_EVENT_CASES):
        raise ValueError("expected exactly 24 DPS procedure flags")
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("DPS procedure flags must be Boolean")
    index = _shared.dispatch_values(tuple(flags) + (False,) * 5)[0]
    if index >= 0:
        return resolve_dps_request(index, True)
    return None


def project_dps_handler_reset(
    flags: Sequence[bool], event_case: int
) -> Tuple[bool, ...]:
    """Project one saved ACQ handler's local DPS-bit reset, without PSP.

    Every implemented event 3..25 writes False to its corresponding
    request bit, then *attempts* a DPS PSP write in the next ordered
    frame. This function models only the local value assignment; it
    does not execute a procedure, publish DPS, or acknowledge success.
    The five trailing DPS schema fields are preserved unchanged.
    """

    if len(flags) != 29 or any(type(flag) is not bool for flag in flags):
        raise ValueError("expected exactly 29 Boolean DPS fields")
    if type(event_case) is not int or event_case not in DPS_FIELD_BY_ACQ_EVENT_CASE:
        raise ValueError(f"unsupported ACQ DPS event case: {event_case!r}")
    return _shared.reset_values(tuple(flags), event_case)
