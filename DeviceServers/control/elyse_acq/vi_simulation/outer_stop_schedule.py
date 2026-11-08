"""Supplied schedules of the two outer-stop loops, never a shutdown driver.

Runtime completion must come from the five-loop replay. Every body/case return
is a fixture assertion: no device, UI, Wait or scheduler is executed. In
particular, emergency46 is sampled independently of General47 and cannot
cancel an already entered controlled-stop sequence.
"""

from dataclasses import dataclass, replace

from .stop_lifecycle import RuntimeStopTrace, StopMemory
from .stop_schedule import RUNTIME_LOOPS

OUTER_LOOPS = ("41705", "42592")
FINAL_FRAME_WRITES = {
    "18163": (46, True),
    "43536": (47, False),
}


@dataclass(frozen=True)
class GeneralStopRead:
    """Read local47 and choose one operator arm in the current iteration."""


@dataclass(frozen=True)
class EmergencyStopRead:
    loop_uid: str


@dataclass(frozen=True)
class ControlledFinalFrameEntered:
    """Fixture asserts the preceding six controlled-stop phases returned."""


@dataclass(frozen=True)
class ControlledFinalAssignment:
    node_uid: str


@dataclass(frozen=True)
class OperatorArmReturned:
    """All entered arm work, including properties/waits/calls, returned.

    For True, both last-frame flag writes must already be supplied. This token
    does not certify external success or assert a physical shutdown.
    """


@dataclass(frozen=True)
class OuterBodyReturned:
    """Fixture asserts ALL body work returned, not just its condition read."""

    loop_uid: str


@dataclass(frozen=True)
class OuterNextIteration:
    loop_uid: str


@dataclass(frozen=True)
class SuppliedOuterFlagChange:
    """Unqualified UI/indirect actor supplied explicitly, not performed."""

    bank: int
    value: bool


@dataclass(frozen=True)
class FinalCleanupEntry:
    """Advance the outer root sequence only after its stop frame returned."""


@dataclass(frozen=True)
class OuterDecision:
    loop_uid: str
    iteration: int
    sampled_emergency: bool


@dataclass(frozen=True)
class OperatorChoice:
    iteration: int
    sampled_general: bool

    @property
    def sequence_uid(self):
        return "51954" if self.sampled_general else None


@dataclass(frozen=True)
class OuterStopTrace:
    memory_after: StopMemory
    sampled_tcp: bool
    choices: tuple[OperatorChoice, ...]
    decisions: tuple[OuterDecision, ...]
    final_frame_entries: tuple[int, ...]
    final_assignments: tuple[tuple[int, str, int, bool], ...]
    returned_operator_arms: tuple[int, ...]
    exited_loops: tuple[str, ...]
    next_iteration_ready: tuple[str, ...]
    inflight_loops: tuple[str, ...]
    pending_snapshots: tuple[tuple[str, int, bool], ...]
    cleanup_ready: bool
    cleanup_entered: bool


def replay_outer_stop(schedule, *, runtime, emergency_stop, general_stop):
    """Retain captured conditions, independent flag writes and the two-loop join.

    General47 chooses an arm without a NewVal edge. An early emergency=False
    may therefore require another iteration AFTER the seven-phase sequence
    returned. Neither the final flag writes nor a later supplied external
    change rewrites an already captured condition. Even emergency=True needs
    the entered body to return. Nothing schedules a next iteration or bounds
    external-call/handler/Wait duration.
    """
    if type(runtime) is not RuntimeStopTrace or (
        type(runtime.outer_tcp_snapshot) is not bool
        or runtime.exited_loops != RUNTIME_LOOPS
        or runtime.inflight_loops
        or runtime.next_iteration_ready
        or runtime.pending_snapshots
    ):
        raise ValueError("completed five-loop runtime join and TCP read required")
    memory = StopMemory(
        runtime.stop_after, runtime.tcp_after, emergency_stop, general_stop
    )
    tcp = runtime.outer_tcp_snapshot
    status = dict.fromkeys(OUTER_LOOPS, "inflight") if tcp else {}
    iterations = dict.fromkeys(OUTER_LOOPS, 0)
    snapshots, choices, decisions = {}, [], []
    entries, assignments, returned = [], [], []
    general = None
    final_entered = arm_returned = False
    written = set()
    cleanup = False

    def require_body(loop):
        if loop not in status or status[loop] != "inflight":
            raise ValueError("known inflight outer body required")

    def ready():
        return not tcp or all(value == "exited" for value in status.values())

    for token in schedule:
        if cleanup:
            raise ValueError("outer trace ends at cleanup entry")
        if type(token) is FinalCleanupEntry:
            if not ready():
                raise ValueError("cleanup requires the two-loop outer join")
            cleanup = True
            continue
        if not tcp:
            raise ValueError("TCP=False has no entered outer loops")
        if type(token) is GeneralStopRead:
            require_body("42592")
            if general is not None:
                raise ValueError("one General read per operator iteration required")
            general = memory.general_stop
            choices.append(OperatorChoice(iterations["42592"], general))
        elif type(token) is EmergencyStopRead:
            loop = token.loop_uid
            require_body(loop)
            if loop in snapshots:
                raise ValueError("one emergency read per body required")
            snapshots[loop] = memory.emergency_stop
        elif type(token) is ControlledFinalFrameEntered:
            require_body("42592")
            if general is not True or final_entered or arm_returned:
                raise ValueError("one final frame in an entered True arm required")
            final_entered = True
            entries.append(iterations["42592"])
        elif type(token) is ControlledFinalAssignment:
            require_body("42592")
            node = token.node_uid
            if (
                not final_entered
                or arm_returned
                or node not in FINAL_FRAME_WRITES
                or node in written
            ):
                raise ValueError("one known entered final-frame assignment required")
            bank, value = FINAL_FRAME_WRITES[node]
            field = "emergency_stop" if bank == 46 else "general_stop"
            memory = replace(memory, **{field: value})
            written.add(node)
            assignments.append((iterations["42592"], node, bank, value))
        elif type(token) is OperatorArmReturned:
            require_body("42592")
            if (
                general is None
                or arm_returned
                or (
                    general
                    and (not final_entered or written != set(FINAL_FRAME_WRITES))
                )
            ):
                raise ValueError("entered complete operator arm required")
            arm_returned = True
            returned.append(iterations["42592"])
        elif type(token) is OuterBodyReturned:
            loop = token.loop_uid
            require_body(loop)
            if loop not in snapshots or (loop == "42592" and not arm_returned):
                raise ValueError("body requires condition and all entered arm work")
            captured = snapshots.pop(loop)
            decisions.append(OuterDecision(loop, iterations[loop], captured))
            status[loop] = "exited" if captured else "next"
        elif type(token) is OuterNextIteration:
            loop = token.loop_uid
            if loop not in status or status[loop] != "next":
                raise ValueError("next body requires a completed False condition")
            if iterations[loop] == 2147483647:
                raise ValueError("I32 loop-index overflow is not qualified")
            iterations[loop] += 1
            status[loop] = "inflight"
            if loop == "42592":
                general = None
                final_entered = arm_returned = False
                written.clear()
        elif type(token) is SuppliedOuterFlagChange:
            if type(token.bank) is not int or token.bank not in (46, 47):
                raise ValueError("only separately supplied banks46/47 supported")
            if type(token.value) is not bool:
                raise TypeError("explicit Boolean external flag required")
            field = "emergency_stop" if token.bank == 46 else "general_stop"
            memory = replace(memory, **{field: token.value})
        else:
            raise TypeError("known inert outer-loop token required")
    return OuterStopTrace(
        memory,
        tcp,
        tuple(choices),
        tuple(decisions),
        tuple(entries),
        tuple(assignments),
        tuple(returned),
        tuple(loop for loop in OUTER_LOOPS if status.get(loop) == "exited"),
        tuple(loop for loop in OUTER_LOOPS if status.get(loop) == "next"),
        tuple(loop for loop in OUTER_LOOPS if status.get(loop) == "inflight"),
        tuple((loop, iterations[loop], value) for loop, value in snapshots.items()),
        ready(),
        cleanup,
    )
