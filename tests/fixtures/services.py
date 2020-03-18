from pathlib import Path
from devices.devices import DeviceFactory
from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
import pytest

app_folder = str(Path(__file__).resolve().parents[2])


@pytest.fixture
def stpmtr_emulate(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', db_name='Devices.db') -> \
        StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'DB' / db_name))

