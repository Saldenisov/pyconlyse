from pathlib import Path

import pytest

from devices.devices import DeviceFactory
from devices.devices import Server

app_folder = str(Path(__file__).resolve().parents[2])


@pytest.fixture
def server(device_id="Server:Main:sfqvtyjsdf23qa23xcv", db_name='Devices.db') -> Server:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name))

@pytest.fixture
def server_test(device_id="Server:Main:sfqvtyjsdf23qa23xcv", db_name='Devices.db') -> Server:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name), test=True)


def server_test_non_fixture(device_id="Server:Main:sfqvtyjsdf23qa23xcv", db_name='Devices.db') -> Server:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name), test=True)