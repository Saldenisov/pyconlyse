"""
Created on 16.07.2020

@author: saldenisov
"""
import copy
import logging
from _functools import partial

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage

from communication.messaging.messages import MsgComExt, MsgComInt, MessageInt
from devices.devices import Device
from devices.service_devices.cameras import CameraController
from gui.views.ui import Ui_CameraGUI
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.myfunc import info_msg, get_local_ip, error_logger

module_logger = logging.getLogger(__name__)


class CamerasView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: DeviceInfoExt, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.controller_status = CamerasCtrlStatusMultiCameras(cameras=service_parameters.device_description.cameras,
                                                               device_status=service_parameters.device_status)

        self.name = f'CamerasClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("Cameras." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: DeviceInfoExt = service_parameters

        self.ui = Ui_CameraGUI()
        self.ui.setupUi(CameraGUI=self, service_parameters=service_parameters)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)

        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.checkBox_activate.clicked.connect(self.activate_controller)

        self.update_state(force_camera=True)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                       func_input=FuncGetCameraControllerStateInput())
        self.device.send_msg_externally(msg)
        info_msg(self, 'INITIALIZED')

    def activate_controller(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def activate_camera(self):
        flag = 1 if self.ui.checkBox_On.isChecked() else 0
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncActivateCameraInput(axis_id=int(self.ui.spinBox_axis.value()),
                                                                     flag=flag))
        client.send_msg_externally(msg)

        self._asked_status = 0

    @property
    def controller_cameras(self):
        return self.controller_status.cameras

    @controller_cameras.setter
    def controller_cameras(self, value: Union[Dict[int, CameraEssentials], Dict[int, Camera]]):
        try:
            if type(next(iter(value.values()))) == Camera:
                self.controller_status.cameras = value
            else:
                for camera_id, camera in value.items():
                    self.controller_status.cameras[camera_id].status = camera.status
        except Exception as e:
            error_logger(self, self.controller_axes, e)

    def model_is_changed(self, msg: MessageInt):
        try:
            if self.service_parameters.device_id == msg.forwarded_from or \
                    self.service_parameters.device_id == msg.sender_id:
                com = msg.com
                info: Union[DoneIt, MsgError] = msg.info
                if com == MsgComInt.DONE_IT.msg_name:
                    result: Union[FuncActivateOutput,
                                  FuncPowerOutput] = info
                    self.ui.textEdit_comments.setText(result.comments)
                    if info.com == CameraController.ACTIVATE.name:
                        result: FuncActivateOutput = result
                        if result.device_status.active:
                            client = self.device
                            msg = client.generate_msg(msg_com=MsgComExt.DO_IT,
                                                      receiver_id=self.service_parameters.device_id,
                                                      func_input=FuncGetCameraControllerStateInput())
                            client.send_msg_externally(msg)
                        self.controller_status.device_status = result.device_status
                    elif info.com == CameraController.ACTIVATE_CAMERA.name:
                        result: FuncActivateCameraOutput = result
                        self.controller_cameras = result.cameras
                    elif info.com == CameraController.GET_CONTROLLER_STATE.name:
                        result: FuncGetCameraControllerStateOutput = result
                        self.controller_cameras = result.cameras
                        self.controller_status.device_status = result.device_status
                    elif info.com == CameraController.POWER.name:
                        result: FuncPowerOutput = result
                        self.controller_status.device_status = result.device_status

                elif com == MsgComInt.ERROR.msg_name:
                    self.ui.textEdit_comments.setText(info.comments)
                    client = self.device
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                              func_input=FuncGetCameraControllerStateInput())
                    client.send_msg_externally(msg)

                self.update_state()
        except Exception as e:
            error_logger(self, self.model_is_changed, f'Error:"{e}". Msg={msg}')

    def power(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncPowerInput(flag=self.ui.checkBox_power.isChecked()))
        client.send_msg_externally(msg)

    def update_state(self, force_camera=False, force_device=False):
        cs = self.controller_status
        ui = self.ui

        if cs.cameras != cs.cameras_previous or force_camera:
            camera_ids = list(cs.cameras)
            ui.spinBox_cameraID.setMinimum(min(camera_ids))
            ui.spinBox_cameraID.setMaximum(max(camera_ids))
            if ui.spinBox_cameraID.value() not in camera_ids:
                ui.spinBox_cameraID.setValue(min(camera_ids))
            camera_id = int(ui.spinBox_cameraID.value())

            camera: CameraEssentials = cs.cameras[camera_id]
            ui.checkBox_On.setChecked(camera.status)
            _translate = QtCore.QCoreApplication.translate
            if camera.friendly_name != '':
                name = camera.friendly_name
            else:
                name = camera.name

            ui.label_name.setText(_translate("CameraGUI", name))

            if force_camera:
                pass

            self.controller_status.cameras_previous = copy.deepcopy(cs.cameras)