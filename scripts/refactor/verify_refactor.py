#!/usr/bin/env python3
"""Build and run safe, local-only refactor verification commands.

This module deliberately contains no Tango, SSH, PDU, or hardware control.
Other refactor tools import its validation helpers so command construction can
be unit tested without a laboratory network.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENVIRONMENT = "pyconlyse39"
LINT_ROOTS = (
    "DeviceServers",
    "gui/controllers/openers",
    "web/backend",
    "scripts/refactor",
    "tests",
)
NON_SOFTWARE_TEST_PREFIXES = (
    "tests/manual",
    "tests/integration",
    "tests/legacy",
    "tests/main_app",
    "tests/utilities",
)
SOFTWARE_TEST_COMMAND = (
    "python",
    "-m",
    "pytest",
    "--strict-config",
    "--deny-network",
)
COVERAGE_CONFIG = ".coveragerc"
COVERAGE_JSON = ".coverage-refactor.json"
FRONTEND_COVERAGE_ARGS = (
    "--coverage",
    "--collectCoverageFrom=src/api/treatmentClient.js",
    "--collectCoverageFrom=src/api/csrfRequest.js",
    "--collectCoverageFrom=src/utils/deviceFamily.js",
    '--coverageThreshold={"global":{"branches":75,"functions":90,"lines":90,"statements":90}}',
)

_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SERVER_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RefactorToolError(RuntimeError):
    """Raised when a safety precondition is not satisfied."""


@dataclass(frozen=True)
class Command:
    """A command expressed as argv so it can be tested without execution."""

    argv: tuple[str, ...]
    cwd: Path = PROJECT_ROOT

    def display(self) -> str:
        return " ".join(self.argv)


def validate_branch(branch: str) -> str:
    if not _BRANCH_PATTERN.fullmatch(branch):
        raise RefactorToolError(f"Unsafe branch name: {branch!r}")
    return branch


def validate_commit(commit: str) -> str:
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise RefactorToolError("Commit must be a 40-character lowercase SHA-1.")
    return commit


def validate_servers(servers: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(servers)
    if not normalized:
        raise RefactorToolError("Provide at least one explicit --server value.")
    invalid = [server for server in normalized if not _SERVER_PATTERN.fullmatch(server)]
    if invalid:
        raise RefactorToolError(f"Unsafe Tango server name(s): {', '.join(invalid)}")
    return normalized


def changed_python_files(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, ...]:
    """Return changed Python files covered by the refactor verification gate."""
    def eligible_paths(raw_paths: Iterable[str]) -> set[str]:
        paths: set[str] = set()
        for raw_path in raw_paths:
            path = Path(raw_path.strip())
            if (
                path.suffix == ".py"
                and not path.is_absolute()
                and ".." not in path.parts
                and not any(
                    path.as_posix() == prefix
                    or path.as_posix().startswith(f"{prefix}/")
                    for prefix in NON_SOFTWARE_TEST_PREFIXES
                )
                and any(
                    path.as_posix() == root
                    or path.as_posix().startswith(f"{root}/")
                    for root in LINT_ROOTS
                )
            ):
                paths.add(path.as_posix())
        return paths

    commands = (
        ("git", "diff", "--name-only", "--diff-filter=ACMR"),
        ("git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    )
    raw_paths: set[str] = set()
    for argv in commands:
        completed = runner(
            argv,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        raw_paths.update(completed.stdout.splitlines())
    paths = eligible_paths(raw_paths)
    if not paths:
        completed = runner(
            ("git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD^", "HEAD"),
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        paths.update(eligible_paths(completed.stdout.splitlines()))
    return tuple(sorted(paths))


def build_verification_commands(
    environment: str = DEFAULT_ENVIRONMENT,
    include_frontend: bool = False,
    full: bool = False,
    changed_files: Iterable[str] = (),
) -> tuple[Command, ...]:
    commands = [
        Command(("git", "diff", "--check")),
        Command(("git", "diff", "--cached", "--check")),
        Command(
            (
                "conda",
                "run",
                "-n",
                environment,
                "python",
                "-m",
                "compileall",
                "-q",
                "DeviceServers",
                "gui/controllers/openers",
                "web/backend",
                "scripts/refactor",
                "tests",
            )
        ),
        Command(
            (
                "conda",
                "run",
                "-n",
                environment,
                "python",
                "-m",
                "pytest",
                "--strict-config",
                "--deny-network",
                "tests/unit/test_network_isolation.py",
                "tests/unit/test_refactor_tooling.py",
                "tests/unit/test_refactor_coverage.py",
                "tests/unit/test_pytest_module_isolation.py",
            )
        ),
    ]
    lint_targets = tuple(changed_files)
    if lint_targets:
        commands.insert(
            3,
            Command(
                (
                    "conda",
                    "run",
                    "-n",
                    environment,
                    "ruff",
                    "check",
                    "--select",
                    "F",
                    *lint_targets,
                )
            ),
        )
    if full:
        commands.append(
            Command(
                (
                    "conda",
                    "run",
                    "-n",
                    environment,
                    "python",
                    "-m",
                    "coverage",
                    "erase",
                )
            )
        )
        commands.extend(
            [
                Command(
                    (
                        "conda",
                        "run",
                        "-n",
                        environment,
                        "python",
                        "-m",
                        "coverage",
                        "run",
                        "--rcfile",
                        COVERAGE_CONFIG,
                        *SOFTWARE_TEST_COMMAND[1:],
                    )
                ),
                Command(
                    (
                        "conda",
                        "run",
                        "-n",
                        environment,
                        "python",
                        "-m",
                        "coverage",
                        "report",
                        "--rcfile",
                        COVERAGE_CONFIG,
                        "--fail-under",
                        "60",
                    )
                ),
                Command(
                    (
                        "conda",
                        "run",
                        "-n",
                        environment,
                        "python",
                        "-m",
                        "coverage",
                        "json",
                        "--rcfile",
                        COVERAGE_CONFIG,
                        "-o",
                        COVERAGE_JSON,
                    )
                ),
                Command(
                    (
                        "conda",
                        "run",
                        "-n",
                        environment,
                        "python",
                        "scripts/refactor/verify_coverage.py",
                        "--json",
                        COVERAGE_JSON,
                    )
                ),
            ]
        )
    if include_frontend:
        commands.extend(
            [
                Command(("npm", "ci", "--legacy-peer-deps"), PROJECT_ROOT / "web/frontend"),
                Command(
                    ("npm", "test", "--", "--watchAll=false", *FRONTEND_COVERAGE_ARGS),
                    PROJECT_ROOT / "web/frontend",
                ),
                Command(("npm", "run", "build"), PROJECT_ROOT / "web/frontend"),
            ]
        )
    return tuple(commands)


def run_commands(
    commands: Sequence[Command],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    for command in commands:
        print(f"+ {command.display()}")
        runner(command.argv, cwd=command.cwd, check=True, text=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Execute local verification commands.")
    parser.add_argument("--frontend", action="store_true", help="Include frontend test and build commands.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the complete software-only pytest suite; implies frontend checks.",
    )
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    commands = build_verification_commands(
        args.environment,
        include_frontend=args.frontend or args.full,
        full=args.full,
        changed_files=changed_python_files(),
    )
    if not args.apply:
        print("Dry run. No commands executed. Re-run with --apply to verify locally.")
        for command in commands:
            print(f"+ {command.display()}")
        return 0
    run_commands(commands)
    return 0


if __name__ == "__main__":
    sys.exit(main())
