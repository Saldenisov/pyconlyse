#!/usr/bin/env python3
"""Safely fast-forward an exact origin commit to Everest.

Default mode is dry-run. This tool never powers hardware, moves stages,
controls shutters, starts HPD-TA, or restarts Tango servers.
"""

from __future__ import annotations

import argparse
import base64
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.refactor.verify_refactor import (
    DEFAULT_ENVIRONMENT,
    PROJECT_ROOT,
    RefactorToolError,
    validate_branch,
    validate_commit,
)


EVEREST_HOST = "elyse@10.20.30.202"
EVEREST_REPOSITORY = r"C:\dev\pyconlyse"


def _run_git(
    argv: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    completed = runner(
        tuple(argv), cwd=PROJECT_ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def assert_clean_local_tree(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    status = _run_git(("git", "status", "--porcelain"), runner)
    if status:
        raise RefactorToolError(
            "Refusing deployment: local worktree is dirty. Commit or stash it first."
        )


def resolve_origin_commit(
    branch: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    branch = validate_branch(branch)
    _run_git(("git", "fetch", "origin", branch), runner)
    return validate_commit(_run_git(("git", "rev-parse", f"origin/{branch}"), runner))


def assert_local_branch(
    branch: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    actual = _run_git(("git", "branch", "--show-current"), runner)
    if actual != validate_branch(branch):
        raise RefactorToolError(
            f"Refusing deployment: local branch is {actual!r}, expected {branch!r}."
        )


def assert_local_head(
    expected_commit: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    expected_commit = validate_commit(expected_commit)
    actual = validate_commit(_run_git(("git", "rev-parse", "HEAD"), runner))
    if actual != expected_commit:
        raise RefactorToolError(
            f"Refusing deployment: local HEAD is {actual}, "
            f"but origin resolves to {expected_commit}."
        )


def encode_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def build_deploy_powershell(
    branch: str,
    commit: str,
    repository: str = EVEREST_REPOSITORY,
    environment: str = DEFAULT_ENVIRONMENT,
) -> str:
    branch = validate_branch(branch)
    commit = validate_commit(commit)
    return f"""$ErrorActionPreference = 'Stop'

function Invoke-Native {{
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    $output = & $Command
    if ($LASTEXITCODE -ne 0) {{
        throw "$Label failed with native exit code $LASTEXITCODE."
    }}
    return $output
}}

Set-Location -LiteralPath '{repository}'
$status = Invoke-Native 'git status' {{ git status --porcelain }}
if ($status) {{ throw 'Refusing deployment: Everest worktree is dirty.' }}
$currentBranch = (Invoke-Native 'git branch' {{ git branch --show-current }}).Trim()
if ($currentBranch -ne '{branch}') {{ throw "Refusing deployment: Everest branch is $currentBranch, expected {branch}." }}
Invoke-Native 'git fetch' {{ git fetch origin {branch} }} | Out-Null
$originCommit = (Invoke-Native 'git rev-parse origin' {{ git rev-parse origin/{branch} }}).Trim()
if ($originCommit -ne '{commit}') {{ throw "Origin commit mismatch: $originCommit" }}

$testWorktree = Join-Path ([System.IO.Path]::GetTempPath()) "pyconlyse-refactor-{commit}-$([guid]::NewGuid().ToString('N'))"
$worktreeAdded = $false
try {{
    Invoke-Native 'git worktree add' {{ git worktree add --detach -- $testWorktree {commit} }} | Out-Null
    $worktreeAdded = $true
    Set-Location -LiteralPath $testWorktree
    Invoke-Native 'software-only verification' {{
        conda run -n {environment} python scripts/refactor/verify_refactor.py --apply --full
    }} | Out-Host
}} finally {{
    if ($worktreeAdded) {{
        Set-Location -LiteralPath '{repository}'
        Invoke-Native 'git worktree remove' {{ git worktree remove --force -- $testWorktree }} | Out-Null
    }}
}}

Set-Location -LiteralPath '{repository}'
Invoke-Native 'git merge' {{ git merge --ff-only {commit} }} | Out-Null
$headCommit = (Invoke-Native 'git rev-parse HEAD' {{ git rev-parse HEAD }}).Trim()
if ($headCommit -ne '{commit}') {{ throw "Deployment did not reach expected commit: $headCommit" }}
Write-Output "DEPLOYED {commit}"
"""


def build_ssh_command(host: str, powershell_script: str) -> tuple[str, ...]:
    return (
        "ssh",
        host,
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encode_powershell(powershell_script),
    )


def deploy(
    branch: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    assert_clean_local_tree(runner)
    assert_local_branch(branch, runner)
    commit = resolve_origin_commit(branch, runner)
    assert_local_head(commit, runner)
    command = build_ssh_command(EVEREST_HOST, build_deploy_powershell(branch, commit))
    print("+ " + " ".join(command[:8]) + " <encoded PowerShell>")
    runner(command, cwd=PROJECT_ROOT, check=True, text=True)
    return commit


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--apply", action="store_true", help="Run the remote fast-forward deployment.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    branch = validate_branch(args.branch)
    if not args.apply:
        print("Dry run. No git, SSH, or remote commands executed.")
        print(f"Target: {EVEREST_HOST} {EVEREST_REPOSITORY} branch={branch}")
        return 0
    commit = deploy(branch)
    print(f"Deployment verified at {commit}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
