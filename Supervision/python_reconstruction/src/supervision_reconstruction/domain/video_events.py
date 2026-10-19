"""Main events 21/24/25/32/33: source-grounded offline UI/camera intents.

No IMAQ, VISA, filesystem, dialogs, sleeps or network operations are executed.
Supplied errors/formatter text are external observations, not simulated success.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .event_effects import (
    EffectIntent,
    SequenceFrameIntent,
    UiPatch,
    boolean,
    error_message,
)
from .fw102x_errors import ErrorCluster

VIDEO_TOOL_FIELDS = ("zoom 0,5", "zoom x1", "zoom x2", "zoom x3", "250", "Clear 250")
VIDEO_TOOL_ERROR = "Erreur de commande du cluster d'outils vidéo"
THRESHOLD_ERROR = "Erreur de changement du seuil Noir et Blanc de la carte NI1409"
CHANNEL_ERROR = "Erreur de changement voie de la carte NI1409"


@dataclass(frozen=True)
class RoiIntent:
    global_rectangle: tuple[int, int, int, int]
    contour_type: int = 0
    roi_type: int = 3

    @property
    def points(self) -> tuple[int, int, int, int]:
        """Native rectangular contour Points equals its global rectangle."""
        return self.global_rectangle


@dataclass(frozen=True)
class VideoToolPlan:
    mask: int
    selected_case: int
    branch_properties: tuple[UiPatch, ...]
    reset_tools: tuple[bool, ...]
    center_properties: tuple[UiPatch, ...]
    ter_text: str | None
    delay_ms: None = None  # native 250 feeds image centers, NOT Wait (ms)
    external_effects_blocked: bool = field(default=True, init=False)


def plan_video_tools(
    values: tuple[bool, ...], *, final_property_error: ErrorCluster
) -> VideoToolPlan:
    if len(values) != 6 or any(type(v) is not bool for v in values):
        raise ValueError("Outils vidéo requires six ordered Boolean fields")
    mask = sum(1 << i for i, v in enumerate(values) if v)
    selected = mask if mask in (1, 2, 4, 8, 16, 32) else 0
    properties = ()
    zooms = {1: 0.5, 2: 1.0, 4: 2.0, 8: 4.0}
    zoom_uids = {
        1: (3786, 22165),
        2: (26637, 26672),
        4: (20043, 20091),
        8: (20895, 20966),
    }
    if selected in zooms:
        properties = tuple(
            UiPatch(control, axis, zooms[selected], uid)
            for control, uid in zip(("SOURCE", "CALCULS"), zoom_uids[selected])
            for axis in ("X Zoom", "Y Zoom")
        )
    elif selected in (16, 32):
        rectangle = (200, 200, 300, 300) if selected == 16 else (0, 0, 0, 0)
        properties = (
            UiPatch(
                "SOURCE",
                "ROI",
                RoiIntent(rectangle),
                33679 if selected == 16 else 20341,
            ),
        )
    return VideoToolPlan(
        mask,
        selected,
        properties,
        (False,) * 6,
        tuple(
            UiPatch("SOURCE", f"Image Center {axis} Position", 250, 23647)
            for axis in ("X", "Y")
        ),
        error_message(final_property_error, VIDEO_TOOL_ERROR),
    )


@dataclass(frozen=True)
class CameraEventPlan:
    event_index: int
    pre_sequence_patches: tuple[UiPatch, ...]
    frames: tuple[SequenceFrameIntent, ...]
    final_patches: tuple[UiPatch, ...]
    ter_text: str | None
    success_format: str | None
    runtime_boundary: str
    external_effects_blocked: bool = field(default=True, init=False)


def _result_patches(error, prefix, formatted_text, wait_reset_uid):
    ter = error_message(error, prefix)
    patches = []
    if ter is not None:
        patches.append(UiPatch("TER", "Value", ter))
    else:
        if formatted_text is not None:
            if not isinstance(formatted_text, str):
                raise ValueError("formatted_text is an external string result")
            patches.append(UiPatch("TME", "Value", formatted_text))
        if wait_reset_uid is not None:
            patches.append(UiPatch("Wait", "Value", False, wait_reset_uid))
    return ter, tuple(patches)


def plan_threshold_mouse_up(
    *, final_error: ErrorCluster, formatted_text: str | None = None
) -> CameraEventPlan:
    """Mouse Up on either threshold, NOT only black-threshold Value Change."""
    ter, result = _result_patches(final_error, THRESHOLD_ERROR, formatted_text, None)
    frames = (
        SequenceFrameIntent(
            0,
            (EffectIntent("Wait (ms)", 14738, (("ms", 300),)),),
            (UiPatch("Wait", "Value", True, 16708),),
        ),
        SequenceFrameIntent(
            1,
            (
                EffectIntent("IMAQ Stop.vi", 17684, (("session", "IMAQ Session Out"),)),
                EffectIntent("IMAQ Close.vi", 17967, (("after", 17684),)),
            ),
            note=(
                "read both fresh local thresholds; Stop -> Close by error/session wires"
            ),
        ),
        SequenceFrameIntent(
            2,
            (
                EffectIntent("IMAQ Init.vi", 36570, (("interface", "img0"),)),
                EffectIntent(
                    "IMAQ property",
                    15786,
                    (
                        ("White Reference", "fresh local Seuil BLANC (V)"),
                        ("Black Reference", "fresh local Seuil NOIR (V)"),
                        ("read", "Image Type"),
                    ),
                ),
                EffectIntent("IMAQ Create", 36610, (("name", "image souce"),)),
                EffectIntent(
                    "IMAQ Grab Setup.vi",
                    36531,
                    (("channel", "fresh local Voies NI1409"),),
                ),
            ),
            note=(
                "Init -> property -> Create -> Grab by error wires; defaults unresolved"
            ),
        ),
        SequenceFrameIntent(
            3,
            (EffectIntent("Wait (ms)", 18644, (("ms", 50),)),),
            (UiPatch("IMAQ Session Out", "Value", "Grab Setup session result", 15483),),
        ),
    )
    return CameraEventPlan(
        24,
        (),
        frames,
        (UiPatch("Wait", "Value", False, 14709),) + result,
        ter,
        None if ter else "Changement des seuils: Blanc = %.2fV, Noir = %.2fV.",
        "IMAQ/refnum/property/errors and formatter supplied externally; no rollback",
    )


def plan_camera_channel_change(
    *, final_error: ErrorCluster, formatted_text: str | None = None
) -> CameraEventPlan:
    ter, result = _result_patches(final_error, CHANNEL_ERROR, formatted_text, 58781)
    frames = (
        SequenceFrameIntent(0, (EffectIntent("Wait (ms)", 92671, (("ms", 500),)),)),
        SequenceFrameIntent(
            1,
            (
                EffectIntent("IMAQ Stop.vi", 71816, (("session", "IMAQ Session Out"),)),
                EffectIntent("IMAQ Close.vi", 92287, (("after", 71816),)),
            ),
        ),
        SequenceFrameIntent(
            2,
            (
                EffectIntent(
                    "Clear Errors.vi", 72477, (("input", "Close error result"),)
                ),
                EffectIntent("Wait (ms)", 92232, (("ms", 500),)),
            ),
        ),
        SequenceFrameIntent(
            3,
            (
                EffectIntent("IMAQ Init.vi", 92484, (("interface", "img0"),)),
                EffectIntent(
                    "IMAQ Grab Setup.vi",
                    92441,
                    (("channel", "fresh local Voies NI1409, NOT Event NewVal"),),
                ),
            ),
            note="Init -> Grab by original wires; Clear Errors precedes Init",
        ),
        SequenceFrameIntent(
            4,
            (),
            (UiPatch("IMAQ Session Out", "Value", "Grab Setup session result", 92679),),
        ),
    )
    return CameraEventPlan(
        25,
        (UiPatch("Wait", "Value", True, 92224),),
        frames,
        result,
        ter,
        None if ter else "Changement de voies de \nla carte NI1409:\nVoie N°: %.0f. ",
        "Wait stays True on Error; fresh local channel and formatter are external",
    )


@dataclass(frozen=True)
class DensityEventPlan:
    event_index: int = 32
    selector: bool = False
    reachable_effects: tuple[EffectIntent, ...] = ()
    dead_branch_uids: tuple[int, ...] = (
        17431,
        17485,
        17531,
        17574,
        17627,
        17666,
        28756,
        30337,
        31193,
        34747,
    )
    external_effects_blocked: bool = field(default=True, init=False)


def plan_density_change() -> DensityEventPlan:
    """Original case 24546 has a literal False input, not NewVal."""
    return DensityEventPlan()


@dataclass(frozen=True)
class SaveImagePlan:
    active: bool
    dialog_pending: bool
    dialog_cancelled: bool | None
    start_path: str | None
    prepare_effects: tuple[EffectIntent, ...]
    write_effects: tuple[EffectIntent, ...]
    reset_value: bool = False
    unresolved_image_uid: int = 83225
    external_effects_blocked: bool = field(default=True, init=False)


def plan_save_image(
    new_value: bool,
    *,
    resolved_year: int | None = None,
    dialog_cancelled: bool | None = None,
    selected_path: str | None = None,
) -> SaveImagePlan:
    boolean(new_value, "new_value")
    if not new_value:
        return SaveImagePlan(False, False, None, None, (), ())
    if type(resolved_year) is not int or not -(2**31) <= resolved_year <= 2**31 - 1:
        raise ValueError("resolved_year requires an externally decoded I32 integer")
    if dialog_cancelled is not None:
        boolean(dialog_cancelled, "dialog_cancelled")
    start_path = "Z:\\Manips\\Mesures\\" + str(resolved_year)
    prepare = (
        EffectIntent(
            "IMAQ Extract",
            82316,
            (("source", "SOURCE"), ("destination_local_uid", 83225)),
        ),
        EffectIntent(
            "IMAQ WindDraw",
            82401,
            (
                ("window", 1),
                ("title", "Image sauvegardée"),
                ("flag", False),
                ("after", 82316),
            ),
        ),
        EffectIntent(
            "Boîte de dialogue de fichier",
            56786,
            (("start_path", start_path), ("error_from", 82401)),
        ),
    )
    write = ()
    if dialog_cancelled is False:
        if not isinstance(selected_path, str):
            raise ValueError("selected_path requires an external dialog string result")
        write = (
            EffectIntent(
                "IMAQ GetPalette", 56663, (("palette", 2), ("error_from", 56786))
            ),
            EffectIntent(
                "IMAQ Write TIFF File",
                83086,
                (
                    ("selected_path", selected_path),
                    ("Rows Per Strip", 0),
                    ("Photometric", 1),
                    ("Compression Type", 0),
                    ("image_from", 82401),
                    ("palette_and_error_from", 56663),
                ),
            ),
        )
    return SaveImagePlan(
        True, dialog_cancelled is None, dialog_cancelled, start_path, prepare, write
    )
