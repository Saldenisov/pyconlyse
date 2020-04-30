from pathlib import Path
from devices.devices import DeviceFactory
from devices.devices import Server
import pytest

app_folder = str(Path(__file__).resolve().parents[2])


@pytest.fixture
def server(device_id="Server:Main:sfqvtyjsdf23qa23xcv", db_name='Devices.db') -> Server:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name))

@pytest.fixture
def server_test(device_id="Server:Main:sfqvtyjsdf23qa23xcv", db_name='Devices.db') -> Server:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name),
                                     test=True)