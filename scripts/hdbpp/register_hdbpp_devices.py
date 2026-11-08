"""Register the ELYSE HDB++ services and their Linux Starter in Tango.

The command is a dry run unless ``--apply`` is supplied. Database passwords are
intentionally absent: the Linux Starter injects them from /etc/hdbpp/hdbpp.env.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DeviceRegistration:
    name: str
    device_class: str
    server: str
    properties: dict[str, object]


def build_plan(
    *,
    vm_hostname: str,
    database_host: str,
    database_port: int,
    database_name: str,
) -> list[DeviceRegistration]:
    lib_configuration = [
        "libname=libhdb++mysql.so",
        f"host={database_host}",
        f"port={database_port}",
        f"dbname={database_name}",
        "ignore_duplicates=1",
        "json_array=1",
        "batch_size=10000",
    ]
    event_subscriber = "archiving/hdbpp/es01"
    return [
        DeviceRegistration(
            name=f"tango/admin/{vm_hostname}",
            device_class="Starter",
            server="Starter/hdbpp-archive",
            properties={
                "StartDsPath": ["/opt/hdbpp/bin", "/usr/lib/tango", "/usr/bin"],
            },
        ),
        DeviceRegistration(
            name=event_subscriber,
            device_class="HdbEventSubscriber",
            server="hdb++es-srv/everest01",
            properties={"LibConfiguration": lib_configuration},
        ),
        DeviceRegistration(
            name="archiving/hdbpp/cm",
            device_class="HdbConfigurationManager",
            server="hdb++cm-srv/everest",
            properties={
                "ArchiverList": [event_subscriber],
                "LibConfiguration": lib_configuration,
            },
        ),
    ]


def parse_tango_host(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host:
        raise argparse.ArgumentTypeError("TANGO host must have the form host:port")
    try:
        parsed_port = int(port)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("TANGO port must be an integer") from exc
    if not 1 <= parsed_port <= 65535:
        raise argparse.ArgumentTypeError("TANGO port is outside the valid range")
    return host, parsed_port


def apply_plan(
    plan: list[DeviceRegistration],
    *,
    tango_host: tuple[str, int],
    vm_hostname: str,
) -> None:
    from tango import Database, DbDevInfo, DbServerInfo

    database = Database(*tango_host)
    existing_devices = {
        str(name).lower()
        for name in database.get_device_name("*", "*")
    }
    existing_servers = {str(name).lower() for name in database.get_server_list()}
    device_conflicts = [
        item.name for item in plan if item.name.lower() in existing_devices
    ]
    server_conflicts = sorted(
        {item.server for item in plan if item.server.lower() in existing_servers}
    )
    if device_conflicts or server_conflicts:
        joined = ", ".join(device_conflicts + server_conflicts)
        raise RuntimeError(
            f"Refusing to replace existing Tango registration(s): {joined}. "
            "Review them in Jive/Astor first."
        )

    for item in plan:
        device_info = DbDevInfo()
        device_info.name = item.name
        device_info._class = item.device_class
        device_info.server = item.server
        database.add_device(device_info)
        if item.properties:
            database.put_device_property(item.name, item.properties)

        server_info = DbServerInfo()
        server_info.name = item.server
        server_info.host = vm_hostname
        server_info.mode = 1
        server_info.level = 1 if item.device_class == "Starter" else 2
        database.put_server_info(server_info)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm-hostname", required=True, help="Ubuntu short hostname")
    parser.add_argument("--tango-host", default="10.20.30.202:10000")
    parser.add_argument("--database-host", default="10.20.30.202")
    parser.add_argument("--database-port", type=int, default=3307)
    parser.add_argument("--database-name", default="hdbpp")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    tango_host = parse_tango_host(args.tango_host)
    plan = build_plan(
        vm_hostname=args.vm_hostname,
        database_host=args.database_host,
        database_port=args.database_port,
        database_name=args.database_name,
    )
    print(json.dumps([asdict(item) for item in plan], indent=2))
    if not args.apply:
        print("Dry run only; pass --apply after reviewing this plan.")
        return 0

    apply_plan(plan, tango_host=tango_host, vm_hostname=args.vm_hostname)
    print("Registered Tango Starter, EventSubscriber, and ConfigurationManager.")
    print("Archiving remains empty/passive until attributes are added.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
