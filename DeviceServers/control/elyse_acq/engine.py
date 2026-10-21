"""Single-flight executor for ELYSE acquisition procedures."""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import asdict
from typing import Dict, List, Mapping, Optional, Sequence

from .contracts import (
    Clock,
    HardwareAdapter,
    Operation,
    ProcedurePlan,
    RunSnapshot,
    RunState,
    Step,
    TraceEntry,
)
from .plans import get_plan


class SystemClock:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ProcedureCancelled(RuntimeError):
    pass


class ProcedureEngine:
    """Execute one immutable plan through one adapter.

    The engine intentionally exposes no raw write API. All mutation originates
    from a named, reviewed procedure plan.
    """

    def __init__(
        self,
        hardware: HardwareAdapter,
        *,
        clock: Optional[Clock] = None,
    ) -> None:
        self.hardware = hardware
        self.clock = clock or SystemClock()
        self._cancel = threading.Event()
        self._lock = threading.RLock()
        self._snapshot = RunSnapshot(RunState.IDLE)
        self._trace: List[TraceEntry] = []
        self._sequence = 0
        self._seen_intents: Dict[str, RunSnapshot] = {}

    def snapshot(self) -> RunSnapshot:
        with self._lock:
            return self._snapshot

    def trace(self) -> List[TraceEntry]:
        with self._lock:
            return list(self._trace)

    def trace_json(self) -> str:
        return json.dumps([asdict(entry) for entry in self.trace()], indent=2)

    def cancel(self) -> None:
        self._cancel.set()

    def run(self, plan: ProcedurePlan, intent_id: str) -> RunSnapshot:
        intent_id = str(intent_id).strip()
        if not intent_id:
            raise ValueError("intent_id is required")
        with self._lock:
            if self._snapshot.state == RunState.RUNNING:
                raise RuntimeError(
                    f"procedure {self._snapshot.procedure} is already running"
                )
            if intent_id in self._seen_intents:
                return self._seen_intents[intent_id]
            self._cancel.clear()
            self._snapshot = RunSnapshot(
                RunState.RUNNING,
                procedure=plan.name,
                intent_id=intent_id,
            )

        try:
            for index, step in enumerate(plan.steps):
                self._check_cancelled()
                self._set_current_step(plan, intent_id, index, step)
                self._record(plan, intent_id, index, step, "STARTED", {})
                detail = self._execute(step)
                self._record(plan, intent_id, index, step, "SUCCEEDED", detail)
            result = RunSnapshot(
                RunState.SUCCEEDED,
                procedure=plan.name,
                intent_id=intent_id,
                step_index=len(plan.steps) - 1,
                step_label=plan.steps[-1].label,
            )
        except ProcedureCancelled as exc:
            result = RunSnapshot(
                RunState.CANCELLED,
                procedure=plan.name,
                intent_id=intent_id,
                step_index=self.snapshot().step_index,
                step_label=self.snapshot().step_label,
                error=str(exc),
            )
        except Exception as exc:
            result = RunSnapshot(
                RunState.FAILED,
                procedure=plan.name,
                intent_id=intent_id,
                step_index=self.snapshot().step_index,
                step_label=self.snapshot().step_label,
                error=f"{type(exc).__name__}: {exc}",
            )
        with self._lock:
            self._snapshot = result
            self._seen_intents[intent_id] = result
        return result

    def run_named(self, procedure: str, intent_id: str) -> RunSnapshot:
        return self.run(get_plan(procedure), intent_id)

    def _set_current_step(
        self,
        plan: ProcedurePlan,
        intent_id: str,
        index: int,
        step: Step,
    ) -> None:
        with self._lock:
            self._snapshot = RunSnapshot(
                RunState.RUNNING,
                procedure=plan.name,
                intent_id=intent_id,
                step_index=index,
                step_label=step.label,
            )

    def _record(
        self,
        plan: ProcedurePlan,
        intent_id: str,
        index: int,
        step: Step,
        outcome: str,
        detail: Mapping[str, object],
    ) -> None:
        with self._lock:
            self._sequence += 1
            self._trace.append(
                TraceEntry(
                    sequence=self._sequence,
                    procedure=plan.name,
                    intent_id=intent_id,
                    step_index=index,
                    operation=step.operation.value,
                    label=step.label,
                    outcome=outcome,
                    detail=dict(detail),
                )
            )

    def _check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise ProcedureCancelled("procedure cancellation requested")

    def _sleep(self, seconds: float) -> None:
        remaining = float(seconds)
        quantum = 0.050
        while remaining > 0:
            self._check_cancelled()
            interval = min(remaining, quantum)
            self.clock.sleep(interval)
            remaining -= interval

    def _execute(self, step: Step) -> Mapping[str, object]:
        operation = step.operation
        if operation == Operation.WAIT:
            self._sleep(step.duration_s)
            return {"seconds": step.duration_s}
        if operation == Operation.WRITE_DIGITAL:
            self.hardware.write_digital(step.targets[0], bool(step.value))
            return {"target": step.targets[0], "value": bool(step.value)}
        if operation == Operation.WRITE_DIGITAL_GROUP:
            self.hardware.write_digital_group(step.targets, bool(step.value))
            return {"targets": list(step.targets), "value": bool(step.value)}
        if operation == Operation.WRITE_ANALOG_GROUP:
            value = float(step.value)
            self.hardware.write_analog_group(
                {target: value for target in step.targets}
            )
            return {"targets": list(step.targets), "value": value}
        if operation == Operation.START_COUNTERS:
            self.hardware.start_counters(step.targets)
            return {"targets": list(step.targets)}
        if operation == Operation.STOP_COUNTER_WHEN_DONE:
            poll = float(step.metadata["poll_interval_s"])
            limit = int(step.metadata["max_loop_index"])
            self.hardware.stop_counter_when_done(step.targets[0], poll, limit)
            return {
                "target": step.targets[0],
                "poll_interval_s": poll,
                "max_loop_index": limit,
            }
        if operation == Operation.SET_FOCAL_SUPPLIES:
            self.hardware.set_focal_supplies(bool(step.value))
            return {"enabled": bool(step.value)}
        if operation == Operation.ANALOG_SWEEP:
            return self._execute_sweep(step)
        raise ValueError(f"unsupported operation {operation}")

    def _execute_sweep(self, step: Step) -> Mapping[str, object]:
        initial = float(step.metadata["initial"])
        delta = float(step.metadata["delta"])
        iterations = int(step.metadata["iterations"])
        period_s = float(step.metadata["period_s"])
        if iterations <= 0 or not math.isfinite(initial) or not math.isfinite(delta):
            raise ValueError(f"invalid analog sweep in {step.label}")
        value = initial
        for _ in range(iterations):
            self._check_cancelled()
            value += delta
            self.hardware.write_analog_group(
                {target: value for target in step.targets}
            )
            self._sleep(period_s)
        return {
            "targets": list(step.targets),
            "initial": initial,
            "delta": delta,
            "iterations": iterations,
            "period_s": period_s,
            "final": value,
        }


class ProcedureController:
    """Background single-flight facade suitable for a Tango command server."""

    def __init__(self, engine: ProcedureEngine) -> None:
        self.engine = engine
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

    def submit(self, procedure: str, intent_id: str) -> RunSnapshot:
        plan = get_plan(procedure)
        with self._lock:
            current = self.engine.snapshot()
            if current.state == RunState.RUNNING:
                raise RuntimeError(f"procedure {current.procedure} is already running")
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("procedure worker is still active")
            self._thread = threading.Thread(
                target=self.engine.run,
                args=(plan, intent_id),
                name=f"elyse-acq-{plan.name}",
                daemon=True,
            )
            self._thread.start()
        return self.engine.snapshot()

    def cancel(self) -> RunSnapshot:
        self.engine.cancel()
        return self.engine.snapshot()

