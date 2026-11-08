"""Journal byte concatenation and file-write intent, without executing effects.

Original constant bytes prove CRLF and three trailing format spaces. New text
is prepended; Message OUTPUT is cleared. Two independent clock nodes supply
the display and file timestamps. The caller must supply both already-rendered
byte strings: this module does not emulate LabVIEW date rendering or encoding.
The source wires append=True and one 1D row directly to the spreadsheet writer,
without an empty-path guard or the 100-line trim claimed by its panel comment.
File dialog, delimiters, formatting, I/O failure and writer execution remain
unqualified. No filesystem, clock or LabVIEW operation occurs here.
"""

from dataclasses import dataclass, field
from typing import Tuple

SOURCE_VI_SHA256 = "E8B8E05803ED7BC37F3AE82F2C133D4BC43E1DE7AD22E76B2C2D6DDA26681E49"
EVIDENCE_PATH = "analysis/non_event_logic_evidence_20261004.json"
EVIDENCE_SHA256 = "A93291A2988B13C704AAAC2C5602666578CF645543F842940FDB0E00F61F863E"
DISPLAY_TIMESTAMP_FORMAT = b"%d/%m %H:%M:%S   "
FILE_TIMESTAMP_FORMAT = b"%Y %d/%m %H:%M:%S   "


@dataclass(frozen=True)
class JournalTransformationBlocked:
    """Residual whole-VI limits; known byte projection is separately available."""

    vi_name: str
    implementation_allowed: bool
    observed_timestamp_formats: Tuple[str, ...]
    unresolved_contracts: Tuple[str, ...]


JOURNAL_TRANSFORMATION_BLOCKED = JournalTransformationBlocked(
    vi_name="2_SUP_Journal_des _erreurs.vi",
    implementation_allowed=False,
    observed_timestamp_formats=("%Y %d/%m %H:%M:%S   ", "%d/%m %H:%M:%S   "),
    unresolved_contracts=(
        "LabVIEW timestamp rendering, locale/timezone and two-clock scheduling",
        "legacy text encoding at any Unicode boundary",
        "spreadsheet writer unwired format/delimiter defaults and cancellation",
        "file-write errors, persistence and ordering relative to output updates",
    ),
)


@dataclass(frozen=True)
class JournalBytesProjection:
    journal_out: bytes
    file_row: bytes
    message_output: bytes = field(default=b"", init=False)


@dataclass(frozen=True)
class JournalFileWriteIntent:
    """Opaque path token and wired arguments; never a filesystem operation."""

    file_path_token: str | None
    one_dimensional_data: tuple[bytes, ...]
    append_to_file: bool = field(default=True, init=False)
    external_effects_blocked: bool = field(default=True, init=False)
    file_format_and_delimiter_qualified: bool = field(default=False, init=False)


def project_journal_bytes(
    *,
    message_input: bytes,
    journal_in: bytes,
    display_timestamp: bytes,
    file_timestamp: bytes,
) -> JournalBytesProjection:
    """Preserve exact bytes, two supplied timestamps, prepend order and CRLF.

    Timestamp strings are external inputs, not formatted here. Embedded NULs,
    line breaks, arbitrary byte encodings and journals over 100 lines survive.
    No equality between the two independently rendered timestamps is assumed.
    """

    for name, value in (
        ("message_input", message_input),
        ("journal_in", journal_in),
        ("display_timestamp", display_timestamp),
        ("file_timestamp", file_timestamp),
    ):
        if type(value) is not bytes:
            raise TypeError(f"{name} must be bytes; encoding must be explicit")
    return JournalBytesProjection(
        journal_out=display_timestamp + message_input + b"\r\n" + journal_in,
        file_row=file_timestamp + message_input,
    )


def plan_journal_file_write(
    projection: JournalBytesProjection, *, file_path_token: str | None
) -> JournalFileWriteIntent:
    """Record a direct append request even for empty/unresolved path tokens.

    Empty path is not interpreted as skip or resolved to an OS filename.
    The writer's own path-dialog/default handling remains unqualified.
    """

    if not isinstance(projection, JournalBytesProjection):
        raise TypeError("projection must be JournalBytesProjection")
    if file_path_token is not None and type(file_path_token) is not str:
        raise TypeError("file_path_token must be str or None")
    return JournalFileWriteIntent(file_path_token, (projection.file_row,))


def journal_transformation_status() -> JournalTransformationBlocked:
    """Return the immutable block; this function never formats or writes text."""

    return JOURNAL_TRANSFORMATION_BLOCKED
