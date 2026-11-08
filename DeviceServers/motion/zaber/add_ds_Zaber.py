"""Register the VD2 Zaber stage on Elysium2 in the Tango database."""

import argparse
import socket

from tango import Database, DbDevInfo, DbServerInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-name", default="manip/VD2/Zaber")
    parser.add_argument("--instance", default="1_Zaber")
    parser.add_argument("--host", default=socket.getfqdn())
    parser.add_argument("--port", default="COM1")
    parser.add_argument("--baud-rate", type=int, default=9600)
    args = parser.parse_args()

    db = Database()
    info = DbDevInfo()
    info.name = args.device_name
    info._class = "DS_Zaber"
    info.server = "DS_Zaber/{}".format(args.instance)
    db.add_device(info)

    server = DbServerInfo()
    server.name = info.server
    server.host = args.host
    server.mode = 1
    server.level = 1
    db.put_server_info(server)
    db.put_device_property(
        info.name,
        {
            "port": args.port,
            "baud_rate": args.baud_rate,
            "address": 1,
            "motion_timeout_s": 120.0,
            "reconnect_interval_s": 5.0,
            "power_dependency_device": "manip/VD2/PDU_VD2",
            "power_dependency_output_id": 3,
        },
    )
    print("Registered {} on {} at {}:9600".format(info.name, args.host, args.port))


if __name__ == "__main__":
    main()
