"""Pure font conversion, geometry, and text-control effect plans.

No font metrics or control properties are evaluated. LabVIEW text byte/encoding,
font fallback, Get Text Rect, and property-node contracts are explicit evidence
boundaries; only visible wiring and arithmetic are represented here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropertyNodeFont:
    font_name: str
    size: int
    bold: bool
    italic: bool
    underline: bool
    strikeout: bool
    color: int


@dataclass(frozen=True)
class GraphicsFont:
    font_name: str
    size: int
    strikeout: bool
    italic: bool
    underline: bool
    outline: bool
    shadow: bool
    bold: bool


@dataclass(frozen=True)
class TextRect:
    left: int
    right: int


@dataclass(frozen=True)
class UiEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


FONT_METRICS_BLOCKED = UiEvidenceBlock(
    vi_names=(
        "Convert property node font to graphics font.vi",
        "Longest Line Length in Pixels.vi",
    ),
    implementation_allowed=False,
    unresolved_contracts=(
        "LabVIEW string byte/encoding and line enumeration semantics",
        "control font property/word conversion semantics",
        "Get Text Rect font metrics, fallback, DPI, and platform rendering",
        "LabVIEW U16-to-I16 font-size coercion outside the shared 0..32767 range",
    ),
)
SET_BOLD_TEXT_BLOCKED = UiEvidenceBlock(
    vi_names=("Set Bold Text.vi",),
    implementation_allowed=False,
    unresolved_contracts=(
        "exact identity of abbreviated nested text-control property labels",
        "control refnum/error propagation semantics",
        "font-rendering effect of the final Boolean property write",
    ),
)


@dataclass(frozen=True)
class LongestLineMeasurementPlan:
    control_identity: str
    operations: tuple[str, ...]
    blocked: UiEvidenceBlock


@dataclass(frozen=True)
class SelectionEffect:
    start: int
    end: int
    final_boolean_value: bool


@dataclass(frozen=True)
class SetBoldTextPlan:
    text_control_identity: str
    initialize_visible: bool
    initialize_selection: tuple[int, int]
    initialize_selection_boolean: bool
    selection_effects: tuple[SelectionEffect, ...]
    blocked: UiEvidenceBlock


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not -(2**31) <= value <= 2**31 - 1:
        raise TypeError(f"{name} must be signed I32 int")


def _require_i16(value: int, *, name: str) -> None:
    if type(value) is not int or not -(2**15) <= value <= 2**15 - 1:
        raise TypeError(f"{name} must be signed I16 int")


def _require_u16(value: int, *, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 2**16 - 1:
        raise TypeError(f"{name} must be unsigned U16 int")


def _require_u32(value: int, *, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 2**32 - 1:
        raise TypeError(f"{name} must be unsigned U32 int")


def _checked_i32(value: int, *, expression: str) -> int:
    if not -(2**31) <= value <= 2**31 - 1:
        raise OverflowError(f"{expression} exceeds signed I32; LabVIEW overflow is unproven")
    return value


def _require_bool(value: bool, *, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def convert_property_node_font_to_graphics_font(font: PropertyNodeFont) -> GraphicsFont:
    """Exact field remap; Color is intentionally discarded, Outline/Shadow false."""

    if not isinstance(font, PropertyNodeFont):
        raise TypeError("font must be PropertyNodeFont")
    if not isinstance(font.font_name, str):
        raise TypeError("font.font_name must be str")
    _require_u16(font.size, name="font.size")
    _require_u32(font.color, name="font.color")
    if font.size > 2**15 - 1:
        raise OverflowError("font.size U16-to-I16 coercion is unproven above 32767")
    for name in ("bold", "italic", "underline", "strikeout"):
        _require_bool(getattr(font, name), name=f"font.{name}")
    return GraphicsFont(font.font_name, font.size, font.strikeout, font.italic, font.underline, False, False, font.bold)


def longest_line_width_from_rectangles(rectangles: tuple[TextRect, ...]) -> int:
    """Exact Select feedback arithmetic from supplied, already-measured rectangles."""

    if not isinstance(rectangles, tuple):
        raise TypeError("rectangles must be tuple")
    widest = 0
    for rect in rectangles:
        if not isinstance(rect, TextRect):
            raise TypeError("rectangles must contain TextRect")
        _require_i16(rect.left, name="rect.left")
        _require_i16(rect.right, name="rect.right")
        width = rect.right - rect.left
        if not -(2**15) <= width <= 2**15 - 1:
            raise OverflowError("I16 rectangle subtraction overflow semantics are unproven")
        if width > widest:
            widest = width
    return widest


def plan_longest_line_measurement(control_identity: str) -> LongestLineMeasurementPlan:
    if not isinstance(control_identity, str):
        raise TypeError("control_identity must be str")
    return LongestLineMeasurementPlan(
        control_identity,
        ("read Text", "read Font", "convert font", "enumerate lines", "Get Text Rect", "max(right-left)"),
        FONT_METRICS_BLOCKED,
    )


def plan_set_bold_text(
    text_control_identity: str, starts: tuple[int, ...], lengths: tuple[int, ...], prefix_adjustment: int
) -> SetBoldTextPlan:
    """Return ordered nonexecuting control effects visible in Set Bold Text.vi.

    Print frames establish case ``0`` as no per-item write and ``1, Default``
    as the range-write frame. Therefore every nonzero Length produces a range
    plan; exact final property identity is left blocked.
    """

    if not isinstance(text_control_identity, str):
        raise TypeError("text_control_identity must be str")
    if not isinstance(starts, tuple) or not isinstance(lengths, tuple):
        raise TypeError("starts and lengths must be tuples")
    if len(starts) != len(lengths):
        raise ValueError("starts and lengths must have equal length")
    _require_i32(prefix_adjustment, name="prefix_adjustment")
    effects: list[SelectionEffect] = []
    for start, length in zip(starts, lengths):
        _require_i32(start, name="start")
        _require_i32(length, name="length")
        if length != 0:
            start_plus_prefix = _checked_i32(
                start + prefix_adjustment,
                expression="start + prefix_adjustment",
            )
            end = _checked_i32(
                start_plus_prefix + length,
                expression="start + prefix_adjustment + length",
            )
            effects.append(SelectionEffect(start_plus_prefix, end, True))
    return SetBoldTextPlan(text_control_identity, True, (0, 0), False, tuple(effects), SET_BOLD_TEXT_BLOCKED)
