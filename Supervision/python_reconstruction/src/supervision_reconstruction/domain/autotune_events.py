"""Event 30 convergence decisions, not a motion or camera-control runtime."""

from __future__ import annotations

import math
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
from .motion_events import MOTION_CONTROLS
from .video_events import CHANNEL_ERROR

NETLIST_PATH = "analysis/main_original_netlist_20261004_r2.json"
NETLIST_SHA256 = "30D8B0A36D67A6C0407A4910CB8F27B364120667363C99256B37E09392CD3731"


class AutotuneStage(Enum):
    CHANNEL3_X = (1, 3, "X", 10, 91014, 35769, 102481, 2, 10)
    CHANNEL3_Y = (2, 3, "Y", 10, 92438, 116973, 36633, 9, 1)
    CHANNEL2_X = (4, 2, "X", 3, 90490, 71114, 99649, 10, 2)
    CHANNEL2_Y = (5, 2, "Y", 3, 91775, 108635, 36234, 9, 1)


@dataclass(frozen=True)
class AutotuneIteration:
    stage: AutotuneStage
    above: bool
    below: bool
    in_band: bool
    move_intent: EffectIntent | None
    terminate_inner_loop: bool
    wait_ms: int = 3000
    read_fresh_centroid_after_frame_barrier: bool = True
    freshness_after_wait_proven: bool = False
    pre_move_stop_guard: bool = False
    maximum_iterations: None = None
    external_effects_blocked: bool = field(default=True, init=False)


def project_autotune_iteration(
    stage: AutotuneStage,
    coordinate: float,
    *,
    stop_motor: bool,
    motor_error: bool,
) -> AutotuneIteration:
    if not isinstance(stage, AutotuneStage):
        raise ValueError("stage must be an AutotuneStage")
    if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
        raise ValueError("coordinate requires a resolved DBL centroid")
    if not math.isfinite(coordinate):
        raise ValueError(
            "NaN/infinity centroid policy remains unqualified; fail closed"
        )
    boolean(stop_motor, "stop_motor")
    boolean(motor_error, "motor_error")
    above, below = coordinate > 251.0, coordinate < 249.0
    in_band = not (above or below)
    _, channel, axis, steps, _, high_uid, low_uid, high_port, low_port = stage.value
    move = None
    if above or below:
        move = EffectIntent(
            "Moteurs SdC GoTo.vi",
            high_uid if above else low_uid,
            (
                ("laser1/laser2", "fresh local Voies NI1409"),
                ("preceding_camera_channel", channel),
                ("Relative Steps", steps),
                ("true_connector_index", high_port if above else low_port),
                ("stop motor", stop_motor),
                ("coordinate_axis", axis),
                ("other_boolean_defaults", "unqualified"),
                ("channel3_callee", "selector 2/Default path, not strict planner"),
            ),
        )
    return AutotuneIteration(
        stage, above, below, in_band, move, in_band or stop_motor or motor_error
    )


def autotune_outer_termination(
    *,
    channel3_y_in_band: bool,
    channel2_y_in_band: bool,
    stop_motor: bool,
) -> bool:
    """Outer loop ignores motor error and BOTH X convergence outputs."""
    for name, value in (
        ("channel3_y_in_band", channel3_y_in_band),
        ("channel2_y_in_band", channel2_y_in_band),
        ("stop_motor", stop_motor),
    ):
        boolean(value, name)
    return (channel3_y_in_band and channel2_y_in_band) or stop_motor


@dataclass(frozen=True)
class AutotuneCameraPlan:
    sequence_uid: int
    requested_channel: int
    frames: tuple[SequenceFrameIntent, ...]
    camera_error_skips_following_motion_stages: bool = False
    external_effects_blocked: bool = field(default=True, init=False)


def plan_autotune_camera_switch(
    channel: int,
    *,
    final_error: ErrorCluster,
) -> AutotuneCameraPlan:
    """Eight barriers differ from the five-frame ordinary channel event."""
    if type(channel) is not int or channel not in (2, 3):
        raise ValueError("autotune camera stage requires channel 2 or 3")
    ter = error_message(final_error, CHANNEL_ERROR)
    if channel == 3:
        (
            seq,
            busy,
            selector,
            delay1,
            stop,
            close,
            delay2,
            clear,
            init,
            grab,
            session,
            idle,
            err,
            settle,
        ) = (
            11854,
            14418,
            92689,
            18939,
            26031,
            20961,
            31574,
            32145,
            57265,
            38132,
            95316,
            95369,
            95417,
            125117,
        )
    else:
        (
            seq,
            busy,
            selector,
            delay1,
            stop,
            close,
            delay2,
            clear,
            init,
            grab,
            session,
            idle,
            err,
            settle,
        ) = (
            35260,
            72350,
            92642,
            71300,
            71379,
            71329,
            71601,
            71621,
            71884,
            71781,
            71977,
            72251,
            72329,
            144916,
        )
    frames = (
        SequenceFrameIntent(
            0,
            (),
            (
                UiPatch("Wait", "Value", True, busy),
                UiPatch("Voies NI1409", "Value", channel, selector),
            ),
        ),
        SequenceFrameIntent(1, (EffectIntent("Wait (ms)", delay1, (("ms", 500),)),)),
        SequenceFrameIntent(
            2,
            (
                EffectIntent(
                    "IMAQ Stop.vi", stop, (("session", "fresh local IMAQ Session Out"),)
                ),
                EffectIntent("IMAQ Close.vi", close, (("after", stop),)),
            ),
        ),
        SequenceFrameIntent(
            3,
            (
                EffectIntent("Clear Errors.vi", clear, (("error", "Close result"),)),
                EffectIntent("Wait (ms)", delay2, (("ms", 500),)),
            ),
        ),
        SequenceFrameIntent(
            4,
            (
                EffectIntent(
                    "IMAQ Init.vi",
                    init,
                    (("interface", "img0"), ("error", "Clear Errors result")),
                ),
                EffectIntent(
                    "IMAQ Grab Setup.vi",
                    grab,
                    (("after", init), ("channel", "fresh local Voies NI1409")),
                ),
            ),
        ),
        SequenceFrameIntent(
            5,
            (),
            (
                UiPatch(
                    "IMAQ Session Out", "Value", "Grab Setup session result", session
                ),
            ),
        ),
        SequenceFrameIntent(
            6,
            (),
            (UiPatch("TER", "Value", ter, err),)
            if ter is not None
            else (UiPatch("Wait", "Value", False, idle),),
        ),
        SequenceFrameIntent(7, (EffectIntent("Wait (ms)", settle, (("ms", 3000),)),)),
    )
    return AutotuneCameraPlan(seq, channel, frames)


@dataclass(frozen=True)
class AutotunePlan:
    entry_patches: tuple[UiPatch, ...]
    stage_order: tuple[str, ...]
    camera_switch_sequences: tuple[tuple[int, int], ...]
    exit_patches: tuple[UiPatch, ...]
    completion_journal: EffectIntent
    disabled_control_hide_uid: int = 89678
    complete_runtime: bool = False
    external_effects_blocked: bool = field(default=True, init=False)


def plan_autotune() -> AutotunePlan:
    return AutotunePlan(
        tuple(UiPatch(x, "Visible", False) for x in MOTION_CONTROLS if x != "autotune")
        + (
            UiPatch("Initialisation", "Visible", False),
            UiPatch("Odd / Even", "Value", 1, 71284),
            UiPatch("Moyenne CxCy", "Value", 16, 89557),
        ),
        (
            "camera channel 3",
            "channel 3 X",
            "channel 3 Y",
            "camera channel 2",
            "channel 2 X",
            "channel 2 Y",
        ),
        ((11854, 3), (35260, 2)),
        tuple(UiPatch(x, "Visible", True) for x in MOTION_CONTROLS if x != "autotune")
        + (
            UiPatch("Initialisation", "Visible", True),
            UiPatch("Voies NI1409", "Visible", True, 151603),
            UiPatch("autotune", "Value", False, 92879),
            UiPatch("stop motor", "Value", False, 125466),
        ),
        EffectIntent(
            "2_SUP_Journal_des _erreurs.vi",
            92885,
            (
                ("text", "Autotune terminé "),
                ("path", "c:\\Messages.xls"),
                ("local_journal", "Jounal des messages"),
                ("success_guard", False),
            ),
        ),
    )
