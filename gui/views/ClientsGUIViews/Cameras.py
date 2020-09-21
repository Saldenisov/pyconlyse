"""
Created on 16.07.2020

@author: saldenisov
"""
import logging
from _functools import partial
from time import sleep

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMenu, QErrorMessage
from matplotlib.widgets import RectangleSelector

from communication.messaging.messages import MessageInt, MsgComExt
from devices.service_devices.cameras.camera_controller import CameraController
from gui.views.ClientsGUIViews.DeviceCtrlClient import DeviceControllerView
from gui.views.matplotlib_canvas.DataCanvasCamera import DataCanvasCamera
from gui.views.ui import Ui_CameraGUI
from devices.service_devices.cameras.camera_dataclass import *
from utilities.datastructures.mes_independent.measurments_dataclass import CameraReadings
from devices.service_devices.stepmotors.stpmtr_dataclass import *
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


class CamerasView(DeviceControllerView):

    def __init__(self, **kwargs):
        self.RS: RectangleSelector = None
        kwargs['ui_class'] = Ui_CameraGUI
        super().__init__(**kwargs)
        self._displacement = 0.5

    def extra_ui_init(self):
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
        self.ui.horizontalLayout_canvas.addWidget(self.ui.datacanvas)
        self.ui.comboBox_x_stepmotor.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.comboBox_y_stepmotor.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.pushButton_increase_X.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.pushButton_increase_Y.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.pushButton_decrease_X.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.pushButton_decrease_Y.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.ui.pushButton_GetImage.clicked.connect(partial(self.get_image, False))
        self.ui.pushButton_GetImages.clicked.connect(partial(self.get_image, True))
        self.ui.pushButton_stop.clicked.connect(self.stop_acquisition)
        self.ui.pushButton_set_parameters.clicked.connect(self.set_parameters)
        self.ui.comboBox_x_stepmotor.activated.connect(partial(self.step_motor_changed, 'X'))
        self.ui.comboBox_y_stepmotor.activated.connect(partial(self.step_motor_changed, 'Y'))
        self.ui.pushButton_increase_X.clicked.connect(partial(self.move_actuator, 'X_increase'))
        self.ui.pushButton_increase_Y.clicked.connect(partial(self.move_actuator, 'Y_increase'))
        self.ui.pushButton_decrease_X.clicked.connect(partial(self.move_actuator, 'X_decrease'))
        self.ui.pushButton_decrease_Y.clicked.connect(partial(self.move_actuator, 'Y_decrease'))

        # Context Menus
        self.ui.datacanvas.customContextMenuRequested.connect(self.menu_datacanvas)
        self.ui.comboBox_x_stepmotor.customContextMenuRequested.connect(partial(self.menu_stepmotor, 'X'))
        self.ui.comboBox_y_stepmotor.customContextMenuRequested.connect(partial(self.menu_stepmotor, 'Y'))
        self.ui.pushButton_increase_X.customContextMenuRequested.connect(partial(self.menu_actuator, 'X_increase'))
        self.ui.pushButton_increase_Y.customContextMenuRequested.connect(partial(self.menu_actuator, 'Y_increase'))
        self.ui.pushButton_decrease_X.customContextMenuRequested.connect(partial(self.menu_actuator, 'X_decrease'))
        self.ui.pushButton_decrease_Y.customContextMenuRequested.connect(partial(self.menu_actuator, 'Y_decrease'))

    def menu_datacanvas(self, point):
        menu = QMenu()
        action_full_image = menu.addAction('Full Image')

        action = menu.exec_(self.ui.datacanvas.mapToGlobal(point))

        if action:
            if action == action_full_image:
                camera_id = self.selected_device_id
                size_of_matrix = self.device_ctrl_state.devices[camera_id].matrix_size
                if len(size_of_matrix) != 0:
                    self.ui.spinBox_Xoffset.setValue(0)
                    self.ui.spinBox_Yoffset.setValue(0)
                    self.set_image_parameters()
                    sleep(0.2)
                    self.ui.spinBox_Width.setValue(size_of_matrix[0])
                    self.ui.spinBox_Height.setValue(size_of_matrix[1])
                    sleep(0.2)
                    self.set_image_parameters()

    def menu_stepmotor(self, axis: str, point):
        menu = QMenu()
        action_get_axes = menu.addAction('Get Axes')

        if axis == 'X':
            action = menu.exec_(self.ui.comboBox_x_stepmotor.mapToGlobal(point))
        elif axis == 'Y':
            action = menu.exec_(self.ui.comboBox_y_stepmotor.mapToGlobal(point))
        else:
            action = None

        if action:
            camera_id = self.selected_device_id
            camera: Camera = self.controller_cameras[camera_id]
            if action == action_get_axes:
                if camera.stpmtr_ctrl_id in list(self.model.service_parameters.keys()):
                    param = self.model.service_parameters
                    stpmtr_ctrl_descrip: ServiceDescription = param[camera.stpmtr_ctrl_id].device_description
                    self.ui.comboBox_x_stepmotor.clear()
                    self.ui.comboBox_y_stepmotor.clear()
                    for i, axis in stpmtr_ctrl_descrip.hardware_devices.items():
                        self.ui.comboBox_x_stepmotor.addItem(f'{axis.friendly_name}::{i}')
                        self.ui.comboBox_y_stepmotor.addItem(f'{axis.friendly_name}::{i}')

    def menu_actuator(self, button: str, point):
        menu = QMenu()
        action_displacement_half = menu.addAction('0.5')
        action_displacement_one = menu.addAction('1')
        action_displacement_two = menu.addAction('2')
        action_displacement_five = menu.addAction('5')
        action_displacement_ten = menu.addAction('10')
        action_displacement_twenty = menu.addAction('20')
        action_displacement_fifty = menu.addAction('50')
        action_displacement_hundred = menu.addAction('100')

        if button == 'X_decrease':
            action = menu.exec_(self.ui.pushButton_decrease_X.mapToGlobal(point))
        elif button == 'X_increase':
            action = menu.exec_(self.ui.pushButton_increase_X.mapToGlobal(point))
        elif button == 'Y_decrease':
            action = menu.exec_(self.ui.pushButton_decrease_Y.mapToGlobal(point))
        elif button == 'Y_increase':
            action = menu.exec_(self.ui.pushButton_increase_Y.mapToGlobal(point))
        else:
            action = None

        if action == action_displacement_half:
            self._displacement = 0.5
        elif action == action_displacement_one:
            self._displacement = 1
        elif action == action_displacement_two:
            self._displacement = 2
        elif action == action_displacement_five:
            self._displacement = 5
        elif action == action_displacement_ten:
            self._displacement = 10
        elif action == action_displacement_twenty:
            self._displacement = 20
        elif action == action_displacement_fifty:
            self._displacement = 50
        elif action == action_displacement_hundred:
            self._displacement = 100

    @property
    def controller_cameras(self):
        return self.controller_devices

    @controller_cameras.setter
    def controller_cameras(self, value: Union[Dict[int, CameraEssentials], Dict[int, Camera],
                                           Camera, CameraEssentials]):
        self.controller_devices = value

    def get_image(self, grab_cont=False):
        client = self.superuser

        if grab_cont:
            if self.ui.radioButton_RT.isChecked():
                every_sec = 0
            else:
                every_sec = float(self.ui.spinBox_seconds.value())
        else:
            every_sec = -1

        if self.ui.checkBox_cg.isChecked():
            cg_points = self.ui.spinBox_cg_points.value()
        else:
            cg_points = 0

        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetImagesInput(camera_id=self.selected_device_id,
                                                                demander_device_id=client.id,
                                                                every_n_sec=every_sec,
                                                                return_images=self.ui.checkBox_images.isChecked(),
                                                                post_treatment='cg',
                                                                treatment_param={'threshold':
                                                                                 self.ui.spinBox_threshold.value()},
                                                                history_post_treatment_n=cg_points))
        self.send_msg(msg)

    def model_is_changed(self, msg: MessageInt):
        def func_local(info: Union[DoneIt]) -> DoneIt:
            result = info
            if info.com == CameraController.GET_IMAGES.name:
                result: FuncGetImagesOutput = result
                if self.selected_device_id == result.camera_id:
                    datacanvas: DataCanvasCamera = self.ui.datacanvas
                    if result.image:
                        datacanvas.update_data(CameraReadings(data=np.array(result.image),
                                                              time_stamp=result.timestamp,
                                                              description=result.description),
                                               offsets=(self.ui.spinBox_Xoffset.value(),
                                                        self.ui.spinBox_Yoffset.value()))
                    if result.post_treatment_points and self.ui.checkBox_show_history.isChecked():
                        datacanvas.add_points(result.post_treatment_points, offsets=(self.ui.spinBox_Xoffset.value(),
                                                        self.ui.spinBox_Yoffset.value()))
            elif info.com == CameraController.GET_IMAGES.name_prepared:
                result: FuncGetImagesPrepared = result
                self.controller_cameras = result.camera
                if result.ready:
                    comments = f'Camera with id {result.camera.device_id_seq} is ready to send images. ' \
                               f'Acquisition is started.'
                else:
                    comments = f'Camera {result.camera.device_id_seq} is not ready to send images.'
                result.comments = f'{comments} {result.comments}'
            elif info.com == CameraController.SET_IMAGE_PARAMETERS.name:
                result: FuncSetImageParametersOutput = result
                self.controller_cameras = result.camera
            elif info.com == CameraController.SET_SYNC_PARAMETERS.name:
                result: FuncSetSyncParametersOutput = result
                self.controller_cameras = result.camera
            elif info.com == CameraController.SET_TRANSPORT_PARAMETERS.name:
                result: FuncSetTransportParametersOutput = result
                self.controller_cameras = result.camera
            elif info.com == CameraController.STOP_ACQUISITION.name:
                result: FuncStopAcquisitionOutput = result
                self.controller_cameras = result.camera
            return result
        super(CamerasView, self).model_is_changed(msg, func_local=func_local)

    def move_actuator(self, button_name: str):
        try:
            client = self.superuser
            camera: Camera = self.controller_cameras[self.selected_device_id]
            axis_id = 0
            if 'X' in button_name:
                axis_id = int(self.ui.comboBox_x_stepmotor.currentText().split('::')[1])
            else:
                axis_id = int(self.ui.comboBox_y_stepmotor.currentText().split('::')[1])

            if 'decrease' in button_name:
                direction = -1
            elif 'increase' in button_name:
                direction = 1

            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=camera.stpmtr_ctrl_id,
                                      func_input=FuncActivateDeviceInput(device_id=axis_id, flag=1))
            self.send_msg(msg)
            sleep(0.02)
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=camera.stpmtr_ctrl_id,
                                      func_input=FuncMoveAxisToInput(axis_id=axis_id,
                                                                     pos=self._displacement * direction,
                                                                     how=relative.__name__))
            self.send_msg(msg)
        except (IndexError, ValueError) as e:
            comments = f'During attempt to move actuator error occurred: {e}.'
            error_logger(self, self.move_actuator, e)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def set_parameters(self):
        ui = self.ui
        camera_id = self.selected_device_id
        camera: Camera = self.device_ctrl_state.devices[camera_id]
        acq_ctrls: Acquisition_Controls = camera.parameters['Acquisition_Controls']
        analog_ctrls: Analog_Controls = camera.parameters['Analog_Controls']
        aoi_ctrls: AOI_Controls = camera.parameters['AOI_Controls']
        transport_ctrls: Transport_Layer = camera.parameters['Transport_Layer']

        # Acquisition controls
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
        transport_ctrls_new = Transport_Layer(GevSCPSPacketSize=packet_size, GevSCPD=interpacket_delay)
        if transport_ctrls_new != transport_ctrls:
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
        aoi_ctrls_new = AOI_Controls(Width=width, Height=height, OffsetX=xoffset, OffsetY=yoffset)

        if analog_ctrls_new != analog_ctrls or aoi_ctrls_new != aoi_ctrls:
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
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetImageParametersInput(camera_id=self.selected_device_id, width=width,
                                                                         height=height, offset_x=xoffset,
                                                                         offset_y=yoffset,
                                                                         gain_mode=gain_mode,
                                                                         gain=gainraw, blacklevel=blacklevel,
                                                                         balance_ratio=balance_ratio,
                                                                         pixel_format='Mono8'))
        self.send_msg(msg)
        self._asked_status = 0

    def set_sync_parameters(self):
        from distutils.util import strtobool
        ui = self.ui
        exposure_time = ui.spinBox_exposure_time.value()
        trigger_mode = strtobool(ui.comboBox_syncmode.currentText())
        trigger_delay = ui.spinBox_trigger_delay.value()
        fps = ui.spinBox_fps.value()
        trigger_source = ui.comboBox_TrigSource.currentText()
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetSyncParametersInput(camera_id=self.selected_device_id,
                                                                        exposure_time=exposure_time,
                                                                        trigger_mode=trigger_mode,
                                                                        trigger_delay=trigger_delay,
                                                                        frame_rate=fps,
                                                                        trigger_source=trigger_source))
        self.send_msg(msg)
        self._asked_status = 0

    def set_transport_parameters(self):
        ui = self.ui
        packet_size = ui.spinBox_packetsize.value()
        interpacket_delay = ui.spinBox_interpacket_delay.value()
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetTransportParametersInput(camera_id=self.selected_device_id,
                                                                             packet_size=packet_size,
                                                                             inter_packet_delay=interpacket_delay))
        self.send_msg(msg)
        self._asked_status = 0

    def step_motor_changed(self, axis: str):
        pass

    def stop_acquisition(self):
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncStopAcquisitionInput(camera_id=self.selected_device_id))
        self.send_msg(msg)
        self._asked_status = 0

    def update_state(self, force_device=False, force_ctrl=False):
        def update_func_local(self,force_device, force_ctrl):
            cs = self.device_ctrl_state
            ui = self.ui
            camera: Camera = cs.devices[self.selected_device_id]

            if cs.devices != cs.devices_previous or force_device:
                acq_ctrls: Acquisition_Controls = camera.parameters['Acquisition_Controls']
                analog_ctrls: Analog_Controls = camera.parameters['Analog_Controls']
                aoi_ctrls: AOI_Controls = camera.parameters['AOI_Controls']
                transport_ctrls: Transport_Layer = camera.parameters['Transport_Layer']

                # Setting Acquisition_Controls
                ui.spinBox_fps.setValue(acq_ctrls.AcquisitionFrameRateAbs)
                ui.spinBox_exposure_time.setValue(acq_ctrls.ExposureTimeAbs)
                ui.spinBox_trigger_delay.setValue(acq_ctrls.TriggerDelayAbs)
                # Setting Analog_Controls
                ui.spinBox_gainraw.setValue(analog_ctrls.GainRaw)
                ui.spinBox_blacklevel.setValue(analog_ctrls.BlackLevelRaw)
                ui.comboBox_syncmode.setCurrentText(acq_ctrls.TriggerMode)
                # Setting AOI_Controls
                ui.spinBox_Width.setValue(aoi_ctrls.Width)
                ui.spinBox_Height.setValue(aoi_ctrls.Height)
                ui.spinBox_Xoffset.setValue(aoi_ctrls.OffsetX)
                ui.spinBox_Yoffset.setValue(aoi_ctrls.OffsetY)
                # Setting Transport_Layer
                ui.spinBox_packetsize.setValue(transport_ctrls.GevSCPSPacketSize)
                ui.spinBox_interpacket_delay.setValue(transport_ctrls.GevSCPD)

            if force_device:
                pass

        super(CamerasView, self).update_state(force_device, force_ctrl, func=update_func_local)

    def update_cursors(self, eclick, erelease):
        camera_id = self.selected_device_id
        size_of_matrix = self.device_ctrl_state.devices[camera_id].matrix_size
        xoffset_prev = self.ui.spinBox_Xoffset.value()
        yoffset_prev = self.ui.spinBox_Yoffset.value()

        pixel_x_start, pixel_x_end, pixel_y_start, pixel_y_end = int(eclick.xdata), int(erelease.xdata), \
                                                                 int(eclick.ydata), int(erelease.ydata)

        if pixel_x_start > pixel_x_end:
            pixel_x_start, pixel_x_end = pixel_x_end, pixel_x_start

        if pixel_y_start > pixel_y_end:
            pixel_y_start, pixel_y_end = pixel_y_end, pixel_y_start

        print(pixel_x_start, pixel_x_end, pixel_y_start, pixel_y_end)

        width_new = pixel_x_end - pixel_x_start
        if width_new % 2 != 0:
            width_new += 1

        height_new = pixel_y_end - pixel_y_start
        if height_new % 2 != 0:
            height_new += 1

        xoffset_new = pixel_x_start
        if xoffset_new % 2 != 0:
            xoffset_new += 1

        yoffset_new = pixel_y_start
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

