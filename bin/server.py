"""Hardware server_p programm is tests_hardware CUI.
It allows to control multiple devices from GUI client applications

sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
17/01/2019"""


from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]

import devices.devices as dev

def init():
    server = dev.DeviceFactory.make_device(cls=dev.Server,
                                           name='Server',
                                           db_path=Path(app_folder / 'DB' / 'Devices.db'))
    server.start()


if __name__ == "__main__":
    init()



