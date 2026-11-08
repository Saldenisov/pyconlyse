"""In-memory replay of the final resource-close frame, not DAQ deinitialization.

PSP/VISA/handler returns are explicit ScriptedBoundary fixtures. A token is an
admissible call-node execution, not confirmation that a resource closed. No
NI output bank, task-stop call, transport or native handle exists here.
"""

from dataclasses import dataclass, replace

from .boundary import (
    UNWIRED,
    BoundaryCall,
    ErrorCluster,
    TaskReference,
    require_boundary,
    require_error,
)
from .outer_stop_schedule import OuterStopTrace
from .runtime_io import SOURCE
from .stop_lifecycle import StopMemory

from legacy.xp_acq_agent.elyse_agent.saved_cleanup import (
    VARIABLES as VARIABLES,
    FIXED_PSP_TAGS as FIXED_PSP_TAGS,
    TPG_BRANCHES as TPG_BRANCHES,
    PSP_HANDLER as PSP_HANDLER,
    CleanupEvent,
    begin_cleanup,
    cleanup_ready,
    plan_cleanup_step,
    commit_cleanup_step,
    replay_saved_cleanup as replay_saved_cleanup,
)


@dataclass(frozen=True)
class PspClose:
    index: int


@dataclass(frozen=True)
class TpgClose:
    bank: int


@dataclass(frozen=True)
class CleanupHandler:
    node_uid: str


@dataclass(frozen=True)
class CleanupStopReset:
    """Independent local30=False write; not a card-output assignment."""


@dataclass(frozen=True)
class CleanupFrameReturned:
    """All branches returned; source frame itself has no retry/close-success gate."""


@dataclass(frozen=True)
class CleanupTrace:
    memory_after: StopMemory
    psp_error_seed: ErrorCluster
    psp_error_after: ErrorCluster
    returned_psp_close_nodes: int
    returned_tpg_close_nodes: tuple[int, ...]
    returned_handlers: tuple[str, ...]
    stop_reset: bool
    frame_ready: bool
    frame_returned: bool
    calls: tuple[BoundaryCall, ...]


def replay_cleanup(schedule, *, outer, boundary, psp_error_seed, tpg_sessions):
    """Order only the wired dependencies; allow cross-branch interleaving.

    The For error register is uninitialized in the saved frame: its first
    value must be supplied, never silently replaced with NO_ERROR. The final
    close error feeds handler88, whose unused output does NOT feed that
    register. Two TPG input errors and all handler modes are unwired. Boundary
    defaults for those unwired errors are simulation assumptions, not native
    return guarantees. A partial schedule may end while cleanup is blocked.
    """
    if type(outer) is not OuterStopTrace or not (
        outer.cleanup_ready and outer.cleanup_entered
    ):
        raise ValueError("joined outer stop and cleanup entry required")
    require_boundary(boundary)
    require_error(psp_error_seed)
    if (
        type(tpg_sessions) is not tuple
        or len(tpg_sessions) != 2
        or any(type(value) is not TaskReference for value in tpg_sessions)
    ):
        raise TypeError("two explicit opaque TPG session fixtures required")
    memory = outer.memory_after
    state = begin_cleanup(psp_error_seed, memory.stop)
    start = len(boundary.calls)

    for token in schedule:
        if state.frame_returned:
            raise ValueError("cleanup trace ends at frame return")
        if type(token) is PspClose:
            event = CleanupEvent("psp_close", token.index)
        elif type(token) is TpgClose:
            event = CleanupEvent("tpg_close", token.bank)
        elif type(token) is CleanupHandler:
            hash(token.node_uid)
            event = CleanupEvent("handler", token.node_uid)
        elif type(token) is CleanupStopReset:
            event = CleanupEvent("stop_reset", None)
        elif type(token) is CleanupFrameReturned:
            event = CleanupEvent("frame_returned", None)
        else:
            raise TypeError("known inert cleanup token required")
        plan = plan_cleanup_step(state, event, tpg_sessions, UNWIRED)
        returned_error = None
        if plan.operation is not None:
            returned_error = boundary.invoke(
                SOURCE, plan.node_uid, plan.diagram_uid, plan.operation,
                iteration=plan.iteration, task_in=plan.task_in, error_in=plan.error_in,
                **dict(plan.arguments),
            ).error
        state = commit_cleanup_step(state, plan, returned_error)
        if event.kind == "stop_reset":
            memory = replace(memory, stop=False)
    return CleanupTrace(
        memory,
        state.psp_error_seed,
        state.psp_error_after,
        state.psp_index,
        tuple(sorted(bank for bank, error in state.tpg_errors)),
        tuple(sorted(state.handlers)),
        state.stop_reset,
        cleanup_ready(state),
        state.frame_returned,
        boundary.calls[start:],
    )
