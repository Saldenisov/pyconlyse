"""Register the passive ELYSE health monitor in Tango/Astor."""

from __future__ import annotations

import argparse

from tango import Database, DbDevInfo, DbServerInfo


def register(*, tango_host: str, host: str, apply: bool) -> None:
    db_host, db_port = tango_host.rsplit(":", 1)
    database = Database(db_host, int(db_port))
    device_name = "sys/health/elyse"
    server_name = "DS_HealthMonitor/elyse"
    print(f"Device: {device_name}")
    print(f"Server: {server_name}")
    print(f"Host:   {host}")
    if not apply:
        print("Dry run only; pass --apply to register.")
        return

    existing = {
        str(item).lower() for item in database.get_device_name("*", "*")
    }
    if device_name.lower() in existing:
        raise RuntimeError(f"Refusing to replace existing device {device_name}")

    info = DbDevInfo()
    info.name = device_name
    info._class = "DS_HealthMonitor"
    info.server = server_name
    database.add_device(info)
    database.put_device_property(
        device_name,
        {"poll_period_ms": 2000, "device_timeout_ms": 700},
    )
    server = DbServerInfo()
    server.name = server_name
    server.host = host
    server.mode = 1
    server.level = 1
    database.put_server_info(server)
    print("Registered. Monitoring is passive and performs no hardware commands.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tango-host", default="10.20.30.202:10000")
    parser.add_argument("--host", default="everest")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    register(tango_host=args.tango_host, host=args.host, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

