from pathlib import Path

import pytest

from devices.devices import DeviceFactory
from devices.virtual_devices.clients import SuperUser

app_folder = str(Path(__file__).resolve().parents[2])


@pytest.fixture
def superuser(device_id='SuperUser:37cc841a6f8f907deaa49f117aa1a2f9', db_name='Devices.db') -> SuperUser:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name))


@pytest.fixture
def superuser_test(device_id='SuperUser:37cc841a6f8f907deaa49f117aa1a2f9', db_name='Devices.db') -> SuperUser:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name), test=True)