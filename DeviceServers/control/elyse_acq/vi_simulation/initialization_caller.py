"""Pure frame-227 projection with explicit initializer/Clear Errors returns.

No callback, transport, default success, task validity or public-output seed
is inferred. The NI6071E public error output must be supplied just like every
other returned cluster; its existing subVI proof does not establish a writer.
"""

from dataclasses import dataclass

from .boundary import UNWIRED, ErrorCluster, TaskReference
from legacy.xp_acq_agent.elyse_agent.saved_initializer import (
    AI_ARGUMENTS as AI_ARGUMENTS,
    STAGES,
    route_ai_test_values,
    route_initializer_values,
    replay_saved_initializer as replay_saved_initializer,
)


@dataclass(frozen=True)
class InitializerFixture:
    """Caller-visible outputs only; tokens do not establish valid NI tasks."""

    tasks: tuple[TaskReference, ...]
    error_out: ErrorCluster

    def __post_init__(self):
        if type(self.tasks) is not tuple or any(
            type(t) is not TaskReference for t in self.tasks
        ):
            raise TypeError("initializer tasks require an immutable token tuple")
        if type(self.error_out) is not ErrorCluster:
            raise TypeError("caller-visible error output must be supplied")


@dataclass(frozen=True)
class CallerStep:
    node_uid: str
    operation: str
    error_in: object
    error_out: ErrorCluster
    arguments: tuple
    local_assignments: tuple


@dataclass(frozen=True)
class CallerProjection:
    steps: tuple[CallerStep, ...]
    next_read_error: ErrorCluster


@dataclass(frozen=True)
class AiFallbackProjection:
    steps: tuple[CallerStep, ...]
    original_read_error: ErrorCluster
    sequence_local_306: ErrorCluster


def project_ai_test_frame(*, read_error, fallback_result=None, clear_returns=None):
    """Project only the error-dependent suffix after the supplied test read.

    The read's sample-count port is unwired. Its original returned error also
    writes a separate sequence local, untouched by fallback clearing. Task
    clear returns and replacement references are supplied, never executed.
    The saved -200284 annotation is not an equality test.
    """
    if type(read_error) is not ErrorCluster:
        raise TypeError("test-read returned error must be supplied")
    if not read_error.status:
        if fallback_result is not None or clear_returns not in (None, {}):
            raise ValueError("no-error test read cannot consume fallback fixtures")
        return AiFallbackProjection((), read_error, read_error)
    if (
        type(fallback_result) is not InitializerFixture
        or len(fallback_result.tasks) != 2
    ):
        raise TypeError("two explicit replacement AI tasks and returned error required")
    required = {"2134", "4034", "7931"}
    if fallback_result.error_out.status:
        required.add("2268")
    if type(clear_returns) is not dict or set(clear_returns) != required:
        raise ValueError("explicit returns must match selected fallback calls")
    if any(type(e) is not ErrorCluster for e in clear_returns.values()):
        raise TypeError("fallback calls require explicit ErrorCluster returns")
    result = route_ai_test_values(read_error, fallback_result, clear_returns)
    return AiFallbackProjection(
        tuple(CallerStep(*step) for step in result.steps),
        result.original_read_error,
        result.sequence_local_306,
    )


def project_initializer_frame(fixtures, *, clear_returns):
    """Trace error-chain order, not total scheduling order of bank writes.

    Every stage runs if previous calls return. Error.status selects Clear
    Errors, but that call's returned error is an explicit fixture, not assumed
    False. Code/source cannot independently select the error arm. Whole task
    assignments are independent of each stage's error arm. No retry, stop,
    cleanup or readiness transition is added to this frame.
    """
    if type(fixtures) is not tuple or len(fixtures) != len(STAGES):
        raise TypeError("four ordered initializer fixtures required")
    if type(clear_returns) is not dict:
        raise TypeError("explicit Clear Errors return dictionary required")
    required_clears = set()
    for fixture, (_, _, clear_uid, _, banks) in zip(fixtures, STAGES):
        if type(fixture) is not InitializerFixture:
            raise TypeError("initializer fixture type required")
        if len(fixture.tasks) != sum(count for _, count in banks):
            raise ValueError("caller task-output cardinality differs from saved source")
        if fixture.error_out.status:
            required_clears.add(clear_uid)
    if set(clear_returns) != required_clears:
        raise ValueError("Clear Errors fixtures must match selected error arms exactly")
    if any(type(e) is not ErrorCluster for e in clear_returns.values()):
        raise TypeError(
            "Clear Errors returned clusters must be explicit ErrorCluster values"
        )
    result = route_initializer_values(fixtures, clear_returns, UNWIRED)
    return CallerProjection(tuple(CallerStep(*step) for step in result.steps), result.next_read_error)
