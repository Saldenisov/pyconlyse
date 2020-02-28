import sys
from pathlib import Path
app_folder = str(Path(__file__).resolve().parents[1])
sys.path.append(app_folder)

from devices.devices import DeviceFactory

device = DeviceFactory.make_device(device_id='StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b',
                                               db_path=Path(Path(app_folder) / 'DB' / 'Devices.db'))

device.activate(True)

device.activate_axis(axis_id=0, flag=1)