"""Offline current provenance, freshness, and request/readback comparison.

No Tango reads, driver calls, timestamps from the system clock, or command
dispatch occur. A matching current is one predicate, not proof of output state,
interlocks, stable settling, safe shutdown, or complete command success.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .magnet_registry import (
    Binding, DeviceServerBinding, LegacyCurrentBinding, MagnetOwner,
    MagnetRegistry, RouteVerification, registry_snapshot, _binding_key, _number, _text,
)


class ReadbackQuality(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"
    DISCONNECTED = "DISCONNECTED"
    SIMULATED = "SIMULATED"
    UNKNOWN = "UNKNOWN"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware acquisition/receive/evaluation time required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ITestMeasuredCurrentPoint:
    binding: DeviceServerBinding

    def __post_init__(self) -> None:
        if not isinstance(self.binding, DeviceServerBinding):
            raise ValueError("explicit device and slot ID required")

    @property
    def attribute(self) -> str:
        return "currents_meas"  # currents_setpoint is never a measurement source.

    @property
    def owner(self) -> MagnetOwner:
        return MagnetOwner.DEVICE_SERVER


@dataclass(frozen=True)
class LegacyMeasuredCurrentPoint:
    variable: str
    field: str

    def __post_init__(self) -> None:
        _text(self.variable)
        _text(self.field)

    @property
    def owner(self) -> MagnetOwner:
        return MagnetOwner.LEGACY_ACQ


MeasuredCurrentPoint = ITestMeasuredCurrentPoint | LegacyMeasuredCurrentPoint


@dataclass(frozen=True)
class CurrentReadbackAssociation:
    equipment_id: str
    registry_revision: str
    command_binding: Binding | None
    source: MeasuredCurrentPoint | None
    verification: RouteVerification
    provenance: tuple[str, ...]
    cross_owner_approved: bool = False

    def __post_init__(self) -> None:
        _text(self.equipment_id)
        _text(self.registry_revision)
        if self.command_binding is not None and not isinstance(self.command_binding, (DeviceServerBinding, LegacyCurrentBinding)):
            raise ValueError("typed command route required")
        if self.source is not None and not isinstance(self.source, (ITestMeasuredCurrentPoint, LegacyMeasuredCurrentPoint)):
            raise ValueError("typed measured-current source required")
        if not isinstance(self.verification, RouteVerification):
            raise ValueError("typed readback verification required")
        if type(self.provenance) is not tuple:
            raise ValueError("immutable readback provenance required")
        for value in self.provenance:
            _text(value)
        if type(self.cross_owner_approved) is not bool:
            raise ValueError("explicit Boolean cross-owner approval required")
        if self.verification is RouteVerification.VERIFIED:
            if self.source is None or self.command_binding is None or not self.provenance:
                raise ValueError("verified readback needs source, bound command route, and independent provenance")
        if self.cross_owner_approved and self.verification is not RouteVerification.VERIFIED:
            raise ValueError("cross-owner readback requires independent verification")


@dataclass(frozen=True)
class CurrentReadbackPolicy:
    max_age_ms: float
    tolerance_a: float

    def __post_init__(self) -> None:
        if _number(self.max_age_ms) <= 0 or _number(self.tolerance_a) < 0:
            raise ValueError("positive maximum age and nonnegative current tolerance required")


@dataclass(frozen=True)
class MeasuredCurrentSample:
    equipment_id: str
    registry_revision: str
    source: MeasuredCurrentPoint
    value_a: object
    source_time: datetime | None
    received_at: datetime
    quality: ReadbackQuality
    acquisition_confirmed: bool = False

    def __post_init__(self) -> None:
        _text(self.equipment_id)
        _text(self.registry_revision)
        if not isinstance(self.source, (ITestMeasuredCurrentPoint, LegacyMeasuredCurrentPoint)):
            raise ValueError("typed physical measurement source required")
        if self.source_time is not None:
            _utc(self.source_time)
        _utc(self.received_at)
        if not isinstance(self.quality, ReadbackQuality) or type(self.acquisition_confirmed) is not bool:
            raise ValueError("typed quality and explicit acquisition evidence required")
        if type(self.value_a) not in (float, int, str, bool, type(None)):
            raise ValueError("immutable scalar measurement payload required")
        # NaN and malformed numeric payloads are accepted as evidence inputs,
        # then projected INVALID, never coerced to zero or a valid measurement.


def sample_from_itest_arrays(
    *,
    equipment_id: str,
    registry_revision: str,
    source: ITestMeasuredCurrentPoint,
    slot_ids: tuple[int, ...],
    measured_currents: tuple[object, ...],
    source_time: datetime | None,
    received_at: datetime,
    quality: ReadbackQuality,
    acquisition_confirmed: bool = False,
) -> MeasuredCurrentSample:
    """Select by explicit ID, never slot-1 or display position.

Caller must establish that IDs and currents belong to one coherent successful
hardware refresh. Independent cached attribute reads cannot establish this;
they must not assert acquisition_confirmed or fabricate source_time.
"""
    if not isinstance(source, ITestMeasuredCurrentPoint):
        raise ValueError("typed iTest measured-current point required")
    if type(slot_ids) is not tuple or type(measured_currents) is not tuple:
        raise ValueError("immutable coherent ID/current arrays required")
    if not slot_ids or len(slot_ids) != len(measured_currents):
        raise ValueError("ID/current arrays must have matching nonzero lengths")
    if any(type(slot_id) is not int or slot_id <= 0 for slot_id in slot_ids) or len(set(slot_ids)) != len(slot_ids):
        raise ValueError("positive unique hardware slot IDs required")
    if source.binding.slot_id not in slot_ids:
        raise ValueError("configured slot absent from observed hardware IDs")
    return MeasuredCurrentSample(
        equipment_id, registry_revision, source,
        measured_currents[slot_ids.index(source.binding.slot_id)], source_time,
        received_at, quality, acquisition_confirmed,
    )


@dataclass(frozen=True)
class CurrentReadbackView:
    equipment_id: str
    registry_revision: str
    source: MeasuredCurrentPoint | None
    source_time: datetime | None
    received_at: datetime | None
    evaluated_at: datetime
    age_ms: float | None
    quality: ReadbackQuality
    measured_a: float | None
    reasons: tuple[str, ...]
    association: CurrentReadbackAssociation
    sample: MeasuredCurrentSample | None
    transport_available: bool


def project_current_readback(
    registry: MagnetRegistry,
    association: CurrentReadbackAssociation,
    sample: MeasuredCurrentSample | None,
    *,
    now: datetime,
    policy: CurrentReadbackPolicy,
    transport_available: bool = False,
) -> CurrentReadbackView:
    """Server-side pure projection with an explicit clock and no default limits.

Future or absent producer times fail closed. All timestamps must be verified in
one clock domain before deployment; receive time cannot replace acquisition time.
Stale/simulated valid numbers may be displayed with their quality, never compared
as physical confirmation. Unverified/wrong-source/cached/invalid numbers are hidden.
"""
    now = _utc(now)
    if not isinstance(association, CurrentReadbackAssociation) or not isinstance(policy, CurrentReadbackPolicy):
        raise ValueError("typed association and current policy required")
    if type(transport_available) is not bool:
        raise ValueError("explicit Boolean transport availability required")
    if sample is not None and not isinstance(sample, MeasuredCurrentSample):
        raise ValueError("typed measured-current sample required")
    entry = registry.find(association.equipment_id)
    blockers: list[str] = []
    if association.registry_revision != registry.revision:
        blockers.append("REGISTRY_REVISION_MISMATCH")
    if entry is None or association.equipment_id != entry.equipment_id:
        blockers.append("UNKNOWN_EQUIPMENT_ID")
    else:
        if entry.owner is MagnetOwner.UNKNOWN:
            blockers.append("OWNER_UNKNOWN")
        if entry.verification is not RouteVerification.VERIFIED:
            blockers.append("COMMAND_ROUTE_UNVERIFIED")
        if association.command_binding is None or entry.binding is None or _binding_key(association.command_binding) != _binding_key(entry.binding):
            blockers.append("COMMAND_ROUTE_MISMATCH")
        if association.source is not None:
            if association.source.owner is not entry.owner and not association.cross_owner_approved:
                blockers.append("CROSS_OWNER_READBACK_UNAPPROVED")
            if isinstance(entry.binding, DeviceServerBinding) and isinstance(association.source, ITestMeasuredCurrentPoint):
                if _binding_key(association.source.binding) != _binding_key(entry.binding):
                    blockers.append("ITEST_READBACK_SLOT_MISMATCH")
    if association.verification is not RouteVerification.VERIFIED or association.source is None:
        blockers.append("READBACK_ASSOCIATION_UNVERIFIED")
    if isinstance(association.source, LegacyMeasuredCurrentPoint):
        command_fields = {_binding_key(binding) for item in registry.entries
                          for binding in (*item.retired_legacy, item.legacy_candidate, item.binding)
                          if isinstance(binding, LegacyCurrentBinding)}
        source_key = _binding_key(LegacyCurrentBinding(association.source.variable, association.source.field))
        if source_key in command_fields:
            blockers.append("COMMAND_FIELD_IS_NOT_MEASURED_CURRENT")
    if not transport_available:
        blockers.append("TRANSPORT_UNAVAILABLE")
    if sample is None:
        blockers.append("NO_SAMPLE")
    else:
        if sample.equipment_id != association.equipment_id:
            blockers.append("SAMPLE_EQUIPMENT_MISMATCH")
        if sample.registry_revision != registry.revision:
            blockers.append("SAMPLE_REVISION_MISMATCH")
        if sample.source != association.source:
            blockers.append("SAMPLE_SOURCE_MISMATCH")

    def view(quality: ReadbackQuality, value: float | None = None, age: float | None = None) -> CurrentReadbackView:
        return CurrentReadbackView(
            association.equipment_id, registry.revision, association.source,
            _utc(sample.source_time) if sample and sample.source_time else None,
            _utc(sample.received_at) if sample else None, now, age, quality, value, tuple(blockers),
            association, sample, transport_available,
        )

    if blockers:
        return view(ReadbackQuality.DISCONNECTED if not transport_available else ReadbackQuality.UNKNOWN)
    assert sample is not None
    if sample.quality in (ReadbackQuality.INVALID, ReadbackQuality.DISCONNECTED, ReadbackQuality.UNKNOWN):
        blockers.append(f"SOURCE_QUALITY_{sample.quality.value}")
        return view(sample.quality)
    try:
        value = _number(sample.value_a)
    except ValueError:
        blockers.append("INVALID_CURRENT_PAYLOAD")
        return view(ReadbackQuality.INVALID)
    if not sample.acquisition_confirmed:
        blockers.append("PHYSICAL_ACQUISITION_UNPROVEN")
    if sample.source_time is None:
        blockers.append("ACQUISITION_TIME_UNKNOWN")
    elif _utc(sample.source_time) > _utc(sample.received_at):
        blockers.append("SOURCE_TIME_AFTER_RECEIVE_TIME")
    if _utc(sample.received_at) > now:
        blockers.append("RECEIVE_TIME_IN_FUTURE")
    if blockers:
        clock_error = any(reason in blockers for reason in ("SOURCE_TIME_AFTER_RECEIVE_TIME", "RECEIVE_TIME_IN_FUTURE"))
        return view(ReadbackQuality.INVALID if clock_error else ReadbackQuality.UNKNOWN)
    assert sample.source_time is not None
    age_ms = (now - _utc(sample.source_time)).total_seconds() * 1000
    if sample.quality is ReadbackQuality.SIMULATED:
        blockers.append("SIMULATED_MEASUREMENT")
        if age_ms > policy.max_age_ms:
            blockers.append("ACQUISITION_STALE")
        return view(ReadbackQuality.SIMULATED, value, age_ms)
    if sample.quality is ReadbackQuality.STALE or age_ms > policy.max_age_ms:
        blockers.append("ACQUISITION_STALE")
        return view(ReadbackQuality.STALE, value, age_ms)
    return view(ReadbackQuality.VALID, value, age_ms)


class DispatchObservation(str, Enum):
    ACCEPTED = "ACCEPTED"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class RecordedCurrentRequest:
    """Externally recorded or synthetic request; never an executable command."""
    command_id: str
    equipment_id: str
    registry_revision: str
    target: Binding
    requested_a: float
    dispatch_observation: DispatchObservation
    dispatched_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (self.command_id, self.equipment_id, self.registry_revision):
            _text(value)
        if not isinstance(self.target, (DeviceServerBinding, LegacyCurrentBinding)):
            raise ValueError("typed recorded command target required")
        _number(self.requested_a)
        if not isinstance(self.dispatch_observation, DispatchObservation):
            raise ValueError("typed dispatch observation required")
        if self.dispatched_at is not None:
            _utc(self.dispatched_at)
        if self.dispatch_observation is DispatchObservation.DISPATCHED and self.dispatched_at is None:
            raise ValueError("dispatched request requires dispatch time")


@dataclass(frozen=True)
class CurrentRequestComparison:
    current_matches_request: bool | None
    absolute_difference_a: float | None
    orange_flag: bool | None
    reasons: tuple[str, ...]
    evaluated_at: datetime

    @property
    def establishes_command_success(self) -> bool:
        return False


def compare_recorded_current_request(
    registry: MagnetRegistry,
    request: RecordedCurrentRequest,
    view: CurrentReadbackView,
    *,
    now: datetime,
    policy: CurrentReadbackPolicy,
) -> CurrentRequestComparison:
    """Apply the old strict-greater-than orange rule only to trusted post-dispatch data.

Pure current comparison is not a physical-success acknowledgement. No timeout,
dwell/settling, fault, or output-state success predicate is silently invented.
"""
    if not isinstance(request, RecordedCurrentRequest) or not isinstance(view, CurrentReadbackView) or not isinstance(policy, CurrentReadbackPolicy):
        raise ValueError("typed request, projection, and policy required")
    now = _utc(now)
    checked = project_current_readback(
        registry, view.association, view.sample, now=view.evaluated_at,
        policy=policy, transport_available=view.transport_available,
    )
    blockers = list(checked.reasons)
    if checked != view:
        blockers.append("READBACK_PROJECTION_MISMATCH")
    if now < view.evaluated_at:
        blockers.append("EVALUATION_CLOCK_REGRESSION")
    # A previously VALID display projection can become STALE without any new
    # sample. Recalculate at comparison time; never reuse its cached quality.
    view = project_current_readback(
        registry, view.association, view.sample, now=now,
        policy=policy, transport_available=view.transport_available,
    )
    blockers.extend(view.reasons)
    entry = registry.find(request.equipment_id)
    if request.registry_revision != registry.revision or view.registry_revision != registry.revision:
        blockers.append("REGISTRY_REVISION_MISMATCH")
    if request.equipment_id != view.equipment_id:
        blockers.append("REQUEST_EQUIPMENT_MISMATCH")
    if entry is None or request.equipment_id != entry.equipment_id:
        blockers.append("UNKNOWN_EQUIPMENT_ID")
    else:
        if entry.verification is not RouteVerification.VERIFIED or entry.binding is None:
            blockers.append("COMMAND_ROUTE_UNVERIFIED")
        elif _binding_key(request.target) != _binding_key(entry.binding):
            blockers.append("REQUEST_ROUTE_MISMATCH")
        if entry.limits is None:
            blockers.append("CURRENT_LIMITS_UNVERIFIED")
        elif not entry.limits.minimum_a <= request.requested_a <= entry.limits.maximum_a:
            blockers.append("CURRENT_OUT_OF_RANGE")
    if request.dispatch_observation is not DispatchObservation.DISPATCHED:
        blockers.append(f"DISPATCH_{request.dispatch_observation.value}")
    if view.quality is not ReadbackQuality.VALID or view.measured_a is None:
        blockers.append("READBACK_NOT_VALID")
    if request.dispatched_at is not None:
        if _utc(request.dispatched_at) > view.evaluated_at:
            blockers.append("DISPATCH_TIME_IN_FUTURE")
        if view.source_time is None or view.source_time <= _utc(request.dispatched_at):
            blockers.append("NO_POST_DISPATCH_MEASUREMENT")
    if blockers:
        return CurrentRequestComparison(None, None, None, tuple(dict.fromkeys(blockers)), now)
    difference = abs(request.requested_a - view.measured_a)
    orange = difference > policy.tolerance_a
    return CurrentRequestComparison(not orange, difference, orange, (), now)


ITEST_IMPLEMENTATION_SOURCE = "DeviceServers/power/iTest/DS_itest_psu.py"
ITEST_SCPI_SOURCE = "DeviceServers/power/iTest/scpi_client.py"


def candidate_readback_associations(registry: MagnetRegistry) -> tuple[CurrentReadbackAssociation, ...]:
    """Only iTest measured-current attribute candidates; no invented legacy AI map."""
    return tuple(CurrentReadbackAssociation(
        entry.equipment_id, registry.revision, entry.binding,
        ITestMeasuredCurrentPoint(entry.binding) if isinstance(entry.binding, DeviceServerBinding) else None,
        RouteVerification.CANDIDATE,
        (*entry.provenance, ITEST_IMPLEMENTATION_SOURCE, ITEST_SCPI_SOURCE)
        if isinstance(entry.binding, DeviceServerBinding) else entry.provenance,
    ) for entry in registry.entries)


def readback_candidate_snapshot(association: CurrentReadbackAssociation) -> dict:
    source = association.source
    if isinstance(source, ITestMeasuredCurrentPoint):
        point = {"device": source.binding.device, "slot_id": source.binding.slot_id,
                 "attribute": source.attribute, "ids_attribute": "ids"}
    elif isinstance(source, LegacyMeasuredCurrentPoint):
        point = {"variable": source.variable, "field": source.field}
    else:
        point = None
    return {"source": point, "verification": association.verification.value,
            "provenance": list(association.provenance), "physical_acquisition_required": True,
            "source_time_required": True, "cross_owner_approved": association.cross_owner_approved}


def magnet_display_snapshot(registry: MagnetRegistry) -> dict:
    """Shared display composition for the static export and offline server."""
    snapshot = registry_snapshot(registry)
    snapshot["readback_candidates"] = {
        association.equipment_id: readback_candidate_snapshot(association)
        for association in candidate_readback_associations(registry)
    }
    return snapshot
