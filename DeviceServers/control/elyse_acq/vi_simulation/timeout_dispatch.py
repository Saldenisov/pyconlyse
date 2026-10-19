"""Inert procedure/counter ingress projections; no event queue or equipment I/O.

Each argument represents its own observed local read, not an atomic global
snapshot. Handler success, fractional Index Array
coercion and effects of the actual NI6602 helper remain supplied boundaries.
"""

from dataclasses import dataclass
from legacy.xp_acq_agent.elyse_agent.saved_dispatch import dispatch_values

from .boundary import UNSUPPLIED, UNWIRED, ErrorCluster, MissingValue, TaskReference

# DPS field ordinal -> saved DDO and registered event diagram index.
TARGETS = (
    ("59266", 3),
    ("59274", 4),
    ("59370", 5),
    ("59378", 6),
    ("66579", 12),
    ("66587", 7),
    ("66627", 13),
    ("66635", 8),
    ("66675", 14),
    ("66683", 9),
    ("66723", 15),
    ("66731", 10),
    ("59386", 11),
    ("59482", 18),
    ("59474", 19),
    ("59314", 20),
    ("59330", 22),
    ("59322", 21),
    ("59426", 23),
    ("59434", 24),
    ("66411", 16),
    ("66443", 25),
    ("66459", None),
    ("66419", 17),
)
COUNTER_URI = "ni.var.psp://10.20.30.2/SUPERVISION/C1011NI6602"


@dataclass(frozen=True)
class PropertyIntent:
    target_ddo: str
    assignments: tuple[tuple[str, bool], ...]
    registered_event: int | None
    error_in: MissingValue = UNWIRED


@dataclass(frozen=True)
class ProcedureDispatch:
    first_true_index: int
    case_selector: int
    bank43_assignment: int
    action_assignment: bool | MissingValue
    property_intent: PropertyIntent | MissingValue


def procedure_dispatch(dps_snapshot):
    """Select first request and retain its raw index, including five tail fields.

    An explicit case0 writes ACTION False; request cases do not write ACTION.
    Tail selectors25..29 reach saved default0/frame9471 and write ACTION False.
    Static source interpretation is qualified; original12 runtime is not.
    Registered target is not a claim that its event handler runs/succeeds.
    """
    first, selector, kind, _action, ddo, event = dispatch_values(dps_snapshot)
    if kind in ('NO_REQUEST', 'SAVED_DEFAULT'):
        return ProcedureDispatch(first, selector, first, False, UNWIRED)
    intent = PropertyIntent(ddo, (("Value", True), ("Val(Sgnl)", True)), event)
    return ProcedureDispatch(first, selector, first, UNWIRED, intent)


@dataclass(frozen=True)
class CounterIntent:
    accepted: bool
    task_index: int | MissingValue
    task: TaskReference | MissingValue
    delay_index: int | MissingValue
    width_index: int | MissingValue
    delay: float | MissingValue
    width: float | MissingValue
    error_in: MissingValue = UNWIRED


def _counter_bank(snapshot):
    if (
        type(snapshot) is not tuple
        or len(snapshot) != 33
        or any(type(x) is not float for x in snapshot)
    ):
        raise TypeError("explicit 33-DBL counter snapshot required")


def counter_intent(counter_snapshot, task_snapshot):
    """Saved guard accepts DBL0<n<17; integer routing is proven for1..16.

    Fractional requests pass the guard but their Index Array conversion is
    deliberately not invented. Timing values are passed unchanged, including
    negative fixture values: validation by a driver is not caller behavior.
    """
    _counter_bank(counter_snapshot)
    if (
        type(task_snapshot) is not tuple
        or len(task_snapshot) != 8
        or any(not isinstance(x, TaskReference) for x in task_snapshot)
    ):
        raise TypeError("explicit eight-token NI6602 task snapshot required")
    n = counter_snapshot[32]
    if not (n > 0.0 and n < 17.0):
        return CounterIntent(
            False, UNWIRED, UNWIRED, UNWIRED, UNWIRED, UNWIRED, UNWIRED
        )
    if not n.is_integer():
        return CounterIntent(
            True, UNSUPPLIED, UNSUPPLIED, UNSUPPLIED, UNSUPPLIED, UNSUPPLIED, UNSUPPLIED
        )
    q = (int(n) - 1) // 2
    delay_index, width_index = 2 * q, 2 * q + 1
    return CounterIntent(
        True,
        q,
        task_snapshot[q],
        delay_index,
        width_index,
        counter_snapshot[delay_index],
        counter_snapshot[width_index],
    )


def counter_reset_frame(reset_snapshot, *, helper_returned_error):
    """True frame1 resets its independently read bank even on returned error.

    Reaching frame1 requires prior frame/handler completion. This function
    does not promise completion of a driver or a modal error handler.
    """
    _counter_bank(reset_snapshot)
    if not isinstance(helper_returned_error, ErrorCluster):
        raise TypeError("explicit NI6602 helper error return required")
    return reset_snapshot[:32] + (-1.0,)


@dataclass(frozen=True)
class CounterPublication:
    uri: str
    data: tuple[float, ...]
    error_in: MissingValue = UNWIRED
    returned_error_consumer: MissingValue = UNWIRED


def counter_publication_frame(publication_snapshot):
    """True frame2 publishes a new local read, not necessarily the reset snapshot."""
    _counter_bank(publication_snapshot)
    return CounterPublication(COUNTER_URI, publication_snapshot)
