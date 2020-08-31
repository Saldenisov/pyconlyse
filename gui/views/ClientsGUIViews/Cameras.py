"""
Created on 16.07.2020

@author: saldenisov
"""
import copy
import logging
import numpy as np
from _functools import partial
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage, QMenu
from typing import Union
from time import sleep
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
        from matplotlib.widgets import Cursor, RectangleSelector

        self.ui.datacanvas = DataCanvasCamera(width=9, height=10, dpi=70, canvas_parent=self.ui.verticalWidget_toolbox)
        self.RS = RectangleSelector(self.ui.datacanvas.axis,
                                    self.update_cursors,
                                    drawtype='box',
                                    useblit=True,
                                    button=[1, 3],
                                    minspanx=5,
                                    minspany=5,
                                    spancoords='pixels')
        self.ui.datacanvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.ui.datacanvas.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.comboBox_x_stepmotor.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.comboBox_y_stepmotor.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.horizontalLayout_canvas.addWidget(self.ui.datacanvas)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)

        self.ui.checkBox_On.clicked.connect(self.activate_camera)
        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.checkBox_activate.clicked.connect(self.activate_controller)
        self.ui.spinBox_cameraID.valueChanged.connect(partial(self.update_state, *[True, False]))
        self.ui.pushButton_GetImage.clicked.connect(self.get_image)
        self.ui.pushButton_GetImages.clicked.connect(partial(self.get_image, True))
        self.ui.pushButton_stop.clicked.connect(self.stop_acquisition)
        self.ui.pushButton_GetImage.clicked.connect(partial(self.get_image, False))
        self.ui.pushButton_GetImages.clicked.connect(partial(self.get_image, True))
        self.ui.pushButton_set_parameters.clicked.connect(self.set_parameters)
        self.ui.comboBox_x_stepmotor.activated.connect(partial(self.step_motor_changed, 'X'))
        self.ui.comboBox_y_stepmotor.activated.connect(partial(self.step_motor_changed, 'Y'))

        # Context Menus
        self.ui.datacanvas.customContextMenuRequested.connect(self.menuContextDataCanvas)
        self.ui.comboBox_x_stepmotor.customContextMenuRequested.connect(partial(self.menuContextStepMotor, 'X'))
        self.ui.comboBox_y_stepmotor.customContextMenuRequested.connect(partial(self.menuContextStepMotor, 'Y'))

        self.update_state(force_camera=True, force_device=True)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.device.server_id,
                                       forward_to=self.service_parameters.device_id,
                                       func_input=FuncGetCameraControllerStateInput())
        self.device.send_msg_externally(msg)
        info_msg(self, 'INITIALIZED')

    def menuContextDataCanvas(self, point):
        menu = QMenu()
        action_full_image = menu.addAction('Full Image')

        action = menu.exec_(self.ui.datacanvas.mapToGlobal(point))

        if action:
            if action == action_full_image:
                camera_id = self.ui.spinBox_cameraID.value()
                size_of_matrix = self.controller_status.cameras[camera_id].matrix_size
                if len(size_of_matrix) != 0:
                    self.ui.spinBox_Xoffset.setValue(0)
                    self.ui.spinBox_Yoffset.setValue(0)
                    self.ui.spinBox_Width.setValue(size_of_matrix[0])
                    self.ui.spinBox_Height.setValue(size_of_matrix[1])
                    self.set_image_parameters()

    def menuContextStepMotor(self, axis: str, point):
        menu = QMenu()
        action_get_axes = menu.addAction('Get Axes')

        if axis == 'X':
            action = menu.exec_(self.ui.comboBox_x_stepmotor.mapToGlobal(point))
        elif axis == 'Y':
            action = menu.exec_(self.ui.comboBox_y_stepmotor.mapToGlobal(point))

        if action:
            camera_id = self.ui.spinBox_cameraID.value()
            camera: Camera = self.controller_status.cameras[camera_id]
            if action == action_get_axes:
                if camera.stpmtr_ctrl_id != '' and camera.stpmtr_ctrl_id in list(self.device.service_parameters.keys()):
                    client = self.device
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                              forward_to=camera.stpmtr_ctrl_id,
                                              func_input=FuncGetControllerStateInput())
                    client.send_msg_externally(msg)
                    self._asked_status = 0


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
            if Camera in type(next(iter(value.values()))).__bases__:
                for camera_id, camera in value.items():
                    self.controller_status.cameras[camera_id] = camera
            else:
                for camera_id, camera in value.items():
                    self.controller_status.cameras[camera_id].status = camera.status
        except Exception as e:
            error_logger(self, self.controller_axes, e)

    def get_image(self, grab_cont=False):
        client = self.device

        if grab_cont:
            if self.ui.radioButton_RT.isChecked():
                every_sec = 0
            else:
                every_sec = float(self.ui.spinBox_seconds.value())
        else:
            every_sec = -1

        send_images_back = self.ui.checkBox_images.isChecked()
        if self.ui.checkBox_cg.isChecked():
            cg_points = self.ui.spinBox_cg_points.value()
        else:
            cg_points = -1

        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetImagesInput(camera_id=int(self.ui.spinBox_cameraID.value()),
                                                                demander_device_id=client.id,
                                                                every_n_sec=every_sec,
                                                                return_images=self.ui.checkBox_images.isChecked(),
                                                                post_treatment='cg',
                                                                history_post_treament_n=cg_points))
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
                            if result.image and self.ui.spinBox_cameraID.value() == result.camera_id:
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
                    elif info.com == CameraController.SET_IMAGE_PARAMETERS.name:
                        result: FuncSetImageParametersOutput = result
                        self.controller_cameras = {result.camera_id: result.camera}
                        if result.comments:
                            self.ui.textEdit_comments.setText(result.comments)
                    elif info.com == CameraController.SET_SYNC_PARAMETERS.name:
                        result: FuncSetSyncParametersOutput = result
                        self.controller_cameras = {result.camera_id: result.camera}
                        if result.comments:
                            self.ui.textEdit_comments.setText(result.comments)
                    elif info.com == CameraController.SET_TRANSPORT_PARAMETERS.name:
                        result: FuncSetTransportParametersOutput = result
                        self.controller_cameras = {result.camera_id: result.camera}
                        if result.comments:
                            self.ui.textEdit_comments.setText(result.comments)
                    elif info.com == CameraController.STOP_ACQUISITION.name:
                        result: FuncStopAcquisitionOutput = result
                        if result.func_success:
                            self.ui.textEdit_comments.setText(f'Acquisition for camera with id {result.camera_id} '
                                                              f'is stopped.')
                        else:
                            self.ui.textEdit_comments.setText(f'Acqusition for camera with id {result.camera_id} '
                                                              f'was not stopped. {result.comments}')
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

    def set_parameters(self):
        cs = self.controller_status
        ui = self.ui
        camera_id = int(ui.spinBox_cameraID.value())
        camera: CameraEssentials = cs.cameras[camera_id]
        acq_ctrls: Acquisition_Controls = camera.parameters['Acquisition_Controls']
        analog_ctrls: Analog_Controls = camera.parameters['Analog_Controls']
        aoi_cntrls: AOI_Controls = camera.parameters['AOI_Controls']
        transport_cntrls: Transport_Layer = camera.parameters['Transport_Layer']


        # Acqusition controls
        from distutils.util import strtobool
        exposure_time = ui.spinBox_exposure_time.value()
        trigger_mode = strtobool(ui.comboBox_syncmode.currentText())
        trigger_delay = ui.spinBox_trigger_delay.value()
        fps = ui.spinBox_fps.value()
        trigger_source = ui.comboBox_TrigSource.currentText()
        acq_ctrls_new = Acquisition_Controls(TriggerSource=trigger_source, TriggerMode=trigger_mode,
                                             TriggerDelayAbs=trigger_delay, ExposureTimeAbs=exposure_time,
                                             AcquisitionFrameRateAbs=fps, AcquisitionFrameRateEnable=trigger_mode)
        if acq_ctrls_new != acq_ctrls:
            self.set_sync_parameters()

        # Transport layer
        packet_size = ui.spinBox_packetsize.value()
        interpacket_delay = ui.spinBox_interpacket_delay.value()
        transport_cntrls_new = Transport_Layer(GevSCPSPacketSize=packet_size, GevSCPD=interpacket_delay)
        if transport_cntrls_new != transport_cntrls:
            self.set_transport_parameters()

        # Image parameters
        width = ui.spinBox_Width.value()
        height = ui.spinBox_Height.value()
        xoffset = ui.spinBox_Xoffset.value()
        yoffset = ui.spinBox_Yoffset.value()
        blacklevel = ui.spinBox_blacklevel.value()
        gainraw = ui.spinBox_gainraw.value()
        gain_mode = ui.comboBox_gain_mode.currentText()
        balance_ratio = ui.spinBox_balance_ratio.value()
        analog_ctrls_new = Analog_Controls(GainAuto=gain_mode, GainRaw=gainraw, BlackLevelRaw=blacklevel,
                                           BalanceRatioRaw=balance_ratio)
        aoi_cntrls_new = AOI_Controls(Width=width, Height=height, OffsetX=xoffset, OffsetY=yoffset)

        if analog_ctrls_new != analog_ctrls or aoi_cntrls_new != aoi_cntrls:
            self.set_image_parameters()

    def set_image_parameters(self):
        ui = self.ui
        width = ui.spinBox_Width.value()
        height = ui.spinBox_Height.value()
        xoffset = ui.spinBox_Xoffset.value()
        yoffset = ui.spinBox_Yoffset.value()
        blacklevel = ui.spinBox_blacklevel.value()
        gainraw = ui.spinBox_gainraw.value()
        gain_mode = ui.comboBox_gain_mode.currentText()
        balance_ratio = ui.spinBox_balance_ratio.value()
        camera_id = ui.spinBox_cameraID.value()
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetImageParametersInput(camera_id=camera_id, width=width,
                                                                         height=height, offset_x=xoffset,
                                                                         offset_y=yoffset, gain_mode=gain_mode,
                                                                         gain=gainraw, blacklevel=blacklevel,
                                                                         balance_ratio=balance_ratio,
                                                                         pixel_format='Mono8'))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def set_sync_parameters(self):
        from distutils.util import strtobool
        ui = self.ui
        exposure_time = ui.spinBox_exposure_time.value()
        trigger_mode = strtobool(ui.comboBox_syncmode.currentText())
        trigger_delay = ui.spinBox_trigger_delay.value()
        fps = ui.spinBox_fps.value()
        trigger_source = ui.comboBox_TrigSource.currentText()
        camera_id = ui.spinBox_cameraID.value()
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetSyncParametersInput(camera_id=camera_id,
                                                                        exposure_time=exposure_time,
                                                                        trigger_mode=trigger_mode,
                                                                        trigger_delay=trigger_delay,
                                                                        frame_rate=fps,
                                                                        trigger_source=trigger_source))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def set_transport_parameters(self):
        ui = self.ui
        packet_size = ui.spinBox_packetsize.value()
        interpacket_delay = ui.spinBox_interpacket_delay.value()
        camera_id = ui.spinBox_cameraID.value()
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetTransportParametersInput(camera_id=camera_id,
                                                                             packet_size=packet_size,
                                                                             inter_packet_delay=interpacket_delay))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def step_motor_changed(self, axis: str):
        pass

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
            camera_id = ui.spinBox_cameraID.value()

            camera: CameraEssentials = cs.cameras[camera_id]
            acq_ctrls: Acquisition_Controls = camera.parameters['Acquisition_Controls']
            analog_ctrls: Analog_Controls = camera.parameters['Analog_Controls']
            aoi_cntrls: AOI_Controls = camera.parameters['AOI_Controls']
            transport_cntrls: Transport_Layer = camera.parameters['Transport_Layer']

            _translate = QtCore.QCoreApplication.translate
            if camera.friendly_name != '':
                name = camera.friendly_name
            else:
                name = camera.name

            ui.checkBox_On.setChecked(camera.status)
            ui.label_name.setText(_translate("CameraGUI", name))
            ui.spinBox_fps.setValue(acq_ctrls.AcquisitionFrameRateAbs)
            ui.spinBox_exposure_time.setValue(acq_ctrls.ExposureTimeAbs)
            ui.spinBox_trigger_delay.setValue(acq_ctrls.TriggerDelayAbs)
            ui.spinBox_gainraw.setValue(analog_ctrls.GainRaw)
            ui.spinBox_blacklevel.setValue(analog_ctrls.BlackLevelRaw)
            ui.comboBox_syncmode.setCurrentText(acq_ctrls.TriggerMode)

            ui.spinBox_Width.setValue(aoi_cntrls.Width)
            ui.spinBox_Height.setValue(aoi_cntrls.Height)
            ui.spinBox_Xoffset.setValue(aoi_cntrls.OffsetX)
            ui.spinBox_Yoffset.setValue(aoi_cntrls.OffsetY)

            ui.spinBox_packetsize.setValue(transport_cntrls.GevSCPSPacketSize)
            ui.spinBox_interpacket_delay.setValue(transport_cntrls.GevSCPD)

            self.controller_status.cameras_previous = copy.deepcopy(cs.cameras)

            if force_camera:
                pass

            if cs.device_status != cs.device_status_previous or force_device:
                ui.checkBox_power.setChecked(cs.device_status.power)
                ui.checkBox_activate.setChecked(cs.device_status.active)
                ui.checkBox_On.setChecked(camera.status)
                self.controller_status.device_status_previous = copy.deepcopy(self.controller_status.device_status)

    def update_cursors(self, eclick, erelease):
        camera_id = self.ui.spinBox_cameraID.value()
        size_of_matrix = self.controller_status.cameras[camera_id].matrix_size
        width_prev = self.ui.spinBox_Width.value()
        height_prev = self.ui.spinBox_Height.value()
        xoffset_prev = self.ui.spinBox_Xoffset.value()
        yoffset_prev = self.ui.spinBox_Yoffset.value()

        pixel_x_start, pixel_x_end, pixel_y_start, pixel_y_end = int(eclick.xdata), int(erelease.xdata), \
                                                                 int(eclick.ydata), int(erelease.ydata)

        if pixel_x_start > pixel_x_end:
            pixel_x_start, pixel_x_end = pixel_x_end, pixel_x_start

        if pixel_y_start > pixel_y_end:
            pixel_y_start, pixel_y_end = pixel_y_end, pixel_y_start

        width_new = pixel_x_end - pixel_x_start
        if width_new % 2 != 0:
            width_new += 1

        height_new = pixel_y_end - pixel_y_start
        if height_new % 2 != 0:
            height_new += 1

        xoffset_new = xoffset_prev + pixel_x_start
        if xoffset_new % 2 != 0:
            xoffset_new += 1

        yoffset_new = yoffset_prev + pixel_y_start
        if yoffset_new % 2 != 0:
            yoffset_new += 1

        if width_new + xoffset_new > size_of_matrix[0]:
            width_new = size_of_matrix[0] - xoffset_new

        if height_new + yoffset_new > size_of_matrix[1]:
            height_new = size_of_matrix[1] - yoffset_new

        self.ui.spinBox_Width.setValue(width_new)
        self.ui.spinBox_Height.setValue(height_new)
        self.ui.spinBox_Xoffset.setValue(xoffset_new)
        self.ui.spinBox_Yoffset.setValue(yoffset_new)

