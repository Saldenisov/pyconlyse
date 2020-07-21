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
                                        db_path=Path(Path(app_folder) / 'utilities' / 'database' / db_name))

    service.start()


if __name__ == "__main__":
    """
    python device_start.py -id StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd -db Devices.db
    python device_start.py -s newport_4axes stpmtr_emulate
    """
    preselection = {'server_main': ['Server:Main:sfqvtyjsdf23qa23xcv', 'Devices.db'],
                    'a4988_4axes': ['StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b', 'Devices.db'],
                    'stpmtr_emulate': ['StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', 'Devices.db'],
                    'owis_3axes': ['StpMtrCtrl_OWIS:b161e87bee35bc4160f2dfeef63ef058', 'Devices.db'],
                    'project_default': ['ProjectManager_default:2d23d885d1c63ab03166ffa858b90ada', 'Devices.db'],
                    'stpmtr_standa': ['StpMtrCtrl_Standa:b7257a502aef1d55485fc8ea403ac573', 'Devices.db'],
                    'topdirect': ['StpMtrCtrl_TopDirect_1axis:c1371a888f2e7490fd3ec04363b1e79c', 'Devices.db'],
                    'basler_cameras': ['CameraCtrl_Basler:042c2cfbadef3d2e2c42e87e3dd32e02', 'Devices.db']}

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
            selections = sys.argv[sys.argv.index('-s')+1:]
            for device_name in selections:
                device_id = preselection[device_name][0]
                db = preselection[device_name][1]
                init(device_id=device_id, db_name=db)
        except (KeyError, IndexError):
            raise Exception('Not enough arguments were passed')
    else:
        raise Exception('Not enough arguments were passed')




