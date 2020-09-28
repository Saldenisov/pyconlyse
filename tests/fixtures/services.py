from pathlib import Path

import pytest

from devices.devices import DeviceFactory
from devices.service_devices.project_treatment import ProjectManager_controller
from devices.service_devices.stepmotors import (StpMtrCtrl_emulate, StpMtrCtrl_a4988_4axes, StpMtrCtrl_TopDirect_1axis,
                                                StpMtrCtrl_Standa)
from devices.service_devices.cameras import CameraCtrl_Basler
from devices.service_devices.pdu import PDUCtrl_NETIO
from devices.service_devices.daqmx import DAQmxCtrl_NI

app_folder = str(Path(__file__).resolve().parents[2])


# Stepmotors
@pytest.fixture
def stpmtr_emulate(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', db_name='Devices.db') -> \
        StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name))


def stpmtr_emulate_test_non_fixture(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd',
                                    db_name='Devices.db') -> StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name), test=True)


@pytest.fixture
def stpmtr_emulate_test(device_id='StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd', db_name='Devices.db') -> \
        StpMtrCtrl_emulate:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database'
                                                                       / db_name), test=True)


@pytest.fixture
def stpmtr_a4988_4axes_test(device_id='StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b',
                            db_name='Devices.db') -> StpMtrCtrl_a4988_4axes:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


def stpmtr_a4988_4axes_test_non_fixture(device_id='StpMtrCtrl_a4988_4axes:2ecfc6712ca714be8b65f13dc490638b',
                                        db_name='Devices.db') -> StpMtrCtrl_a4988_4axes:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


def stpmtr_Standa_test_non_fixture(device_id='StpMtrCtrl_Standa:b7257a502aef1d55485fc8ea403ac573',
                                   db_name='Devices.db') -> StpMtrCtrl_a4988_4axes:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


def stpmtr_TopDirect_test_non_fixture(device_id='StpMtrCtrl_TopDirect_1axis:c1371a888f2e7490fd3ec04363b1e79c',
                                      db_name='Devices.db') -> StpMtrCtrl_TopDirect_1axis:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


# Project managers
@pytest.fixture
def projectmanager(device_id='ProjectManager_controller:2d23d885d1c63ab03166ffa858b90ada',
                                db_name='Devices.db') -> ProjectManager_controller:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


def projectmanager_default_non_fixture(device_id='ProjectManager_default:2d23d885d1c63ab03166ffa858b90ada',
                                       db_name='Devices.db') -> ProjectManager_controller:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


# Cameras
def camera_basler_test_non_fixture(device_id='CameraCtrl_Basler:042c2cfbadef3d2e2c42e87e3dd32e02',
                                   db_name='Devices.db') -> CameraCtrl_Basler:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


#PDUs
def pdu_netio_test_non_fixture(device_id='PDUCtrl_NETIO:deeb24a77539736744b550885fb6ba4f',
                               db_name='Devices.db') -> PDUCtrl_NETIO:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)


#DAQmx
def daqmx_ni_test_non_fixture(device_id='DAQmxCtrl_NI:0801d25ef5783deff0cf99d321674115',
                               db_name='Devices.db') -> PDUCtrl_NETIO:
    return DeviceFactory.make_device(device_id=device_id, db_path=Path(Path(app_folder) / 'utilities' / 'database' /
                                                                       db_name), test=True)