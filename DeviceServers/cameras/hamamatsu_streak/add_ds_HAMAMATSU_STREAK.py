from tango import Database, DbDevInfo

db = Database()


names = {
    "hamamatsu_streak_main": {
        "device_name": "manip/camera/hamamatsu_streak_main",
        "friendly_name": "Hamamatsu_Streak_Main",
        "host": "localhost",
        "command_port": 1001,
        "data_port": 1002,
        "ini_path": r"C:\ProgramData\Hamamatsu\HPDTA\HPDTA8.INI",
        "default_save_dir": r"C:\Data\Hamamatsu",
        "command_timeout_s": 5.0,
        "async_timeout_s": 120.0,
        "command_encoding": "ascii",
        "connect_data_port": 0,
        "start_application_on_turn_on": 1,
        "start_on_init": 0,
    }
}


def main():
    for index, (device_id, config) in enumerate(names.items(), start=1):
        dev_info = DbDevInfo()
        dev_info.name = config["device_name"]
        dev_info._class = "DS_HAMAMATSU_STREAK"
        dev_info.server = f"DS_HAMAMATSU_STREAK/{index}_{device_id}"
        db.add_device(dev_info)
        db.put_device_property(
            config["device_name"],
            {
                "device_id": device_id,
                "friendly_name": config["friendly_name"],
                "server_id": index,
                "host": config["host"],
                "command_port": config["command_port"],
                "data_port": config["data_port"],
                "ini_path": config["ini_path"],
                "default_save_dir": config["default_save_dir"],
                "command_timeout_s": config["command_timeout_s"],
                "async_timeout_s": config["async_timeout_s"],
                "command_encoding": config["command_encoding"],
                "connect_data_port": config["connect_data_port"],
                "start_application_on_turn_on": config["start_application_on_turn_on"],
                "start_on_init": config["start_on_init"],
            },
        )


if __name__ == "__main__":
    main()
