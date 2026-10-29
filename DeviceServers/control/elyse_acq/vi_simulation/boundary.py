"""In-memory external returns for saved-VI controller traces, never a driver.

Default fixtures pass a wired error/task through; an unwired error receives
NO_ERROR and Create Task receives a synthetic reference. These are explicit
simulation assumptions, not claims about DAQmx behavior. Overrides can model
arbitrary returned errors/references without changing the controller wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Mapping


class MissingValue(Enum):
    UNWIRED = "unwired"
    UNASSIGNED = "unassigned"
    UNSUPPLIED = "unsupplied_external_return"


UNWIRED = MissingValue.UNWIRED
UNASSIGNED = MissingValue.UNASSIGNED
UNSUPPLIED = MissingValue.UNSUPPLIED


@dataclass(frozen=True)
class ErrorCluster:
    status: bool
    code: int
    source: str = ""

    def __post_init__(self):
        if type(self.status) is not bool or type(self.code) is not int:
            raise TypeError("error status/code require bool/int, respectively")
        if type(self.source) is not str:
            raise TypeError("error source requires str")


NO_ERROR = ErrorCluster(False, 0)


@dataclass(frozen=True)
class TaskReference:
    """Opaque simulation token; does not imply a valid or started NI task."""

    token: str

    def __post_init__(self):
        if type(self.token) is not str or not self.token:
            raise ValueError("simulation task token requires a nonempty string")


@dataclass(frozen=True)
class SourceVi:
    name: str
    sha256: str


@dataclass(frozen=True)
class CallKey:
    vi: str
    node_uid: str
    iteration: int | None = None


@dataclass(frozen=True)
class SampleMatrix:
    """Immutable channel-by-sample numeric fixture, never a NumPy/NI buffer."""

    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self):
        if (
            type(self.rows) is not tuple
            or any(type(row) is not tuple for row in self.rows)
            or any(
                type(value) not in (int, float) for row in self.rows for value in row
            )
            or len({len(row) for row in self.rows}) > 1
        ):
            raise TypeError(
                "sample matrix requires rectangular immutable numeric tuples"
            )


@dataclass(frozen=True)
class BoundaryReturn:
    task: TaskReference | MissingValue
    error: ErrorCluster
    data: tuple | SampleMatrix | MissingValue = UNSUPPLIED


@dataclass(frozen=True)
class BoundaryCall:
    key: CallKey
    diagram_uid: str
    operation: str
    arguments: tuple[tuple[str, object], ...]
    task_in: TaskReference | MissingValue
    error_in: ErrorCluster | MissingValue
    returned: BoundaryReturn

    @property
    def args(self) -> dict[str, object]:
        return dict(self.arguments)


@dataclass(frozen=True)
class InitializerResult:
    source: SourceVi
    tasks: tuple[TaskReference, ...]
    error_out: ErrorCluster | MissingValue
    internal_error: ErrorCluster
    calls: tuple[BoundaryCall, ...]

    def to_dict(self) -> dict:
        def error(value):
            if isinstance(value, MissingValue):
                return {"connection": value.value}
            return {"status": value.status, "code": value.code, "source": value.source}

        def task(value):
            return (
                {"connection": value.value}
                if isinstance(value, MissingValue)
                else value.token
            )

        return {
            "mode": "simulation-only",
            "source_vi": self.source.name,
            "source_sha256": self.source.sha256,
            "external_returns": "supplied fixtures, not driver observations",
            "tasks": [task(t) for t in self.tasks],
            "error_out": error(self.error_out),
            "internal_error": error(self.internal_error),
            "calls": [
                {
                    "node_uid": c.key.node_uid,
                    "diagram_uid": c.diagram_uid,
                    "iteration": c.key.iteration,
                    "operation": c.operation,
                    "arguments": c.args,
                    "task_in": task(c.task_in),
                    "error_in": error(c.error_in),
                    "task_out": task(c.returned.task),
                    "error_returned": error(c.returned.error),
                }
                for c in self.calls
            ],
        }


@dataclass(frozen=True)
class SampleClockInputs:
    """Caller values, not inferred root defaults or hardware-valid settings.

    Python-only representation guards reject nonfinite rates and negative or
    noninteger counts. Finite zero/negative rates are forwarded, not repaired;
    whether an external call rejects them belongs to its supplied fixture.
    """

    rate_hz: float
    samples_per_channel: int

    def __post_init__(self):
        if type(self.rate_hz) not in (int, float) or not isfinite(self.rate_hz):
            raise ValueError("rate_hz requires a finite numeric value")
        if type(self.samples_per_channel) is not int or self.samples_per_channel < 0:
            raise ValueError("samples_per_channel requires a nonnegative integer")


class ScriptedBoundary:
    """Record calls and substitute data; accepts no adapter, callback or socket.

    One instance represents one trace. Duplicate keys and unused fixtures are
    rejected to expose faulty tests, not as legacy controller behavior.
    """

    __slots__ = ("_errors", "_tasks", "_data", "_calls", "_keys")

    def __init__(
        self,
        *,
        errors: Mapping[CallKey, ErrorCluster] | None = None,
        tasks: Mapping[CallKey, TaskReference] | None = None,
        data: Mapping[CallKey, tuple | SampleMatrix] | None = None,
    ):
        self._errors = dict(errors or {})
        self._tasks = dict(tasks or {})
        self._data = dict(data or {})
        for key, value in self._errors.items():
            if type(key) is not CallKey or type(value) is not ErrorCluster:
                raise TypeError("error fixtures require CallKey -> ErrorCluster")
        for key, value in self._tasks.items():
            if type(key) is not CallKey or type(value) is not TaskReference:
                raise TypeError("task fixtures require CallKey -> TaskReference")
        for key, value in self._data.items():
            if type(key) is not CallKey or not (
                type(value) is SampleMatrix
                or (
                    type(value) is tuple
                    and all(type(item) in (bool, int, float, str) for item in value)
                )
            ):
                raise TypeError(
                    "data fixtures require CallKey -> immutable scalar tuple "
                    "or SampleMatrix"
                )
        self._calls: list[BoundaryCall] = []
        self._keys: set[CallKey] = set()

    @property
    def calls(self) -> tuple[BoundaryCall, ...]:
        return tuple(self._calls)

    def invoke(
        self,
        source_vi: SourceVi,
        node_uid: str,
        diagram_uid: str,
        operation: str,
        *,
        iteration: int | None = None,
        task_in: TaskReference | MissingValue = UNWIRED,
        error_in: ErrorCluster | MissingValue = UNWIRED,
        **arguments,
    ) -> BoundaryReturn:
        key = CallKey(source_vi.name, node_uid, iteration)
        if key in self._keys:
            raise ValueError(f"duplicate simulation call key: {key}")
        if type(task_in) is not TaskReference and task_in is not UNWIRED:
            raise TypeError("task input requires a simulation reference or UNWIRED")
        if type(error_in) is not ErrorCluster and error_in is not UNWIRED:
            raise TypeError("error input requires ErrorCluster or UNWIRED")

        def is_data(value):
            return type(value) in (bool, int, float, str) or (
                type(value) is tuple
                and all(type(item) in (bool, int, float, str) for item in value)
            )

        if any(not is_data(v) for v in arguments.values()):
            raise TypeError(
                "trace arguments require scalars or scalar tuples, "
                "not executable adapters"
            )
        default_task = (
            TaskReference(f"sim:{source_vi.name}/{node_uid}")
            if operation == "create_task"
            else task_in
        )
        returned = BoundaryReturn(
            self._tasks.get(key, default_task),
            self._errors.get(key, NO_ERROR if error_in is UNWIRED else error_in),
            self._data.get(key, UNSUPPLIED),
        )
        self._calls.append(
            BoundaryCall(
                key,
                diagram_uid,
                operation,
                tuple(arguments.items()),
                task_in,
                error_in,
                returned,
            )
        )
        self._keys.add(key)
        return returned

    def assert_all_fixtures_used(self):
        unused = (set(self._errors) | set(self._tasks) | set(self._data)) - self._keys
        if unused:
            raise ValueError(f"unused simulation fixtures: {sorted(map(str, unused))}")


def require_boundary(boundary: ScriptedBoundary):
    # A live HardwareAdapter is not a supported substitution for this recorder.
    if type(boundary) is not ScriptedBoundary:
        raise TypeError("only the in-memory ScriptedBoundary is supported")


def require_error(error: ErrorCluster):
    if type(error) is not ErrorCluster:
        raise TypeError("caller error requires ErrorCluster")
