"""Supplied multi-iteration stop traces and completed-frame reset projections.

No scheduler, transport, driver, UI operation or apparatus shutdown exists
here. Body completion is a fixture assertion, never a simulated NI return.
"""

from dataclasses import dataclass

from legacy.xp_acq_agent.elyse_agent import saved_stop as _shared

from .stop_schedule import (
    ERROR_SITES,
    RUNTIME_LOOPS,
    BodyCompleted,
    ErrorArmEntry,
    LocalAssignment,
    OuterTcpRead,
    StopLocalRead,
)

STOP_RESETS = {
    "post_init": ((45, False), (46, False)),
    "controlled_complete": ((46, True), (47, False)),
    "final_cleanup": ((30, False),),
}
STOP_FIELDS = {30: "stop", 45: "tcp_ed", 46: "emergency_stop", 47: "general_stop"}


@dataclass(frozen=True)
class StopMemory:
    stop: bool
    tcp_ed: bool
    emergency_stop: bool
    general_stop: bool

    def __post_init__(self):
        if any(
            type(getattr(self, field)) is not bool for field in STOP_FIELDS.values()
        ):
            raise TypeError("four explicit Boolean local snapshots required")


@dataclass(frozen=True)
class StopResetProjection:
    independent_assignments: tuple[tuple[int, bool], ...]
    after: StopMemory


def project_stop_reset(stage, before):
    """Completed-frame postcondition only; listed writes are not an atomic pair.

    Initialization does not contain a gRef reset of stop30 or general_stop47.
    No loaded default, UI action or indirect writer is inferred. Cleanup does
    not reset TCP45, emergency46 or general47 and does not zero card outputs.
    """
    if type(stage) is not str or stage not in STOP_RESETS:
        raise ValueError("known saved reset stage required")
    if type(before) is not StopMemory:
        raise TypeError("explicit StopMemory required")
    result = _shared.project_stop_reset(stage, _shared.StopMemory(
        before.stop, before.tcp_ed, before.emergency_stop, before.general_stop))
    return StopResetProjection(result.independent_assignments, StopMemory(*result.after))


@dataclass(frozen=True)
class NextIteration:
    loop_uid: str


@dataclass(frozen=True)
class SuppliedStopChange:
    """Unmodeled external/local30 source supplied by the fixture, not UI I/O."""

    value: bool


@dataclass(frozen=True)
class IterationDecision:
    loop_uid: str
    iteration: int
    sampled_stop: bool


@dataclass(frozen=True)
class RuntimeStopTrace:
    stop_after: bool
    tcp_after: bool
    decisions: tuple[IterationDecision, ...]
    exited_loops: tuple[str, ...]
    next_iteration_ready: tuple[str, ...]
    inflight_loops: tuple[str, ...]
    pending_snapshots: tuple[tuple[str, int, bool], ...]
    outer_tcp_snapshot: bool | None


def replay_runtime(schedule, *, stop_before, tcp_before):
    """Consume explicit partial-order tokens across any finite fixture trace.

    All five first iterations are available after runtime-frame entry. A
    False completed condition only enables a supplied NextIteration token;
    it does not schedule it. A True condition makes that loop absorbing.
    Error arms may recur in later iterations. Both writes must finish before
    their owner body completes; their relative order is unspecified. Other
    loops may keep captured values even after the shared stop flag changes.

    No fairness, external-call completion, next-iteration latency, restart
    semantics or physical stop is inferred. I32 loop-index overflow is outside
    this model. A trace may end with unfinished calls/assignments.
    """
    token_types = {
        NextIteration: _shared.NextIteration,
        SuppliedStopChange: _shared.SuppliedStopChange,
        ErrorArmEntry: _shared.ErrorArmEntry,
        LocalAssignment: _shared.LocalAssignment,
        StopLocalRead: _shared.StopLocalRead,
        BodyCompleted: _shared.BodyCompleted,
        OuterTcpRead: _shared.OuterTcpRead,
    }
    def convert(item):
        cls = token_types.get(type(item))
        if cls is None:
            return item
        return cls(*(getattr(item, name) for name in cls._fields))
    result = _shared.replay_runtime((convert(item) for item in schedule),
        stop_before=stop_before, tcp_before=tcp_before)
    return RuntimeStopTrace(result.stop_after, result.tcp_after,
        tuple(IterationDecision(*d) for d in result.decisions),
        result.exited_loops, result.next_iteration_ready, result.inflight_loops,
        result.pending_snapshots, result.outer_tcp_snapshot)

assert RUNTIME_LOOPS == _shared.RUNTIME_LOOPS
assert ERROR_SITES == _shared.ERROR_SITES
assert STOP_RESETS == _shared.STOP_RESETS
