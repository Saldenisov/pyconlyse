"""Typed absolute-current previews. All results are plans, never command execution."""

from dataclasses import dataclass
import json
import re

from ..domain.magnet_registry import (
    DeviceServerBinding, MagnetRegistry, _number, plan_group_currents,
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


class InvalidPreview(ValueError):
    """Malformed intent; no journal entry or physical action occurs."""


@dataclass(frozen=True)
class CurrentPreview:
    idempotency_key: str
    expected_revision: str
    currents: tuple[tuple[str, float], ...]

    def canonical_request(self) -> dict:
        return {"expected_revision": self.expected_revision,
                "requests": [{"equipment_id": name, "current_a": value} for name, value in self.currents]}


def parse_preview(registry: MagnetRegistry, body: object) -> CurrentPreview:
    if type(body) is not dict or set(body) != {"idempotency_key", "expected_revision", "requests"}:
        raise InvalidPreview("Only idempotency_key, expected_revision, and requests are allowed")
    key = body["idempotency_key"]
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key) is None:
        raise InvalidPreview("Invalid idempotency key")
    revision = body["expected_revision"]
    if not isinstance(revision, str) or not revision.strip() or len(revision) > 128:
        raise InvalidPreview("Explicit bounded registry revision required")
    requests = body["requests"]
    if type(requests) is not list or not 1 <= len(requests) <= len(registry.entries):
        raise InvalidPreview("A bounded nonempty equipment request group is required")
    currents = []
    identifiers = set()
    for item in requests:
        if type(item) is not dict or set(item) != {"equipment_id", "current_a"}:
            raise InvalidPreview("Only equipment_id and current_a are allowed per request")
        name = item["equipment_id"]
        if not isinstance(name, str) or not name.strip() or len(name) > 128:
            raise InvalidPreview("Known equipment ID or alias required")
        entry = registry.find(name)
        if entry is None:
            raise InvalidPreview("Equipment is not in the registry")
        if entry.equipment_id in identifiers:
            raise InvalidPreview("Duplicate physical magnet in request group")
        identifiers.add(entry.equipment_id)
        try:
            value = _number(item["current_a"])
        except ValueError as error:
            raise InvalidPreview(str(error)) from error
        currents.append((entry.equipment_id, 0.0 if value == 0 else value))
    return CurrentPreview(key, revision, tuple(currents))


def preview_currents(
    registry: MagnetRegistry,
    preview: CurrentPreview,
    *,
    available_equipment: frozenset[str] = frozenset(),
) -> dict:
    plans = plan_group_currents(registry, preview.currents,
        expected_revision=preview.expected_revision, available_equipment=available_equipment)
    rows = []
    for plan in plans:
        target = plan.target
        if isinstance(target, DeviceServerBinding):
            route = {"owner": "DEVICE_SERVER", "device": target.device, "slot_id": target.slot_id}
        elif target is not None:
            route = {"owner": "LEGACY_ACQ", "variable": target.variable, "field": target.field}
        else:
            route = None
        rows.append({"equipment_id": plan.equipment_id, "current_a": plan.current_a,
                     "route": route, "resolved": plan.resolved,
                     "blocked_reasons": list(plan.blocked_reasons), "execution_allowed": False})
    resolved = sum(plan.resolved for plan in plans)
    state = "PREVIEW_RESOLVED" if resolved == len(plans) else "PREVIEW_BLOCKED" if not resolved else "PREVIEW_MIXED"
    return {"kind": "CURRENT_INTENT_PREVIEW", "state": state,
            "registry_revision": registry.revision, "plans": rows,
            "resolved_count": resolved, "blocked_count": len(plans) - resolved,
            "physical_status": "NOT_EXECUTED", "execution_allowed": False,
            "establishes_command_success": False}
