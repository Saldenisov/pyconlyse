"""Pure reconstructions of the Initialize and Validate LabVIEW utility VIs.

The module returns values and UI-effect *plans* only.  It never reads a path,
opens a dialog, mutates a GUI control, or calls LabVIEW.
"""

from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Tuple


@dataclass(frozen=True)
class BoolPropertyWrite:
    """One ordered Boolean property-node write, without GUI I/O."""

    property_name: str
    value: bool


@dataclass(frozen=True)
class BoolControlEffectPlan:
    """Ordered property writes for one control identity; error propagation is unmodeled."""

    control_identity: str
    writes: Tuple[BoolPropertyWrite, ...]


@dataclass(frozen=True)
class InitializePlan:
    """Pure result of ``Initialize.vi``."""

    paths: Tuple[str, ...]
    working_effect: BoolControlEffectPlan


@dataclass(frozen=True)
class ValidatePathResult:
    """Pure result of the evidenced ``Valid Path?`` boolean graph."""

    valid_path: bool
    is_windows_shortcut: bool
    path_ref_is_valid: bool
    leaf_name: str


def initialize_search(
    path_to_start_search: str, *, working_control_identity: str
) -> InitializePlan:
    """Build the VI's single-element path array and Working-control effect plan."""

    if not isinstance(path_to_start_search, str):
        raise TypeError("path_to_start_search must be str")
    if not isinstance(working_control_identity, str):
        raise TypeError("working_control_identity must be str")

    return InitializePlan(
        paths=(path_to_start_search,),
        working_effect=BoolControlEffectPlan(
            control_identity=working_control_identity,
            writes=(
                BoolPropertyWrite("Visible", True),
                BoolPropertyWrite("Blinking", True),
            ),
        ),
    )


def is_legacy_windows_shortcut_leaf_name(leaf_name: str) -> bool:
    """Match the diagram's two exact suffix comparisons: ``.LNK`` and ``.lnk``."""

    if not isinstance(leaf_name, str):
        raise TypeError("leaf_name must be str")

    return leaf_name.endswith(".LNK") or leaf_name.endswith(".lnk")


def strip_windows_path_leaf_name(path: str) -> str:
    """Pure Windows-path counterpart of the diagram's ``Strip Path`` name output."""

    if not isinstance(path, str):
        raise TypeError("path must be str")
    return PureWindowsPath(path).name


def validate_path_signal(
    *, path_ref_is_valid: bool, path: str
) -> ValidatePathResult:
    """Reconstruct ``NOT((not a path) OR (.LNK or .lnk))`` without filesystem I/O.

    ``path_ref_is_valid`` represents the output complement of LabVIEW's
    ``Not A Number/Path/Refnum?`` primitive.  Supplying it explicitly avoids
    guessing LabVIEW Path refnum coercion or inspecting the caller filesystem.
    """

    if type(path_ref_is_valid) is not bool:
        raise TypeError("path_ref_is_valid must be bool")
    leaf_name = strip_windows_path_leaf_name(path)
    is_shortcut = is_legacy_windows_shortcut_leaf_name(leaf_name)
    return ValidatePathResult(
        valid_path=path_ref_is_valid and not is_shortcut,
        is_windows_shortcut=is_shortcut,
        path_ref_is_valid=path_ref_is_valid,
        leaf_name=leaf_name,
    )
