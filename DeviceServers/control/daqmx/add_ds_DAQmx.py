"""
Register the direct local DS_DAQmx device server in the Tango database.

This is separate from add_ds_DAQmx_zmq.py, which is kept for remote cards.
"""

import socket
from pathlib import Path

from tango import Database, DbDevInfo, DbServerInfo

db = Database()


def _starter_host(server_name: str) -> str:
    hostname = socket.gethostname()
    fallback_host = ""
    controlled_fallback_host = ""
    try:
        for server in db.get_server_list("*"):
            if str(server).lower() == str(server_name).lower():
                continue
            info = db.get_server_info(server)
            host = str(getattr(info, "host", "") or "").strip()
            mode = int(getattr(info, "mode", 0) or 0)
            level = int(getattr(info, "level", 0) or 0)
            if not host or host == "None":
                continue
            if host.split(".", 1)[0].lower() != hostname.lower():
                continue
            if mode == 1 and level > 0:
                if "." in host:
                    return host
                controlled_fallback_host = controlled_fallback_host or host
            if "." in host:
                fallback_host = fallback_host or host
                continue
            fallback_host = fallback_host or host
    except Exception:
        pass
    if controlled_fallback_host:
        return controlled_fallback_host
    if fallback_host:
        return fallback_host

    fqdn = socket.getfqdn()
    if fqdn and "." in fqdn:
        return fqdn
    return hostname or fqdn


def register_device():
    device_name = "control/DAQ/DAQMX_1"
    instance_name = "DAQMX_1"
    server_name = f"DS_DAQmx/1_{instance_name}"
    config_path = Path(__file__).with_name("daqmx_transcon.ini")

    dev_info = DbDevInfo()
    dev_info.name = device_name
    dev_info._class = "DS_DAQmx"
    dev_info.server = server_name

    try:
        db.add_device(dev_info)
        print(f"Added device: {device_name}")
    except Exception as exc:
        print(f"Device may already exist, continuing with properties: {exc}")

    db.put_device_property(
        device_name,
        {
            "device_id": "TRANCON-DAQ",
            "friendly_name": "TRANCON DAQmx",
            "server_id": 1,
            "daq_device_name": "TRANCON-DAQ",
            "channel_config_path": str(config_path),
            "terminal_config": "RSE",
            "archive_enabled": 0,
            "always_on": 1,
            "start_on_init": 1,
        },
    )
    print(f"Set properties for: {device_name}")
    print(f"  - Server: {server_name}")
    print(f"  - Config: {config_path}")

    server_info = DbServerInfo()
    server_info.name = server_name
    server_info.host = _starter_host(server_name)
    server_info.mode = 1
    server_info.level = 1
    db.put_server_info(server_info)
    print("Set Astor/Starter metadata:")
    print(f"  - Host: {server_info.host}")
    print(f"  - Startup level: {server_info.level}")
    print(f"  - Controlled mode: {server_info.mode}")


def main():
    print("=" * 70)
    print("Registering direct DS_DAQmx Device Server")
    print("=" * 70)
    register_device()
    print("=" * 70)
    print("Done.")
    print("=" * 70)
    print("Start command:")
    print("  python DS_DAQmx.py 1_DAQMX_1")


if __name__ == "__main__":
    main()
