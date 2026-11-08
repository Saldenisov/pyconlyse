"""Register the disposable HDB++ acceptance probe."""

from __future__ import annotations

import argparse

from tango import Database, DbDevInfo, DbServerInfo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tango-host", default="10.20.30.202:10000")
    parser.add_argument("--host", default="everest")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db_host, db_port = args.tango_host.rsplit(":", 1)
    database = Database(db_host, int(db_port))
    device_name = "test/hdbpp/probe"
    server_name = "DS_HdbppProbe/acceptance"
    print(f"Device: {device_name}\nServer: {server_name}\nHost: {args.host}")
    if not args.apply:
        print("Dry run only; pass --apply to register.")
        return 0
    existing = {
        str(item).lower() for item in database.get_device_name("*", "*")
    }
    if device_name.lower() in existing:
        raise RuntimeError(f"Refusing to replace existing device {device_name}")
    device = DbDevInfo()
    device.name = device_name
    device._class = "DS_HdbppProbe"
    device.server = server_name
    database.add_device(device)
    server = DbServerInfo()
    server.name = server_name
    server.host = args.host
    server.mode = 1
    server.level = 1
    database.put_server_info(server)
    print("Registered disposable acceptance probe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

