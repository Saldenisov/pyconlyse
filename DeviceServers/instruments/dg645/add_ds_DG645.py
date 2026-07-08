from tango import Database, DbDevInfo


def main():
    db = Database()

    dev_info = DbDevInfo()
    dev_info.name = "manip/sync/DG645"
    dev_info._class = "DS_DG645"
    dev_info.server = "DS_DG645/1_DG645"
    db.add_device(dev_info)
    db.put_device_property(
        dev_info.name,
        {
            "device_id": "DG645",
            "server_id": 1,
            "friendly_name": "DG645 digital delay generator",
            "resource": "",
            "host": "",
            "port": 5025,
            "interface_type": "",
            "serial_baud_rate": 9600,
            "driver_backend": "auto",
            "timeout_ms": 2000,
            "always_on": 1,
        },
    )
    print("Registered device : manip/sync/DG645")
    print("Server instance   : DS_DG645/1_DG645")
    print("Set either 'resource' or 'host' property before starting hardware.")


if __name__ == "__main__":
    main()
