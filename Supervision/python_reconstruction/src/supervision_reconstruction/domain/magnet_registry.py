"""Offline magnet ownership and current-intent planning; never hardware dispatch.

Historical SuperVision fields are candidates, not deployed connections. Local
iTest configuration supplies eight candidate bindings; no live Tango properties,
electrical limits, interlocks, or readback sources have been commissioned here.
Even a resolved plan is non-executable. No fallback or whole-bank writer exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .beamline_commands import DIRECT_CHANNEL_RULES, DEVIATED_CHANNEL_RULES


class MagnetOwner(str, Enum):
    DEVICE_SERVER = "DEVICE_SERVER"
    LEGACY_ACQ = "LEGACY_ACQ"
    UNKNOWN = "UNKNOWN"


class RouteVerification(str, Enum):
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"


def _text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty text required")
    return value.strip().casefold()


def _number(value: float) -> float:
    if type(value) not in (float, int):
        raise ValueError("finite current in amperes required; bool is not a current")
    try:
        current = float(value)
    except OverflowError as error:
        raise ValueError("current cannot be represented as finite amperes") from error
    if not math.isfinite(current):
        raise ValueError("finite current in amperes required")
    return current


@dataclass(frozen=True)
class DeviceServerBinding:
    device: str
    slot_id: int

    def __post_init__(self) -> None:
        _text(self.device)
        if type(self.slot_id) is not int or self.slot_id <= 0:
            raise ValueError("positive explicit slot ID required, not array position")


@dataclass(frozen=True)
class LegacyCurrentBinding:
    variable: str
    field: str

    def __post_init__(self) -> None:
        _text(self.variable)
        _text(self.field)


Binding = DeviceServerBinding | LegacyCurrentBinding


def _binding_key(binding: Binding) -> tuple[str, str, str | int]:
    if isinstance(binding, DeviceServerBinding):
        return ("itest", _text(binding.device), binding.slot_id)
    return ("legacy", _text(binding.variable), _text(binding.field))


@dataclass(frozen=True)
class CurrentLimits:
    minimum_a: float
    maximum_a: float

    def __post_init__(self) -> None:
        if _number(self.minimum_a) > _number(self.maximum_a):
            raise ValueError("minimum current exceeds maximum")


@dataclass(frozen=True)
class MagnetEntry:
    equipment_id: str
    label: str
    aliases: tuple[str, ...]
    beam_line: str
    owner: MagnetOwner
    binding: Binding | None
    verification: RouteVerification
    provenance: tuple[str, ...]
    limits: CurrentLimits | None = None
    legacy_candidate: LegacyCurrentBinding | None = None
    retired_legacy: tuple[LegacyCurrentBinding, ...] = ()
    crosswalk_status: str = "UNRESOLVED"

    def __post_init__(self) -> None:
        for value in (self.equipment_id, self.label, self.beam_line, self.crosswalk_status):
            _text(value)
        if type(self.aliases) is not tuple or type(self.provenance) is not tuple:
            raise ValueError("aliases and provenance must be immutable tuples")
        for value in (*self.aliases, *self.provenance):
            _text(value)
        if not isinstance(self.owner, MagnetOwner) or not isinstance(self.verification, RouteVerification):
            raise ValueError("typed owner and verification required")
        expected_type = {
            MagnetOwner.DEVICE_SERVER: DeviceServerBinding,
            MagnetOwner.LEGACY_ACQ: LegacyCurrentBinding,
            MagnetOwner.UNKNOWN: type(None),
        }[self.owner]
        if not isinstance(self.binding, expected_type):
            raise ValueError("binding must match the single command owner")
        if self.verification is RouteVerification.VERIFIED:
            if self.owner is MagnetOwner.UNKNOWN or not self.provenance:
                raise ValueError("verified route requires known owner and verification provenance")
        if self.limits is not None and not isinstance(self.limits, CurrentLimits):
            raise ValueError("typed current limits required")
        if self.legacy_candidate is not None and not isinstance(self.legacy_candidate, LegacyCurrentBinding):
            raise ValueError("typed historical legacy candidate required")
        if type(self.retired_legacy) is not tuple or any(
            not isinstance(item, LegacyCurrentBinding) for item in self.retired_legacy
        ):
            raise ValueError("retired assignments must be immutable legacy bindings")
        if self.owner is MagnetOwner.DEVICE_SERVER and self.legacy_candidate is not None:
            if self.legacy_candidate not in self.retired_legacy:
                raise ValueError("iTest candidate's former DAQmx assignment must remain retired")


@dataclass(frozen=True)
class MagnetRegistry:
    revision: str
    entries: tuple[MagnetEntry, ...]

    def __post_init__(self) -> None:
        _text(self.revision)
        if type(self.entries) is not tuple or not self.entries:
            raise ValueError("nonempty immutable equipment inventory required")
        identifiers: set[str] = set()
        aliases: dict[str, str] = {}
        bindings: set[tuple[str, str, str | int]] = set()
        retired: set[tuple[str, str, str | int]] = set()
        for entry in self.entries:
            if not isinstance(entry, MagnetEntry):
                raise ValueError("typed magnet entries required")
            identifier = _text(entry.equipment_id)
            if identifier in identifiers:
                raise ValueError("duplicate equipment ID")
            identifiers.add(identifier)
            for alias in (entry.equipment_id, entry.label, *entry.aliases):
                key = _text(alias)
                if key in aliases and aliases[key] != identifier:
                    raise ValueError(f"ambiguous equipment alias: {alias}")
                aliases[key] = identifier
            if entry.binding is not None:
                key = _binding_key(entry.binding)
                if key in bindings:
                    raise ValueError("duplicate command endpoint/slot or legacy field")
                bindings.add(key)
            retired.update(_binding_key(item) for item in entry.retired_legacy)
        if bindings & retired:
            raise ValueError("retired DAQmx assignment cannot be an active route")

    def find(self, name: str) -> MagnetEntry | None:
        key = _text(name)
        return next((entry for entry in self.entries if key in {
            _text(value) for value in (entry.equipment_id, entry.label, *entry.aliases)
        }), None)


@dataclass(frozen=True)
class CurrentIntentPlan:
    equipment_id: str
    registry_revision: str
    current_a: float
    target: Binding | None
    blocked_reasons: tuple[str, ...]

    @property
    def resolved(self) -> bool:
        return self.target is not None and not self.blocked_reasons

    @property
    def external_effects_blocked(self) -> bool:
        return True

    @property
    def execution_allowed(self) -> bool:
        return False


def plan_current_intent(
    registry: MagnetRegistry,
    name: str,
    current_a: float,
    *,
    expected_revision: str,
    transport_available: bool = False,
) -> CurrentIntentPlan:
    """Resolve absolute ampere intent, not relative UI steps or physical success.

Availability is caller-supplied offline evidence, not a network probe. A true
value never enables execution. Unknown limits block even a zero-current intent.
"""
    current = _number(current_a)
    if type(transport_available) is not bool:
        raise ValueError("explicit Boolean availability required")
    entry = registry.find(name)
    reasons: list[str] = []
    if expected_revision != registry.revision:
        reasons.append("REGISTRY_REVISION_MISMATCH")
    if entry is None:
        reasons.append("UNKNOWN_EQUIPMENT")
    else:
        if entry.owner is MagnetOwner.UNKNOWN:
            reasons.append("OWNER_UNKNOWN")
        if entry.verification is not RouteVerification.VERIFIED:
            reasons.append("ROUTE_UNVERIFIED")
        if entry.limits is None:
            reasons.append("CURRENT_LIMITS_UNVERIFIED")
        elif not entry.limits.minimum_a <= current <= entry.limits.maximum_a:
            reasons.append("CURRENT_OUT_OF_RANGE")
    if not transport_available:
        reasons.append("TRANSPORT_UNAVAILABLE")
    return CurrentIntentPlan(
        entry.equipment_id if entry is not None else name,
        registry.revision,
        current,
        entry.binding if entry is not None and not reasons else None,
        tuple(reasons),
    )


def plan_group_currents(
    registry: MagnetRegistry,
    requests: tuple[tuple[str, float], ...],
    *,
    expected_revision: str,
    available_equipment: frozenset[str] = frozenset(),
) -> tuple[CurrentIntentPlan, ...]:
    """Per-equipment planning, no server-global start/stop and no execution.

Availability is keyed only by canonical equipment ID. Duplicate physical
equipment (including two aliases of one magnet) is rejected before planning.
Resolved/blocked items are not completed/failed hardware operations.
"""
    if type(requests) is not tuple or not requests:
        raise ValueError("nonempty immutable request group required")
    if type(available_equipment) is not frozenset:
        raise ValueError("immutable availability evidence required")
    if not available_equipment <= {entry.equipment_id for entry in registry.entries}:
        raise ValueError("availability must use known canonical equipment IDs")
    seen: set[str] = set()
    plans: list[CurrentIntentPlan] = []
    for name, current in requests:
        entry = registry.find(name)
        identity = entry.equipment_id if entry else _text(name)
        if identity in seen:
            raise ValueError("duplicate magnet in grouped request")
        seen.add(identity)
        plans.append(plan_current_intent(
            registry, name, current, expected_revision=expected_revision,
            transport_available=identity in available_equipment,
        ))
    return tuple(plans)


def legacy_selection_blockers(
    registry: MagnetRegistry,
    variable: str,
    fields: tuple[str, ...],
    *,
    expected_revision: str,
) -> tuple[str, ...]:
    """Audit named legacy fields; an empty result does NOT authorize a bank write.

This checks ownership only. It does not validate values, interlocks, telemetry,
transport, or the other fields in a cluster. Raw whole-cluster writes remain
outside the model even when every selected field belongs to legacy equipment.
"""
    _text(variable)
    if type(fields) is not tuple or not fields:
        raise ValueError("explicit nonempty legacy field selection required")
    keys = [_binding_key(LegacyCurrentBinding(variable, field)) for field in fields]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate legacy field in selection")
    reasons = [] if expected_revision == registry.revision else ["REGISTRY_REVISION_MISMATCH"]
    retired = {_binding_key(binding) for entry in registry.entries for binding in entry.retired_legacy}
    active = {_binding_key(entry.binding): entry for entry in registry.entries if entry.binding is not None}
    for field, key in zip(fields, keys):
        if key in retired:
            reasons.append(f"RETIRED_LEGACY_FIELD: {variable}/{field}")
        elif key not in active or active[key].owner is not MagnetOwner.LEGACY_ACQ:
            reasons.append(f"NO_LEGACY_OWNER: {variable}/{field}")
        elif active[key].verification is not RouteVerification.VERIFIED:
            reasons.append(f"ROUTE_UNVERIFIED: {variable}/{field}")
    return tuple(reasons)


LOCAL_ITEST_SOURCE = "DeviceServers/power/iTest/test_config.py"
LOCAL_ITEST_SHA256 = "D0D062599330D37082B73BD72F24402D6826D4C0D47B851264CD139F44D9A6B4"
CROSSWALK_SOURCE = "Supervision/integration_analysis/BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv"
CROSSWALK_SHA256 = "BC9209FA7BB6A16702A84A95C0805EBCF815CB267457D9DA356B9A902754C400"


def candidate_registry() -> MagnetRegistry:
    """19 historical magnet controls + two iTest aliases, not all accelerator equipment."""
    direct_ids = (
        "dipole-1", "focale", None, "corrector-h1", "corrector-v1",
        "corrector-h2", "corrector-v2", "triplet-1-1", "triplet-1-2",
        "corrector-h3", "corrector-v3",
    )
    deviated_ids = (
        "quadrupole-1", "quadrupole-2", "triplet-2-1", "triplet-2-2",
        "corrector-h4", "corrector-v4", "dipole-2", "corrector-h5", "corrector-v5",
    )
    itest = {
        "triplet-1-1": ("T1-1", 1), "triplet-1-2": ("T1-2", 3),
        "corrector-h1": ("H1", 5), "corrector-v1": ("V1", 6),
        "dipole-1": ("Dip1", 7), "dipole-2": ("Dip2", 9),
        "bcd-1": ("Bcd1", 11), "bcd-2": ("Bcd2", 12),
    }
    entries: list[MagnetEntry] = []
    for beam_line, identifiers, rules in (
        ("direct", direct_ids, DIRECT_CHANNEL_RULES),
        ("deviated", deviated_ids, DEVIATED_CHANNEL_RULES),
    ):
        for equipment_id, rule in zip(identifiers, rules, strict=True):
            if equipment_id is None:  # Phase HF / Laser is not a magnet.
                continue
            legacy = LegacyCurrentBinding(rule.destination.observed_variable, rule.destination.legacy_field)
            candidate = itest.get(equipment_id)
            entries.append(MagnetEntry(
                equipment_id, rule.legacy_name, (candidate[0],) if candidate else (),
                beam_line, MagnetOwner.DEVICE_SERVER if candidate else MagnetOwner.UNKNOWN,
                DeviceServerBinding("elyse/pdu/itest", candidate[1]) if candidate else None,
                RouteVerification.CANDIDATE,
                (CROSSWALK_SOURCE, LOCAL_ITEST_SOURCE) if candidate else (CROSSWALK_SOURCE,),
                legacy_candidate=legacy, retired_legacy=(legacy,) if candidate else (),
                crosswalk_status=rule.crosswalk_status,
            ))
    for equipment_id, label in (("bcd-1", "BCD 1"), ("bcd-2", "BCD 2")):
        alias, slot_id = itest[equipment_id]
        entries.append(MagnetEntry(
            equipment_id, label, (alias,), "unresolved", MagnetOwner.DEVICE_SERVER,
            DeviceServerBinding("elyse/pdu/itest", slot_id), RouteVerification.CANDIDATE,
            (LOCAL_ITEST_SOURCE,), crosswalk_status="LEGACY_UI_ASSOCIATION_UNRESOLVED",
        ))
    return MagnetRegistry("offline-candidates-2026-10-02.v1", tuple(entries))


def registry_snapshot(registry: MagnetRegistry) -> dict:
    """Display-only export. Null telemetry cannot confirm any equipment state."""
    def legacy_dict(binding: LegacyCurrentBinding) -> dict:
        return {"variable": binding.variable, "field": binding.field}

    rows = []
    for entry in registry.entries:
        binding = entry.binding
        if isinstance(binding, DeviceServerBinding):
            route = {"device": binding.device, "slot_id": binding.slot_id}
        elif isinstance(binding, LegacyCurrentBinding):
            route = legacy_dict(binding)
        else:
            route = None
        rows.append({
            "equipment_id": entry.equipment_id, "label": entry.label,
            "aliases": list(entry.aliases), "beam_line": entry.beam_line,
            "owner": entry.owner.value, "verification": entry.verification.value,
            "route": route, "provenance": list(entry.provenance),
            "legacy_candidate": legacy_dict(entry.legacy_candidate) if entry.legacy_candidate else None,
            "retired_legacy": [legacy_dict(item) for item in entry.retired_legacy],
            "crosswalk_status": entry.crosswalk_status,
            "current_limits_a": [entry.limits.minimum_a, entry.limits.maximum_a] if entry.limits else None,
            "telemetry": {"setpoint_a": None, "measured_a": None, "timestamp": None,
                          "quality": "UNAVAILABLE", "source": None},
            "execution_allowed": False,
        })
    return {"registry_revision": registry.revision, "display_only": True,
            "external_effects_blocked": True, "entries": rows}
