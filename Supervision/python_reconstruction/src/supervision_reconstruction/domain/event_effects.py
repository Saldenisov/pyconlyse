"""Immutable effect descriptions, never drivers, callbacks or schedulers."""

from __future__ import annotations

from dataclasses import dataclass, field

from .fw102x_errors import ErrorCluster

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/remaining_event_evidence_20261004.json"
EVIDENCE_SHA256 = "B32366AB45F2F50416E94303A602F9C215A4D01902B82BC3C657679EAD02CE92"


@dataclass(frozen=True)
class UiPatch:
    control: str
    property: str
    value: object
    node_uid: int | None = None


@dataclass(frozen=True)
class EffectIntent:
    operation: str
    node_uid: int
    arguments: tuple[tuple[str, object], ...] = ()
    external_effects_blocked: bool = field(default=True, init=False)


@dataclass(frozen=True)
class SequenceFrameIntent:
    """Frame barrier is ordered; members without wires are NOT a serial list."""

    index: int
    effects: tuple[EffectIntent, ...] = ()
    ui_patches: tuple[UiPatch, ...] = ()
    note: str = "same-frame operations follow original wires, not tuple order"


def boolean(value: bool, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a Boolean")
    return value


def error_message(error: ErrorCluster, prefix: str) -> str | None:
    if not isinstance(error, ErrorCluster):
        raise ValueError("error must be an externally resolved ErrorCluster")
    boolean(error.status, "error.status")
    if not isinstance(error.source, str):
        raise ValueError("error.source must be a string")
    return prefix + error.source if error.status else None
