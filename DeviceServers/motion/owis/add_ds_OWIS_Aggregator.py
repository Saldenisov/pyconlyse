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
            "gear_ratio": 1.0,
            "pitch": 1.0,
            "speed": 5.0,
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
            "revolution": 200.0,
            "limit_min": -900.0,
            "limit_max": 100.0,
            "real_pos": -100.0,
            "wait_time": 5,
            "preset_positions": [0.0, 75.0, -100.0, -800.0],
            "relative_shift": 1.0,
        },
        4: {
            "device_name": "manip/V0/DLl2_V0",
            "friendly_name": "Delay line for OPA",
            "drive_current": 2.5,
            "hold_current": 0.5,
            "keep_on": True,
            "gear_ratio": 1.0,
            "pitch": 5.0,
            "speed": 30.0,
            "revolution": 200,
            "limit_min": -900.0,
            "limit_max": 100.0,
            "real_pos": -100.0,
            "wait_time": 5,
            "preset_positions": [0, 75.0, -100.0, -250.0, -500.0, -800.0],
            "relative_shift": 1.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register DS_OWIS_Aggregator — unified 4-axis OWIS proxy DS."
    )
    parser.add_argument("--device-name", default="manip/general/DS_OWIS_Aggregator")
    parser.add_argument("--instance", default="AGG")
    parser.add_argument("--server-id", default="9")
    parser.add_argument("--device-id", default="9")
    parser.add_argument("--friendly-name", default="OWIS Aggregator")
    parser.add_argument("--backend-3axes", default="manip/general/DS_OWIS_PS90_IP")
    parser.add_argument("--backend-axis4", default="manip/general/DS_OWIS_PS90")
    parser.add_argument("--reconnect-interval", type=float, default=5.0)
    parser.add_argument("--backend-timeout-ms", type=int, default=3000)
    args = parser.parse_args()

    db = Database()

    dev_info = DbDevInfo()
    dev_info.name = args.device_name
    dev_info._class = "DS_OWIS_Aggregator"
    dev_info.server = f"DS_OWIS_Aggregator/{args.instance}"
    db.add_device(dev_info)

    properties = {
        "device_id": args.device_id,
        "server_id": args.server_id,
        "friendly_name": args.friendly_name,
        "backend_three_axes_device": args.backend_3axes,
        "backend_fourth_axis_device": args.backend_axis4,
        "reconnect_interval_seconds": args.reconnect_interval,
        "backend_timeout_ms": args.backend_timeout_ms,
        "delay_lines_parameters": str(_delay_lines()),
        "always_on": 1,
    }
    db.put_device_property(args.device_name, properties)

    print(f"Registered device : {args.device_name}")
    print(f"Server instance   : DS_OWIS_Aggregator/{args.instance}")
    print(f"Backend 1..3      : {args.backend_3axes}")
    print(f"Backend 4         : {args.backend_axis4}")


if __name__ == "__main__":
    main()
