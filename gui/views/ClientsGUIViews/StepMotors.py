'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5.QtWidgets import (QMainWindow)
from PyQt5 import QtCore

from communication.messaging.messages import MsgComExt, MsgComInt, MessageExt, MessageInt
from communication.messaging.message_utils import MsgGenerator
from datastructures.mes_independent.devices_dataclass import *
from datastructures.mes_independent.stpmtr_dataclass import *
from devices.devices import Device
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ui import Ui_StpMtrGUI
from utilities.myfunc import info_msg, get_local_ip, error_logger


module_logger = logging.getLogger(__name__)


class StepMotorsView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: Desription, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.controller_status = StpMtrCtrlStatusMultiAxes(axes=service_parameters.device_description.axes,
                                                           axes_previous=dict(service_parameters.device_description.axes),
                                                           device_status=service_parameters.device_status,
                                                           device_status_previous=service_parameters.device_status)
        if not self.controller_status.start_stop:
            self.controller_status.start_stop = [[0, 0]] * len(self.controller_status.axes)
        self.name = f'StepMotorsClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("StepMotors." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: DeviceInfoExt = service_parameters

        self.ui = Ui_StpMtrGUI()
        self.ui.setupUi(self, service_parameters)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.checkBox_activate.clicked.connect(self.activate)
        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.pushButton_stop.clicked.connect(self.stop_axis)
        self.ui.checkBox_On.clicked.connect(self.activate_axis)
        self.ui.spinBox_axis.valueChanged.connect(partial(self.update_state, True))
        self.ui.closeEvent = self.closeEvent

        self.update_state()
        info_msg(self, 'INITIALIZED')

    def activate(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def activate_axis(self):
        flag = 1 if self.ui.checkBox_On.isChecked() else 0
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncActivateAxisInput(axis_id=int(self.ui.spinBox_axis.value()),
                                                                   flag=flag))
        client.send_msg_externally(msg)

        self._asked_status = 0

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    @property
    def controller_axes(self):
        return self.controller_status.axes

    def get_pos(self, axis_id=None, with_return=False):
        if axis_id is None:
            axis_id = int(self.ui.spinBox_axis.value())
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncGetPosInput(axis_id))
        client.send_msg_externally(msg)
        if with_return:
            return True if self.controller_status.axes[axis_id].status == 2 else False

    @controller_axes.setter
    def controller_axes(self, value: Union[Dict[int, AxisStpMtrEssentials], Dict[int, AxisStpMtr]]):
        try:
            if type(next(iter(value.values()))) == AxisStpMtr:
                self.controller_status.axes = value
            else:
                for axis_id, axis in value.items():
                    self.controller_status.axes[axis_id].status = axis.status
                    self.controller_status.axes[axis_id].position = axis.position
        except Exception as e:
            self.logger.error(e)

    def move_axis(self):
        if self.ui.radioButton_absolute.isChecked():
            how = absolute.__name__
        else:
            how = relative.__name__
        axis_id = int(self.ui.spinBox_axis.value())
        pos = float(self.ui.lineEdit_value.text())

        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how))
        client.send_msg_externally(msg)

        self.controller_status.start_stop[axis_id] = [self.controller_status.axes[axis_id].position, pos]
        self.controller_status.axes[axis_id].status = 2
        self.ui.progressBar_movement.setValue(0)
        self.device.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos, delay=1, n_max=25,
                                    specific={'axis_id': axis_id, 'with_return': True})
        self._asked_status = 0

    def model_is_changed(self, msg: MessageInt):
        try:
            if self.service_parameters.device_id == msg.forwarded_from or \
                    self.service_parameters.device_id == msg.sender_id:
                com = msg.com
                info: Union[DoneIt, MsgError] = msg.info
                if com == MsgComInt.DONE_IT.msg_name:
                    result: Union[FuncActivateOutput,
                                  FuncActivateAxisOutput,
                                  FuncGetStpMtrControllerStateOutput,
                                  FuncMoveAxisToOutput,
                                  FuncGetPosOutput,
                                  FuncStopAxisOutput,
                                  FuncPowerOutput] = info
                    self.ui.comments.setText(result.comments)
                    if info.com == StpMtrController.ACTIVATE.name:
                        result: FuncActivateOutput = result
                        self.controller_status.device_status = result.device_status
                    elif info.com == StpMtrController.ACTIVATE_AXIS.name:
                        result: FuncActivateAxisOutput = result
                        self.controller_axes = result.axes
                    elif info.com == StpMtrController.MOVE_AXIS_TO.name:
                        result: FuncMoveAxisToOutput = result
                        self.controller_axes = result.axes
                    elif info.com == StpMtrController.GET_POS.name:
                        result: FuncGetPosOutput = result
                        self.controller_axes = result.axes
                    elif info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                        result: FuncGetStpMtrControllerStateOutput = result
                        self.controller_axes = result.axes
                        self.controller_status.device_status = result.device_status
                        if not self.controller_status.start_stop:
                            self.controller_status.start_stop = [[0.0, 0.0]] * len(self.controller_status.axes)
                    elif info.com == StpMtrController.STOP_AXIS.name:
                        result: FuncStopAxisOutput = result
                        self.controller_axes = result.axes
                    elif info.com == StpMtrController.POWER.name:
                        result: FuncPowerOutput = result
                        self.controller_status.device_status = result.device_status

                elif com == MsgComInt.ERROR.msg_name:
                    self.ui.comments.setText(info.comments)
                    client = self.device
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                              func_input=FuncGetStpMtrControllerStateInput())
                    client.send_msg_externally(msg)

                self.update_state()
        except Exception as e:
            error_logger(self, self.model_is_changed, e)

    def stop_axis(self):
        axis_id = int(self.ui.spinBox_axis.value())
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncStopAxisInput(axis_id=axis_id))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def power(self):
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncPowerInput(flag=self.ui.checkBox_power.isChecked()))
        client.send_msg_externally(msg)

    def update_state(self, force=False):
        cs = self.controller_status
        ui = self.ui
        if cs.axes != cs.axes_previous or force:
            for now, then in zip(cs.axes.items(), cs.axes_previous.items()):
                if now != then:
                    axis: AxisStpMtrEssentials = now[1]
                    ui.checkBox_On.setChecked(axis.status)
            axis_id = int(ui.spinBox_axis.value())
            axis: AxisStpMtrEssentials = cs.axes[axis_id]
            ui.lcdNumber_position.display(axis.position)
            _translate = QtCore.QCoreApplication.translate
            axis: AxisStpMtr = self.service_parameters.device_description.axes[axis_id]
            ui.label.setText(_translate("StpMtrGUI", "axis ID"))
            ui.label_name.setText(_translate("StpMtrGUI", axis.name))
            ui.label_ranges.setText(_translate("StpMtrGUI", str(axis.limits)))
            ui.label_preset.setText(_translate("StpMtrGUI", str(axis.preset_values)))

            self._update_progessbar_pos()

            self.controller_status.axes_previous = copy.deepcopy(cs.axes)

        if cs.device_status != cs.device_status_previous or force:
            ui.checkBox_power.setChecked(cs.device_status.power)
            ui.checkBox_activate.setChecked(cs.device_status.active)
            axis: AxisStpMtrEssentials = cs.axes[int(ui.spinBox_axis.value())]
            ui.checkBox_On.setChecked(axis.status)
            ui.lcdNumber_position.display(axis.position)

            self.controller_status.device_status_previous = copy.deepcopy(self.controller_status.device_status)

    def _update_progessbar_pos(self):
        axis = int(self.ui.spinBox_axis.value())
        pos = self.controller_status.axes[axis].position
        if self.controller_status.axes[axis].status == 2 and self.ui.spinBox_axis.value() == axis:
            start = self.controller_status.start_stop[axis][0]
            stop = self.controller_status.start_stop[axis][1]
            per = int((pos - start) / (stop - start) * 100.0)
            self.ui.progressBar_movement.setValue(per)
            self.ui.lcdNumber_position.display(pos)

