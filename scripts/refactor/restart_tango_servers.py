#!/usr/bin/env python3
"""Restart explicitly named Tango servers through Starter after a safe deploy.

Default mode is dry-run. Actual DevStop/DevStart requires --apply and a
human-created approval TOML outside this repository. This tool never uses
HardKillServer, taskkill, PDU, motion, shutter, HPD-TA, or power commands.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.refactor.deploy_everest import (
    EVEREST_HOST,
    EVEREST_REPOSITORY,
    build_ssh_command,
)
from scripts.refactor.verify_refactor import (
    DEFAULT_ENVIRONMENT,
    PROJECT_ROOT,
    RefactorToolError,
    validate_commit,
    validate_servers,
)


@dataclass(frozen=True)
class RestartApproval:
    """Human authorization bound to one deployed commit and ordered server list."""

    path: Path
    commit: str
    servers: tuple[str, ...]
    approver: str
    expires_at_utc: datetime


def _parse_minimal_toml(text: str) -> dict[str, Any]:
    """Parse the small, documented root-only approval TOML subset on Python 3.9."""
    values: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") or "=" not in line:
            raise RefactorToolError("Approval TOML must contain only root key/value pairs.")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        if key in values:
            raise RefactorToolError(f"Approval TOML repeats key {key!r}.")
        if key == "hardware_safe":
            if raw_value not in {"true", "false"}:
                raise RefactorToolError("Approval hardware_safe must be TOML true or false.")
            values[key] = raw_value == "true"
            continue
        try:
            values[key] = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise RefactorToolError(
                f"Approval value for {key!r} must use JSON-compatible TOML syntax."
            ) from exc
    return values


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return _parse_minimal_toml(path.read_text(encoding="utf-8"))
    with path.open("rb") as approval_file:
        return tomllib.load(approval_file)


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def load_restart_approval(
    approval_file: str | Path,
    expected_commit: str,
    servers: Sequence[str],
    *,
    now: datetime | None = None,
) -> RestartApproval:
    """Validate an external, operator-authored TOML approval before restart."""
    requested_servers = validate_servers(servers)
    expected_commit = validate_commit(expected_commit)
    raw_path = Path(approval_file).expanduser()
    if not raw_path.is_absolute():
        raise RefactorToolError("Approval file must be an absolute path outside the repository.")
    path = raw_path.resolve()
    if _is_inside(path, PROJECT_ROOT.resolve()):
        raise RefactorToolError("Approval file must be outside the repository.")
    if not path.is_file():
        raise RefactorToolError(f"Approval file does not exist: {path}")

    payload = _read_toml(path)
    required = {"commit", "servers", "approver", "hardware_safe", "expires_at_utc"}
    missing = sorted(required - payload.keys())
    if missing:
        raise RefactorToolError(f"Approval TOML is missing: {', '.join(missing)}")
    if payload["commit"] != expected_commit:
        raise RefactorToolError("Approval commit does not match --expected-commit.")
    if not isinstance(payload["servers"], list):
        raise RefactorToolError("Approval servers must be a TOML array.")
    approved_servers = validate_servers(payload["servers"])
    if approved_servers != requested_servers:
        raise RefactorToolError("Approval server list must exactly match requested ordered servers.")
    if payload["hardware_safe"] is not True:
        raise RefactorToolError("Approval hardware_safe must be true.")
    approver = str(payload["approver"]).strip()
    if not approver:
        raise RefactorToolError("Approval approver must not be empty.")
    expires_raw = payload["expires_at_utc"]
    if not isinstance(expires_raw, str):
        raise RefactorToolError("Approval expires_at_utc must be an ISO-8601 UTC string.")
    try:
        expires_at_utc = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RefactorToolError("Approval expires_at_utc is not valid ISO-8601.") from exc
    if expires_at_utc.tzinfo is None or expires_at_utc.utcoffset() != timezone.utc.utcoffset(expires_at_utc):
        raise RefactorToolError("Approval expires_at_utc must use UTC, for example 2026-07-27T15:00:00Z.")
    current_time = now or datetime.now(timezone.utc)
    if expires_at_utc <= current_time:
        raise RefactorToolError("Approval has expired.")
    return RestartApproval(path, expected_commit, requested_servers, approver, expires_at_utc)


def build_restart_powershell(
    servers: Sequence[str],
    expected_commit: str,
    repository: str = EVEREST_REPOSITORY,
    environment: str = DEFAULT_ENVIRONMENT,
    starter_device: str = "tango/admin/everest",
) -> str:
    servers = validate_servers(servers)
    expected_commit = validate_commit(expected_commit)
    server_json = json.dumps(list(servers))
    python_code = f"""import json
import time
from tango import DeviceProxy

servers = json.loads({server_json!r})
starter = DeviceProxy({starter_device!r})

def starter_lists():
    running = set(starter.command_inout('DevGetRunningServers', True))
    stopped = set(starter.command_inout('DevGetStopServers', True))
    return running, stopped

def wait_for(server, expected_running, timeout_s=20.0):
    deadline = time.monotonic() + timeout_s
    last_running, last_stopped = set(), set()
    while time.monotonic() < deadline:
        last_running, last_stopped = starter_lists()
        if expected_running and server in last_running:
            return True
        if not expected_running and server not in last_running and server in last_stopped:
            return True
        time.sleep(0.5)
    return False

def start_once(server):
    try:
        starter.command_inout('DevStart', server)
    except Exception:
        if wait_for(server, True):
            return
        raise
    if not wait_for(server, True):
        raise RuntimeError(f'{{server}} did not appear in DevGetRunningServers.')

def restart_one(server):
    running, _ = starter_lists()
    stopped_by_this_run = False
    started = False
    primary_error = None
    try:
        if server in running:
            starter.command_inout('DevStop', server)
            if not wait_for(server, False):
                raise RuntimeError(f'{{server}} did not appear in DevGetStopServers.')
            stopped_by_this_run = True
        start_once(server)
        started = True
    except Exception as exc:
        primary_error = exc
    finally:
        running_after_failure, _ = starter_lists()
        if not started and (stopped_by_this_run or server not in running_after_failure):
            try:
                start_once(server)
                started = True
                primary_error = None
                print('DEVSTART_RETRY_OK ' + server)
            except Exception as recovery_error:
                raise RuntimeError(
                    f'{{server}} restart failed; recovery DevStart also failed: {{recovery_error}}'
                ) from recovery_error
    if not started:
        raise RuntimeError(f'{{server}} restart failed: {{primary_error}}') from primary_error
    print('RESTARTED ' + server)

for server in servers:
    restart_one(server)
print('RESTART_COMPLETE ' + ','.join(servers))
"""
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
if ($status) {{ throw 'Refusing restart: Everest worktree is dirty.' }}
$headCommit = (Invoke-Native 'git rev-parse HEAD' {{ git rev-parse HEAD }}).Trim()
if ($headCommit -ne '{expected_commit}') {{ throw "Refusing restart: HEAD is $headCommit, expected {expected_commit}." }}
$code = @'
{python_code}'@
Invoke-Native 'Tango Starter restart' {{ conda run -n {environment} python -c $code }} | Out-Host
"""


def restart(
    servers: Sequence[str],
    expected_commit: str,
    approval_file: str | Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> RestartApproval:
    approval = load_restart_approval(approval_file, expected_commit, servers)
    script = build_restart_powershell(servers, expected_commit)
    command = build_ssh_command(EVEREST_HOST, script)
    print("+ " + " ".join(command[:8]) + " <encoded PowerShell>")
    runner(command, cwd=PROJECT_ROOT, check=True, text=True)
    return approval


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", action="append", default=[], help="Exact Tango server name, e.g. DS_DG645/main")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--approval-file", help="Absolute path to a human-created approval TOML outside this repository.")
    parser.add_argument("--apply", action="store_true", help="Send DevStop and DevStart through Tango Starter.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    servers = validate_servers(args.server)
    expected_commit = validate_commit(args.expected_commit)
    if not args.apply:
        print("Dry run. No Tango, SSH, or remote commands executed.")
        print("Servers: " + ", ".join(servers))
        return 0
    if not args.approval_file:
        raise RefactorToolError("Refusing DevStop/DevStart without --approval-file.")
    approval = restart(servers, expected_commit, args.approval_file)
    print(
        "Restart approval accepted: "
        f"approver={approval.approver} expires_at_utc={approval.expires_at_utc.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RefactorToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
