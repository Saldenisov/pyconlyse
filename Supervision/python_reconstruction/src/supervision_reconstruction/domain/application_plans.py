"""Pure calculations and immutable UI plans for remaining application VIs."""

from __future__ import annotations

from dataclasses import dataclass

from .dialog_error import DialogType


@dataclass(frozen=True)
class ApplicationEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


CENTROID_FLOAT_CONVERSION_BLOCKED = ApplicationEvidenceBlock(
    ("sous vi LigneCentroide2.vi",), False,
    ("LabVIEW To Long Integer rounding, NaN/Inf, and overflow semantics for centroid floating inputs",),
)
INIT_OPEN_CLOSE_BLOCKED = ApplicationEvidenceBlock(
    ("Init_Open_Close.vi",), False,
    ("Tree Invoke Node method/refnum/error semantics", "Directory to Tree filesystem/path traversal semantics"),
)
DETAILS_DIALOG_BLOCKED = ApplicationEvidenceBlock(
    ("Details Display Dialog.vi",), False,
    (
        "modal front-panel/event-loop timing and stop-event propagation",
        "control refnum/property/error semantics",
        "text encoding, size measurement, help-window status, and window geometry",
    ),
)


@dataclass(frozen=True)
class CentroidLines:
    ligne_x: tuple[int, int, int, int]
    ligne_z: tuple[int, int, int, int]


@dataclass(frozen=True)
class InitOpenClosePlan:
    tree_identity: str
    search_root: str
    pattern: str
    operations: tuple[str, ...]
    blocked: ApplicationEvidenceBlock


@dataclass(frozen=True)
class DetailsDialogPlan:
    dialog_type: DialogType
    error_or_warning: bool
    ok_visible: bool
    continue_visible: bool
    stop_visible: bool
    operations: tuple[str, ...]
    blocked: ApplicationEvidenceBlock


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not -(2**31) <= value <= 2**31 - 1:
        raise TypeError(f"{name} must be signed I32 int")


def centroid_lines_from_i32(centroid_x: int, centroid_y: int) -> CentroidLines:
    """Exact Formula Node/Bundle ordering after already-resolved I32 conversion."""

    _require_i32(centroid_x, name="centroid_x")
    _require_i32(centroid_y, name="centroid_y")
    values = (centroid_x - 10, centroid_y, centroid_x + 10, centroid_y, centroid_x, centroid_y + 10, centroid_x, centroid_y - 10)
    if any(not -(2**31) <= value <= 2**31 - 1 for value in values):
        raise OverflowError("Formula Node output exceeds signed I32")
    return CentroidLines(values[:4], values[4:])


def plan_init_open_close(tree_identity: str, search_root: str, pattern: str) -> InitOpenClosePlan:
    for name, value in (("tree_identity", tree_identity), ("search_root", search_root), ("pattern", pattern)):
        if not isinstance(value, str):
            raise TypeError(f"{name} must be str")
    return InitOpenClosePlan(tree_identity, search_root, pattern, (
        "Invoke Tree Delete Tree Items (ÉditerÉltsArbre.Suppr) with True",
        "invoke Directory to Tree(tree, search root, pattern)",
        "Invoke Tree Open/Close All (Ouvrir/Fermer.Tout) with False",
    ), INIT_OPEN_CLOSE_BLOCKED)


def plan_details_display_dialog(
    dialog_type: DialogType | int,
    error_or_warning: bool,
) -> DetailsDialogPlan:
    """Return only the proven initial button-visibility branch and sequence plan."""

    if type(dialog_type) is bool or not isinstance(dialog_type, (DialogType, int)):
        raise TypeError("dialog_type must be DialogType or int")
    try:
        typed_dialog = DialogType(dialog_type)
    except ValueError as exc:
        raise ValueError("dialog_type is not a wired DialogTypeEnum value") from exc
    if type(error_or_warning) is not bool:
        raise TypeError("error_or_warning must be bool")
    ok_visible = typed_dialog is DialogType.OK_MESSAGE
    return DetailsDialogPlan(
        typed_dialog, error_or_warning, ok_visible, not ok_visible, not ok_visible,
        (
            "sequence 0: configure button captions and initial visibility",
            "sequence 0: prepare source/details controls and optional truncation/help text",
            "sequence 1: Set Bold Text and scrollbar-height branch plan",
            "sequence 2: compute/control window geometry plan",
            "sequence 3: open front panel, configure keyboard focus, run event loop, close reference",
        ), DETAILS_DIALOG_BLOCKED,
    )
