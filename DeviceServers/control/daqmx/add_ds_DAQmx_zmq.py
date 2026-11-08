"""Register DS_DAQmx_ZMQ in Tango and Astor/Starter."""

import socket

from tango import Database, DbDevInfo, DbServerInfo

db = Database()


def _starter_host(server_name: str) -> str:
    """Return the managed Astor host name already used on this computer."""
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
    return controlled_fallback_host or fallback_host or socket.getfqdn() or hostname


# Configuration for DAQmx ZMQ Device Servers
# Format: [domain/family, friendly_name, instance_name, zmq_host, zmq_port, retention_time]
devices = {
    1: [
        "control/DAQ",
        "DAQmx_ZMQ_Main",
        "DAQMX_ZMQ_1",
        "*",  # Bind to all interfaces
        6050,
        100,  # 100 seconds retention
    ],
}


def register_device(dev_id: int, config: list):
    """Register a single device to Tango database"""
    
    domain_family = config[0]
    friendly_name = config[1]
    instance_name = config[2]
    zmq_host = config[3]
    zmq_port = config[4]
    retention_time = config[5]
    
    # Full device name
    dev_name = f"{domain_family}/{instance_name}"
    
    # Create device info
    dev_info = DbDevInfo()
    dev_info.name = dev_name
    dev_info._class = "DS_DAQmx_ZMQ"
    server_name = f"DS_DAQmx_ZMQ/{dev_id}_{instance_name}"
    dev_info.server = server_name
    
    # Add device to database
    try:
        db.add_device(dev_info)
        print(f"Added device: {dev_name}")
    except Exception as exc:
        print(f"Device may already exist, continuing with properties: {exc}")
    
    # Set device properties
    db.put_device_property(
        dev_name,
        {
            "device_id": dev_id,
            "friendly_name": friendly_name,
            "server_id": dev_id,
            "device_name": instance_name,
            "zmq_host": zmq_host,
            "zmq_port": zmq_port,
            "retention_time": retention_time,
        },
    )
    print(f"Set properties for: {dev_name}")
    print(f"  - ZMQ: {zmq_host}:{zmq_port}")
    print(f"  - Retention: {retention_time}s")

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
    """Register all configured devices"""
    print("="*70)
    print("Registering DS_DAQmx_ZMQ Device Servers")
    print("="*70)
    print()
    
    for dev_id, config in devices.items():
        try:
            register_device(dev_id, config)
            print()
        except Exception as e:
            print(f"Error registering device {dev_id}: {e}")
            print()
    
    print("="*70)
    print("Registration complete!")
    print("="*70)
    print()
    print("To start the device server, run:")
    print("  python DS_DAQmx_zmq.py 1_DAQMX_ZMQ_1")


if __name__ == "__main__":
    main()
