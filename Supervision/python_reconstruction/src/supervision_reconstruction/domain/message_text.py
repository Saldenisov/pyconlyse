"""Pure, evidence-bounded text transforms for General Error Handler helper VIs.

The control-flow topology is reconstructed from LabVIEW Print diagrams and
both lvkit description contexts for ``Check Special Tags.vi``, ``Find Tag.vi``,
``Search and Replace Pattern.vi``, and ``Format Message String.vi``. This is
not a GUI adapter: property-node and ``Set Bold Text.vi`` effects are returned
as immutable plans only.

LabVIEW's Match Pattern regular-expression dialect has not been established
for arbitrary expressions. The wired tag expressions are ASCII character
classes and have identical Python ``re`` behaviour. General expressions
require explicit opt-in to a Python-only modelling boundary; they do not prove
cross-engine equivalence. Position-bearing results reject non-ASCII text until
the LabVIEW string encoding and byte-offset contract are established.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import re


class TagFound(IntEnum):
    """Wired ``TagReturnType`` numeric values from Check Special Tags.vi."""

    NO_TAG = 0
    ERROR = 1
    APPEND = 2


@dataclass(frozen=True)
class EvidenceBlock:
    """An explicit boundary that must not be mistaken for a proven contract."""

    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contract: str


LABVIEW_REGEX_DIALECT_BLOCKED = EvidenceBlock(
    vi_names=(
        "Check Special Tags.vi",
        "Find Tag.vi",
        "Search and Replace Pattern.vi",
        "Format Message String.vi",
    ),
    implementation_allowed=False,
    unresolved_contract=(
        "equivalence of arbitrary LabVIEW Match Pattern regular expressions "
        "to Python re"
    ),
)


@dataclass(frozen=True)
class SpecialTagResult:
    """Three outputs of ``Check Special Tags.vi``."""

    tag_found: TagFound
    after_tag_special_data: str
    before_tag_source: str


@dataclass(frozen=True)
class SearchReplaceResult:
    """Two outputs of ``Search and Replace Pattern.vi``."""

    result_string: str
    offset_past_match: int


@dataclass(frozen=True)
class FindTagResult:
    """Value and indexing-tunnel arrays emitted by ``Find Tag.vi``."""

    string_out: str
    starts: tuple[int, ...]
    lengths: tuple[int, ...]


@dataclass(frozen=True)
class BoldTextEffectPlan:
    """Non-executing input plan for the downstream ``Set Bold Text.vi``."""

    target_identity: str
    prefix_adjustment: int
    starts: tuple[int, ...]
    lengths: tuple[int, ...]
    requires_successful_value_write: bool


@dataclass(frozen=True)
class TextValueWritePlan:
    """A property-node write intent; no control or GUI is touched."""

    target_identity: str
    property_name: str
    value: str


@dataclass(frozen=True)
class FormatMessageResult:
    """Pure outputs and conditional UI-effect plan of Format Message String.vi."""

    source_out: str
    details_out: str
    message: str
    bold_start: tuple[int, ...]
    bold_length: tuple[int, ...]
    value_write: TextValueWritePlan | None
    bold_effect: BoldTextEffectPlan | None
    ordered_effects: tuple[TextValueWritePlan | BoldTextEffectPlan, ...]


_ERROR_TAG = re.compile(r"<[Ee][Rr][Rr]>")
_APPEND_TAG = re.compile(r"<[Aa][Pp][Pp][Ee][Nn][Dd]>")
_BOLD_OPEN_TAG = r"<[Bb]>"
_BOLD_CLOSE_TAG = r"</[Bb]>"
_EVIDENCED_TAG_PAIRS = frozenset({(_BOLD_OPEN_TAG, _BOLD_CLOSE_TAG)})
_I32_MIN = -(2**31)
_I32_MAX = 2**31 - 1


def _require_string(value: str, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not _I32_MIN <= value <= _I32_MAX:
        raise TypeError(f"{name} must be a signed I32 int")


def _require_bool(value: bool, *, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def _require_ascii(value: str, *, name: str) -> None:
    _require_string(value, name=name)
    if not value.isascii():
        raise ValueError(
            f"{name} must be ASCII until LabVIEW string encoding and byte offsets are proven"
        )


def _match_or_not_found(pattern: re.Pattern[str], string: str, offset: int = 0) -> re.Match[str] | None:
    """Python-compatible model of wired Match Pattern uses."""

    return pattern.search(string, offset)


def check_special_tags(source: str) -> SpecialTagResult:
    """Classify first ``<ERR>`` or, only if absent, first ``<APPEND>`` tag.

    Case acceptance is deliberately not general case-insensitivity: only exact
    ASCII variants encoded by LabVIEW character classes are accepted. ``<ERR>``
    has priority even when APPEND occurs earlier in the source.
    """

    _require_string(source, name="source")
    error = _ERROR_TAG.search(source)
    if error is not None:
        return SpecialTagResult(TagFound.ERROR, source[error.end():], source[:error.start()])

    append = _APPEND_TAG.search(source)
    if append is not None:
        return SpecialTagResult(TagFound.APPEND, source[append.end():], source[:append.start()])

    return SpecialTagResult(TagFound.NO_TAG, "", source)


def search_and_replace_pattern(
    string: str,
    regular_expression: str,
    replace_string: str = "",
    offset: int = 0,
    replace_all: bool = False,
    *,
    allow_python_regex_model: bool = False,
) -> SearchReplaceResult:
    """Model evidenced while-loop wiring of Search and Replace Pattern.vi.

    A terminating no-match retains the prior output-feedback value (initially
    ``-1``). A zero-length match takes diagram's non-replacement branch and
    advances only internal search offset, preventing an unbounded all-mode loop. This
    preserves observed control topology, not arbitrary LabVIEW/Python regex
    equivalence.
    """

    _require_ascii(string, name="string")
    _require_ascii(regular_expression, name="regular_expression")
    _require_ascii(replace_string, name="replace_string")
    _require_i32(offset, name="offset")
    _require_bool(replace_all, name="replace_all")
    _require_bool(allow_python_regex_model, name="allow_python_regex_model")
    if not allow_python_regex_model and regular_expression not in {
        _BOLD_OPEN_TAG,
        _BOLD_CLOSE_TAG,
    }:
        raise ValueError(
            "arbitrary LabVIEW regex equivalence is blocked; "
            "set allow_python_regex_model=True only for an explicit Python-only model"
        )
    if offset < 0:
        raise ValueError("offset must be non-negative for this evidence-bounded model")

    try:
        pattern = re.compile(regular_expression)
    except re.error as exc:
        raise ValueError("regular_expression is not Python-compatible") from exc

    current_string = string
    current_offset = offset
    output_offset = -1
    stop_after_this_iteration = not replace_all

    while True:
        match = _match_or_not_found(pattern, current_string, current_offset)
        offset_past_match = -1 if match is None else match.end()
        no_match = offset_past_match < 0
        same_offset = offset_past_match == current_offset

        # case_224: Default replaces; True leaves text unchanged. The True
        # case is selected by ``no_match OR same_offset``.
        if no_match or same_offset:
            if same_offset:
                output_offset = offset_past_match
            current_offset = offset_past_match + 1
        else:
            before = current_string[:match.start()]
            current_string = before + replace_string + current_string[match.end():]
            current_offset = len(before + replace_string)
            output_offset = current_offset

        # While terminal is Stop if True: ``not replace_all`` is latched on
        # first iteration, while no-match terminates all-mode.
        if stop_after_this_iteration or no_match:
            return SearchReplaceResult(current_string, output_offset)


def _compile_tag_pattern(expression: str, *, name: str) -> re.Pattern[str]:
    _require_string(expression, name=name)
    try:
        compiled = re.compile(expression)
    except re.error as exc:
        raise ValueError(f"{name} is not Python-compatible") from exc
    if compiled.search("") is not None:
        raise ValueError(f"{name} may match an empty string; LabVIEW loop termination is not proven")
    return compiled


def find_tag(
    string: str,
    open_tag: str,
    close_tag: str,
    *,
    allow_python_regex_model: bool = False,
) -> FindTagResult:
    """Remove tag pairs and return per-loop start/length indexing arrays.

    Wire order is: match open, match close after open, strip all close tags
    before open and all open tags between, concatenate, then stop only when
    neither initial match is found. The terminating loop iteration contributes
    a trailing ``(len(string_out), 0)`` because VI uses indexing tunnels.
    """

    _require_ascii(string, name="string")
    _require_bool(allow_python_regex_model, name="allow_python_regex_model")
    if not allow_python_regex_model and (open_tag, close_tag) not in _EVIDENCED_TAG_PAIRS:
        raise ValueError(
            "arbitrary LabVIEW tag regex equivalence is blocked; "
            "set allow_python_regex_model=True only for an explicit Python-only model"
        )
    open_pattern = _compile_tag_pattern(open_tag, name="open_tag")
    close_pattern = _compile_tag_pattern(close_tag, name="close_tag")

    current_string = string
    starts: list[int] = []
    lengths: list[int] = []

    while True:
        open_match = _match_or_not_found(open_pattern, current_string)
        before_open = current_string if open_match is None else current_string[:open_match.start()]
        after_open = "" if open_match is None else current_string[open_match.end():]

        close_match = _match_or_not_found(close_pattern, after_open)
        before_close = after_open if close_match is None else after_open[:close_match.start()]
        after_close = "" if close_match is None else after_open[close_match.end():]

        before_result = search_and_replace_pattern(
            before_open,
            close_tag,
            replace_all=True,
            allow_python_regex_model=True,
        ).result_string
        tagged_result = search_and_replace_pattern(
            before_close,
            open_tag,
            replace_all=True,
            allow_python_regex_model=True,
        ).result_string
        starts.append(len(before_result))
        lengths.append(len(tagged_result))
        next_string = before_result + tagged_result + after_close

        if open_match is None and close_match is None:
            return FindTagResult(next_string, tuple(starts), tuple(lengths))
        if next_string == current_string:
            raise RuntimeError("tag-removal loop made no progress; exact LabVIEW termination is blocked")
        current_string = next_string


def format_message_string(
    source: str,
    details: str,
    *,
    target_identity: str,
    current_control_value: str,
) -> FormatMessageResult:
    """Plan pure value/control effects of ``Format Message String.vi``.

    The only control branch evidenced by diagram writes ``Valeur`` and invokes
    Set Bold Text when generated message differs from current control value.
    This function records that branch as data and never accesses a refnum/GUI.
    """

    _require_ascii(source, name="source")
    _require_ascii(details, name="details")
    _require_string(target_identity, name="target_identity")
    _require_string(current_control_value, name="current_control_value")

    tags = find_tag(details, _BOLD_OPEN_TAG, _BOLD_CLOSE_TAG)
    source_out = source + "\r\n\r\n"
    message = source_out + tags.string_out
    if message == current_control_value:
        return FormatMessageResult(
            source_out=source_out,
            details_out=tags.string_out,
            message=message,
            bold_start=tags.starts,
            bold_length=tags.lengths,
            value_write=None,
            bold_effect=None,
            ordered_effects=(),
        )

    value_write = TextValueWritePlan(target_identity, "Valeur", message)
    bold_effect = BoldTextEffectPlan(
        target_identity,
        len(source_out),
        tags.starts,
        tags.lengths,
        requires_successful_value_write=True,
    )
    return FormatMessageResult(
        source_out=source_out,
        details_out=tags.string_out,
        message=message,
        bold_start=tags.starts,
        bold_length=tags.lengths,
        value_write=value_write,
        bold_effect=bold_effect,
        ordered_effects=(value_write, bold_effect),
    )
