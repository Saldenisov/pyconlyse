"""Resolve a direct Python executable for Windows device-server wrappers.

The resolver is intentionally pure: it does not start Python, touch Tango, or
modify a process environment.  ``resolve_python.cmd`` implements the same
ordered Windows paths for wrappers that must choose an interpreter before any
Python process exists.  A missing direct executable is not an error here;
callers may retain the legacy Conda activation fallback.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence


DEFAULT_ENVIRONMENT = "pyconlyse39"


@dataclass(frozen=True)
class PythonRuntime:
    """A validated direct Python executable and the source that selected it."""

    executable: str
    source: str


def _is_absolute_windows_path(path: str) -> bool:
    return ntpath.isabs(path) and path.lower().endswith(".exe")


def _environment_root_candidates(environment: Mapping[str, str]) -> Sequence[tuple[str, str]]:
    """Return common Conda roots without assuming a particular Windows user."""
    user_profile = environment.get("USERPROFILE", "")
    local_app_data = environment.get("LOCALAPPDATA", "")
    roots = (
        (environment.get("ANACONDA", ""), "ANACONDA"),
        (ntpath.join(user_profile, ".conda"), "USERPROFILE/.conda"),
        (ntpath.join(user_profile, "miniconda3"), "USERPROFILE/miniconda3"),
        (ntpath.join(user_profile, "anaconda3"), "USERPROFILE/anaconda3"),
        (ntpath.join(user_profile, "miniforge3"), "USERPROFILE/miniforge3"),
        (ntpath.join(local_app_data, "miniconda3"), "LOCALAPPDATA/miniconda3"),
        (r"C:\ProgramData\miniconda3", "ProgramData/miniconda3"),
        (r"C:\ProgramData\anaconda3", "ProgramData/anaconda3"),
    )
    return tuple((root, source) for root, source in roots if root)


def direct_python_candidates(environment: Mapping[str, str]) -> Sequence[PythonRuntime]:
    """Return direct interpreters in stable preference order.

    ``PYCONLYSE_PYTHON`` wins only when it is an absolute ``.exe`` path.  The
    remaining candidates cover configured Conda, active Conda, and common
    per-user/base installation roots.  Duplicates are removed case-insensitively.
    """
    env_name = environment.get("PYCONLYSE_ENV", DEFAULT_ENVIRONMENT)
    candidates: list[PythonRuntime] = []
    configured = environment.get("PYCONLYSE_PYTHON", "")
    if configured and _is_absolute_windows_path(configured):
        candidates.append(PythonRuntime(configured, "PYCONLYSE_PYTHON"))

    conda_prefix = environment.get("CONDA_PREFIX", "")
    if conda_prefix and environment.get("CONDA_DEFAULT_ENV") == env_name:
        candidates.append(PythonRuntime(ntpath.join(conda_prefix, "python.exe"), "CONDA_PREFIX"))

    for root, source in _environment_root_candidates(environment):
        candidates.append(
            PythonRuntime(ntpath.join(root, "envs", env_name, "python.exe"), source)
        )
        if source == "ANACONDA" and environment.get("CONDA_DEFAULT_ENV") == env_name:
            candidates.append(PythonRuntime(ntpath.join(root, "python.exe"), source))

    unique: list[PythonRuntime] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = ntpath.normcase(ntpath.normpath(candidate.executable))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return tuple(unique)


def resolve_direct_python(
    environment: Mapping[str, str],
    exists: Callable[[str], bool],
) -> Optional[PythonRuntime]:
    """Return first available direct Python; ``None`` leaves Conda fallback intact."""
    for candidate in direct_python_candidates(environment):
        if exists(candidate.executable):
            return candidate
    return None
