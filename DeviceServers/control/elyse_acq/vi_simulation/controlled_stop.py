"""Original ACQ outer stop: inert, frame-ordered plans and explicit snapshots.

This is not the event6 shutdown procedure or a hardware emergency controller.
The separate I/O loop may read/write between any two effects below. Same-frame
effects have no mutual ordering. No sleep, device call or global state exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from .boundary import UNSUPPLIED
from .procedure_sequences import BANK_SHAPES
from .runtime_io import RuntimeIoResult, _record_io_frame


def _write(bank, fields):
    return ("write", bank, tuple(sorted(fields)))


def _bools(bank, false=(), true=()):
    return _write(bank, [(i, False) for i in false] + [(i, True) for i in true])


def _phase(uid, *effects):
    return (uid, tuple(sorted(effects, key=repr)))


CONTROLLED_STOP = (
    _phase("60323", ("ht_ramp", "18613", "42212")),
    _phase(
        "51962",
        _bools(35, true=(-1,)),
        (
            "subsequence",
            (
                _phase(
                    "47671",
                    ("counter_poll_stop_clear", 21, 3, "47770", 40, 1),
                    _write(50, [(-1, 5.0)]),
                ),
                _phase("47989", ("counter_poll_stop_clear", 21, 4, "48062", 40, 1)),
                _phase("48537", ("wait", 1000)),
            ),
        ),
    ),
    _phase(
        "43360",
        (
            "subsequence",
            (
                _phase(
                    "49114",
                    ("wait", 150),
                    _bools(15, false=(19,)),
                    _write(50, [(-1, 4.0)]),
                ),
                _phase("49284", _bools(15, true=(19,))),
                _phase("49853", ("wait", 1000)),
            ),
        ),
    ),
    _phase(
        "129793",
        (
            "subsequence",
            (
                _phase(
                    "128452",
                    _write(50, [(-1, 3.0)]),
                    _write(9, [(i, 0.0) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)]),
                    _write(10, [(i, 0.0) for i in (0, 1, 3, 4, 5, 6, 7, 8, 9)]),
                ),
                _phase("128743", ("wait", 1000)),
                _phase(
                    "128773",
                    _bools(
                        17,
                        false=(
                            9,
                            11,
                            15,
                            17,
                            21,
                            23,
                            25,
                            27,
                            29,
                            31,
                            32,
                            33,
                            34,
                            35,
                            36,
                            37,
                            38,
                            39,
                        ),
                    ),
                ),
                _phase("129221", ("wait", 1000)),
            ),
        ),
    ),
    _phase(
        "1722",
        (
            "subsequence",
            (
                _phase(
                    "42424",
                    ("wait", 150),
                    _bools(15, false=(8,)),
                    _write(50, [(-1, 2.0)]),
                ),
                _phase("42549", _bools(15, true=(8,))),
                _phase("42712", ("wait", 1000)),
                _phase("42763", ("wait", 150), _bools(15, false=(17,))),
                _phase("42895", _bools(15, true=(17,))),
                _phase("43136", ("wait", 1000)),
                _phase("43197", ("wait", 150), _bools(15, false=(6,))),
                _phase("43264", _bools(15, true=(6,))),
                _phase("43315", ("wait", 1000)),
                _phase("43345", ("wait", 150), _bools(15, false=(4,))),
                _phase("43418", _bools(15, true=(4,))),
                _phase("43468", ("wait", 2000)),
                _phase("43520", ("wait", 150), _bools(15, false=(1,))),
                _phase("43589", _bools(15, true=(1,))),
                _phase("43933", ("wait", 1000)),
            ),
        ),
    ),
    _phase(
        "52159",
        (
            "subsequence",
            (
                _phase(
                    "54293",
                    ("wait", 150),
                    _bools(17, false=(1,)),
                    _write(50, [(-1, 1.0)]),
                ),
                _phase("54391", _bools(17, true=(1,))),
                _phase("54440", ("wait", 400)),
                _phase("54470", ("wait", 150), _bools(17, false=(4,))),
                _phase("54530", ("wait", 150), _bools(17, true=(4,))),
                _phase(
                    "54590",
                    _bools(36, false=(1,)),
                    _bools(44, false=(1, 2, 3), true=(5,)),
                ),
                _phase(
                    "58827",
                    _bools(36, false=(1,)),
                    _bools(44, false=(1, 2, 3), true=(5,)),
                ),
                _phase("54731", ("wait", 100)),
            ),
        ),
    ),
    _phase(
        "64826",
        ("wait", 1000),
        _bools(46, true=(-1,)),
        _bools(47, false=(-1,)),
        _write(50, [(-1, 0.0)]),
    ),
)


def all_stop_phases():
    def walk(phase):
        yield phase
        for effect in phase[1]:
            if effect[0] == "subsequence":
                for child in effect[1]:
                    yield from walk(child)

    return tuple(row for phase in CONTROLLED_STOP for row in walk(phase))


@dataclass(frozen=True)
class StopFrameProjection:
    diagram_uid: str
    local_writes: tuple
    wait_requests_ms: tuple[int, ...]
    subsequence_requests: tuple
    loop_requests: tuple
    counter_requests: tuple


def _snapshot(bank, supplied):
    size, kind = (10, float) if bank == 12 else BANK_SHAPES[bank]
    values = tuple(supplied)
    if len(values) != size or any(type(v) is not kind for v in values):
        raise ValueError("saved local bank snapshot shape/type required")
    if kind is float and not all(math.isfinite(v) for v in values):
        raise ValueError("nonfinite DBL is outside qualification")
    return values


def project_stop_frame(
    uid: str, snapshots: Mapping[int, object]
) -> StopFrameProjection:
    """Return effects of one frame, not a completed shutdown or ordered effects."""
    if type(uid) is not str or uid not in dict(all_stop_phases()):
        raise ValueError("controlled-stop frame is not qualified")
    writes, waits, sequences, loops, counters = [], [], [], [], []
    for effect in dict(all_stop_phases())[uid]:
        if effect[0] == "write":
            _, bank, fields = effect
            if bank in (35, 46, 47, 50):
                writes.append((bank, fields[0][1]))
            else:
                state = list(_snapshot(bank, snapshots[bank]))
                for index, value in fields:
                    state[index] = value
                writes.append((bank, tuple(state)))
        elif effect[0] == "wait":
            waits.append(effect[1])
        elif effect[0] == "subsequence":
            sequences.append(effect[1])
        elif effect[0] == "ht_ramp":
            loops.append(effect)
        elif effect[0] == "counter_poll_stop_clear":
            counters.append(effect)
        else:
            raise ValueError("unsupported controlled-stop effect")
    return StopFrameProjection(
        uid,
        tuple(writes),
        tuple(waits),
        tuple(sequences),
        tuple(loops),
        tuple(counters),
    )


@dataclass(frozen=True)
class HtRampIteration:
    should_stop: bool
    local_writes: tuple
    wait_requests_ms: tuple[int, ...]


def project_ht_ramp_iteration(check_snapshot, bundle_snapshot=None) -> HtRampIteration:
    """Use independent check and RMW reads; no zeroing, clamp or iteration limit.

    The saved strict comparison is command<6.6. Equality requests another
    subtraction. The root's ordinary PSP receiver has already exited at the
    five-loop join before this outer-phase ramp. Arbitrary supplied snapshots
    can still represent unqualified indirect/UI writers or another invocation,
    not overlap with that exited receiver. The 500ms Wait shares a frame with
    the RMW write; it does not order that write.
    """
    checked = _snapshot(12, check_snapshot)[0]
    writes = [(50, 6.0), (48, checked)]
    if checked < 6.6:
        return HtRampIteration(True, tuple(writes), ())
    if bundle_snapshot is None:
        raise ValueError("False arm requires a separate bundle-base snapshot")
    state = list(_snapshot(12, bundle_snapshot))
    state[0] = checked - 0.1
    writes.append((12, tuple(state)))
    return HtRampIteration(False, tuple(writes), (500,))


def controlled_counter_should_stop(body_uid: str, iteration: int, done: bool) -> bool:
    """Done OR i>40: 42 calls if Done stays False, not a 42ms deadline."""
    if body_uid not in ("47770", "48062"):
        raise ValueError("controlled-stop poll body is not qualified")
    if type(iteration) is not int or not 0 <= iteration <= 2147483647:
        raise ValueError("saved nonnegative I32 iteration required")
    if type(done) is not bool:
        raise TypeError("Done must be bool")
    return done or iteration > 40


@dataclass(frozen=True)
class StopOperatorIteration:
    sequence_requests: tuple
    enabled_property_requests: tuple
    wait_requests_ms: tuple[int, ...]
    sampled_should_stop: bool


def project_stop_operator_iteration(general_stop: bool, emergency_stop: bool):
    """Separate local read fixtures, not an atomic global state or interrupt.

    A sampled True stop flag does not cancel an entered seven-phase sequence.
    The condition, case and50ms Wait have no mutual dataflow ordering.
    """
    if type(general_stop) is not bool or type(emergency_stop) is not bool:
        raise TypeError("saved Boolean local snapshots required")
    properties = (
        ()
        if general_stop
        else tuple(
            (ddo, "DisabledEnum", 0)
            for ddo in ("79089", "40722", "70708", "8957", "11783")
        )
    )
    return StopOperatorIteration(
        (CONTROLLED_STOP,) if general_stop else (), properties, (50,), emergency_stop
    )


def project_outer_tcp_decision(tcp_ed: bool):
    """After the five runtime loops join: False skips, True enters two loops."""
    if type(tcp_ed) is not bool:
        raise TypeError("saved TCP ED Boolean snapshot required")
    return ("41705", "42592") if tcp_ed else ()


@dataclass(frozen=True)
class StopIoIteration:
    io_result: RuntimeIoResult
    scalar_assignments: tuple
    wait_requests_ms: tuple[int, ...]
    sampled_should_stop: bool


def record_stop_io(boundary, *, emergency_stop: bool, **io_snapshots):
    """AI -> DIO -> AO -> handler continues during the separate stop sequence.

    Scalar49 is C2/local20 field7, not C1/local19 or an output-card voltage.
    Unprovided/short-array padding remains unknown. The sampled46 condition
    is independent of the I/O errors and does not cancel that iteration.
    """
    if type(emergency_stop) is not bool:
        raise TypeError("saved emergency-stop Boolean snapshot required")
    result = _record_io_frame(
        boundary, frame_uid="41713", handler_uid="55822", **io_snapshots
    )
    prefix = dict(result.local_assignments)[20].known_prefix
    ht_readback = (
        prefix[7] if type(prefix) is tuple and len(prefix) >= 8 else UNSUPPLIED
    )
    return StopIoIteration(result, ((49, ht_readback),), (50,), emergency_stop)
