"""Exhaustive finite interleavings of one source-qualified runtime fault window.

Not a real scheduler or apparatus safety model. All three error arms have
entered, each performs its two independent saved writes, five loop conditions
sample stop once, and all entered body work returns. No other writer acts.
Driver/event outcomes and the next iteration remain outside this window.
"""

from dataclasses import dataclass

from .stop_schedule import ERROR_SITES, RUNTIME_LOOPS


@dataclass(frozen=True)
class FaultWindowOutcome:
    stop_after: bool
    tcp_after: bool
    exited_loops: tuple[str, ...]
    entered_outer_frame: bool
    outer_tcp_selector: bool | None
    order_count: int
    witness: tuple[str, ...]


def exhaustive_fault_window(*, stop_before, tcp_before):
    """Return every joint outcome, exact order counts, and one witness each.

    State merging preserves all 11! orders of six independent assignments and
    five independent condition reads. Counts describe this chosen finite
    window only; they are not likelihoods or native timing predictions.
    A True stop condition exits its loop only after the assumed body return.
    """
    if type(stop_before) is not bool or type(tcp_before) is not bool:
        raise TypeError("explicit initial Boolean stop/TCP values required")
    writes = tuple(item for _, entries in ERROR_SITES.values() for item in entries)
    # Independently enumerated source sites; do not silently broaden the model.
    if writes != (
        ("43027", 30, True),
        ("43040", 45, True),
        ("50011", 30, True),
        ("50019", 45, True),
        ("85095", 30, False),
        ("68231", 45, False),
    ) or RUNTIME_LOOPS != ("47483", "59483", "20601", "203", "102"):
        raise ValueError("source-qualified fault-window sites changed")
    # (completed-writes, completed-reads, captured-stop-bits, stop, TCP)
    layer = {(0, 0, 0, stop_before, tcp_before): (1, ())}
    for _ in range(len(writes) + len(RUNTIME_LOOPS)):
        following = {}
        for (wmask, rmask, captured, stop, tcp), (count, witness) in layer.items():
            successors = []
            for index, (uid, bank, value) in enumerate(writes):
                bit = 1 << index
                if not wmask & bit:
                    successors.append(
                        (
                            (
                                wmask | bit,
                                rmask,
                                captured,
                                value if bank == 30 else stop,
                                value if bank == 45 else tcp,
                            ),
                            "write:" + uid,
                        )
                    )
            for index, uid in enumerate(RUNTIME_LOOPS):
                bit = 1 << index
                if not rmask & bit:
                    successors.append(
                        (
                            (
                                wmask,
                                rmask | bit,
                                captured | (bit if stop else 0),
                                stop,
                                tcp,
                            ),
                            "read:" + uid,
                        )
                    )
            for state, action in successors:
                previous = following.get(state)
                following[state] = (
                    (previous[0] if previous else 0) + count,
                    previous[1] if previous else witness + (action,),
                )
        layer = following
    result = []
    for (_, _, captured, stop, tcp), (count, witness) in sorted(layer.items()):
        exited = tuple(
            uid for i, uid in enumerate(RUNTIME_LOOPS) if captured & (1 << i)
        )
        joined = len(exited) == len(RUNTIME_LOOPS)
        result.append(
            FaultWindowOutcome(
                stop,
                tcp,
                exited,
                joined,
                tcp if joined else None,
                count,
                witness,
            )
        )
    return tuple(result)
