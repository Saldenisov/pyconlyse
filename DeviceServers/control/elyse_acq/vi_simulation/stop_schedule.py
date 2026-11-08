"""Single-iteration, supplied-order stop-local trace; never a real scheduler.

Case entry and body completion are explicit inputs. Loop stop locals can be
read before an error branch writes the same bank; a condition consumes that
already captured Boolean after body completion. This does not synthesize
driver latency, the next iteration or an apparatus emergency-stop action.
"""

from dataclasses import dataclass

RUNTIME_LOOPS = ("47483", "59483", "20601", "203", "102")
# Source-case -> owner loop, two independent gRef node/bank/value writes.
ERROR_SITES = {
    "28682": ("20601", (("43027", 30, True), ("43040", 45, True))),
    "40346": ("203", (("50011", 30, True), ("50019", 45, True))),
    "40205": ("102", (("85095", 30, False), ("68231", 45, False))),
}


@dataclass(frozen=True)
class ErrorArmEntry:
    selector_uid: str


@dataclass(frozen=True)
class LocalAssignment:
    node_uid: str


@dataclass(frozen=True)
class StopLocalRead:
    loop_uid: str


@dataclass(frozen=True)
class BodyCompleted:
    loop_uid: str


@dataclass(frozen=True)
class OuterTcpRead:
    pass


@dataclass(frozen=True)
class StopReplay:
    stop_after: bool
    tcp_after: bool
    snapshots: tuple[tuple[str, bool], ...]
    completed: tuple[tuple[str, bool], ...]
    outer_tcp_snapshot: bool | None


def replay(schedule, *, stop_before, tcp_before):
    """Apply one caller-supplied schedule consistent with the checked boundaries.

    A BodyCompleted token asserts that all body work has returned/completed;
    the fixture cannot make a blocked call or Wait actually finish. Error arm
    entry is not an inferred NI/PSP result. Each entered arm must perform both
    saved writes before its owner body can complete, but writes have no mutual
    ordering. Replaying these partial orders demonstrates possible logical
    outcomes, not which schedule LabVIEW chose or a latency/fairness bound.
    """
    if type(stop_before) is not bool or type(tcp_before) is not bool:
        raise TypeError("explicit Boolean stop/TCP snapshots required")
    stop, tcp = stop_before, tcp_before
    entered, assigned, snapshots, completed = set(), set(), {}, {}
    outer = None
    writer_sites = {
        node: (case, owner, bank, value)
        for case, (owner, writes) in ERROR_SITES.items()
        for node, bank, value in writes
    }
    for item in schedule:
        if isinstance(item, ErrorArmEntry):
            case = item.selector_uid
            if (
                case not in ERROR_SITES
                or case in entered
                or ERROR_SITES[case][0] in completed
            ):
                raise ValueError(
                    "one known error arm entry before owner completion required"
                )
            entered.add(case)
        elif isinstance(item, LocalAssignment):
            node = item.node_uid
            if node not in writer_sites or node in assigned:
                raise ValueError("one known saved assignment site required")
            case, owner, bank, value = writer_sites[node]
            if case not in entered or owner in completed:
                raise ValueError(
                    "assignment must follow its arm entry before owner completion"
                )
            assigned.add(node)
            if bank == 30:
                stop = value
            else:
                tcp = value
        elif isinstance(item, StopLocalRead):
            loop = item.loop_uid
            if loop not in RUNTIME_LOOPS or loop in snapshots or loop in completed:
                raise ValueError(
                    "one condition snapshot per known loop/iteration required"
                )
            snapshots[loop] = stop
        elif isinstance(item, BodyCompleted):
            loop = item.loop_uid
            if loop not in snapshots or loop in completed:
                raise ValueError("loop body completion requires a prior stop snapshot")
            required = {
                node
                for case in entered
                if ERROR_SITES[case][0] == loop
                for node, _, _ in ERROR_SITES[case][1]
            }
            if not required <= assigned:
                raise ValueError(
                    "entered error-arm writes must complete with their body"
                )
            completed[loop] = snapshots[loop]
        elif isinstance(item, OuterTcpRead):
            if (
                outer is not None
                or set(completed) != set(RUNTIME_LOOPS)
                or not all(completed.values())
            ):
                raise ValueError("outer frame requires all five runtime loops to exit")
            outer = tcp
        else:
            raise TypeError("known inert schedule token required")
    return StopReplay(
        stop, tcp, tuple(snapshots.items()), tuple(completed.items()), outer
    )
