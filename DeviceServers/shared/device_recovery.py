"""Safe Tango device-server restart and configured PDU power-cycle helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import tango


class DeviceRecoveryError(RuntimeError):
    """Raised when a requested recovery operation cannot be confirmed."""


@dataclass(frozen=True)
class PowerCycleConfig:
    pdu_device: str
    output_id: int
    off_seconds: float = 3.0
    settle_seconds: float = 5.0


def _first_property(properties, name, default=None):
    value = properties.get(name, default)
    if not isinstance(value, (str, bytes)):
        try:
            return value[0] if len(value) else default
        except (TypeError, KeyError, IndexError):
            pass
    return value


def get_power_cycle_config(
    device_name: str,
    *,
    database=None,
    off_seconds: float = 3.0,
) -> Optional[PowerCycleConfig]:
    """Read an explicit DS-to-PDU mapping without contacting the target DS."""
    db = database or tango.Database()
    names = (
        "power_dependency_device",
        "power_dependency_output_id",
        "power_on_settle_seconds",
    )
    properties = db.get_device_property(str(device_name), list(names))
    pdu_device = str(_first_property(properties, names[0], "") or "").strip()
    try:
        output_id = int(_first_property(properties, names[1], 0) or 0)
        settle_seconds = max(
            0.0, float(_first_property(properties, names[2], 5.0) or 0.0)
        )
    except (TypeError, ValueError):
        return None

    if not pdu_device or output_id <= 0:
        return None
    return PowerCycleConfig(
        pdu_device=pdu_device,
        output_id=output_id,
        off_seconds=max(0.5, float(off_seconds)),
        settle_seconds=settle_seconds,
    )


def resolve_server_name(device_name: str, *, database=None) -> str:
    """Resolve the exact Tango server/instance registered for a device."""
    db = database or tango.Database()
    info = db.get_device_info(str(device_name))
    server_name = getattr(info, "ds_full_name", None) or getattr(info, "server", None)
    if not server_name:
        raise DeviceRecoveryError(f"Could not resolve Tango server for {device_name}")
    return str(server_name)


def _proxy(name: str, proxy_factory=None):
    proxy = (proxy_factory or tango.DeviceProxy)(str(name))
    set_timeout = getattr(proxy, "set_timeout_millis", None)
    if callable(set_timeout):
        set_timeout(5000)
    return proxy


def _starter_lists(starter):
    running = {
        str(value) for value in starter.command_inout("DevGetRunningServers", False)
    }
    stopped = {
        str(value) for value in starter.command_inout("DevGetStopServers", False)
    }
    return running, stopped


def _starter_devices(database):
    try:
        exported = database.get_device_exported("tango/admin/*")
    except Exception:
        exported = database.get_device_exported("*")
    return sorted(
        {
            str(name)
            for name in exported
            if str(name).lower().startswith("tango/admin/")
        }
    )


def find_starter_for_server(server_name: str, *, database=None, proxy_factory=None):
    """Return the Starter which reports the registered server."""
    db = database or tango.Database()
    errors = []
    starter_names = _starter_devices(db)
    for starter_name in starter_names:
        try:
            starter = _proxy(starter_name, proxy_factory)
            running, stopped = _starter_lists(starter)
            if server_name in running or server_name in stopped:
                return starter_name, starter, running, stopped
        except Exception as error:
            errors.append(f"{starter_name}: {error}")

    # A crashed server may temporarily disappear from both Starter lists. The
    # Tango database still records the host which owns it, so use that Starter
    # as a fail-safe without guessing another machine.
    try:
        server_info = db.get_server_info(server_name)
        host = str(getattr(server_info, "host", "") or "").strip().lower()
        short_host = host.split(".", 1)[0]
        fallback_name = next(
            (
                name
                for name in starter_names
                if name.rsplit("/", 1)[-1].lower() in {host, short_host}
            ),
            "",
        )
        if fallback_name:
            starter = _proxy(fallback_name, proxy_factory)
            running, stopped = _starter_lists(starter)
            return fallback_name, starter, running, stopped
    except Exception as error:
        errors.append(f"database host fallback: {error}")
    suffix = f" ({'; '.join(errors[-2:])})" if errors else ""
    raise DeviceRecoveryError(f"No Tango Starter manages {server_name}{suffix}")


def _wait_for_server_state(
    starter,
    server_name: str,
    *,
    should_run: bool,
    timeout_s: float,
    poll_s: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
):
    deadline = monotonic() + max(0.0, float(timeout_s))
    while True:
        running, stopped = _starter_lists(starter)
        reached = server_name in running if should_run else server_name not in running
        if reached:
            return running, stopped
        if monotonic() >= deadline:
            state = "start" if should_run else "stop"
            raise DeviceRecoveryError(
                f"{server_name} did not {state} within {timeout_s:.1f} seconds"
            )
        sleeper(max(0.05, float(poll_s)))


def restart_device_server(
    device_name: str,
    *,
    database=None,
    proxy_factory=None,
    timeout_s: float = 12.0,
    poll_s: float = 0.5,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
):
    """Gracefully stop and start a DS through Starter; never hard-kill it."""
    db = database or tango.Database()
    server_name = resolve_server_name(device_name, database=db)
    starter_name, starter, running, _stopped = find_starter_for_server(
        server_name,
        database=db,
        proxy_factory=proxy_factory,
    )

    if server_name in running:
        try:
            starter.command_inout("DevStop", server_name)
        except Exception as error:
            running_after_error, _ = _starter_lists(starter)
            if server_name in running_after_error:
                raise DeviceRecoveryError(
                    f"Starter could not stop {server_name}: {error}"
                ) from error
        _wait_for_server_state(
            starter,
            server_name,
            should_run=False,
            timeout_s=timeout_s,
            poll_s=poll_s,
            sleeper=sleeper,
            monotonic=monotonic,
        )

    try:
        starter.command_inout("DevStart", server_name)
    except Exception as error:
        text = str(error).lower()
        if "already_running" not in text and "already running" not in text:
            raise DeviceRecoveryError(
                f"Starter could not start {server_name}: {error}"
            ) from error

    _wait_for_server_state(
        starter,
        server_name,
        should_run=True,
        timeout_s=timeout_s,
        poll_s=poll_s,
        sleeper=sleeper,
        monotonic=monotonic,
    )
    return {"device": str(device_name), "server": server_name, "starter": starter_name}


def _read_pdu_outputs(pdu):
    output_ids = [int(value) for value in pdu.read_attribute("ids").value]
    output_states = [int(value) for value in pdu.read_attribute("states").value]
    if len(output_ids) != len(output_states):
        raise DeviceRecoveryError("PDU ids/states lengths do not match")
    return output_ids, output_states


def _wait_for_pdu_output(
    pdu,
    output_id: int,
    expected: int,
    *,
    timeout_s: float,
    poll_s: float,
    sleeper: Callable[[float], None],
    monotonic: Callable[[], float],
):
    deadline = monotonic() + max(0.0, float(timeout_s))
    while True:
        output_ids, output_states = _read_pdu_outputs(pdu)
        try:
            observed = output_states[output_ids.index(int(output_id))]
        except ValueError as error:
            raise DeviceRecoveryError(
                f"PDU no longer reports output {output_id}"
            ) from error
        if observed == int(expected):
            return
        if monotonic() >= deadline:
            raise DeviceRecoveryError(
                f"PDU output {output_id} did not become {'ON' if expected else 'OFF'}"
            )
        sleeper(max(0.05, float(poll_s)))


def _set_pdu_output(pdu, output_id: int, state: int):
    output_ids, output_states = _read_pdu_outputs(pdu)
    try:
        index = output_ids.index(int(output_id))
    except ValueError as error:
        raise DeviceRecoveryError(f"PDU does not provide output {output_id}") from error
    requested = list(output_states)
    requested[index] = int(state)
    pdu.command_inout("set_channels_states", requested)


def power_cycle_device(
    device_name: str,
    *,
    config: Optional[PowerCycleConfig] = None,
    database=None,
    proxy_factory=None,
    verify_timeout_s: float = 8.0,
    poll_s: float = 0.25,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
):
    """Cycle only an explicitly configured PDU output and confirm both edges."""
    resolved = config or get_power_cycle_config(device_name, database=database)
    if resolved is None:
        raise DeviceRecoveryError(
            f"{device_name} has no configured PDU power dependency"
        )

    pdu = _proxy(resolved.pdu_device, proxy_factory)
    output_ids, output_states = _read_pdu_outputs(pdu)
    try:
        current_state = output_states[output_ids.index(resolved.output_id)]
    except ValueError as error:
        raise DeviceRecoveryError(
            f"{resolved.pdu_device} does not provide output {resolved.output_id}"
        ) from error
    if current_state != 1:
        raise DeviceRecoveryError(
            f"{resolved.pdu_device} output {resolved.output_id} is already OFF; "
            "it was not turned on automatically"
        )

    restore_required = True
    try:
        _set_pdu_output(pdu, resolved.output_id, 0)
        _wait_for_pdu_output(
            pdu,
            resolved.output_id,
            0,
            timeout_s=verify_timeout_s,
            poll_s=poll_s,
            sleeper=sleeper,
            monotonic=monotonic,
        )
        sleeper(resolved.off_seconds)
        # Re-read all outputs before restoring this one so concurrent changes to
        # unrelated PDU channels are never overwritten with a stale vector.
        _set_pdu_output(pdu, resolved.output_id, 1)
        _wait_for_pdu_output(
            pdu,
            resolved.output_id,
            1,
            timeout_s=verify_timeout_s,
            poll_s=poll_s,
            sleeper=sleeper,
            monotonic=monotonic,
        )
        restore_required = False
        sleeper(resolved.settle_seconds)
    finally:
        if restore_required:
            try:
                _set_pdu_output(pdu, resolved.output_id, 1)
                _wait_for_pdu_output(
                    pdu,
                    resolved.output_id,
                    1,
                    timeout_s=verify_timeout_s,
                    poll_s=poll_s,
                    sleeper=sleeper,
                    monotonic=monotonic,
                )
            except Exception as restore_error:
                raise DeviceRecoveryError(
                    f"Power-cycle recovery failed and automatic restoration of "
                    f"{resolved.pdu_device} output {resolved.output_id} also failed: "
                    f"{restore_error}. The output may still be OFF."
                ) from restore_error

    return {
        "device": str(device_name),
        "pdu_device": resolved.pdu_device,
        "output_id": resolved.output_id,
        "off_seconds": resolved.off_seconds,
        "settle_seconds": resolved.settle_seconds,
    }
