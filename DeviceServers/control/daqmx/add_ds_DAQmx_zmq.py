"""
Register DS_DAQmx_ZMQ Device Server to Tango Database
"""

from tango import Database, DbDevInfo

db = Database()


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
    dev_info.server = f"DS_DAQmx_ZMQ/{dev_id}_{instance_name}"
    
    # Add device to database
    db.add_device(dev_info)
    print(f"✓ Added device: {dev_name}")
    
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
    print(f"✓ Set properties for: {dev_name}")
    print(f"  - ZMQ: {zmq_host}:{zmq_port}")
    print(f"  - Retention: {retention_time}s")


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
            print(f"✗ Error registering device {dev_id}: {e}")
            print()
    
    print("="*70)
    print("Registration complete!")
    print("="*70)
    print()
    print("To start the device server, run:")
    print("  python DS_DAQmx_zmq.py 1_DAQMX_ZMQ_1")


if __name__ == "__main__":
    main()
