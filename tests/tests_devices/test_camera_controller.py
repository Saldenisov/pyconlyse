from devices.service_devices.cameras import *
from tests.fixtures.services import *
from devices.service_devices.cameras.camera_dataclass import *
from devices.service_devices.cameras.camera_dataclass import FuncGetImagesInput

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
    SET_TRANSPORT_LAYER = FuncSetTransportParametersInput(1, 1500, 1000)
    SET_SYNC_PARAM = FuncSetSyncParametersInput(1, 9999, False, 189999, 20)
    SET_IMAGE_PARAM = FuncSetImageParametersInput(1, 546, 550, 0, 0, 'Off', 0, -30, 64, 'Mono8')
    GET_IMAGE = FuncGetImagesInput(1, '', 1, True, '', {}, 0)
    GET_IMAGES = FuncGetImagesInput(1, '', 1, True, '', {}, 0)

    # description
    res: ServiceDescription = cameractrl.description()
    assert res.info == 'Basler cameras controller'

    # power on
    res: FuncPowerOutput = cameractrl.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.controller_status.power
    # activate controller
    res: FuncActivateOutput = cameractrl.activate(ACTIVATE)
    assert res.func_success
    assert res.controller_status.active
    # deactivate controller
    res: FuncActivateOutput = cameractrl.activate(DEACTIVATE)
    assert res.func_success
    assert not res.controller_status.active
    # activate controller
    res: FuncActivateOutput = cameractrl.activate(ACTIVATE)
    assert res.func_success
    assert res.controller_status.active
    # turn on first camera
    res: FuncActivateDeviceOutput = cameractrl.activate_camera(ACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 1
    assert res.cameras[1].friendly_name == 'Camera1LaserSpot'
    # turn off first camera
    res: FuncActivateDeviceOutput = cameractrl.activate_camera(DEACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 0
    # turn on first camera
    res: FuncActivateDeviceOutput = cameractrl.activate_camera(ACTIVATE_CAMERA_ONE)
    assert res.func_success
    assert res.cameras[1].status == 1
    # set transport settings for camera 1
    assert cameractrl.cameras[1].parameters['Transport_Layer'].GevSCPSPacketSize == 1500
    res: FuncSetTransportParametersOutput = cameractrl.set_transport_parameters(SET_TRANSPORT_LAYER)
    assert res.func_success
    assert res.camera.parameters['Transport_Layer'].GevSCPSPacketSize == 1500
    # set sync settings for camera 1
    assert cameractrl.cameras[1].parameters['Acquisition_Controls'].TriggerDelayAbs == 189000
    res: FuncSetSyncParametersOutput = cameractrl.set_sync_parameters(SET_SYNC_PARAM)
    assert res.func_success
    assert res.camera.parameters['Acquisition_Controls'].TriggerDelayAbs == 189999
    # set image settings for camera 1
    assert cameractrl.cameras[1].parameters['AOI_Controls'].Width == 550
    res: FuncSetImageParametersOutput = cameractrl.set_image_parameters(SET_IMAGE_PARAM)
    assert res.func_success
    assert res.camera.parameters['AOI_Controls'].Width == 546
    # test GET_IMAGES
    res: FuncGetImagesPrepared = cameractrl.get_images(GET_IMAGE)
    assert cameractrl._last_image == None
    assert len(cameractrl._images_demanders) == 1
    assert res.func_success
    assert res.camera.status == 2
    sleep(0.5)
    assert len(cameractrl._images_demanders) == 0
    assert cameractrl._last_image.shape == (550, 546)
    cameractrl.stop()

#test_func_stpmtr(one_service[0])
