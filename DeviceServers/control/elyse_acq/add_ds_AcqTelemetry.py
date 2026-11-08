"""Register only the persistent, receive-only Everest telemetry server.

Configuration is stored in Tango; telemetry stays in latest-only RAM. The
initial deployment deliberately accepts fixture producers only. A real
producer requires an explicit key/filter change on both ends after review.
No Starter-wide policies or existing device registrations are overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEVICE = "elyse/acquisition/telemetry"
SERVER = "DS_AcqTelemetry/everest"
STARTER = "tango/admin/everest"
CLASS = "DS_AcqTelemetry"


def deployment_plan(key_file: Path) -> dict:
    from legacy.xp_acq_agent.elyse_agent.supervision_wire import validate_key

    key_file = key_file.resolve(strict=True)
    validate_key(key_file.read_bytes().strip())
    return {
        "device": DEVICE,
        "server": SERVER,
        "host": "everest",
        "mode": 1,
        "level": 1,
        "properties": {
            "listen_host": "10.20.30.202",
            "listen_port": 8767,
            "permitted_xp_host": "10.20.30.10",
            "key_file": key_file.as_posix(),
            "producer_kind_filter": "fixture",
        },
        "storage": "RAM latest per publication; no SQLite or telemetry history",
        "stop_deadline": None,
    }


def register(database, plan: dict, *, apply: bool = False) -> bool:
    """Reject collisions before any writes; dry run performs reads only."""
    devices = {str(name).lower() for name in database.get_device_name("*", "*")}
    servers = {str(name).lower() for name in database.get_server_list()}
    if DEVICE.lower() in devices or SERVER.lower() in servers:
        raise RuntimeError(f"Refusing to replace existing {DEVICE} or {SERVER}")
    if not apply:
        return False

    from tango import DbDevInfo, DbServerInfo

    device = DbDevInfo()
    device.name, device._class, device.server = DEVICE, CLASS, SERVER
    database.add_device(device)
    database.put_device_property(DEVICE, plan["properties"])
    server = DbServerInfo()
    server.name, server.host = SERVER, plan["host"]
    server.mode, server.level = plan["mode"], plan["level"]
    database.put_server_info(server)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--tango-host", default="10.20.30.202:10000")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    plan = deployment_plan(args.key_file)
    from tango import Database, DeviceProxy

    host, port = args.tango_host.rsplit(":", 1)
    database = Database(host, int(port))
    database.set_timeout_millis(3000)
    starter = DeviceProxy(f"tango://{args.tango_host}/{STARTER}")
    starter.set_timeout_millis(3000)
    starter.ping()
    paths = database.get_device_property(STARTER, ["StartDsPath"])["StartDsPath"]
    wrapper = ROOT / "DeviceServers" / "DS_AcqTelemetry.bat"
    if not wrapper.is_file() or not any(
        Path(str(path)).resolve() == wrapper.parent.resolve() for path in paths
    ):
        raise RuntimeError(
            "DS_AcqTelemetry.bat must be in existing Starter StartDsPath"
        )
    print(json.dumps(plan, indent=2))
    applied = register(database, plan, apply=args.apply)
    print(
        "Registered; start only this server with Starter DevStart."
        if applied
        else "Dry run: no writes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
