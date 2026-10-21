"""Deterministic non-actuating adapter for offline tests and UI development."""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence


class SimulatedHardware:
    def __init__(self) -> None:
        self.digital: Dict[str, bool] = {}
        self.analog: Dict[str, float] = {}
        self.counters: Dict[str, str] = {}
        self.focal_supplies_enabled = False
        self.operations: List[dict] = []

    def write_digital(self, logical_id: str, value: bool) -> None:
        self.digital[logical_id] = bool(value)
        self.operations.append(
            {"operation": "write_digital", "target": logical_id, "value": bool(value)}
        )

    def write_digital_group(
        self, logical_ids: Sequence[str], value: bool
    ) -> None:
        for logical_id in logical_ids:
            self.digital[logical_id] = bool(value)
        self.operations.append(
            {
                "operation": "write_digital_group",
                "targets": list(logical_ids),
                "value": bool(value),
            }
        )

    def write_analog_group(self, values: Mapping[str, float]) -> None:
        clean = {key: float(value) for key, value in values.items()}
        self.analog.update(clean)
        self.operations.append(
            {"operation": "write_analog_group", "values": clean}
        )

    def start_counters(self, logical_ids: Sequence[str]) -> None:
        for logical_id in logical_ids:
            self.counters[logical_id] = "RUNNING"
        self.operations.append(
            {"operation": "start_counters", "targets": list(logical_ids)}
        )

    def stop_counter_when_done(
        self, logical_id: str, poll_interval_s: float, max_loop_index: int
    ) -> None:
        self.counters[logical_id] = "STOPPED"
        self.operations.append(
            {
                "operation": "stop_counter_when_done",
                "target": logical_id,
                "poll_interval_s": float(poll_interval_s),
                "max_loop_index": int(max_loop_index),
            }
        )

    def set_focal_supplies(self, enabled: bool) -> None:
        self.focal_supplies_enabled = bool(enabled)
        self.operations.append(
            {"operation": "set_focal_supplies", "enabled": bool(enabled)}
        )

    def snapshot(self) -> Mapping[str, object]:
        return {
            "simulation": True,
            "digital": dict(self.digital),
            "analog": dict(self.analog),
            "counters": dict(self.counters),
            "focal_supplies_enabled": self.focal_supplies_enabled,
            "operation_count": len(self.operations),
        }

