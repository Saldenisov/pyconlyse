"""Hardware-independent bounded search used by the laser-pointing controller.

The optical response is not assumed to be linear.  A two-dimensional pattern
search is deliberately used instead of a gradient optimiser: it tolerates a
noisy camera objective, never proposes a point outside the supplied bounds,
and can be cancelled between measurements.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Callable, List, Optional, Sequence, Tuple


Position = Tuple[float, float]
Objective = Callable[[Position], float]
CancelCheck = Callable[[], bool]
ResponseSignature = Callable[[], Sequence[float]]


def optical_point_group(point_name: str) -> int:
    """Return the protected mount group for a numbered optical point.

    Points 1-3 belong to diaphragm/plane 1 and may use actuator pair 1.
    Points 4-6 belong to diaphragm/plane 2 and may use actuator pair 2.
    Non-numbered presets such as ``working`` deliberately unlock no pair.
    """

    text = str(point_name or "").strip().lower()
    if not text.startswith("point"):
        return 0
    suffix = text[5:]
    if not suffix.isdigit():
        return 0
    point_number = int(suffix)
    if 1 <= point_number <= 3:
        return 1
    if 4 <= point_number <= 6:
        return 2
    return 0


@dataclass(frozen=True)
class SearchParameters:
    """Tuning values for one X/Y actuator-pair search."""

    initial_step: float = 2.0
    minimum_step: float = 0.125
    tolerance_px: float = 2.0
    max_evaluations: int = 30
    minimum_improvement_px: float = 0.1
    step_schedule: Tuple[float, ...] = ()
    probe_repetitions: int = 1
    unchanged_response_tolerance_px: float = 0.0

    def validate(self) -> None:
        if self.initial_step <= 0:
            raise ValueError("initial_step must be positive")
        if self.minimum_step <= 0 or self.minimum_step > self.initial_step:
            raise ValueError("minimum_step must be positive and <= initial_step")
        if self.tolerance_px < 0:
            raise ValueError("tolerance_px cannot be negative")
        if self.max_evaluations < 1:
            raise ValueError("max_evaluations must be at least 1")
        if self.minimum_improvement_px < 0:
            raise ValueError("minimum_improvement_px cannot be negative")
        if self.probe_repetitions < 1:
            raise ValueError("probe_repetitions must be at least 1")
        if self.unchanged_response_tolerance_px < 0:
            raise ValueError("unchanged_response_tolerance_px cannot be negative")
        if self.step_schedule:
            if any(step <= 0 for step in self.step_schedule):
                raise ValueError("all scheduled steps must be positive")
            if any(
                later >= earlier
                for earlier, later in zip(
                    self.step_schedule, self.step_schedule[1:]
                )
            ):
                raise ValueError("step_schedule must be strictly decreasing")


@dataclass(frozen=True)
class SearchObservation:
    """One objective observation made at an actuator position."""

    position: Position
    score: float
    response_signature: Tuple[float, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    """Result of a completed, exhausted, or cancelled pattern search."""

    best_position: Position
    best_score: float
    evaluations: int
    reason: str
    history: Tuple[SearchObservation, ...]

    @property
    def converged(self) -> bool:
        return self.reason == "tolerance"


def _clamp_position(position: Position, bounds: Sequence[Tuple[float, float]]) -> Position:
    return tuple(
        max(float(lower), min(float(upper), float(value)))
        for value, (lower, upper) in zip(position, bounds)
    )  # type: ignore[return-value]


def bounded_pattern_search(
    objective: Objective,
    start: Position,
    bounds: Sequence[Tuple[float, float]],
    parameters: Optional[SearchParameters] = None,
    cancelled: Optional[CancelCheck] = None,
    response_signature: Optional[ResponseSignature] = None,
) -> SearchResult:
    """Minimise a noisy scalar objective with a bounded coordinate search.

    ``objective`` is responsible for moving the hardware to the requested
    absolute position and returning the measured beam-shape error.
    It must raise when a movement or measurement is invalid; errors are not
    swallowed because silently continuing after a hardware failure is unsafe.
    """

    params = parameters or SearchParameters()
    params.validate()
    if len(start) != 2 or len(bounds) != 2:
        raise ValueError("laser-pointing search requires exactly two axes")
    for lower, upper in bounds:
        if not isfinite(float(lower)) or not isfinite(float(upper)):
            raise ValueError("bounds must be finite")
        if float(lower) > float(upper):
            raise ValueError("each lower bound must be <= its upper bound")

    is_cancelled = cancelled or (lambda: False)
    best_position = _clamp_position(start, bounds)
    history: List[SearchObservation] = []

    if is_cancelled():
        return SearchResult(best_position, float("inf"), 0, "cancelled", tuple())

    best_score = float(objective(best_position))
    if not isfinite(best_score):
        raise ValueError("objective returned a non-finite value")
    best_signature = (
        tuple(float(value) for value in response_signature())
        if response_signature is not None
        else ()
    )
    history.append(SearchObservation(best_position, best_score, best_signature))

    scheduled_steps = list(params.step_schedule)
    step_index = 0
    step = (
        float(scheduled_steps[0])
        if scheduled_steps
        else float(params.initial_step)
    )
    reason = "max_evaluations"
    directions = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))

    while len(history) < params.max_evaluations:
        if is_cancelled():
            reason = "cancelled"
            break
        if best_score <= params.tolerance_px:
            reason = "tolerance"
            break
        if not scheduled_steps and step < params.minimum_step:
            reason = "minimum_step"
            break

        centre = best_position
        round_best_position = best_position
        round_best_score = best_score
        round_best_signature = best_signature
        visited = set()

        for dx, dy in directions:
            if len(history) >= params.max_evaluations or is_cancelled():
                break
            for repetition in range(1, params.probe_repetitions + 1):
                if len(history) >= params.max_evaluations or is_cancelled():
                    break
                candidate = _clamp_position(
                    (
                        centre[0] + dx * step * repetition,
                        centre[1] + dy * step * repetition,
                    ),
                    bounds,
                )
                if candidate == centre or candidate in visited:
                    break
                visited.add(candidate)
                score = float(objective(candidate))
                if not isfinite(score):
                    raise ValueError("objective returned a non-finite value")
                candidate_signature = (
                    tuple(float(value) for value in response_signature())
                    if response_signature is not None
                    else ()
                )
                history.append(
                    SearchObservation(candidate, score, candidate_signature)
                )
                if score < round_best_score:
                    round_best_position = candidate
                    round_best_score = score
                    round_best_signature = candidate_signature

                # A changed optical score means that the mount responded. Only
                # keep adding movement in the same direction while the score
                # is effectively unchanged, which is the observed stiction
                # signature of these optical mounts.
                if response_signature is not None:
                    response_unchanged = (
                        len(candidate_signature) == len(best_signature)
                        and all(
                            abs(candidate_value - best_value)
                            <= params.unchanged_response_tolerance_px
                            for candidate_value, best_value in zip(
                                candidate_signature, best_signature
                            )
                        )
                    )
                else:
                    response_unchanged = (
                        abs(score - best_score)
                        <= params.unchanged_response_tolerance_px
                    )
                if not response_unchanged:
                    break

        if is_cancelled():
            reason = "cancelled"
            break

        improvement = best_score - round_best_score
        if improvement >= params.minimum_improvement_px:
            best_position = round_best_position
            best_score = round_best_score
            best_signature = round_best_signature
        else:
            if scheduled_steps:
                step_index += 1
                if step_index >= len(scheduled_steps):
                    reason = "minimum_step"
                    break
                step = float(scheduled_steps[step_index])
            else:
                step /= 2.0

    else:
        reason = "max_evaluations"

    return SearchResult(
        best_position=best_position,
        best_score=best_score,
        evaluations=len(history),
        reason=reason,
        history=tuple(history),
    )
