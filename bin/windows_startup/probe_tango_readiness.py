#!/usr/bin/env python3
"""Tango readiness and controlled-server startup helpers for Windows boot."""

from __future__ import annotations

import argparse
import sys


def _database_ready() -> None:
    from tango import Database

    database = Database()
    database.set_timeout_millis(2500)
    database.get_server_list()


def _starter_ready(device_name: str) -> None:
    from tango import DeviceProxy

    starter = DeviceProxy(device_name)
    starter.set_timeout_millis(2500)
    starter.ping()
    starter.command_inout("DevGetRunningServers", True)


def _start_controlled_servers(device_name: str) -> None:
    """Start every stopped server that Starter marks for automatic control."""
    from tango import DeviceProxy

    starter = DeviceProxy(device_name)
    starter.set_timeout_millis(2500)
    starter.ping()
    stopped = [
        str(server)
        for server in starter.command_inout("DevGetStopServers", False)
    ]
    for server in stopped:
        print(f"STARTING_CONTROLLED_SERVER: {server}")
        starter.command_inout("DevStart", server)


def _controlled_servers_ready(device_name: str) -> None:
    """Check live admin endpoints; a hardware FAULT is not a stopped server."""
    from tango import Database, DeviceProxy

    _starter_ready(device_name)
    database = Database()
    database.set_timeout_millis(2500)
    host = device_name.rsplit("/", 1)[-1]
    servers = []
    unavailable = []
    for server in database.get_host_server_list(host):
        info = database.get_server_info(server)
        if not info.mode or info.level <= 0:
            continue
        servers.append(str(server))
        try:
            proxy = DeviceProxy(f"dserver/{server}")
            proxy.set_timeout_millis(2500)
            proxy.ping()
        except Exception as exc:
            unavailable.append(f"{server}: {exc}")
    if not servers:
        raise RuntimeError(f"No automatic servers configured for {host}")
    if unavailable:
        raise RuntimeError("Controlled servers unavailable: " + "; ".join(unavailable))
    print(f"CONTROLLED_SERVERS_READY: host={host} count={len(servers)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--database", action="store_true")
    group.add_argument("--starter")
    group.add_argument("--start-controlled")
    group.add_argument("--controlled-ready")
    args = parser.parse_args(argv)
    if args.database:
        _database_ready()
    elif args.start_controlled:
        _start_controlled_servers(args.start_controlled)
    elif args.controlled_ready:
        _controlled_servers_ready(args.controlled_ready)
    else:
        _starter_ready(args.starter)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TANGO_READINESS_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
