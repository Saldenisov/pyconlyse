from pathlib import Path
from devices.devices import DeviceFactory
from devices.service_devices.stepmotors import StpMtrCtrl_emulate, StpMtrCtrl_a4988_4axes
from devices.service_devices.project_treatment import ProjectManager_controller
import pytest

app_folder = str(Path(__file__).resolve().parents[2])


# Stepmotors
@pytest.fixture
def stpmtr_emulate(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', db_name='Devices.db') -> \
        StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name))


def stpmtr_emulate_test_non_fixture(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd',
                                    db_name='Devices.db') -> StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)


@pytest.fixture
def stpmtr_emulate_test(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', db_name='Devices.db') -> \
        StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)


@pytest.fixture
def stpmtr_a4988_4axes_test(device_id='StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b',
                            db_name='Devices.db') -> StpMtrCtrl_a4988_4axes:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)


def stpmtr_a4988_4axes_test_non_fixture(device_id='StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b',
                                        db_name='Devices.db') -> StpMtrCtrl_a4988_4axes:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)


# Project managers
@pytest.fixture
def projectmanager(device_id='ProjectManager_controller:2d23d885d1c63ab03166ffa858b90ada',
                                db_name='Devices.db') -> ProjectManager_controller:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)


def projectmanager_non_fixture(device_id='ProjectManager_controller:2d23d885d1c63ab03166ffa858b90ada',
                                db_name='Devices.db') -> ProjectManager_controller:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'database' / db_name), test=True)