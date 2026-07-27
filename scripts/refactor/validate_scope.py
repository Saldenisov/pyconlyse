#!/usr/bin/env python3
"""Validate a refactoring worktree against one Terra/Luna work package."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Sequence

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 uses the project tomli dependency.
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "docs" / "refactoring" / "work-packages.toml"
GitRunner = Callable[..., subprocess.CompletedProcess[str]]


class ScopeValidationError(ValueError):
    """Raised when manifest or selected package is invalid."""


def _normalise_path(path: str) -> str:
    value = path.strip().replace("\\", "/")
    if value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ".." in PurePosixPath(value).parts:
        raise ScopeValidationError(f"Invalid repository-relative path: {path!r}")
    return value


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Mapping[str, object]:
    with path.open("rb") as stream:
        manifest = tomllib.load(stream)
    if manifest.get("version") != 1:
        raise ScopeValidationError("Manifest must declare version = 1")
    packages = manifest.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise ScopeValidationError("Manifest must contain packages")
    protected = manifest.get("protected_paths", [])
    if not isinstance(protected, list) or not all(isinstance(item, str) for item in protected):
        raise ScopeValidationError("protected_paths must be a list of strings")
    return manifest


def _matches(path: str, pattern: str) -> bool:
    # Use both match implementations: fnmatch handles explicit filename globs,
    # while PurePosixPath handles recursive directory patterns consistently.
    return (
        path == pattern
        or fnmatch.fnmatchcase(path, pattern)
        or PurePosixPath(path).match(pattern)
    )


def _patterns(package: Mapping[str, object]) -> tuple[str, ...]:
    exact = package.get("allowed_paths", [])
    globs = package.get("allowed_globs", [])
    values = list(exact if isinstance(exact, list) else []) + list(globs if isinstance(globs, list) else [])
    if not values or not all(isinstance(item, str) and item for item in values):
        raise ScopeValidationError("Selected package must define non-empty allowed paths")
    return tuple(values)


def validate_paths(
    paths: Iterable[str],
    package_name: str,
    manifest: Mapping[str, object],
) -> list[str]:
    packages = manifest["packages"]
    assert isinstance(packages, dict)
    package = packages.get(package_name)
    if not isinstance(package, dict):
        raise ScopeValidationError(f"Unknown work package: {package_name}")
    patterns = _patterns(package)
    protected = manifest.get("protected_paths", [])
    assert isinstance(protected, list)
    violations: list[str] = []
    for raw_path in sorted({_normalise_path(path) for path in paths}):
        matched_protected = next((pattern for pattern in protected if _matches(raw_path, pattern)), None)
        if matched_protected:
            violations.append(f"{raw_path}: protected by {matched_protected}")
        elif not any(_matches(raw_path, pattern) for pattern in patterns):
            violations.append(f"{raw_path}: outside {package_name} scope")
    return violations


def _git_paths(repo_root: Path, runner: GitRunner = subprocess.run) -> set[str]:
    commands = (
        ("git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", "HEAD", "--"),
        ("git", "diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB", "--"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    )
    paths: set[str] = set()
    for argv in commands:
        result = runner(argv, cwd=repo_root, check=False, capture_output=True, text=True)
        if result.returncode:
            detail = result.stderr.strip() or "git command failed"
            raise ScopeValidationError(f"{argv[1]} failed: {detail}")
        paths.update(line for line in result.stdout.splitlines() if line.strip())
    return paths


def changed_paths(repo_root: Path = PROJECT_ROOT, runner: GitRunner = subprocess.run) -> set[str]:
    """Return tracked, staged, and untracked paths without mutating the repo."""
    return _git_paths(repo_root, runner)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Manifest package, for example T3 or L2")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--file", dest="files", action="append", help="Override git discovery; repeatable")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        paths = set(args.files) if args.files is not None else changed_paths(args.repo_root)
        violations = validate_paths(paths, args.package, manifest)
    except (OSError, ScopeValidationError) as exc:
        print(f"Scope validation failed: {exc}", file=sys.stderr)
        return 2
    if violations:
        print(f"Scope validation failed for {args.package}:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print(f"Scope valid: {args.package} ({len(paths)} changed path(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
