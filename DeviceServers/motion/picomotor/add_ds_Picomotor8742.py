"""Print a Picomotor Tango registration; write it only with --apply."""

from __future__ import annotations

import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Tango domain/family/member")
    parser.add_argument("--instance", required=True)
    parser.add_argument(
        "--controller-host", required=True, help="Confirmed Picomotor IP/hostname"
    )
    parser.add_argument(
        "--server-host", required=True, help="Host running this Tango server"
    )
    parser.add_argument("--expected-identification", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if len(args.device.split("/")) != 3 or not all(args.device.split("/")):
        parser.error("--device must be domain/family/member")
    if not args.instance or "/" in args.instance:
        parser.error("--instance must be a nonempty server instance")
    properties = {
        "host": args.controller_host,
        "tcp_port": 23,
        "controller_address": 0,
        "motion_enabled": False,
        "expected_identification": args.expected_identification,
        "io_timeout_s": 1.0,
        "motion_timeout_s": 30.0,
        "poll_interval_s": 0.25,
    }
    plan = {
        "device": args.device,
        "class": "DS_Picomotor8742",
        "server": f"DS_Picomotor8742/{args.instance}",
        "server_host": args.server_host,
        "properties": properties,
    }
    print(json.dumps(plan, indent=2))
    if not args.apply:
        return 0
    from tango import Database, DbDevInfo, DbServerInfo

    db = Database()
    if plan["server"].lower() in {
        str(name).lower() for name in db.get_server_list("*")
    }:
        raise RuntimeError(
            "Server instance already registered; preserve existing ownership"
        )
    if args.device.lower() in {
        str(name).lower() for name in db.get_device_exported("*")
    }:
        raise RuntimeError("Device is exported; do not replace its registration")
    if args.device.lower() in {
        str(name).lower() for name in db.get_device_name("*", "*")
    }:
        raise RuntimeError("Device already registered; review existing ownership first")
    info = DbDevInfo()
    info.name, info._class, info.server = args.device, plan["class"], plan["server"]
    db.add_device(info)
    server = DbServerInfo()
    server.name, server.host, server.mode, server.level = (
        info.server,
        args.server_host,
        1,
        1,
    )
    db.put_server_info(server)
    db.put_device_property(info.name, properties)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
