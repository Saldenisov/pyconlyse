from tango import Database, DbDevInfo

db = Database()

# namespace, friendly_name, name for tango, keep_on parameter, gear_ration,

delay_lines = {
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
names_param = {
    "1": [
        "manip/general/DS_OWIS_PS90",
        {
            "baudrate": 115200,  # Use 115200 for fast, reliable communication
            "com_port": 7,
            "interface": 0,
            "control_unit_id": 1,
            "friendly_name": "DS_OWIS_PS90",
            "serial_number": 15110070,
            "transport": "dll",
            "allow_high_current_level": True,
            "dll_path": "C:/dev/pyconlyse/DeviceServers/motion/owis/drivers/ps90_64.dll",
            "delay_lines_parameters": str(delay_lines),
            "max_retries": 3,  # Retry up to 3 times on communication errors
            "retry_delay": 1.0,  # Wait 1 second between retries
        },
    ]
}


def main():
    i = 1
    for dev_id, val in names_param.items():
        dev_info = DbDevInfo()
        dev_info.name = val[0]
        dev_info._class = "DS_OWIS_PS90"
        dev_info.server = f"DS_OWIS_PS90/{i}"
        db.add_device(dev_info)
        param = val[1]
        param["device_id"] = dev_id
        param["server_id"] = i
        db.put_device_property(val[0], param)
        i += 1


if __name__ == "__main__":
    main()
