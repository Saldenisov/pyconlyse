#!/usr/bin/env python3
"""Passive Tango database and Starter readiness probes for Windows startup."""

from __future__ import annotations

import argparse
import sys


def _database_ready() -> None:
    from tango import Database

    Database().get_server_list()


def _starter_ready(device_name: str) -> None:
    from tango import DeviceProxy

    starter = DeviceProxy(device_name)
    starter.ping()
    starter.command_inout("DevGetRunningServers", True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--database", action="store_true")
    group.add_argument("--starter")
    args = parser.parse_args(argv)
    if args.database:
        _database_ready()
    else:
        _starter_ready(args.starter)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TANGO_READINESS_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
