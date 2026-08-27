#!/usr/bin/env python3
"""Measure approved, sequential Tango Starter restarts on Everest or Elysium 2.

Dry run is the default.  ``--apply`` requires an operator-authored approval
file outside this repository.  This tool only uses Starter ``DevStop`` and
``DevStart`` plus read-only Tango probes.  It never uses ``HardKillServer``,
``taskkill``, PDU, motion, shutter, or power commands.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from statistics import median
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.refactor.deploy_everest import build_ssh_command
from scripts.refactor.restart_tango_servers import load_restart_approval
from scripts.refactor.tango_restart_targets import (
    TANGO_RESTART_TARGETS,
    TangoRestartTarget,
    resolve_tango_restart_target,
)
from scripts.refactor.verify_refactor import (
    PROJECT_ROOT,
    RefactorToolError,
    validate_commit,
    validate_servers,
)


MEASUREMENT_PREFIX = "TANGO_RESTART_MEASUREMENT "
REPORT_SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_POLL_INTERVAL_S = 0.10
_DEVICE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class BenchmarkRun:
    """Result available even when the remote benchmark records a failure."""

    target: str
    expected_commit: str
    measurements: tuple[dict[str, Any], ...]
    returncode: int
    stderr: str
    requested_servers: tuple[str, ...] = ()


def validate_duration(value: float, *, name: str, minimum: float, maximum: float) -> float:
    """Keep timeout and polling values bounded before embedding remote Python."""
    if not minimum <= value <= maximum:
        raise RefactorToolError(f"{name} must be between {minimum:g} and {maximum:g} seconds.")
    return value


def parse_readiness_devices(
    values: Sequence[str], servers: Sequence[str]
) -> dict[str, str]:
    """Parse optional ``SERVER=DEVICE`` read-only readiness probes."""
    allowed_servers = set(validate_servers(servers))
    devices: dict[str, str] = {}
    for value in values:
        server, separator, device = value.partition("=")
        if not separator or not server or not device:
            raise RefactorToolError(
                "--readiness-device must use exact SERVER=domain/family/member syntax."
            )
        if server not in allowed_servers:
            raise RefactorToolError(f"Readiness device names unrequested server: {server!r}.")
        if not _DEVICE_PATTERN.fullmatch(device):
            raise RefactorToolError(f"Unsafe Tango readiness device: {device!r}")
        if server in devices:
            raise RefactorToolError(f"Readiness device is repeated for {server!r}.")
        devices[server] = device
    return devices


def load_benchmark_approval(
    approval_file: str | Path,
    expected_commit: str,
    servers: Sequence[str],
    target: TangoRestartTarget,
) -> None:
    """Require the canonical restart approval, including its target binding."""
    load_restart_approval(approval_file, expected_commit, servers, target=target.name)


def build_benchmark_powershell(
    servers: Sequence[str],
    expected_commit: str,
    target: TangoRestartTarget,
    *,
    readiness_devices: Mapping[str, str] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
) -> str:
    """Build a non-interpolated SSH PowerShell payload with remote monotonic timings."""
    servers = validate_servers(servers)
    expected_commit = validate_commit(expected_commit)
    timeout_s = validate_duration(timeout_s, name="timeout", minimum=1.0, maximum=300.0)
    poll_interval_s = validate_duration(
        poll_interval_s, name="poll interval", minimum=0.05, maximum=1.0
    )
    readiness_devices = parse_readiness_devices(
        [f"{server}={device}" for server, device in (readiness_devices or {}).items()], servers
    )
    server_json = json.dumps(list(servers), separators=(",", ":"))
    readiness_json = json.dumps(readiness_devices, sort_keys=True, separators=(",", ":"))
    python_code = f'''import json
import time
from datetime import datetime, timezone

from tango import DeviceProxy

MEASUREMENT_PREFIX = {MEASUREMENT_PREFIX!r}
servers = json.loads({server_json!r})
readiness_devices = json.loads({readiness_json!r})
starter = DeviceProxy({target.starter_device!r})
timeout_s = {timeout_s!r}
poll_interval_s = {poll_interval_s!r}
run_started_ns = time.monotonic_ns()

def elapsed_ms(started_ns):
    return round((time.monotonic_ns() - started_ns) / 1_000_000.0, 3)

def offset_ms():
    return round((time.monotonic_ns() - run_started_ns) / 1_000_000.0, 3)

def error_text(error):
    return type(error).__name__ + ': ' + str(error)

def add_phase(record, name, started_ns, status, **details):
    phase = {{
        'offset_ms': round((started_ns - run_started_ns) / 1_000_000.0, 3),
        'duration_ms': elapsed_ms(started_ns),
        'status': status,
    }}
    phase.update(details)
    record['phases'][name] = phase

def timed_phase(record, name, operation):
    started_ns = time.monotonic_ns()
    try:
        result = operation()
    except Exception as error:
        add_phase(record, name, started_ns, 'error', error=error_text(error))
        raise
    add_phase(record, name, started_ns, 'ok')
    return result

def starter_lists():
    running = set(starter.command_inout('DevGetRunningServers', True))
    stopped = set(starter.command_inout('DevGetStopServers', True))
    return running, stopped

def capture_lists(record, name):
    started_ns = time.monotonic_ns()
    try:
        running, stopped = starter_lists()
    except Exception as error:
        add_phase(record, name, started_ns, 'error', error=error_text(error))
        raise
    add_phase(
        record,
        name,
        started_ns,
        'ok',
        running_count=len(running),
        stopped_count=len(stopped),
    )
    return running, stopped

def wait_for_server(record, name, server, expected_running):
    started_ns = time.monotonic_ns()
    deadline_ns = started_ns + int(timeout_s * 1_000_000_000)
    polls = 0
    poll_rpc_ms = 0.0
    last_running, last_stopped = set(), set()
    while time.monotonic_ns() < deadline_ns:
        poll_started_ns = time.monotonic_ns()
        try:
            last_running, last_stopped = starter_lists()
        except Exception as error:
            add_phase(
                record,
                name,
                started_ns,
                'error',
                polls=polls,
                poll_rpc_ms=round(poll_rpc_ms, 3),
                error=error_text(error),
            )
            raise
        polls += 1
        poll_rpc_ms += (time.monotonic_ns() - poll_started_ns) / 1_000_000.0
        reached = server in last_running if expected_running else (
            server not in last_running and server in last_stopped
        )
        if reached:
            add_phase(
                record,
                name,
                started_ns,
                'ok',
                polls=polls,
                poll_rpc_ms=round(poll_rpc_ms, 3),
            )
            return
        time.sleep(poll_interval_s)
    add_phase(
        record,
        name,
        started_ns,
        'timeout',
        polls=polls,
        poll_rpc_ms=round(poll_rpc_ms, 3),
        running=server in last_running,
        stopped=server in last_stopped,
    )
    expected = 'DevGetRunningServers' if expected_running else 'DevGetStopServers'
    raise RuntimeError(server + ' did not reach ' + expected + '.')

def wait_for_ping(record, name, device):
    started_ns = time.monotonic_ns()
    deadline_ns = started_ns + int(timeout_s * 1_000_000_000)
    attempts = 0
    last_error = None
    while time.monotonic_ns() < deadline_ns:
        attempts += 1
        try:
            DeviceProxy(device).ping()
        except Exception as error:
            last_error = error_text(error)
            time.sleep(poll_interval_s)
            continue
        add_phase(record, name, started_ns, 'ok', attempts=attempts, device=device)
        return
    add_phase(
        record,
        name,
        started_ns,
        'timeout',
        attempts=attempts,
        device=device,
        error=last_error,
    )
    raise RuntimeError(device + ' did not answer ping.')

def start_once(record, server, phase_prefix):
    request_started_ns = time.monotonic_ns()
    try:
        starter.command_inout('DevStart', server)
    except Exception as error:
        add_phase(
            record,
            phase_prefix + '_request',
            request_started_ns,
            'error',
            error=error_text(error),
        )
        wait_for_server(record, phase_prefix + '_registration', server, True)
        return
    add_phase(record, phase_prefix + '_request', request_started_ns, 'ok')
    wait_for_server(record, phase_prefix + '_registration', server, True)

def benchmark_one(server):
    started_ns = time.monotonic_ns()
    record = {{
        'schema_version': {REPORT_SCHEMA_VERSION},
        'server': server,
        'remote_started_at_utc': datetime.now(timezone.utc).isoformat(),
        'phases': {{}},
        'outcome': 'failed',
    }}
    stopped_by_this_run = False
    started = False
    try:
        running, _ = capture_lists(record, 'precheck')
        if server in running:
            timed_phase(record, 'stop_request', lambda: starter.command_inout('DevStop', server))
            wait_for_server(record, 'stop_confirmation', server, False)
            stopped_by_this_run = True
        start_once(record, server, 'start')
        started = True
        wait_for_ping(record, 'admin_readiness', 'dserver/' + server)
        readiness_device = readiness_devices.get(server)
        if readiness_device:
            wait_for_ping(record, 'device_readiness', readiness_device)
        record['outcome'] = 'ok'
    except Exception as error:
        record['error'] = error_text(error)
    finally:
        if not started and stopped_by_this_run:
            try:
                start_once(record, server, 'recovery_start')
                wait_for_ping(record, 'recovery_admin_readiness', 'dserver/' + server)
                record['recovery'] = 'ok'
            except Exception as recovery_error:
                record['recovery'] = 'failed'
                record['recovery_error'] = error_text(recovery_error)
        record['total_duration_ms'] = elapsed_ms(started_ns)
        record['remote_finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        print(MEASUREMENT_PREFIX + json.dumps(record, sort_keys=True, separators=(',', ':')))
    if record['outcome'] != 'ok':
        raise RuntimeError(server + ' benchmark failed: ' + record.get('error', 'unknown error'))

for server in servers:
    benchmark_one(server)
print('TANGO_RESTART_BENCHMARK_COMPLETE ' + ','.join(servers))
'''
    return f"""$ErrorActionPreference = 'Stop'

function Invoke-Native {{
    param(
        [string]$Label,
        [scriptblock]$Command
    )
    & $Command | Out-Host
    if ($LASTEXITCODE -ne 0) {{
        throw "$Label failed with native exit code $LASTEXITCODE."
    }}
}}

Set-Location -LiteralPath '{target.repository}'
$status = & git status --porcelain
if ($LASTEXITCODE -ne 0) {{ throw 'git status failed.' }}
if ($status) {{ throw 'Refusing benchmark: remote worktree is dirty.' }}
$headCommit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {{ throw 'git rev-parse HEAD failed.' }}
if ($headCommit -ne '{expected_commit}') {{ throw "Refusing benchmark: HEAD is $headCommit, expected {expected_commit}." }}
$code = @'
{python_code}'@
Invoke-Native 'Tango Starter restart benchmark' {{
    conda run -n {target.environment} python -c $code
}}
"""


def parse_measurements(stdout: str) -> tuple[dict[str, Any], ...]:
    """Extract one JSON record per attempted server from remote standard output."""
    records: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith(MEASUREMENT_PREFIX):
            continue
        try:
            record = json.loads(line[len(MEASUREMENT_PREFIX) :])
        except json.JSONDecodeError as exc:
            raise RefactorToolError("Remote benchmark emitted invalid measurement JSON.") from exc
        if not isinstance(record, dict) or not isinstance(record.get("server"), str):
            raise RefactorToolError("Remote benchmark emitted an invalid measurement record.")
        records.append(record)
    return tuple(records)


def build_report(run: BenchmarkRun) -> dict[str, Any]:
    """Produce a stable local report without deriving timestamps from local clock."""
    durations = [
        record["total_duration_ms"]
        for record in run.measurements
        if isinstance(record.get("total_duration_ms"), (int, float))
    ]
    outcomes = [record.get("outcome") for record in run.measurements]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "target": run.target,
        "expected_commit": run.expected_commit,
        "transport_returncode": run.returncode,
        "requested_server_count": len(run.requested_servers),
        "server_count": len(run.measurements),
        "successful_servers": sum(outcome == "ok" for outcome in outcomes),
        "failed_servers": sum(outcome != "ok" for outcome in outcomes),
        "total_duration_ms": {
            "min": min(durations) if durations else None,
            "median": median(durations) if durations else None,
            "max": max(durations) if durations else None,
        },
        "measurements": list(run.measurements),
        "stderr": run.stderr,
    }


def write_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    """Write JSON atomically, so a partial transport failure preserves prior report."""
    output = Path(path).expanduser()
    if not output.is_absolute():
        raise RefactorToolError("--output must be an absolute JSON path outside the repository.")
    output = output.resolve()
    try:
        output.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise RefactorToolError("--output must be outside the repository.")
    if output.suffix.lower() != ".json":
        raise RefactorToolError("--output must have a .json suffix.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return output


def run_benchmark(
    target: TangoRestartTarget,
    servers: Sequence[str],
    expected_commit: str,
    approval_file: str | Path,
    *,
    readiness_devices: Mapping[str, str] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> BenchmarkRun:
    """Run one approved remote benchmark and retain printed failure measurements."""
    servers = validate_servers(servers)
    expected_commit = validate_commit(expected_commit)
    load_benchmark_approval(approval_file, expected_commit, servers, target)
    command = build_ssh_command(
        target.ssh_host,
        build_benchmark_powershell(
            servers,
            expected_commit,
            target,
            readiness_devices=readiness_devices,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
        ),
    )
    print("+ " + " ".join(command[:8]) + " <encoded PowerShell>")
    completed = runner(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr)
    return BenchmarkRun(
        target=target.name,
        expected_commit=expected_commit,
        measurements=parse_measurements(completed.stdout),
        returncode=completed.returncode,
        stderr=completed.stderr,
        requested_servers=tuple(servers),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=tuple(sorted(TANGO_RESTART_TARGETS)))
    parser.add_argument("--server", action="append", default=[], help="Exact Tango server, e.g. DS_DG645/main")
    parser.add_argument(
        "--readiness-device",
        action="append",
        default=[],
        help="Optional read-only ping target: exact SERVER=domain/family/member.",
    )
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--approval-file", help="Absolute operator-authored TOML outside this repository.")
    parser.add_argument("--output", help="Absolute JSON report path outside this repository.")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--poll-interval-s", type=float, default=DEFAULT_POLL_INTERVAL_S)
    parser.add_argument("--apply", action="store_true", help="Send approved DevStop and DevStart requests.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    target = resolve_tango_restart_target(args.target)
    servers = validate_servers(args.server)
    expected_commit = validate_commit(args.expected_commit)
    readiness_devices = parse_readiness_devices(args.readiness_device, servers)
    validate_duration(args.timeout_s, name="timeout", minimum=1.0, maximum=300.0)
    validate_duration(
        args.poll_interval_s, name="poll interval", minimum=0.05, maximum=1.0
    )
    if not args.apply:
        print("Dry run. No Tango, SSH, or remote commands executed.")
        print(f"Target: {target.name} {target.ssh_host} starter={target.starter_device}")
        print("Servers: " + ", ".join(servers))
        return 0
    if not args.approval_file:
        raise RefactorToolError("Refusing DevStop/DevStart without --approval-file.")
    if not args.output:
        raise RefactorToolError("Refusing benchmark without an external --output JSON path.")
    run = run_benchmark(
        target,
        servers,
        expected_commit,
        args.approval_file,
        readiness_devices=readiness_devices,
        timeout_s=args.timeout_s,
        poll_interval_s=args.poll_interval_s,
    )
    output = write_report(args.output, build_report(run))
    print(f"Benchmark report: {output}")
    if run.returncode != 0:
        print(f"ERROR: remote benchmark exited with code {run.returncode}.", file=sys.stderr)
        return 1
    if not run.measurements:
        print("ERROR: remote benchmark emitted no measurements.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RefactorToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
