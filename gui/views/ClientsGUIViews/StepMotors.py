'''
Created on 15.11.2019

@author: saldenisov
'''
import copy
import logging
from _functools import partial

from PyQt5.QtWidgets import QMainWindow, QErrorMessage
from PyQt5 import QtCore

from communication.messaging.messages import MsgComExt, MsgComInt, MessageInt
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.stpmtr_dataclass import *
from devices.devices import Device
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ui import Ui_StpMtrGUI
from utilities.myfunc import info_msg, get_local_ip, error_logger
from utilities.datastructures.mes_independent.stpmtr_dataclass import mm, microstep


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
            self.controller_status.start_stop = {axis_id: [0, 0] for axis_id in self.controller_status.axes.keys()}

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
        self.ui.spinBox_axis.valueChanged.connect(partial(self.update_state, *[True, False]))
        self.ui.closeEvent = self.closeEvent

        self.update_state(force_axis=True)

        msg = self.device.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                  func_input=FuncGetStpMtrControllerStateInput())
        self.device.send_msg_externally(msg)
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
            error_logger(self, self.controller_axes, e)

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
            #pos = self.ui.lineEdit_value.text().strip()
            #pos: Union[microstep, mm, None] = convert_pos(pos)
            pos = float(self.ui.lineEdit_value.text())

            client = self.device
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.service_parameters.device_id,
                                      func_input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how,
                                                                     move_type=self._get_unit()))
            client.send_msg_externally(msg)

            self.controller_status.start_stop[axis_id] = [self.controller_status.axes[axis_id].position, pos]
            self.controller_status.axes[axis_id].status = 2
            self.ui.progressBar_movement.setValue(0)
            self.device.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos, delay=1, n_max=25,
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
                        self._update_progessbar_pos(force=True)
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
                        self._update_progessbar_pos(force=True)
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

    def update_state(self, force_axis=False, force_device=False):

        def form_ranges(ranges: List) -> str:
            out_l = []
            for val in ranges:
                try:
                    val = val.name
                except AttributeError:
                    val = str(val)
                finally:
                    out_l.append(val)
            return '_'.join(out_l)

        cs = self.controller_status
        ui = self.ui
        self._update_progessbar_pos()

        if cs.axes != cs.axes_previous or force_axis:
            for now, then in zip(cs.axes.items(), cs.axes_previous.items()):
                if now != then:
                    axis: AxisStpMtrEssentials = now[1]
                    ui.checkBox_On.setChecked(axis.status)

            axis_id = int(ui.spinBox_axis.value())
            axis: AxisStpMtr = cs.axes[axis_id]

            if force_axis:
                if MoveType.step in axis.type_move or MoveType.microstep in axis.type_move:
                    ui.radioButton_stp.setEnabled(True)
                    ui.radioButton_stp.setChecked(True)
                else:
                    ui.radioButton_stp.setEnabled(False)

                if MoveType.angle in axis.type_move:
                    ui.radioButton_angle.setEnabled(True)
                    ui.radioButton_angle.setChecked(True)
                else:
                    ui.radioButton_angle.setEnabled(False)

                if MoveType.mm in axis.type_move:
                    ui.radioButton_mm.setEnabled(True)
                    ui.radioButton_mm.setChecked(True)
                else:
                    ui.radioButton_mm.setEnabled(False)

            unit = self._get_unit()

            ui.lcdNumber_position.display(axis.convert_pos_to_unit(unit))
            _translate = QtCore.QCoreApplication.translate
            axis: AxisStpMtr = self.service_parameters.device_description.axes[axis_id]
            ui.label.setText(_translate("StpMtrGUI", "axis ID"))
            ui.label_name.setText(_translate("StpMtrGUI", axis.name))
            ui.label_ranges.setText(_translate("StpMtrGUI", form_ranges(axis.limits)))
            ui.label_preset.setText(_translate("StpMtrGUI", form_ranges(axis.preset_values)))

            self.controller_status.axes_previous = copy.deepcopy(cs.axes)

        if cs.device_status != cs.device_status_previous or force_device:
            ui.checkBox_power.setChecked(cs.device_status.power)
            ui.checkBox_activate.setChecked(cs.device_status.active)
            ui.checkBox_On.setChecked(axis.status)
            self.controller_status.device_status_previous = copy.deepcopy(self.controller_status.device_status)

    def _update_progessbar_pos(self, force=False):
        axis = int(self.ui.spinBox_axis.value())
        pos = self.controller_status.axes[axis].convert_pos_to_unit(self._get_unit())
        if (self.controller_status.axes[axis].status == 2 or force) and self.ui.spinBox_axis.value() == axis:
            start = self.controller_status.start_stop[axis][0]
            stop = self.controller_status.start_stop[axis][1]
            per = int((pos - start) / (stop - start) * 100.0)
            self.ui.progressBar_movement.setValue(per)
            self.ui.lcdNumber_position.display(pos)

    def _get_unit(self) -> MoveType:
        rb_dict = {self.ui.radioButton_angle: MoveType.angle, self.ui.radioButton_stp: MoveType.step,
                   self.ui.radioButton_mm: MoveType.mm}
        for rb, unit in rb_dict.items():
            if rb.isChecked():
                return unit
        axis = self.controller_status.axes[int(self.ui.spinBox_axis.value())]
        return axis.basic_unit



