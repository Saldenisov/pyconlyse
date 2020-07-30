import pytest

from devices.service_devices.cameras import *
from tests.fixtures.services import *
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *

one_service = [camera_basler_test_non_fixture()]
#all_services = []
test_param = one_service


@pytest.mark.parametrize('cameractrl', test_param)
def test_func_stpmtr(cameractrl: CameraController):
    cameractrl.start()

    ACTIVATE = FuncActivateInput(flag=True)
    DEACTIVATE = FuncActivateInput(flag=False)
    POWER_ON = FuncPowerInput(flag=True)
    POWER_OFF = FuncPowerInput(flag=False)
    ACTIVATE_CAMERA_ONE = FuncActivateCameraInput(1, 1)
    DEACTIVATE_CAMERA_ONE = FuncActivateCameraInput(1, 0)

    # description
    res: CameraDescription = cameractrl.description()
    assert res.info == 'Basler cameras controller'

    # power on
    res: FuncPowerOutput = cameractrl.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.device_status.power
    # activate controller
    res: FuncActivateOutput = cameractrl.activate(ACTIVATE)
    assert res.func_success
    assert res.device_status.active
    # deactivate controller
    res: FuncActivateOutput = cameractrl.activate(DEACTIVATE)
    assert res.func_success
    assert not res.device_status.active
    # activate controller
    res: FuncActivateOutput = cameractrl.activate(ACTIVATE)
    assert res.func_success
    assert res.device_status.active
    # turn on first camera
    res: FuncActivateCameraOutput = cameractrl.activate_camera(ACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 1
    assert res.cameras[1].friendly_name == 'Camera1LaserSpot'
    # turn off first camera
    res: FuncActivateCameraOutput = cameractrl.activate_camera(DEACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 0
    # turn on first camera
    res: FuncActivateCameraOutput = cameractrl.activate_camera(ACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 1


    cameractrl.stop()

#test_func_stpmtr(one_service[0])
