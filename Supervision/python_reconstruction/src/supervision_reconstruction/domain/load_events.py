"""Events 22/23/31: file-browser/display decisions, not equipment presets."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .event_effects import (
    EffectIntent,
    SequenceFrameIntent,
    UiPatch,
    boolean,
    error_message,
)
from .fw102x_errors import ErrorCluster

TREE_ERROR = "Erreur de lecture du dossier de chargement des Tirs."


class LegacyPathState(Enum):
    VALID = "externally classified valid LabVIEW path"
    EMPTY = "empty path"
    NOT_A_PATH = "Not A Path"


@dataclass(frozen=True)
class LoadEventPlan:
    active: bool
    dialog_required: bool
    selected_directory: str | None
    effects: tuple[EffectIntent, ...]
    ui_patches: tuple[UiPatch, ...]
    hardware_commands: tuple = ()
    external_effects_blocked: bool = field(default=True, init=False)


def plan_load_toggle(
    new_value: bool,
    *,
    path_state: LegacyPathState = LegacyPathState.VALID,
    cached_directory: str | None = None,
    dialog_directory: str | None = None,
) -> LoadEventPlan:
    boolean(new_value, "new_value")
    if not new_value:
        return LoadEventPlan(
            False,
            False,
            None,
            (
                EffectIntent("Close Reference", 20457, (("reference", "Ref fichier"),)),
                EffectIntent("Simple Error Handler.vi", 20468, (("after", 20457),)),
            ),
            (
                UiPatch("Onglet Fichiers", "Value", 2, 17474),
                UiPatch("Onglet Bas Gauche", "Value", 0, 18782),
            ),
        )
    if not isinstance(path_state, LegacyPathState):
        raise ValueError("path_state requires external LabVIEW path classification")
    dialog = path_state is not LegacyPathState.VALID
    directory = dialog_directory if dialog else cached_directory
    if not dialog and directory is None:
        raise ValueError("VALID path requires an externally resolved cached_directory")
    if directory is not None and not isinstance(directory, str):
        raise ValueError("directory must be an externally resolved path string")
    effects = ()
    patches = []
    if dialog:
        effects += (
            EffectIntent("File Dialog", 20536, (("start_path", cached_directory),)),
        )
        if directory is not None:
            patches.append(UiPatch("Chemin des fichiers", "Value", directory, 20571))
    if directory is not None:
        # No explicit cancelled/error guard exists between dialog and wrapper.
        effects += (
            EffectIntent(
                "Init_Open_Close.vi",
                20926,
                (("directory", directory), ("tree", "Tree")),
            ),
            EffectIntent("Simple Error Handler.vi", 4581, (("after", 20926),)),
        )
        patches.append(UiPatch("Ref fichier", "Value", "wrapper refnum result", 2913))
    patches.extend(
        (
            UiPatch("Onglet Bas Gauche", "Value", 1, 13439),
            UiPatch("Onglet Fichiers", "Value", 0, 17802),
        )
    )
    return LoadEventPlan(True, dialog, directory, effects, tuple(patches))


@dataclass(frozen=True)
class ValidateLoadPlan:
    active: bool
    frames: tuple[SequenceFrameIntent, ...]
    reset_value: bool = False
    read_outputs_consumed: bool = False
    equipment_updates: tuple = ()
    external_effects_blocked: bool = field(default=True, init=False)


def plan_validate_load(new_value: bool, *, current_tag: str = "") -> ValidateLoadPlan:
    boolean(new_value, "new_value")
    if not new_value:
        return ValidateLoadPlan(False, ())
    if not isinstance(current_tag, str):
        raise ValueError("current_tag must be an externally resolved string")
    frames = (
        SequenceFrameIntent(
            0,
            tuple(
                EffectIntent(
                    "Read from Text File",
                    13033,
                    (
                        ("path_string", current_tag),
                        ("count", count),
                        ("output_consumed", False),
                    ),
                )
                for count in range(10)
            ),
            note="For Loop 1195 N=10; count=i; ALL read outputs discarded",
        ),
        SequenceFrameIntent(
            1,
            (
                EffectIntent(
                    "Tree property",
                    20744,
                    (
                        ("reference", "Ref fichier"),
                        ("ActiveItemTag", current_tag),
                        ("read", "Cell String"),
                    ),
                ),
                EffectIntent("Close Reference", 6063, (("after", 20744),)),
                EffectIntent("Simple Error Handler.vi", 6121, (("after", 6063),)),
            ),
            (
                UiPatch("Tir en cours:", "Value", "Tree Cell String result", 13796),
                UiPatch("Tir en cours bis", "Value", "Tree Cell String result", 841),
                UiPatch("Onglet Fichiers", "Value", 2, 6178),
                UiPatch("Onglet Bas Gauche", "Value", 0, 6271),
            ),
        ),
    )
    return ValidateLoadPlan(True, frames)


@dataclass(frozen=True)
class TreeSelectionProjection:
    current_tag: str
    ter_text: str | None
    tag_written_even_on_error: bool = True
    external_effects_blocked: bool = field(default=True, init=False)


def project_tree_selection(
    *, variant_string_result: str, final_error: ErrorCluster
) -> TreeSelectionProjection:
    """Property Value -> Variant To Data(string); its output always writes tag."""
    if not isinstance(variant_string_result, str):
        raise ValueError(
            "variant_string_result requires external Variant To Data output"
        )
    return TreeSelectionProjection(
        variant_string_result, error_message(final_error, TREE_ERROR)
    )
