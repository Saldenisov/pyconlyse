from tango import Database, DbDevInfo

if __package__:
    from .avantes_ccd_wavelengths_1 import WAVELENGTHS_1
    from .avantes_ccd_wavelengths_2 import WAVELENGTHS_2
else:
    from avantes_ccd_wavelengths_1 import WAVELENGTHS_1
    from avantes_ccd_wavelengths_2 import WAVELENGTHS_2


db = Database()

names = {
    "1810225U1": [
        "manip/CR",
        "AVANTES_CCD1",
        "AVANTES_CCD1",
        "1810225U1",
        {
            "Acquisition_Controls": {
                "TriggerMode": 2,
                "TriggerSource": 0,
                "TriggerType": 0,
                "IntegrationTime": 100,
                "IntegrationDelay": 0,
                "BGLevel": 7000,
            },
            "Connection": -1,
        },
        {
            "width": 2068,
            "wavelengths": WAVELENGTHS_1,
            "arduino_sync": "10.20.30.47",
        },
        "C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll",
    ],
    "1810226U1": [
        "manip/CR",
        "AVANTES_CCD2",
        "AVANTES_CCD2",
        "1810226U1",
        {
            "Acquisition_Controls": {
                "TriggerMode": 2,
                "TriggerSource": 0,
                "TriggerType": 0,
                "IntegrationTime": 100,
                "IntegrationDelay": 0,
                "BGLevel": 7000,
            },
            "Connection": -1,
        },
        {
            "width": 2068,
            "wavelengths": WAVELENGTHS_2,
            "arduino_sync": "10.20.30.47",
        },
        "C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll",
    ],
}


def main():
    i = 1
    for dev_id, val in names.items():
        dev_info = DbDevInfo()
        dev_name = f"{val[0]}/{val[2]}"
        dev_info.name = dev_name
        dev_info._class = "DS_AVANTES_CCD"
        dev_info.server = f"DS_AVANTES_CCD/{i}_{val[2]}"
        db.add_device(dev_info)
        db.put_device_property(
            dev_name,
            {
                "device_id": dev_id,
                "friendly_name": val[1],
                "server_id": i,
                "serial_number": val[3],
                "parameters": str(val[4]),
                "width": val[5]["width"],
                "wavelengths": str(val[5]["wavelengths"]),
                "dll_path": val[6],
                "arduino_sync": str(val[5]["arduino_sync"]),
            },
        )
        i += 1


if __name__ == "__main__":
    main()
