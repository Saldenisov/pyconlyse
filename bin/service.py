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


def init(device_id: str, db_name: str):
    service = DeviceFactory.make_device(device_id=device_id,
                                        db_path=Path(Path(app_folder) / 'DB' / db_name))

    service.start()


if __name__ == "__main__":
    """
    python service.py -id StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b -db Devices.db 
    """
    preselection = {'newport_4axes': ['StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b', 'Devices.db'],
                    'stpmtr_emulate': ['StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', 'Devices.db']}

    if '-id' in sys.argv and '-db' in sys.argv:
        try:
            device_id_idx = sys.argv.index('-id') + 1
            device_id = sys.argv[device_id_idx]
            db_idx = sys.argv.index('-db') + 1
            db = sys.argv[db_idx]
            device_id = device_id
            db = db

        except (KeyError, IndexError):
            raise Exception('Not enough arguments were passed')
    elif '-s' in sys.argv:
        try:
            selection_idx = sys.argv.index('-s') + 1
            selection = sys.argv[selection_idx]
            device_id = preselection[selection][0]
            db = preselection[selection][1]
        except (KeyError, IndexError):
            raise Exception('Not enough arguments were passed')
    else:
        raise Exception('Not enough arguments were passed')

    init(device_id=device_id, db_name=db)


