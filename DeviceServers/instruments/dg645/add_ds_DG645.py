import argparse
import socket

from tango import Database, DbDevInfo, DbServerInfo


def main():
    parser = argparse.ArgumentParser(description="Register the SRS DG645 Tango device")
    parser.add_argument("--device-name", default="manip/sync/DG645")
    parser.add_argument("--instance", default="1_DG645")
    parser.add_argument("--host", default="10.20.30.131")
    parser.add_argument("--port", type=int, default=5025)
    args = parser.parse_args()

    db = Database()

    dev_info = DbDevInfo()
    dev_info.name = args.device_name
    dev_info._class = "DS_DG645"
    dev_info.server = f"DS_DG645/{args.instance}"
    db.add_device(dev_info)

    server_info = DbServerInfo()
    server_info.name = dev_info.server
    server_info.host = socket.getfqdn()
    server_info.mode = 1
    server_info.level = 1
    db.put_server_info(server_info)
    db.put_device_property(
        dev_info.name,
        {
            "device_id": "DG645",
            "server_id": 1,
            "friendly_name": "DG645 digital delay generator",
            "resource": "",
            "host": args.host,
            "port": args.port,
            "interface_type": "tcpip",
            "serial_baud_rate": 9600,
            "driver_backend": "srsinst",
            "timeout_ms": 2000,
            "always_on": 1,
            "power_dependency_device": "manip/SD2/PDU_SD2",
            "power_dependency_output_id": 2,
            "power_on_settle_seconds": 5.0,
        },
    )
    print(f"Registered device : {dev_info.name}")
    print(f"Server instance   : {dev_info.server}")
    print(f"Transport         : tcpip://{args.host}:{args.port}")


if __name__ == "__main__":
    main()
