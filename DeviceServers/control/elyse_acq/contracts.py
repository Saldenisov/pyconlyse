"""Pure contracts for the ELYSE acquisition procedure engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Protocol, Sequence, Tuple


class Operation(str, Enum):
    WRITE_DIGITAL = "write_digital"
    WRITE_DIGITAL_GROUP = "write_digital_group"
    WRITE_ANALOG_GROUP = "write_analog_group"
    WAIT = "wait"
    START_COUNTERS = "start_counters"
    STOP_COUNTER_WHEN_DONE = "stop_counter_when_done"
    SET_FOCAL_SUPPLIES = "set_focal_supplies"
    ANALOG_SWEEP = "analog_sweep"


class RunState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


JsonValue = Any


@dataclass(frozen=True)
class Step:
    operation: Operation
    label: str
    targets: Tuple[str, ...] = ()
    value: JsonValue = None
    duration_s: float = 0.0
    timeout_s: float = 0.0
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("step label cannot be empty")
        for name, number in (
            ("duration_s", self.duration_s),
            ("timeout_s", self.timeout_s),
        ):
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if len(set(self.targets)) != len(self.targets):
            raise ValueError(f"duplicate targets in step {self.label}")


@dataclass(frozen=True)
class ProcedurePlan:
    name: str
    steps: Tuple[Step, ...]
    legacy_event_case: int
    description: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("procedure name cannot be empty")
        if not self.steps:
            raise ValueError(f"procedure {self.name} has no steps")
        if self.legacy_event_case < 3 or self.legacy_event_case > 25:
            raise ValueError("legacy event case must be in 3..25")


@dataclass(frozen=True)
class TraceEntry:
    sequence: int
    procedure: str
    intent_id: str
    step_index: int
    operation: str
    label: str
    outcome: str
    detail: Mapping[str, JsonValue]


@dataclass(frozen=True)
class RunSnapshot:
    state: RunState
    procedure: str = ""
    intent_id: str = ""
    step_index: int = -1
    step_label: str = ""
    error: str = ""

    def as_dict(self) -> Dict[str, JsonValue]:
        return {
            "state": self.state.value,
            "procedure": self.procedure,
            "intent_id": self.intent_id,
            "step_index": self.step_index,
            "step_label": self.step_label,
            "error": self.error,
        }


class HardwareAdapter(Protocol):
    """Only interface through which a procedure may mutate hardware."""

    def write_digital(self, logical_id: str, value: bool) -> None: ...

    def write_digital_group(
        self, logical_ids: Sequence[str], value: bool
    ) -> None: ...

    def write_analog_group(self, values: Mapping[str, float]) -> None: ...

    def start_counters(self, logical_ids: Sequence[str]) -> None: ...

    def stop_counter_when_done(
        self, logical_id: str, poll_interval_s: float, max_loop_index: int
    ) -> None: ...

    def set_focal_supplies(self, enabled: bool) -> None: ...

    def snapshot(self) -> Mapping[str, JsonValue]: ...


class Clock(Protocol):
    def sleep(self, seconds: float) -> None: ...
