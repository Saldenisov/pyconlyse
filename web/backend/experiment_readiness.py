"""Bounded Tango Starter transitions used by experiment preparation."""

import time


def _has_reason(error, reason):
    text = str(error).lower().replace("_", " ")
    return reason.lower().replace("_", " ") in text


def start_managed_server(starter, server, wait_ready, timeout_s=25.0):
    """Start a stopped server or restart an unhealthy one after confirmed stop.

    Starter acknowledgement is not proof that its child exited. Never send
    DevStart while DevGetRunningServers still reports the previous process.
    An ALREADY_RUNNING race is resolved by checking the actual device readiness.
    """
    running = set(starter.command_inout("DevGetRunningServers", True))
    if server in running:
        try:
            starter.command_inout("DevStop", server)
        except Exception as exc:
            if not _has_reason(exc, "not running"):
                raise RuntimeError(f"Cannot stop {server}: {exc}") from exc
        deadline = time.monotonic() + timeout_s
        while server in set(starter.command_inout("DevGetRunningServers", True)):
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"{server} did not stop within {timeout_s:g} s; "
                    "correct the server/process condition, then press Prepare again"
                )
            time.sleep(0.5)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            starter.command_inout("DevStart", server)
            break
        except Exception as exc:
            if not _has_reason(exc, "already running"):
                raise RuntimeError(f"Cannot start {server}: {exc}") from exc
            if server in set(starter.command_inout("DevGetRunningServers", True)):
                # Another request actually started it; readiness is still
                # required below, never inferred from ALREADY_RUNNING alone.
                break
            # Starter can remove a dying child from its running inventory
            # before its process handle permits another DevStart. Retry only
            # this rejected start, not any accepted hardware command.
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Cannot start {server}: stop/start transition did not settle") from exc
            time.sleep(0.5)
    return wait_ready()


def recover_device(proxy, is_ready, commands=("recover", "Init", "turn_on")):
    """Try supported recovery commands and verify hardware after each attempt."""
    errors = []
    try:
        available = {name.lower() for name in proxy.get_command_list()}
    except Exception:
        available = None
    for command in commands:
        if available is not None and command.lower() not in available:
            continue
        try:
            proxy.command_inout(command)
            if is_ready(proxy):
                return True, errors
        except Exception as exc:
            errors.append(f"{command}: {exc}")
            # A timed-out command may still own the device's SDK/lifecycle
            # lock. Do not enqueue another Init or turn_on into that process.
            if _has_reason(exc, "API_DeviceTimedOut") or _has_reason(exc, "TRANSIENT_CallTimedout"):
                return False, errors
    return False, errors


def stop_managed_server(starter, server, timeout_s=25.0):
    """Stop one managed server and confirm the process left Starter's inventory."""
    try:
        starter.command_inout("DevStop", server)
    except Exception as exc:
        if not (_has_reason(exc, "not running") or _has_reason(exc, "API_DeviceNotExported")):
            raise RuntimeError(f"Cannot stop {server}: {exc}") from exc
        # Unexporting can precede process exit. Still confirm its absence from
        # the all-server inventory before claiming released SDK ownership.
    deadline = time.monotonic() + timeout_s
    while server in set(starter.command_inout("DevGetRunningServers", True)):
        if time.monotonic() >= deadline:
            raise RuntimeError(f"{server} did not stop; SDK ownership was not released")
        time.sleep(0.5)
