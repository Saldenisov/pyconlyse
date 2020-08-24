"""
Created on 16.07.2020

@author: saldenisov
"""
import copy
import logging
import numpy as np
from _functools import partial
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage
from typing import Union
from communication.messaging.messages import MsgComExt, MsgComInt, MessageInt
from datetime import datetime

from gui.views.matplotlib_canvas.DataCanvasCamera import DataCanvasCamera
from devices.devices import Device
from devices.service_devices.cameras import CameraController
from gui.views.ui import Ui_CameraGUI
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.datastructures.mes_independent.measurments_dataclass import CameraReadings
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
        self.ui.setupUi(CameraGUI=self)
        self.ui.datacanvas = DataCanvasCamera(width=9, height=10, dpi=70, canvas_parent=self.ui.centralwidget)
        self.ui.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.ui.horizontalLayout_canvas.addWidget(self.ui.datacanvas)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)

        self.ui.checkBox_On.clicked.connect(self.activate_camera)
        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.checkBox_activate.clicked.connect(self.activate_controller)
        self.ui.spinBox_cameraID.valueChanged.connect(partial(self.update_state, *[True, False]))
        self.ui.pushButton_GetImage.clicked.connect(self.get_images)
        self.ui.pushButton_GetImages.clicked.connect(partial(self.get_images, True))
        self.ui.pushButton_stop.clicked.connect(self.stop_acquisition)
        self.ui.pushButton_GetImage.clicked.connect(partial(self.get_images, False))
        self.ui.pushButton_GetImages.clicked.connect(partial(self.get_images, True))

        self.update_state(force_camera=True, force_device=True)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.device.server_id,
                                       forward_to=self.service_parameters.device_id,
                                       func_input=FuncGetCameraControllerStateInput())
        self.device.send_msg_externally(msg)
        info_msg(self, 'INITIALIZED')

    def activate_controller(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def activate_camera(self):
        flag = 1 if self.ui.checkBox_On.isChecked() else 0
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateCameraInput(camera_id=int(self.ui.spinBox_cameraID.value()),
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

    def get_images(self, images=False):
        client = self.device
        every_sec = 0
        if images:
            n_images = -1
            if self.ui.radioButton_RT.isChecked():
                every_sec = 0
            else:
                every_sec = float(self.ui.spinBox_seconds.value())
        else:
            n_images = 1

        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetImagesInput(camera_id=int(self.ui.spinBox_cameraID.value()),
                                                                n_images=n_images,
                                                                every_n_sec=every_sec,
                                                                demander_device_id=client.id))
        client.send_msg_externally(msg)

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
                            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                                      forward_to=self.service_parameters.device_id,
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
                    elif info.com == CameraController.GET_IMAGES.name:
                        result: FuncGetImagesOutput = result
                        if result.func_success:
                            datacanvas: DataCanvasCamera = self.ui.datacanvas
                            datacanvas.update_data(CameraReadings(data=np.array(result.image),
                                                                  time_stamp=result.timestamp,
                                                                  description=result.description))

                    elif info.com == CameraController.GET_IMAGES.name_prepared:
                        result: FuncGetImagesPrepared = result
                        self.controller_cameras = {result.camera_id: result.camera}
                        if result.ready:
                            comments = f'Camera with id {result.camera_id} is ready to send images. ' \
                                       f'Acquisition is started.'
                        else:
                            comments = f'Camera {result.camera_id} is not ready to send images.'
                        self.ui.textEdit_comments.setText(f'{comments} {result.comments}')
                    elif info.com == CameraController.GET_IMAGES.name:
                        print('Get_images')
                    elif info.com == CameraController.STOP_ACQUISITION.name:
                        result: FuncStopAcquisitionOutput = result
                        if result.func_success:
                            self.ui.textEdit_comments.setText(f'Acquisition for camera with id {result.camera_id} '
                                                              f'is stopped.')
                        else:
                            self.ui.textEdit_comments.setText(f'Acqusition for camera with id {result.camera_id} '
                                                              f'was not stopped. {result.comments}')

                    elif info.com == CameraController.POWER.name:
                        result: FuncPowerOutput = result
                        self.controller_status.device_status = result.device_status

                elif com == MsgComInt.ERROR.msg_name:
                    self.ui.textEdit_comments.setText(info.comments)
                    client = self.device
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                              forward_to=self.service_parameters.device_id,
                                              func_input=FuncGetCameraControllerStateInput())
                    client.send_msg_externally(msg)

                self.update_state()
        except Exception as e:
            error_logger(self, self.model_is_changed, f'Error:"{e}". Msg={msg}')

    def power(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncPowerInput(flag=self.ui.checkBox_power.isChecked()))
        client.send_msg_externally(msg)

    def stop_acquisition(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncStopAcquisitionInput(camera_id=int(self.ui.spinBox_cameraID.value())))
        client.send_msg_externally(msg)
        self._asked_status = 0

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
            acq_ctrls: Acquisition_Controls = camera.parameters['Acquisition_Controls']
            analog_ctrls: Analog_Controls = camera.parameters['Analog_Controls']
            aoi_cntrls: AOI_Controls = camera.parameters['AOI_Controls']

            _translate = QtCore.QCoreApplication.translate
            if camera.friendly_name != '':
                name = camera.friendly_name
            else:
                name = camera.name

            ui.checkBox_On.setChecked(camera.status)
            ui.label_name.setText(_translate("CameraGUI", name))
            ui.spinBox_fps.setValue(acq_ctrls.AcquisitionFrameRateAbs)
            ui.spinBox_gainraw.setValue(analog_ctrls.GainRaw)
            ui.spinBox_blacklevel.setValue(analog_ctrls.BlackLevelRaw)
            ui.comboBox_syncmode.setCurrentText(acq_ctrls.TriggerMode)
            ui.spinBox_Width.setValue(aoi_cntrls.Width)
            ui.spinBox_Height.setValue(aoi_cntrls.Height)
            ui.spinBox_Xoffset.setValue(aoi_cntrls.OffsetX)
            ui.spinBox_Yoffset.setValue(aoi_cntrls.OffsetY)


            self.controller_status.cameras_previous = copy.deepcopy(cs.cameras)

            if force_camera:
                pass

            if cs.device_status != cs.device_status_previous or force_device:
                ui.checkBox_power.setChecked(cs.device_status.power)
                ui.checkBox_activate.setChecked(cs.device_status.active)
                ui.checkBox_On.setChecked(camera.status)
                self.controller_status.device_status_previous = copy.deepcopy(self.controller_status.device_status)
