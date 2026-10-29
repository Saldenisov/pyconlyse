"""Fail-closed boundary for password-protected Error Code Database.vi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn


@dataclass(frozen=True)
class ErrorCodeDatabaseEvidenceBlock:
    vi_name: str
    implementation_allowed: bool
    available_evidence: tuple[str, ...]
    missing_evidence: tuple[str, ...]


ERROR_CODE_DATABASE_BLOCKED = ErrorCodeDatabaseEvidenceBlock(
    vi_name="Error Code Database.vi",
    implementation_allowed=False,
    available_evidence=(
        "connector pane",
        "front panel",
        "password prompt capture",
        "opaque lvkit node identity",
    ),
    missing_evidence=(
        "block diagram",
        "authorized lookup table/source",
        "code-to-description and source formatting contract",
    ),
)


class ErrorCodeDatabaseUnavailable(RuntimeError):
    """Raised instead of inventing behavior hidden by the password boundary."""


def lookup_error_code(*_: object, **__: object) -> NoReturn:
    """Deny lookup until an authorized source establishes the VI contract."""

    raise ErrorCodeDatabaseUnavailable(
        "Error Code Database.vi is password-protected; lookup semantics are unavailable"
    )
