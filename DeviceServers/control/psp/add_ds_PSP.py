"""
Register minimal DS_PSP device in Tango database.

Default target:
    manip/general/PSP
"""

from tango import Database, DbDevInfo

db = Database()


def register_device():
    device_name = "manip/general/PSP"
    instance_name = "PSP"
    server_name = f"DS_PSP/1_{instance_name}"

    dev_info = DbDevInfo()
    dev_info.name = device_name
    dev_info._class = "DS_PSP"
    dev_info.server = server_name

    db.add_device(dev_info)
    print(f"✓ Added device: {device_name}")

    db.put_device_property(
        device_name,
        {
            "device_id": "1",
            "friendly_name": "PSP Receiver",
            "server_id": 1,
            "always_on": 1,
            "archive_enabled": 0,
            "fifo_size": "5000",
        },
    )
    print(f"✓ Set properties for: {device_name}")
    print(f"  - Server: {server_name}")


def main():
    print("=" * 70)
    print("Registering DS_PSP Device Server")
    print("=" * 70)
    try:
        register_device()
    except Exception as exc:
        print(f"✗ Registration failed: {exc}")
        raise
    print("=" * 70)
    print("Done.")
    print("=" * 70)
    print("Start command:")
    print("  python DS_PSP.py 1_PSP")


if __name__ == "__main__":
    main()
