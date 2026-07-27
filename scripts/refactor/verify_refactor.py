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


def build_verification_commands(
    environment: str = DEFAULT_ENVIRONMENT,
    include_frontend: bool = False,
    full: bool = False,
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
                "ruff",
                "check",
                "DeviceServers",
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
                "tests/unit/test_refactor_tooling.py",
            )
        ),
    ]
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
                "pytest",
                "-m",
                "not slow and not integration and not netio",
                )
            )
        )
    if include_frontend:
        commands.extend(
            [
                Command(("npm", "test", "--", "--watchAll=false"), PROJECT_ROOT / "web/frontend"),
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
