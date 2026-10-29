"""Main events 27-29: discovery/jog decisions with every driver call blocked."""

from __future__ import annotations

from dataclasses import dataclass, field

from .event_effects import EffectIntent, SequenceFrameIntent, UiPatch, boolean
from .fw102x_errors import ErrorCluster

MOTION_CONTROLS = (
    "Move forward X",
    "Move reverse X",
    "Move forward Y",
    "Move reverse Y",
    "autotune",
)


@dataclass(frozen=True)
class InitializationPlan:
    frames: tuple[SequenceFrameIntent, ...]
    discovery_key_supplied: bool
    zero_motor_numbers: tuple[int, ...]
    no_devices_message: str | None
    external_effects_blocked: bool = field(default=True, init=False)


def plan_motor_initialization(discovered_key: str | None = None) -> InitializationPlan:
    if discovered_key is not None and not isinstance(discovered_key, str):
        raise ValueError("discovered_key must be an external discovery string result")
    empty = discovered_key == ""
    resolved = discovered_key is not None
    calls = (
        EffectIntent(
            "InitSingleDevice.vi", 274396, (("timeout", 5000), ("flag", True))
        ),
    )
    if resolved and not empty:
        calls += (
            EffectIntent("GetIdentification.vi", 274317, (("device_address", 0),)),
        )
        calls += tuple(
            EffectIntent("SetZeroPosition.vi", 274246, (("motor_number", number),))
            for number in range(1, 5)
        )
    if empty:
        calls += (
            EffectIntent(
                "One Button Dialog",
                274165,
                (("message", "No devices found during discovery."),),
            ),
        )
    local_results = (
        UiPatch("DeviceKey Out", "Value", "InitSingleDevice port 2 result", 286518),
        UiPatch("CmdLib Out", "Value", "InitSingleDevice port 3 result", 273836),
    )
    if resolved and not empty:
        local_results += (
            UiPatch(
                "Identification", "Value", "GetIdentification port 10 result", 61332
            ),
            UiPatch(
                "Device Address Out", "Value", "GetIdentification port 8 result", 91956
            ),
        )
    frames = (
        SequenceFrameIntent(
            0, (), tuple(UiPatch(x, "Visible", False) for x in MOTION_CONTROLS)
        ),
        SequenceFrameIntent(
            1,
            calls,
            local_results,
            note=(
                "Init -> String Length; zero length shows dialog; all positive lengths "
                "take Default discovery branch; zero calls 1..4 lack loop "
                "error feedback"
            ),
        ),
        SequenceFrameIntent(
            2,
            (),
            tuple(UiPatch(x, "Visible", True) for x in MOTION_CONTROLS)
            + (UiPatch("Initialisation", "Value", False, 105428),),
        ),
    )
    return InitializationPlan(
        frames,
        resolved,
        (1, 2, 3, 4) if resolved and not empty else (),
        "No devices found during discovery." if empty else None,
    )


@dataclass(frozen=True)
class ManualJogPlan:
    event_index: int
    control_label: str
    motor_index: int
    motor_number: int
    signed_steps: int
    hide_patches: tuple[UiPatch, ...]
    motion_call: EffectIntent
    polling_calls: tuple[EffectIntent, ...]
    restore_patches: tuple[UiPatch, ...]
    button_resets: tuple[UiPatch, ...]
    event_newval_guarded: bool = False
    loop_timeout_ms: None = None
    external_effects_blocked: bool = field(default=True, init=False)


def plan_manual_jog(
    control_label: str, *, motor_numbers: tuple[int, ...], relative_steps: int
) -> ManualJogPlan:
    labels = {
        "Move forward X": (28, 0, False),
        "Move forward Y": (28, 1, False),
        "Move reverse X": (29, 0, True),
        "Move reverse Y": (29, 1, True),
    }
    if control_label not in labels:
        raise ValueError("Unknown jog label; native Y/Default fallback is not enabled")
    index, axis, reverse = labels[control_label]
    if type(relative_steps) is not int or not -(2**31) <= relative_steps < 2**31:
        raise ValueError("relative_steps must be an I32, not a Boolean")
    if reverse and relative_steps == -(2**31):
        raise ValueError("I32 negate overflow remains unqualified")
    if len(motor_numbers) <= axis:
        raise ValueError("Index Array out-of-range default is not a commissioned motor")
    motor = motor_numbers[axis]
    if type(motor) is not int or not 0 <= motor < 2**32:
        raise ValueError("motor number requires an externally resolved U32")
    signed = -relative_steps if reverse else relative_steps
    hidden = tuple(
        x for x in MOTION_CONTROLS + ("Initialisation",) if x != control_label
    )
    uids = (266618, 266247, 266424, 266475) if reverse else (96219, 95853, 96026, 96077)
    reset = (
        ("Move reverse X", "Move reverse Y")
        if reverse
        else ("Move forward X", "Move forward Y")
    )
    return ManualJogPlan(
        index,
        control_label,
        axis,
        motor,
        signed,
        tuple(UiPatch(x, "Visible", False) for x in hidden)
        + (UiPatch("Voies NI1409", "DisabledEnum", 2),),
        EffectIntent(
            "RelativeMove.vi",
            uids[0],
            (
                ("motor_number", motor),
                ("relative_steps", signed),
                ("session", "fresh local CmdLib/DeviceKey/Device Address Out"),
            ),
        ),
        tuple(
            EffectIntent(name, uid)
            for name, uid in zip(
                ("GetErrorMsg.vi", "GetMotionDone.vi", "GetPosition.vi"), uids[1:]
            )
        ),
        tuple(
            UiPatch(x, "Visible", True) for x in MOTION_CONTROLS + ("Initialisation",)
        )
        + (UiPatch("Voies NI1409", "DisabledEnum", 0),),
        tuple(UiPatch(x, "Value", False) for x in reset + ("stop motor",)),
    )


@dataclass(frozen=True)
class JogPollProjection:
    terminate: bool
    abort_intent: EffectIntent | None
    motor_position: int
    termination_error_source: str = "GetMotionDone.vi, NOT GetPosition/Abort result"
    external_effects_blocked: bool = field(default=True, init=False)


def project_jog_poll(
    *,
    event_index: int,
    motion_done: bool,
    motion_done_error: ErrorCluster,
    stop_motor: bool,
    position_result: int,
) -> JogPollProjection:
    if type(event_index) is not int or event_index not in (28, 29):
        raise ValueError("event_index must be 28 or 29")
    boolean(motion_done, "motion_done")
    boolean(stop_motor, "stop_motor")
    if not isinstance(motion_done_error, ErrorCluster):
        raise ValueError("motion_done_error requires a resolved ErrorCluster")
    boolean(motion_done_error.status, "motion_done_error.status")
    if type(position_result) is not int or not -(2**31) <= position_result < 2**31:
        raise ValueError("position_result requires an I32 GetPosition result")
    abort = (
        EffectIntent(
            "AbortMotion.vi",
            95968 if event_index == 28 else 266362,
            (("after", "GetPosition.vi"),),
        )
        if stop_motor
        else None
    )
    return JogPollProjection(
        motion_done or motion_done_error.status or stop_motor, abort, position_result
    )


def project_motion_error(
    final_error: ErrorCluster,
    *,
    event_index: int = 27,
) -> EffectIntent | None:
    if type(event_index) is not int or event_index not in (27, 28, 29):
        raise ValueError("event_index must be 27, 28 or 29")
    if not isinstance(final_error, ErrorCluster):
        raise ValueError("final_error requires a resolved ErrorCluster")
    boolean(final_error.status, "final_error.status")
    if not final_error.status:
        return None
    if type(final_error.code) is not int or not -(2**31) <= final_error.code < 2**31:
        raise ValueError("final_error.code must be an I32")
    if not isinstance(final_error.source, str):
        raise ValueError("final_error.source must be a string")
    uid = {27: 77718, 28: 170563, 29: 266960}[event_index]
    return EffectIntent(
        "2_SUP_Journal_des _erreurs.vi",
        uid,
        (
            ("text", f"Erreur N° {final_error.code} : {final_error.source}"),
            ("path", "c:\\Erreurs.xls"),
            ("local_journal", "Journal des erreurs"),
        ),
    )
