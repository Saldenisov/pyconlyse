from time import sleep
from typing import Dict
from devices.devices import Device


def start_devices(devices: Dict[str, Device]):
    for device_name, device in devices.items():
        device.start()
        sleep(0.3)


def stop_devices(devices: Dict[str, Device]):
    for device_name, device in devices.items():
        device.stop()