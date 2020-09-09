'''
Created on 15.11.2019

@author: saldenisov
'''
import logging

from PyQt5.QtWidgets import QErrorMessage

from communication.messaging.messages import MsgComExt, MessageInt
from devices.devices import Device
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ClientsGUIViews.DeviceCtrlClient import DeviceControllerView
from gui.views.ui import Ui_StpMtrGUI
from utilities.datastructures.mes_independent.stpmtr_dataclass import *
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


class StepMotorsView(DeviceControllerView):

    def __init__(self, **kwargs):
        kwargs['ui_class'] = Ui_StpMtrGUI
        super().__init__(**kwargs)
        self.device_ctrl_state.start_stop = {}

    @property
    def controller_axes(self):
        return self.controller_devices

    @controller_axes.setter
    def controller_axes(self, value: Union[Dict[int, AxisStpMtrEssentials], Dict[int, AxisStpMtr],
                                           AxisStpMtr, AxisStpMtrEssentials]):
        self.controller_devices = value

    def extra_ui_init(self):
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.pushButton_stop.clicked.connect(self.stop_axis)
        self.ui.pushButton_set.clicked.connect(self.set_pos_axis)
        self.ui.radioButton_stp.toggled.connect(self._update_lcd_screen)
        self.ui.radioButton_mm.toggled.connect(self._update_lcd_screen)
        self.ui.radioButton_angle.toggled.connect(self._update_lcd_screen)

    def get_pos_axis(self, axis_id=None, with_return=False):
        if axis_id is None:
            axis_id = int(self.ui.spinBox_device_id.value())
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncGetPosInput(axis_id))
        self.send_msg(msg)
        if with_return:
            return True if self.device_ctrl_state.devices[axis_id].status == 2 else False

    def set_pos_axis(self, axis_id=None):
        try:
            axis_pos = float(self.ui.lineEdit_value.text())
            client = self.superuser
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=self.service_parameters.device_id,
                                      func_input=FuncSetPosInput(self.selected_device_id, axis_pos, self._get_unit()))
            self.send_msg(msg)
        except TypeError as e:
            comments = f'Pos "{self.ui.lineEdit_value.text()}" has wrong format: {e}.'
            error_logger(self, self.set_pos_axis, comments)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def move_axis(self):
        if self.ui.radioButton_absolute.isChecked():
            how = absolute.__name__
        else:
            how = relative.__name__
        axis_id = self.selected_device_id
        try:
            pos = float(self.ui.lineEdit_value.text())
            client = self.superuser
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                      forward_to=self.service_parameters.device_id,
                                      func_input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how,
                                                                     move_type=self._get_unit()))
            self.send_msg(msg)

            self.device_ctrl_state.start_stop[axis_id] = [self.device_ctrl_state.devices[axis_id].position, pos]
            self.device_ctrl_state.devices[axis_id].status = 2
            self.ui.progressBar_movement.setValue(0)
            client.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos_axis, delay=1, n_max=25,
                                   specific={'axis_id': axis_id, 'with_return': True})
            self._asked_status = 0
        except ValueError as e:
            comments = f'Pos "{pos}" has wrong format: {e}.'
            error_logger(self, self.move_axis, comments)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def model_is_changed(self, msg: MessageInt) -> DoneIt:
        def func_local(info: Union[DoneIt]):
            result = info
            if info.com == StpMtrController.MOVE_AXIS_TO.name:
                result: FuncMoveAxisToOutput = result
                self.controller_axes = result.axis
                self._update_progressbar_pos(axis=self.controller_axes[result.axis.device_id_seq], force=True)
            elif info.com == StpMtrController.GET_POS_AXIS.name:
                result: FuncGetPosOutput = result
                self.controller_axes = result.axis
            elif info.com == StpMtrController.SET_POS_AXIS.name:
                result: FuncSetPosOutput = result
                self.controller_axes = result.axis
            elif info.com == StpMtrController.STOP_AXIS.name:
                result: FuncStopAxisOutput = result
                self.controller_axes = result.axis
                self._update_progressbar_pos(force=True)
            return result
        super(StepMotorsView, self).model_is_changed(msg, func_local=func_local)

    def stop_axis(self):
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncStopAxisInput(axis_id=self.selected_device_id))
        self.send_msg(msg)
        self._asked_status = 0

    def update_state(self, force_device=True, force_ctrl=True):
        device: AxisStpMtr = super(StepMotorsView, self).update_state(force_device, force_ctrl)

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

        cs = self.device_ctrl_state
        ui = self.ui

        if cs.devices != cs.devices_previous or force_device:
            ui.label_ranges.setText(str(device.limits))
            ui.label_preset.setText(str(device.preset_values))

        if force_device:
            # TODO: this is stange...strange activation of update_lcd_screen()
            if MoveType.step in device.type_move or MoveType.microstep in device.type_move:
                ui.radioButton_stp.setEnabled(True)
                ui.radioButton_stp.setChecked(True)
            else:
                ui.radioButton_stp.setEnabled(False)

            if MoveType.angle in device.type_move:
                ui.radioButton_angle.setEnabled(True)
                ui.radioButton_angle.setChecked(True)
            else:
                ui.radioButton_angle.setEnabled(False)

            if MoveType.mm in device.type_move:
                ui.radioButton_mm.setEnabled(True)
                ui.radioButton_mm.setChecked(True)
            else:
                ui.radioButton_mm.setEnabled(False)

        self._update_progressbar_pos(device)
        self._update_lcd_screen()

    def _update_lcd_screen(self):
        unit = self._get_unit()
        axis: AxisStpMtr = self.device_ctrl_state.devices[self.selected_device_id]
        pos = axis.convert_pos_to_unit(unit)
        self.ui.lcdNumber_position.display(pos)

    def _update_progressbar_pos(self, axis: AxisStpMtr, force=False):
        try:
            pos = axis.convert_pos_to_unit(self._get_unit())
        except KeyError:
            pos = axis.position
        if (axis.status == 2 or force) and self.selected_device_id == axis.device_id_seq:
            start = self.device_ctrl_state.start_stop[axis.device_id_seq][0]
            stop = self.device_ctrl_state.start_stop[axis.device_id_seq][1]
            if (stop-start) != 0:
                per = int((pos - start) / (stop - start) * 100.0)
                self.ui.progressBar_movement.setValue(per)
                self.ui.lcdNumber_position.display(pos)

    def _get_unit(self) -> MoveType:
        rb_dict = {self.ui.radioButton_angle: MoveType.angle, self.ui.radioButton_stp: MoveType.step,
                   self.ui.radioButton_mm: MoveType.mm}
        for rb, unit in rb_dict.items():
            if rb.isChecked():
                return unit
        axis = self.device_ctrl_state.devices[self.selected_device_id]
        return axis.basic_unit
