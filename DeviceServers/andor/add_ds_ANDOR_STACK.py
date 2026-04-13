from tango import Database, DbDevInfo

db = Database()


CCD_DEVICE = {
    "device_name": "manip/CR/ANDOR_CCD1",
    "class_name": "DS_ANDOR_CCD",
    "server_instance": "1_ANDOR_CCD1",
    "device_id": "andor_newton_1",
    "friendly_name": "ANDOR Newton CCD",
    "server_id": 1,
    "properties": {
        "dll_path": r"C:\Andor SDK",
        "ini_path": r"C:\Andor SDK",
        "camera_index": 0,
        "width": 1064,
        "wavelengths": "[]",
        "fan_mode": "off",
        "default_temperature": -50,
        "linked_spectrograph_ds": "manip/CR/ANDOR_SHAMROCK1",
        "start_grabbing_on_init": 0,
        "parameters": str(
            {
                "Acquisition_Controls": {
                    "AcquisitionMode": 5,
                    "TriggerMode": 1,
                    "ReadMode": 1,
                    "MultiTrack": (2, 128, 0),
                    "ExposureTime": 0.0001,
                    "HSSpeed": (0, 0),
                    "VSSpeed": 0,
                    "ADChannel": 0,
                    "PreAmpGain": 0,
                    "Temperature": -50,
                    "Cooler": True,
                }
            }
        ),
    },
}


SPECTROGRAPH_DEVICES = [
    {
        "device_name": "manip/CR/ANDOR_SHAMROCK1",
        "class_name": "DS_ANDOR_SPECTROGRAPH",
        "server_instance": "1_ANDOR_SHAMROCK1",
        "device_id": "andor_shamrock_1",
        "friendly_name": "ANDOR Shamrock",
        "server_id": 1,
        "properties": {
            "dll_path": r"C:\Andor SDK",
            "shamrock_dll_path": r"C:\Andor SDK\Shamrock",
            "spectrograph_index": 0,
            "pixel_number": 1064,
            "pixel_width_um": 13.5,
            "linked_camera_ds": "manip/CR/ANDOR_CCD1",
            "start_on_init": 1,
        },
    },
    {
        "device_name": "manip/CR/ANDOR_KYMERA1",
        "class_name": "DS_ANDOR_SPECTROGRAPH",
        "server_instance": "2_ANDOR_KYMERA1",
        "device_id": "andor_kymera_1",
        "friendly_name": "ANDOR Kymera 328i",
        "server_id": 2,
        "properties": {
            "dll_path": r"C:\Andor SDK",
            "shamrock_dll_path": r"C:\Andor SDK\Shamrock",
            "spectrograph_index": 1,
            "pixel_number": 1064,
            "pixel_width_um": 13.5,
            "linked_camera_ds": "manip/CR/ANDOR_CCD1",
            "start_on_init": 1,
        },
    },
]


def upsert_device(device_config):
    dev_info = DbDevInfo()
    dev_info.name = device_config["device_name"]
    dev_info._class = device_config["class_name"]
    dev_info.server = (
        f"{device_config['class_name']}/{device_config['server_instance']}"
    )

    try:
        db.add_device(dev_info)
        print(f"Added device: {dev_info.name}")
    except Exception as exc:
        print(f"add_device warning for {dev_info.name}: {exc}")

    properties = {
        "device_id": device_config["device_id"],
        "friendly_name": device_config["friendly_name"],
        "server_id": device_config["server_id"],
    }
    properties.update(device_config["properties"])

    normalized = {key: [str(value)] for key, value in properties.items()}
    db.put_device_property(device_config["device_name"], normalized)
    print(f"Updated properties: {device_config['device_name']}")


def main():
    upsert_device(CCD_DEVICE)
    for spectrograph in SPECTROGRAPH_DEVICES:
        upsert_device(spectrograph)


if __name__ == "__main__":
    main()
