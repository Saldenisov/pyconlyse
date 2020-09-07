'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage

from communication.messaging.messages import MsgComExt, MsgComInt, MessageInt
from devices.devices import Device
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ui import Ui_PDUs
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.myfunc import info_msg, get_local_ip, error_logger

module_logger = logging.getLogger(__name__)


class PDUsView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: DeviceInfoExt, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.controller_status = StpMtrCtrlStatusMultiAxes(axes=service_parameters.device_description.hardware_devices,
                                                           axes_previous=dict(service_parameters.device_description.hardware_devices),
                                                           device_status=service_parameters.controller_status,
                                                           device_status_previous=service_parameters.controller_status)
        if not self.controller_status.start_stop:
            self.controller_status.start_stop = {axis_id: [0, 0] for axis_id in self.controller_status.axes.keys()}

        self.name = f'PDUsClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("StepMotors." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: DeviceInfoExt = service_parameters

        self.ui = Ui_PDUs()
        self.ui.setupUi(self)
        self.setWindowTitle(service_parameters.device_description.GUI_title)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.checkBox_activate.clicked.connect(self.activate_controller)
        self.ui.checkBox_power.clicked.connect(self.power)

        self.ui.closeEvent = self.closeEvent

        self.update_state(force_axis=True, force_device=True)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.device.server_id,
                                       forward_to=self.service_parameters.device_id,
                                       func_input=FuncGetControllerStateInput())
        self.device.send_msg_externally(msg)
        info_msg(self, 'INITIALIZED')

    def activate_controller(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    @property
    def controller_pdus(self):
        return self.controller_status.axes

    @controller_pdus.setter
    def controller_pdus(self, value: Union[Dict[int, AxisStpMtrEssentials], Dict[int, AxisStpMtr]]):
        try:
            if type(next(iter(value.values()))) == AxisStpMtr:
                self.controller_status.axes = value
            else:
                for axis_id, axis in value.items():
                    self.controller_status.axes[axis_id].status = axis.status
                    self.controller_status.axes[axis_id].position = axis.position
        except Exception as e:
            error_logger(self, self.controller_pdus, e)

    def get_pos_axis(self, axis_id=None, with_return=False):
        if axis_id is None:
            axis_id = int(self.ui.spinBox_axis.value())
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetPosInput(axis_id))
        client.send_msg_externally(msg)
        if with_return:
            return True if self.controller_status.axes[axis_id].status == 2 else False

    def set_pos(self, axis_id=None):
        axis_id = int(self.ui.spinBox_axis.value())
        try:
            axis_pos = float(self.ui.lineEdit_value.text())
            client = self.device
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=self.service_parameters.device_id,
                                      func_input=FuncSetPosInput(axis_id, axis_pos, self._get_unit()))
            client.send_msg_externally(msg)
        except TypeError as e:
            comments = f'Pos "{self.ui.lineEdit_value.text()}" has wrong format: {e}.'
            error_logger(self, self.set_pos, comments)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def move_axis(self):
        def convert_pos(pos: str) -> Union[microstep, mm, None]:
            try:
                pos = float(pos)
                return mm(pos)
            except ValueError:
                pos = pos.split(' ')
                if len(pos) == 2:
                    try:
                        steps_to_go = int(pos[0])
                        microsteps_to_go = int(pos[1])
                        if self.controller_status.microsteps:
                            microsteps = int(self.controller_status.microsteps)
                            if microsteps_to_go > microsteps:
                                steps_to_go += microsteps_to_go // microsteps
                                microsteps_to_go = microsteps_to_go % microsteps
                            return microstep((steps_to_go, microsteps_to_go))
                        else:
                            raise ValueError(f'Could not convert Pos "{pos}" to steps and microsteps. '
                                             f'Microcontroller works with mm only.')
                    except ValueError:
                        raise ValueError(f'Could not convert Pos "{pos}" to steps and microsteps.')
                else:
                    raise ValueError(f'The structure of move command:  "value in mm" or '
                                     f'"value in steps" "value in microsteps."')

        if self.ui.radioButton_absolute.isChecked():
            how = absolute.__name__
        else:
            how = relative.__name__
        axis_id = int(self.ui.spinBox_axis.value())
        try:
            pos = float(self.ui.lineEdit_value.text())
            client = self.device
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=self.service_parameters.device_id,
                                      func_input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how,
                                                                     move_type=self._get_unit()))
            client.send_msg_externally(msg)

            self.controller_status.start_stop[axis_id] = [self.controller_status.axes[axis_id].position, pos]
            self.controller_status.axes[axis_id].status = 2
            self.ui.progressBar_movement.setValue(0)
            self.device.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos_axis, delay=1, n_max=25,
                                        specific={'axis_id': axis_id, 'with_return': True})
            self._asked_status = 0
        except ValueError as e:
            comments = f'Pos "{pos}" has wrong format: {e}.'
            error_logger(self, self.move_axis, comments)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def model_is_changed(self, msg: MessageInt):
        try:
            if self.service_parameters.device_id == msg.forwarded_from or \
                    self.service_parameters.device_id == msg.sender_id:
                com = msg.com
                info: Union[DoneIt, MsgError] = msg.info
                if com == MsgComInt.DONE_IT.msg_name:
                    result = info
                    self.ui.comments.setText(result.comments)
                    if result.func_success:
                        if info.com == StpMtrController.ACTIVATE.name:
                            result: FuncActivateOutput = result

                            if result.controller_status.active:
                                client = self.device
                                msg = client.generate_msg(msg_com=MsgComExt.DO_IT,
                                                          receiver_id=self.service_parameters.device_id,
                                                          func_input=FuncGetControllerStateInput())
                                client.send_msg_externally(msg)
                            self.controller_status.controller_status = result.controller_status
                        elif info.com == StpMtrController.ACTIVATE_AXIS.name:
                            result: FuncActivateAxisOutput = result
                            self.controller_status.axes[result.axis_id] = result.axis
                        elif info.com == StpMtrController.MOVE_AXIS_TO.name:
                            result: FuncMoveAxisToOutput = result
                            self.controller_status.axes[result.axis_id] = result.axis
                            self._update_progessbar_pos(force=True)
                        elif info.com == StpMtrController.GET_POS_AXIS.name:
                            result: FuncGetPosOutput = result
                            self.controller_status.axes[result.axis_id] = result.axis
                        elif info.com == StpMtrController.SET_POS_AXIS.name:
                            result: FuncSetPosOutput = result
                            self.controller_status.axes[result.axis_id] = result.axis
                        elif info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                            result: FuncGetControllerStateOutput = result
                            self.controller_pdus = result.devices_hardware
                            self.controller_status.controller_status = result.controller_status
                            if not self.controller_status.start_stop:
                                self.controller_status.start_stop = [[0.0, 0.0]] * len(self.controller_status.axes)
                        elif info.com == StpMtrController.POWER.name:
                            result: FuncPowerOutput = result
                            self.controller_status.controller_status = result.controller_status
                elif com == MsgComInt.ERROR.msg_name:
                    self.ui.comments.setText(info.comments)
                    client = self.device
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                              func_input=FuncGetControllerStateInput())
                    client.send_msg_externally(msg)
                self.update_state()
        except Exception as e:
            error_logger(self, self.model_is_changed, f'{e}:{msg}')

    def power(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncPowerInput(flag=self.ui.checkBox_power.isChecked()))
        client.send_msg_externally(msg)

    def update_state(self, force_axis=False, force_device=False):

        cs = self.controller_status
        ui = self.ui

        if cs.axes != cs.axes_previous or force_axis:
            pass

            self.controller_status.axes_previous = copy.deepcopy(cs.axes)

            if force_axis:
                pass

            if cs.controller_status != cs.controller_status_previous or force_device:
                ui.checkBox_power.setChecked(cs.controller_status.power)
                ui.checkBox_activate.setChecked(cs.controller_status.active)
                #ui.checkBox_On.setChecked(axis.status)
                self.controller_status.controller_status_previous = copy.deepcopy(self.controller_status.controller_status)

