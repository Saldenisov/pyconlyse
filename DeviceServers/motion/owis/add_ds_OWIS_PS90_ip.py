from __future__ import annotations

import argparse

from tango import Database, DbDevInfo


def _delay_lines() -> dict[int, dict]:
    return {
        1: {
            "device_name": "manip/V0/DLs_V0",
            "friendly_name": "Sample holder V0",
            "drive_current": 2.5,
            "hold_current": 0.5,
            "keep_on": False,
            "gear_ratio": 1,
            "pitch": 1.0,
            "speed": 5.0,
            "acceleration": 4000,
            "revolution": 200.0,
            "limit_min": -13.0,
            "limit_max": 150.0,
            "real_pos": 30.0,
            "wait_time": 5,
            "preset_positions": [155.0, 125.1, 101.8, 70.5, 46.8, 23.3, 0.0, 90.0],
            "relative_shift": 1.0,
        },
        2: {
            "device_name": "manip/VD2/DLs_VD2",
            "friendly_name": "Sample holder VD2",
            "drive_current": 2.75,
            "hold_current": 0.4,
            "keep_on": False,
            "gear_ratio": 1,
            "pitch": 1,
            "speed": 3.5,
            "acceleration": 4000,
            "revolution": 200,
            "limit_min": -40.0,
            "limit_max": 260.0,
            "real_pos": 30.0,
            "wait_time": 5,
            "preset_positions": [0, 12.9, 24.8, 38.7, 51.6, 83.0],
            "relative_shift": 1.0,
        },
        3: {
            "device_name": "manip/V0/DLl1_V0",
            "friendly_name": "Delay line long",
            "drive_current": 2.5,
            "hold_current": 0.5,
            "keep_on": True,
            "gear_ratio": 1,
            "pitch": 5.0,
            "speed": 15.0,
            "acceleration": 4000,
            "revolution": 200.0,
            "limit_min": -900.0,
            "limit_max": 100.0,
            "real_pos": -100.0,
            "wait_time": 5,
            "preset_positions": [0.0, 75.0, -100.0, -800.0],
            "relative_shift": 1.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register DS_OWIS_PS90_IP — OWIS PS90 Tango DS over direct TCP/IP."
    )
    parser.add_argument("--device-name", default="manip/general/DS_OWIS_PS90_IP")
    parser.add_argument("--instance", default="2_IP")
    parser.add_argument("--server-id", default="3")
    parser.add_argument("--device-id", default="3")
    parser.add_argument("--friendly-name", default="DS_OWIS_PS90_IP")
    parser.add_argument("--controller-ip", default="10.20.30.134")
    parser.add_argument("--controller-port", type=int, default=8777)
    parser.add_argument("--serial-number", type=int, default=25010013)
    parser.add_argument(
        "--power-pdu-device",
        default="manip/V0/PDU_VO",
        help="Read-only Tango PDU dependency for the controller supply.",
    )
    parser.add_argument(
        "--power-pdu-output-id",
        type=int,
        default=2,
        help="PDU output ID which supplies the OWIS delay-line controller.",
    )
    args = parser.parse_args()

    db = Database()

    dev_info = DbDevInfo()
    dev_info.name = args.device_name
    dev_info._class = "DS_OWIS_PS90"
    dev_info.server = f"DS_OWIS_PS90/{args.instance}"
    db.add_device(dev_info)

    properties = {
        "device_id": args.device_id,
        "server_id": args.server_id,
        "friendly_name": args.friendly_name,
        "serial_number": args.serial_number,
        "control_unit_id": 2,
        "interface": 0,
        "com_port": -1,
        "baudrate": 115200,
        "transport": "tcp",
        "controller_ip": args.controller_ip,
        "controller_port": args.controller_port,
        "allow_high_current_level": False,
        "ovis_tcp_strict_init_profile": True,
        "ovis_tcp_current_level": 0,
        "ovis_tcp_hold_current_percent": 38,
        "ovis_tcp_drive_current_percent": 50,
        "ovis_tcp_init_ready_timeout": 6.0,
        "ovis_tcp_init_poll_interval": 0.05,
        "ovis_tcp_keep_motor_on": True,
        "power_dependency_device": args.power_pdu_device,
        "power_dependency_output_id": args.power_pdu_output_id,
        "delay_lines_parameters": str(_delay_lines()),
        "max_retries": 3,
        "retry_delay": 1.0,
    }
    db.put_device_property(args.device_name, properties)

    print(f"Registered device : {args.device_name}")
    print(f"Server instance   : DS_OWIS_PS90/{args.instance}")
    print(f"Controller        : {args.controller_ip}:{args.controller_port}")
    print("Transport         : tcp (direct socket, no DLL)")


if __name__ == "__main__":
    main()
