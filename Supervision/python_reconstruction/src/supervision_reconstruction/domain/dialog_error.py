"""Pure, evidence-bounded control flow for SuperVision dialog/error VIs.

The models below encode only decisions visible in the LabVIEW Print diagrams
and confirmed by both lvkit descriptions.  They describe UI/Help/Stop work as
immutable data; they do not open windows, launch Help, touch refnums, or stop
execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .fw102x_errors import ErrorCluster


I32_MIN = -(2**31)
I32_MAX = 2**31 - 1


class DialogType(IntEnum):
    """Wired ``DialogTypeEnum`` values in General Error Handler CORE.vi."""

    NO_DIALOG = 0
    OK_MESSAGE = 1
    CONTINUE_OR_STOP_MESSAGE = 2
    AUTO_ERROR_HANDLING_DIALOG = 3
    OK_MESSAGE_WITH_WARNINGS = 4
    CONTINUE_STOP_WITH_WARNINGS = 5


class ThreeButtonChoice(IntEnum):
    """Connector-pane ordering of Three Button Dialog CORE.vi output."""

    LEFT_BUTTON = 0
    CENTER_BUTTON = 1
    RIGHT_BUTTON = 2
    WINDOW_CLOSE = 3


@dataclass(frozen=True)
class DialogErrorEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


DIALOG_ERROR_EFFECTS_BLOCKED = DialogErrorEvidenceBlock(
    vi_names=(
        "General Error Handler CORE.vi",
        "General Error Handler.vi",
        "Not Found Dialog.vi",
        "Three Button Dialog CORE.vi",
        "Three Button Dialog.vi",
    ),
    implementation_allowed=False,
    unresolved_contracts=(
        "password-protected Error Code Database.vi lookup and descriptions",
        "OS dialog, Help, Stop primitive, modal timing, and event-loop behavior",
        "control/refnum/property/error propagation and front-panel geometry semantics",
        "keyboard shortcut, Escape, and Panel Close event-to-choice mapping",
        "LabVIEW string encoding and external-effect error handling",
    ),
)


@dataclass(frozen=True)
class GeneralErrorClassification:
    """Exact error-cluster selection/suppression before message construction."""

    error_out: ErrorCluster
    error_question: bool
    local_error_substituted: bool
    exception_suppressed: bool


@dataclass(frozen=True)
class GeneralErrorCorePlan:
    """Value-only core result plus the deliberately blocked error branch."""

    classification: GeneralErrorClassification
    dialog_type: DialogType
    no_error_message: str | None
    stop_event_propagated: bool | None
    ordered_effects: tuple[str, ...]
    blocked: DialogErrorEvidenceBlock | None


@dataclass(frozen=True)
class ThreeButtonDialogPlan:
    """Immutable initialization plan for Three Button Dialog CORE.vi."""

    message: str
    left_button_text: str
    center_button_text: str
    effective_center_button_text: str
    right_button_text: str
    window_title: str
    allow_user_to_close_window: bool
    keyboard_shortcuts: tuple[object, object, object]
    justification: str
    ordered_effects: tuple[str, ...]
    blocked: DialogErrorEvidenceBlock


@dataclass(frozen=True)
class NotFoundDialogPlan:
    """Pure post-selection routing for Not Found Dialog.vi."""

    dialog_type: DialogType
    modal_kind: str
    help_requested: bool | None
    stop_event_propagated: bool | None
    stop_primitive_requested: bool | None
    ordered_effects: tuple[str, ...]
    blocked: DialogErrorEvidenceBlock | None


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not I32_MIN <= value <= I32_MAX:
        raise TypeError(f"{name} must be signed I32 int")


def _require_string(value: str, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")


def _require_error_cluster(value: ErrorCluster, *, name: str) -> None:
    if not isinstance(value, ErrorCluster):
        raise TypeError(f"{name} must be ErrorCluster")
    if type(value.status) is not bool:
        raise TypeError(f"{name}.status must be bool")
    _require_i32(value.code, name=f"{name}.code")
    _require_string(value.source, name=f"{name}.source")


def _coerce_dialog_type(value: DialogType | int) -> DialogType:
    if type(value) is bool or not isinstance(value, (DialogType, int)):
        raise TypeError("dialog_type must be DialogType or int")
    try:
        return DialogType(value)
    except ValueError as exc:
        raise ValueError("dialog_type is not a wired DialogTypeEnum value") from exc


def remap_general_error_handler_dialog_type(localized_ring_value: int) -> DialogType:
    """Apply General Error Handler.vi's five-frame localized-ring remap.

    The wrapper's U16 input frames are exactly ``0..4``.  Frames 3 and 4
    become CORE enum values 4 and 5; unrepresented U16 values fail closed.
    """

    if type(localized_ring_value) is not int or not 0 <= localized_ring_value <= 4:
        raise ValueError("localized_ring_value must be one of wrapper frames 0..4")
    return (
        DialogType.NO_DIALOG,
        DialogType.OK_MESSAGE,
        DialogType.CONTINUE_OR_STOP_MESSAGE,
        DialogType.OK_MESSAGE_WITH_WARNINGS,
        DialogType.CONTINUE_STOP_WITH_WARNINGS,
    )[localized_ring_value]


def classify_general_error(
    *,
    local_error_code: int,
    local_error_source: str,
    error_in: ErrorCluster,
    exception_action: int,
    exception_code: int,
    exception_source: str,
) -> GeneralErrorClassification:
    """Reconstruct General Error Handler CORE.vi's visible cluster gates.

    Incoming status takes priority.  With no incoming status, a nonzero local
    code supplies status/code/source.  Only action ``1`` has a visible outer
    case: it clears a matching code when exception source is empty or exactly
    equals the selected source.  Other action values use the Default frame.
    """

    _require_i32(local_error_code, name="local_error_code")
    _require_string(local_error_source, name="local_error_source")
    _require_error_cluster(error_in, name="error_in")
    _require_i32(exception_action, name="exception_action")
    _require_i32(exception_code, name="exception_code")
    _require_string(exception_source, name="exception_source")

    if error_in.status:
        selected = error_in
        local_error_substituted = False
    elif local_error_code != 0:
        selected = ErrorCluster(True, local_error_code, local_error_source)
        local_error_substituted = True
    else:
        selected = error_in
        local_error_substituted = False

    exception_suppressed = (
        exception_action == 1
        and selected.code == exception_code
        and (exception_source == "" or exception_source == selected.source)
    )
    error_out = ErrorCluster(False, 0, "") if exception_suppressed else selected
    return GeneralErrorClassification(
        error_out=error_out,
        error_question=error_out.status or error_out.code != 0,
        local_error_substituted=local_error_substituted,
        exception_suppressed=exception_suppressed,
    )


def plan_general_error_handler_core(
    *,
    dialog_type: DialogType | int,
    no_error_message: str,
    local_error_code: int,
    local_error_source: str,
    error_in: ErrorCluster,
    exception_action: int,
    exception_code: int,
    exception_source: str,
) -> GeneralErrorCorePlan:
    """Return exact cluster/no-error branch and block message/dialog execution."""

    typed_dialog = _coerce_dialog_type(dialog_type)
    _require_string(no_error_message, name="no_error_message")
    classification = classify_general_error(
        local_error_code=local_error_code,
        local_error_source=local_error_source,
        error_in=error_in,
        exception_action=exception_action,
        exception_code=exception_code,
        exception_source=exception_source,
    )
    if not classification.error_question:
        return GeneralErrorCorePlan(
            classification=classification,
            dialog_type=typed_dialog,
            no_error_message=no_error_message,
            stop_event_propagated=False,
            ordered_effects=("write String to Format.Value = no_error_message",),
            blocked=DIALOG_ERROR_EFFECTS_BLOCKED,
        )
    return GeneralErrorCorePlan(
        classification=classification,
        dialog_type=typed_dialog,
        no_error_message=None,
        stop_event_propagated=None,
        ordered_effects=(
            "lookup Error Code Database and construct/format message",
            "route dialog/Help/Stop according to dialog type and UI availability",
        ),
        blocked=DIALOG_ERROR_EFFECTS_BLOCKED,
    )


def plan_three_button_dialog_core(
    *,
    message: str,
    left_button_text: str,
    center_button_text: str,
    right_button_text: str,
    window_title: str,
    keyboard_shortcuts: tuple[object, object, object],
    justification: str,
    allow_user_to_close_window: bool,
) -> ThreeButtonDialogPlan:
    """Record visible CORE initialization phases, never a modal interaction."""

    for name, value in (
        ("message", message),
        ("left_button_text", left_button_text),
        ("center_button_text", center_button_text),
        ("right_button_text", right_button_text),
        ("window_title", window_title),
        ("justification", justification),
    ):
        _require_string(value, name=name)
    if type(allow_user_to_close_window) is not bool:
        raise TypeError("allow_user_to_close_window must be bool")
    if not isinstance(keyboard_shortcuts, tuple) or len(keyboard_shortcuts) != 3:
        raise TypeError("keyboard_shortcuts must be a three-element tuple")

    return ThreeButtonDialogPlan(
        message=message,
        left_button_text=left_button_text,
        center_button_text=center_button_text,
        effective_center_button_text=(
            "OK"
            if left_button_text == "" and center_button_text == "" and right_button_text == ""
            else center_button_text
        ),
        right_button_text=right_button_text,
        window_title=window_title,
        allow_user_to_close_window=allow_user_to_close_window,
        keyboard_shortcuts=keyboard_shortcuts,
        justification=justification,
        ordered_effects=(
            "sequence 0: configure captions, visible controls, and initial bounds; all-empty captions use center=OK",
            "sequence 1: set FP.Closeable from allow_user_to_close_window",
            "sequence 2: write message/title and conditionally bind keyboard shortcuts",
            "sequences 3..6: calculate button/message geometry and panel bounds",
            "sequence 7: set deprecated auto-center false and open front panel",
            "event loop: return a connector-pane ThreeButtonChoice then close panel",
        ),
        blocked=DIALOG_ERROR_EFFECTS_BLOCKED,
    )


def plan_three_button_dialog(**kwargs: object) -> ThreeButtonDialogPlan:
    """Model Three Button Dialog.vi as its direct wrapper around CORE."""

    return plan_three_button_dialog_core(**kwargs)  # type: ignore[arg-type]


def plan_not_found_dialog(
    *,
    dialog_type: DialogType | int,
    three_button_choice: ThreeButtonChoice | int | None = None,
    two_button_t_pressed: bool | None = None,
) -> NotFoundDialogPlan:
    """Reconstruct visible post-dialog gates without producing a UI event.

    For the two-button group the two-button VI's Boolean is retained verbatim:
    the following Help case executes when that Boolean is False.  Its mapping
    to a physical button is not established here.  For the three-button group,
    connector-pane ordinals make Right==Help and Center==stop propagation
    exact; only non-auto center selection requests the visible Stop primitive.
    """

    typed_dialog = _coerce_dialog_type(dialog_type)
    if three_button_choice is not None:
        if type(three_button_choice) is bool or not isinstance(three_button_choice, (ThreeButtonChoice, int)):
            raise TypeError("three_button_choice must be ThreeButtonChoice, int, or None")
        try:
            choice = ThreeButtonChoice(three_button_choice)
        except ValueError as exc:
            raise ValueError("three_button_choice is not a connector-pane choice") from exc
    else:
        choice = None
    if two_button_t_pressed is not None and type(two_button_t_pressed) is not bool:
        raise TypeError("two_button_t_pressed must be bool or None")

    if typed_dialog is DialogType.NO_DIALOG:
        if choice is not None or two_button_t_pressed is not None:
            raise ValueError("no-dialog frame has no modal interaction")
        return NotFoundDialogPlan(typed_dialog, "none", False, False, False, (), None)

    if typed_dialog in {DialogType.OK_MESSAGE, DialogType.OK_MESSAGE_WITH_WARNINGS}:
        if choice is not None:
            raise ValueError("two-button frame does not accept a three-button choice")
        help_requested = None if two_button_t_pressed is None else not two_button_t_pressed
        effects = ("Two Button Dialog(message, Help)",)
        if help_requested:
            effects += ("BuildHelpPath then Control Online Help(Find_Error_Descriptions.html, operation=1)",)
        return NotFoundDialogPlan(
            typed_dialog, "two_button", help_requested, False, False,
            effects, DIALOG_ERROR_EFFECTS_BLOCKED,
        )

    if two_button_t_pressed is not None:
        raise ValueError("three-button frame does not accept a two-button result")
    help_requested = None if choice is None else choice is ThreeButtonChoice.RIGHT_BUTTON
    stop_event = None if choice is None else choice is ThreeButtonChoice.CENTER_BUTTON
    stop_primitive = (
        None
        if choice is None
        else choice is ThreeButtonChoice.CENTER_BUTTON
        and typed_dialog is not DialogType.AUTO_ERROR_HANDLING_DIALOG
    )
    effects = ("Three Button Dialog(Continue, Stop, Help, Message)",)
    if help_requested:
        effects += ("BuildHelpPath then Control Online Help(Find_Error_Descriptions.html, operation=1)",)
    if stop_primitive:
        effects += ("request Stop primitive",)
    return NotFoundDialogPlan(
        typed_dialog, "three_button", help_requested, stop_event, stop_primitive,
        effects, DIALOG_ERROR_EFFECTS_BLOCKED,
    )
