"""
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
05/05/2019
"""

import sys
from pathlib import Path
app_folder = str(Path(__file__).resolve().parents[1])
sys.path.append(app_folder)
from devices.devices import DeviceFactory


from devices.devices import DeviceFactory


def init(device_id: str, db_name: str):
    service = DeviceFactory.make_device(device_id=device_id,
                                        db_path=Path(Path(app_folder) / 'DB' / db_name))

    service.start()


if __name__ == "__main__":
    """
    python service.py b8b10026214c373bffe2b2847a9538dd Devices.db 
    """
    if len(sys.argv) >= 3:
        init(device_id=sys.argv[1], db_name=sys.argv[2])
    else:
        raise Exception('Not enough arguments were passed')



