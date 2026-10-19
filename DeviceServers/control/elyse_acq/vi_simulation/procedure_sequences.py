"""Reviewed linear ACQ procedure plans, not hardware execution.

Frames are ordered. Effects within a frame are unordered: a Wait and a
local write have no dataflow ordering between them. Publications describe
the saved error-wire order, not successful remote delivery. External loops
may replace whole local clusters between any two reads/writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


def _write(bank, fields):
    return ("write", bank, tuple(sorted(fields)))


def _bools(bank, false=(), true=()):
    return _write(bank, [(i, False) for i in false] + [(i, True) for i in true])


def _phase(uid, *effects):
    return (uid, tuple(sorted(effects, key=repr)))


ACTION = _bools(35, true=(-1,))
P_DPS = ("publish", (("DPS", 36),))
P_CONTROL = ("publish", (("DPS", 36), ("EPS", 44), ("C4_OUT_DIO96", 15)))
P_STATUS = ("publish", (("DPS", 36), ("EPS", 44)))
W150 = ("wait", 150)
W100 = ("wait", 100)

# Indices are saved local-bank/cluster indices, not physical pin numbers.
# Field -1 is scalar ACTION. All other untouched fields are retained.
PROCEDURES = MappingProxyType(
    {
        3: (
            _phase("18796", ("wait", 1000), _bools(17, true=(0,)), ACTION),
            _phase("22995", _bools(17, false=(0,))),
            _phase("23795", ("wait", 800)),
            _phase("11213", ("wait", 1000), _bools(17, true=(3,))),
            _phase("31625", _bools(17, false=(3,))),
            _phase("23074", ("wait", 1000), _bools(15, true=(0,))),
            _phase("26107", _bools(15, false=(0,))),
            _phase("29164", ("wait", 500)),
            _phase("20440", ("wait", 1000), _bools(15, true=(2,))),
            _phase("18859", _bools(15, false=(2,))),
            _phase(
                "24540",
                _bools(36, false=(0,)),
                _bools(44, false=(0, 1, 5), true=(2, 8)),
            ),
            _phase("18950", P_DPS, ("wait", 5000)),
        ),
        4: (
            _phase("7963", W150, _bools(17, false=(1,)), ACTION),
            _phase("18101", _bools(17, true=(1,))),
            _phase("21010", ("wait", 400)),
            _phase("21712", W150, _bools(17, false=(4,))),
            _phase("22060", W150, _bools(17, true=(4,))),
            _phase(
                "22878", _bools(36, false=(1,)), _bools(44, false=(1, 2, 3), true=(5,))
            ),
            _phase("23117", P_DPS, W100),
        ),
        5: (
            _phase("34617", W150, _bools(15, true=(0,)), ACTION),
            _phase("34859", _bools(15, false=(0,))),
            _phase("35005", ("wait", 1000)),
            _phase("35043", W150, _bools(15, true=(2,))),
            _phase("25037", _bools(15, false=(2,))),
            _phase("29225", ("wait", 1000)),
            _phase("31989", W150, _bools(15, true=(2,))),
            _phase("33223", _bools(15, false=(2,))),
            _phase(
                "35413", _bools(36, false=(2,)), _bools(44, false=(6, 11), true=(8,))
            ),
            _phase("35570", P_DPS, W100),
        ),
        6: (
            _phase(
                "26598",
                (
                    "subsequence",
                    (
                        _phase("53835", ("call_clear_error", "1_Focales OFF.vi")),
                        _phase("53932", ("wait", 500)),
                    ),
                ),
                W150,
                ACTION,
            ),
            _phase("55133", W150, _bools(15, false=(8,))),
            _phase("31199", _bools(15, true=(8,))),
            _phase("27271", ("wait", 1000)),
            _phase("33229", W150, _bools(15, false=(17,))),
            _phase("35308", _bools(15, true=(17,))),
            _phase("35199", ("wait", 1000)),
            _phase("36873", W150, _bools(15, false=(6,))),
            _phase("23583", _bools(15, true=(6,))),
            _phase("23519", ("wait", 1000)),
            _phase("25035", W150, _bools(15, false=(4,))),
            _phase("29452", _bools(15, true=(4,))),
            _phase("23628", ("wait", 2000)),
            _phase("29980", W150, _bools(15, false=(1,))),
            _phase("32864", _bools(15, true=(1,))),
            _phase(
                "28661",
                _bools(36, false=(3,)),
                _bools(44, false=(8, 9, 14, 20, 26, 32), true=(11, 17, 23, 29, 35)),
            ),
            _phase("35146", P_DPS, W100),
        ),
        7: (
            _phase("23304", W150, _bools(15, false=(4,)), ACTION),
            _phase("23392", _bools(15, true=(4,))),
            _phase(
                "24497", _bools(36, false=(5,)), _bools(44, false=(14, 15), true=(17,))
            ),
            _phase("25430", P_DPS, W100),
        ),
        8: (
            _phase("26246", W150, _bools(15, false=(6,)), ACTION),
            _phase("26330", _bools(15, true=(6,))),
            _phase(
                "26962", _bools(36, false=(7,)), _bools(44, false=(20, 21), true=(23,))
            ),
            _phase("27900", P_DPS, W100),
        ),
        9: (
            _phase("31017", W150, _bools(15, false=(17,)), ACTION),
            _phase("31192", _bools(15, true=(17,))),
            _phase(
                "31360", _bools(36, false=(9,)), _bools(44, false=(26, 27), true=(29,))
            ),
            _phase("31482", P_DPS, W100),
        ),
        10: (
            _phase(
                "23518",
                (
                    "subsequence",
                    (
                        _phase("57312", ("call_handle_error", "1_Focales OFF.vi")),
                        _phase("47864", ("wait", 500)),
                    ),
                ),
                W150,
                ACTION,
            ),
            _phase("54833", W150, _bools(15, false=(8,))),
            _phase("23774", _bools(15, true=(8,))),
            _phase(
                "23880", _bools(36, false=(11,)), _bools(44, false=(32, 33), true=(35,))
            ),
            _phase("24054", P_DPS, W100),
        ),
        11: (
            _phase("33697", W150, _bools(15, true=(2,)), ACTION),
            _phase("33780", _bools(15, false=(2,))),
            _phase("33828", _bools(36, false=(12,)), _bools(44, false=(36,))),
            _phase("33986", P_DPS, W100),
        ),
        12: (
            _phase("38074", W150, _bools(15, true=(3,)), ACTION),
            _phase("38157", _bools(15, false=(3,))),
            _phase("38205", ("wait", 3000)),
            _phase("38235", W150, _bools(15, true=(2,))),
            _phase("38295", _bools(15, false=(2,))),
            _phase(
                "38483", _bools(36, false=(4,)), _bools(44, false=(12, 17), true=(14,))
            ),
            _phase("38592", P_DPS, W100),
        ),
        13: (
            _phase("24338", W150, _bools(15, true=(5,)), ACTION),
            _phase("25366", _bools(15, false=(5,))),
            _phase("28640", ("wait", 500)),
            _phase("28837", W150, _bools(15, true=(2,))),
            _phase("28946", _bools(15, false=(2,))),
            _phase("28995", ("wait", 250)),
            _phase(
                "29025", _bools(36, false=(6,)), _bools(44, false=(18, 23), true=(20,))
            ),
            _phase("29203", P_DPS, W100),
        ),
        14: (
            _phase("36023", W150, _bools(15, true=(16,)), ACTION),
            _phase("36115", _bools(15, false=(16,))),
            _phase("36163", ("wait", 500)),
            _phase("36193", W150, _bools(15, true=(2,))),
            _phase("36255", _bools(15, false=(2,))),
            _phase("36304", ("wait", 250)),
            _phase(
                "36334", _bools(36, false=(8,)), _bools(44, false=(24, 29), true=(26,))
            ),
            _phase("36443", P_DPS, W100),
        ),
        15: (
            _phase("40162", W150, _bools(15, true=(7,)), ACTION),
            _phase("40245", _bools(15, false=(7,))),
            _phase(
                "40293",
                (
                    "subsequence",
                    (
                        _phase("46840", ("wait", 29000)),
                        _phase("48404", ("call_handle_error", "1_Focales ON.vi")),
                        _phase("49054", ("wait", 1500)),
                    ),
                ),
            ),
            _phase("40323", W150, _bools(15, true=(2,))),
            _phase("40383", _bools(15, false=(2,))),
            _phase("40432", ("wait", 250)),
            _phase(
                "40463", _bools(36, false=(10,)), _bools(44, false=(30, 35), true=(32,))
            ),
            _phase("40573", P_DPS, W100),
        ),
        16: (
            _phase("30270", _bools(17, true=(9, 11, 15, 17, 21, 23)), ACTION),
            _phase("46661", ("wait", 500)),
            _phase("24037", _bools(17, true=(27, 29))),
            _phase("37517", ("wait", 500)),
            _phase("39214", _bools(17, true=(25, 31, 32, 33, 34, 35, 36, 37, 38, 39))),
            _phase(
                "43205",
                _write(9, [(i, 0.0) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)]),
                _write(10, [(i, 0.0) for i in (0, 1, 3, 4, 5, 6, 7, 8, 9)]),
            ),
            _phase(
                "44981",
                (
                    "conditioning_ramp",
                    "48496",
                    10,
                    (0, 1, 3, 4, 6, 7, 8, 9),
                    160,
                    0.0,
                    0.1,
                    100,
                ),
            ),
            _phase("39672", ("wait", 20000)),
            _phase(
                "41847",
                (
                    "conditioning_ramp",
                    "41875",
                    10,
                    (0, 1, 3, 4, 6, 7, 8, 9),
                    320,
                    16.0,
                    -0.1,
                    100,
                ),
            ),
            _phase("37203", ("wait", 20000)),
            _phase(
                "39014",
                (
                    "conditioning_ramp",
                    "39041",
                    10,
                    (0, 1, 3, 4, 6, 7, 8, 9),
                    320,
                    -16.0,
                    0.1,
                    100,
                ),
            ),
            _phase("44468", ("wait", 20000)),
            _phase(
                "42572",
                (
                    "conditioning_ramp",
                    "42635",
                    10,
                    (0, 1, 3, 4, 6, 7, 8, 9),
                    160,
                    16.0,
                    -0.1,
                    100,
                ),
            ),
            _phase(
                "32196",
                _bools(36, false=(20,)),
                _bools(44, false=(56, 64, 67), true=(58,)),
            ),
            _phase(
                "32353", ("publish", (("C3_OUT_DIO96", 17), ("DPS", 36), ("EPS", 44)))
            ),
            _phase("32799", ("wait", 200)),
        ),
        17: (
            _phase(
                "42539",
                _write(9, [(i, 0.0) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)]),
                _write(10, [(i, 0.0) for i in (0, 1, 3, 4, 5, 6, 7, 8, 9)]),
                ACTION,
            ),
            _phase("39882", ("publish", (("C6NI6703", 9), ("C7NI6703", 10)))),
            _phase("35750", ("wait", 1000)),
            _phase(
                "1926",
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
            _phase(
                "42901",
                _bools(36, false=(23,)),
                _bools(44, false=(58, 61, 64, 65), true=(67,)),
            ),
            _phase(
                "41314", ("publish", (("C3_OUT_DIO96", 17), ("DPS", 36), ("EPS", 44)))
            ),
            _phase("44333", ("wait", 200)),
        ),
        18: (
            _phase("34284", _bools(15, true=(29,)), ACTION),
            _phase(
                "35506", _bools(36, false=(13,)), _bools(44, false=(42,), true=(39,))
            ),
            _phase("35833", P_CONTROL),
            _phase("35244", W100),
        ),
        19: (
            _phase("43712", _bools(15, false=(29,)), ACTION),
            _phase(
                "43785", _bools(36, false=(14,)), _bools(44, false=(39,), true=(42,))
            ),
            _phase("43894", P_CONTROL),
            _phase("44089", W100),
        ),
        20: (
            _phase("53995", W150, _bools(15, true=(18,)), ACTION),
            _phase("54078", _bools(15, false=(18,))),
            _phase(
                "54126", _bools(36, false=(15,)), _bools(44, false=(49,), true=(45,))
            ),
            _phase("54238", P_CONTROL),
            _phase("50555", W100),
        ),
        21: (
            _phase("31696", W150, _bools(15, false=(19,)), ACTION),
            _phase("31883", _bools(15, true=(19,))),
            _phase(
                "32123", _bools(36, false=(17,)), _bools(44, false=(45,), true=(49,))
            ),
            _phase("32374", P_CONTROL),
            _phase("32729", W100),
        ),
        22: (
            _phase("32931", W150, _bools(15, true=(20,)), ACTION),
            _phase("33169", _bools(15, false=(20,))),
            _phase("33217", _bools(36, false=(16,))),
            _phase("33438", P_CONTROL),
            _phase("33886", W100),
        ),
        23: (
            _phase("45203", ("counter_start_clear_chain", 21, (3, 4)), ACTION),
            _phase(
                "45276", _bools(36, false=(18,)), _bools(44, false=(55,), true=(52,))
            ),
            _phase("45385", P_STATUS),
            _phase("45576", W100),
        ),
        24: (
            _phase("40802", ("counter_poll_stop_clear", 21, 3, "2745", 40, 1), ACTION),
            _phase("49141", ("counter_poll_stop_clear", 21, 4, "49233", 40, 1)),
            _phase(
                "41162", _bools(36, false=(19,)), _bools(44, false=(52,), true=(42,))
            ),
            _phase("41284", P_STATUS),
            _phase("41447", W100),
        ),
        25: (
            _phase(
                "38812",
                _write(9, [(i, 0.0) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9)]),
                _write(10, [(i, 0.0) for i in (0, 1, 3, 4, 6, 7, 8, 9)]),
                ACTION,
            ),
            _phase("38987", ("publish", (("C6NI6703", 9), ("C7NI6703", 10)))),
            _phase("39227", ("wait", 1000)),
            _phase(
                "39387", _bools(36, false=(21,)), _bools(44, false=(59, 64), true=(61,))
            ),
            _phase("39743", P_STATUS),
            _phase("39965", ("wait", 200)),
        ),
    }
)


def plan_procedure(event: int, new_value: bool):
    """No hidden guard: only the reviewed NewVal Boolean case is applied."""
    if type(event) is not int or event not in PROCEDURES:
        raise ValueError("procedure event is not qualified")
    if type(new_value) is not bool:
        raise TypeError("NewVal must be bool")
    return PROCEDURES[event] if new_value else ()


@dataclass(frozen=True)
class FrameProjection:
    diagram_uid: str
    local_writes: tuple
    publication_payloads: tuple
    wait_requests_ms: tuple[int, ...]
    subsequence_requests: tuple
    call_requests: tuple
    conditioning_requests: tuple
    counter_requests: tuple


BANK_SHAPES = {
    9: (10, float),
    10: (10, float),
    15: (32, bool),
    17: (40, bool),
    36: (29, bool),
    44: (77, bool),
}


def all_phases():
    def walk(phase):
        yield phase
        for effect in phase[1]:
            if effect[0] == "subsequence":
                for cell in effect[1]:
                    yield from walk(cell)

    return tuple(
        p for rows in PROCEDURES.values() for phase in rows for p in walk(phase)
    )


def _snapshot(read_snapshots, bank):
    values = tuple(read_snapshots[bank])
    count, kind = BANK_SHAPES[bank]
    if len(values) != count or any(type(v) is not kind for v in values):
        raise ValueError("saved bank snapshot shape/type required")
    return values


def project_frame(
    diagram_uid: str, read_snapshots: Mapping[int, object]
) -> FrameProjection:
    """Project one frame using explicit local-read snapshots; no I/O or sleep.

    A publication is a request, not evidence of PSP success. Error handler
    completion, remote-delivery failure, and scheduling are not simulated.
    Returned whole-cluster writes can overwrite concurrent changes; they
    must not be silently merged into a current global state by this model.
    """
    qualified = dict(all_phases())
    if type(diagram_uid) is not str or diagram_uid not in qualified:
        raise ValueError("frame is not qualified")
    uid, effects = diagram_uid, qualified[diagram_uid]
    writes, publications, waits, subsequences, calls, ramps, counters = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for effect in effects:
        if effect[0] == "wait":
            waits.append(effect[1])
        elif effect[0] == "write":
            _, bank, changes = effect
            if bank == 35:
                writes.append((bank, changes[0][1]))
            else:
                state = list(_snapshot(read_snapshots, bank))
                for index, value in changes:
                    state[index] = value
                writes.append((bank, tuple(state)))
        elif effect[0] == "publish":
            publications.append(
                tuple(
                    (name, bank, _snapshot(read_snapshots, bank))
                    for name, bank in effect[1]
                )
            )
        elif effect[0] == "subsequence":
            subsequences.append(effect[1])
        elif effect[0] in ("call_clear_error", "call_handle_error"):
            calls.append(effect)
        elif effect[0] == "conditioning_ramp":
            ramps.append(effect[1:])
        elif effect[0] in ("counter_start_clear_chain", "counter_poll_stop_clear"):
            counters.append(effect)
        else:
            raise ValueError("effect is not qualified")
    return FrameProjection(
        uid,
        tuple(writes),
        tuple(publications),
        tuple(waits),
        tuple(subsequences),
        tuple(calls),
        tuple(ramps),
        tuple(counters),
    )


def counter_poll_should_stop(body_uid: str, iteration: int, done: bool) -> bool:
    """Saved predicate only: Done==True OR i>40; no query, sleep or task stop.

    If Done never becomes True, indices0..41 produce42 polls. This is not
    a42-ms upper deadline: calls and OS scheduling may take longer/block.
    Error output is not another exit predicate in the reviewed graph.
    """
    if body_uid not in ("2745", "49233"):
        raise ValueError("counter poll body is not qualified")
    if type(iteration) is not int or not 0 <= iteration <= 2147483647:
        raise ValueError("saved nonnegative I32 iteration required")
    if type(done) is not bool:
        raise TypeError("Done must be bool")
    return done or iteration > 40


def project_conditioning_iteration(
    body_uid: str, iteration: int, read_snapshot: tuple[float, ...]
) -> tuple[float, ...]:
    """Pure recurrence and C7 read-modify-write; no clipping or DAC writes.

    Explicitly initialized seeds are independent between ramps. Repeated
    binary64 addition preserves accumulated roundoff; seed+i*step would not.
    Intermediate requested values reach approximately +/-16.0. This is not
    a claim about physical card output range or permission to apply them.
    """
    ramps = [
        e
        for _, effects in all_phases()
        for e in effects
        if e[0] == "conditioning_ramp" and e[1] == body_uid
    ]
    if len(ramps) != 1:
        raise ValueError("conditioning body is not qualified")
    _, _, bank, fields, count, seed, step, _ = ramps[0]
    if type(iteration) is not int or not 0 <= iteration < count:
        raise ValueError("iteration outside saved For count")
    state = list(_snapshot({bank: read_snapshot}, bank))
    value = seed
    for _ in range(iteration + 1):
        value += step
    for field in fields:
        state[field] = value
    return tuple(state)
