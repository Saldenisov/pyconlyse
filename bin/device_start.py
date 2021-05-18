"""
05/05/2019
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
"""

import sys
from pathlib import Path
app_folder = str(Path(__file__).resolve().parents[1])
sys.path.append(app_folder)
from devices.devices import DeviceFactory
from logs_pack import initialize_logger



def init(device_id: str, db_name: str, test=False):
    device = DeviceFactory.make_device(device_id=device_id,
                                        db_path=Path(Path(app_folder) / 'utilities' / 'database' / db_name))

    device.start()


if __name__ == "__main__":
    """
    python device_start.py -id StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd -db Devices.db
    python device_start.py -s stpmtr_standa cameras_basler
    """
    preselection = {'server_main': ['Server:Main:sfqvtyjsdf23qa23xcv', 'Devices.db'],
                    'server_test': ['ServerTEST:Main:sfqvtyjsdf23qa23xcv', 'Devices.db'],
                    'stpmtr_a4988': ['StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b', 'Devices.db'],
                    'stpmtr_emulate': ['StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', 'Devices.db'],
                    'project_default': ['ProjectManager_default:2d23d885d1c63ab03166ffa858b90ada', 'Devices.db'],
                    'stpmtr_standa': ['StpMtrCtrl_Standa:b7257a502aef1d55485fc8ea403ac573', 'Devices.db'],
                    'stpmtr_topdirect': ['StpMtrCtrl_TopDirect_1axis:c1371a888f2e7490fd3ec04363b1e79c', 'Devices.db'],
                    'stpmtr_owis': ['StpMtrCtrl_OWIS:b161e87bee35bc4160f2dfeef63ef058', 'Devices.db'],
                    'cameras_basler': ['CameraCtrl_Basler:042c2cfbadef3d2e2c42e87e3dd32e02', 'Devices.db'],
                    'pdus_netio': ['PDUCtrl_NETIO:deeb24a77539736744b550885fb6ba4f', 'Devices.db'],
                    'daqmx_ni': ['DAQmxCtrl_NI:0801d25ef5783deff0cf99d321674115', 'Devices.db']}

    def respond_direct_choice(test=False):
        try:
            device_id_idx = sys.argv.index('-id') + 1
            device_id = sys.argv[device_id_idx]
            db_idx = sys.argv.index('-db') + 1
            db = sys.argv[db_idx]
            device_id = device_id
            db = db
            init(device_id=device_id, db_name=db, test=test)
        except (KeyError, IndexError):
            raise Exception('Not enough arguments were passed')

    def respond_selection(test=False):
        try:
            selections = sys.argv[sys.argv.index('-s') + 1:]
            for device_name in selections:
                if device_name != '-test':
                    device_id = preselection[device_name][0]
                    db = preselection[device_name][1]
                    init(device_id=device_id, db_name=db, test=test)
        except (KeyError, IndexError) as e:
            raise Exception(f'{e}')

    if '-id' in sys.argv and '-db' in sys.argv:
        test = False
        if '-test' in sys.argv:
            test = True
        respond_direct_choice(test)
    elif '-s' in sys.argv and '-test' not in sys.argv:
        respond_selection()
    elif '-s' in sys.argv and '-test' in sys.argv:
        respond_selection(test=True)
    else:
        raise Exception('Check the arguments that were passed.')
