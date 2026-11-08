"""Evidence plans for BuildHelpPath.vi and GetHelpDir.vi.

The diagrams prove a path-operation graph but not LabVIEW Path semantics across
Windows versions, volumes, relative paths, or an unpacked application.  These
models therefore preserve ordered operations as immutable data and never read
the runtime VI library path or construct an OS path string.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HelpPathOperation(str, Enum):
    STRIP_VI_LIBRARY_PATH = "strip_vi_library_path"
    APPEND_HELP_DIRECTORY = "append_help_directory"
    APPEND_HELP_FILE_NAME = "append_help_file_name"


@dataclass(frozen=True)
class HelpPathEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


HELP_PATH_PLATFORM_BLOCKED = HelpPathEvidenceBlock(
    vi_names=("GetHelpDir.vi", "BuildHelpPath.vi"),
    implementation_allowed=False,
    unresolved_contracts=(
        "runtime value returned by LabVIEW VI Library primitive",
        "LabVIEW Strip Path semantics for roots, volumes, and relative paths",
        "LabVIEW Build Path platform/path-separator semantics",
    ),
)


@dataclass(frozen=True)
class GetHelpDirPlan:
    """Exact primitive sequence wired in GetHelpDir.vi; deliberately unresolved."""

    operations: tuple[HelpPathOperation, ...]
    help_directory_name: str
    resolved_path: None = None


@dataclass(frozen=True)
class BuildHelpPathPlan:
    """Exact BuildHelpPath.vi operation plan, without filesystem/path execution."""

    help_file_name: str
    get_help_dir: GetHelpDirPlan
    operations: tuple[HelpPathOperation, ...]
    resolved_path: None = None


def _require_string(value: str, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")


def plan_get_help_dir() -> GetHelpDirPlan:
    """Return GetHelpDir.vi's proven VI Library → Strip Path → ``help`` plan."""

    return GetHelpDirPlan(
        operations=(
            HelpPathOperation.STRIP_VI_LIBRARY_PATH,
            HelpPathOperation.APPEND_HELP_DIRECTORY,
        ),
        help_directory_name="help",
    )


def plan_build_help_path(help_file_name: str = "lvhelp.chm") -> BuildHelpPathPlan:
    """Return BuildHelpPath.vi's proven composition plan without resolving it."""

    _require_string(help_file_name, name="help_file_name")
    return BuildHelpPathPlan(
        help_file_name=help_file_name,
        get_help_dir=plan_get_help_dir(),
        operations=(
            HelpPathOperation.STRIP_VI_LIBRARY_PATH,
            HelpPathOperation.APPEND_HELP_DIRECTORY,
            HelpPathOperation.APPEND_HELP_FILE_NAME,
        ),
    )
