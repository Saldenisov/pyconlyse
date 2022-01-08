'''
Created on 15.11.2019

@author: saldenisov
'''
import logging
from random import randint
from _functools import partial
from typing import Dict, List, Union
from time import sleep
from PyQt5.QtWidgets import (QMenu, QErrorMessage, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QRadioButton, QGroupBox)
from PyQt5 import QtCore, QtWidgets
from communication.messaging.messages import MsgComExt, MessageInt
from devices.datastruct_for_messaging import *
from devices.devices import Device, HardwareDeviceDict, HardwareDevice
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ClientsGUIViews.DeviceCtrlClient import DeviceControllerView
from gui.views.ui import Ui_StpMtrGUI
from utilities.myfunc import error_logger

module_logger = logging.getLogger(__name__)


class StepMotorsView(DeviceControllerView):

    def __init__(self, **kwargs):
        kwargs['ui_class'] = Ui_StpMtrGUI
        super().__init__(**kwargs)
        self.device_ctrl_state.start_stop = {}

    def menu_actuator(self, button: str, point):
        menu = QMenu()
        action_displacement_tens = menu.addAction('0.1')
        action_displacement_half = menu.addAction('0.5')
        action_displacement_one = menu.addAction('1')
        action_displacement_two = menu.addAction('2')
        action_displacement_five = menu.addAction('5')
        action_displacement_ten = menu.addAction('10')
        action_displacement_twenty = menu.addAction('20')
        action_displacement_fifty = menu.addAction('50')
        action_displacement_hundred = menu.addAction('100')

        if button == 'increase':
            action = menu.exec_(self.ui.pB_increase.mapToGlobal(point))
        elif button == 'decrease':
            action = menu.exec_(self.ui.pB_decrease.mapToGlobal(point))
        else:
            action = None

        if action == action_displacement_tens:
            self._increment = 0.1
        elif action == action_displacement_half:
            self._increment = 0.5
        elif action == action_displacement_one:
            self._increment = 1
        elif action == action_displacement_two:
            self._increment = 2
        elif action == action_displacement_five:
            self._increment = 5
        elif action == action_displacement_ten:
            self._increment = 10
        elif action == action_displacement_twenty:
            self._increment = 20
        elif action == action_displacement_fifty:
            self._increment = 50
        elif action == action_displacement_hundred:
            self._increment = 100

    @property
    def controller_axes(self):
        return self.controller_devices

    @controller_axes.setter
    def controller_axes(self, value: Union[Dict[int, AxisStpMtr], AxisStpMtr]):
        self.controller_devices = value

    def extra_ui_init(self, groups, sets):
        self._increment = 1
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.pushButton_stop.clicked.connect(self.stop_axis)
        self.ui.pushButton_set.clicked.connect(self.set_pos_axis)
        self.ui.radioButton_stp.toggled.connect(self._update_lcd_screen)
        self.ui.radioButton_mm.toggled.connect(self._update_lcd_screen)
        self.ui.radioButton_angle.toggled.connect(self._update_lcd_screen)
        self.ui.pB_increase.clicked.connect(partial(self._incremental_pB_clicked, 1))
        self.ui.pB_decrease.clicked.connect(partial(self._incremental_pB_clicked, -1))

        self.ui.pB_increase.customContextMenuRequested.connect(partial(self.menu_actuator, 'increase'))
        self.ui.pB_decrease.customContextMenuRequested.connect(partial(self.menu_actuator, 'decrease'))

        if groups:
            hardware_devices: HardwareDeviceDict = self.service_parameters.device_description.hardware_devices
            for group in groups:
                group_name = '_'.join(group)
                vlayout_group = QVBoxLayout()
                setattr(self.ui, f'vlayout_group_{group_name}', vlayout_group)
                for device_id in group:
                    try:
                        a, b = randint(0, 100), randint(0, 100)
                        device: HardwareDevice = hardware_devices[device_id]

                        label = QLabel(device.friendly_name)
                        setattr(self.ui, f'label_{device.device_id}_{a}_{b}', label)

                        # layout buttons
                        hlayout_buttons = QHBoxLayout()
                        setattr(self.ui, f'hlayout_buttons_{device_id}_{a}_{b}', hlayout_buttons)

                        # pB increase
                        pB_increase = QPushButton(text='+', parent=self.ui.centralwidget)

                        pB_increase.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                        sizePolicy.setHorizontalStretch(0)
                        sizePolicy.setVerticalStretch(0)
                        sizePolicy.setHeightForWidth(pB_increase.sizePolicy().hasHeightForWidth())
                        pB_increase.setSizePolicy(sizePolicy)
                        pB_increase.setMaximumSize(QtCore.QSize(25, 16777215))
                        pB_increase.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                        object_name = f'pB_increase_{device.device_id}_{a}_{b}'
                        pB_increase.setObjectName(object_name)
                        pB_increase.customContextMenuRequested.connect(partial(self.menu_actuator, 'increase'))
                        pB_increase.clicked.connect(partial(self._pB_group_clicked, 1, device.device_id_seq))
                        setattr(self.ui, object_name, pB_increase)

                        # pB decrease
                        pB_decrease = QPushButton(text='-', parent=self.ui.centralwidget)

                        pB_decrease.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
                        sizePolicy.setHorizontalStretch(0)
                        sizePolicy.setVerticalStretch(0)
                        sizePolicy.setHeightForWidth(pB_decrease.sizePolicy().hasHeightForWidth())
                        pB_decrease.setSizePolicy(sizePolicy)
                        pB_decrease.setMaximumSize(QtCore.QSize(25, 16777215))
                        pB_decrease.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                        object_name = f'pB_decrease_{device.device_id}_{a}_{b}'
                        pB_decrease.setObjectName(object_name)
                        pB_decrease.customContextMenuRequested.connect(partial(self.menu_actuator, 'decrease'))
                        pB_decrease.clicked.connect(partial(self._pB_group_clicked, -1, device.device_id_seq))
                        setattr(self.ui, object_name, pB_decrease)

                        hlayout_buttons.addWidget(pB_decrease)
                        hlayout_buttons.addWidget(pB_increase)
                        hlayout_buttons.addWidget(label)

                        vlayout_group.addLayout(hlayout_buttons)
                    except KeyError:
                        pass

                self.ui.horizontalLayout_groups.addLayout(vlayout_group)
        if sets:
            group = QGroupBox(title='Sets', parent=self.ui.centralwidget)
            setattr(self.ui, 'groupbox_sets', group)
            HL = QHBoxLayout(group)
            setattr(self.ui, 'HL_sets', HL)
            for name, set_values in sets.items():
                widget = QRadioButton(text=name, parent=group)
                HL.addWidget(widget)
                setattr(self.ui, f'set_{name}', widget)
                widget.toggled.connect(partial(self._run_sets_pos, set_values))

            self.ui.horizontalLayout_sets.addWidget(group)

    def get_pos_axis(self, axis_id=None, with_return=False):
        if axis_id is None:
            axis_id = int(self.ui.spinBox_device_id.value())
        client = self.superuser
        service_id = self.service_parameters.device_id
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id(service_id),
                                  forward_to=service_id,
                                  func_input=FuncGetPosInput(axis_id))
        self.send_msg(msg)
        if with_return:
            return True if self.device_ctrl_state.devices[axis_id].status == 2 else False

    def set_pos_axis(self, axis_id=None):
        try:
            axis_pos = float(self.ui.lineEdit_value.text())
            client = self.superuser
            service_id = self.service_parameters.device_id
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id(service_id),
                                      forward_to=service_id,
                                      func_input=FuncSetPosInput(self.selected_device_id, axis_pos, self._get_unit()))
            self.send_msg(msg)
        except (TypeError, ValueError) as e:
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
            service_id = self.service_parameters.device_id
            msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id(service_id),
                                      forward_to=service_id,
                                      func_input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how,
                                                                     move_type=self._get_unit()))
            self.send_msg(msg)

            self.device_ctrl_state.start_stop[axis_id] = [self.device_ctrl_state.devices[axis_id].position, pos]
            self.device_ctrl_state.devices[axis_id].status = 2
            self.ui.progressBar_movement.setValue(0)
            #client.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos_axis, delay=1, n_max=3,
            #                      specific={'axis_id': axis_id, 'with_return': True})
            self._asked_status = 0
        except (ValueError, TypeError) as e:
            comments = f'Pos "{pos}" has wrong format: {e}.'
            error_logger(self, self.move_axis, comments)
            error_dialog = QErrorMessage()
            error_dialog.showMessage(comments)
            error_dialog.exec_()

    def model_is_changed(self, msg: MessageInt) -> DoneIt:
        def func_local(info: Union[DoneIt]):
            result = info
            if info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                if not self.device_ctrl_state.start_stop:
                    for device in self.device_ctrl_state.devices.values():
                        self.device_ctrl_state.start_stop[device.device_id_seq] = (0, 0)
            elif info.com == StpMtrController.MOVE_AXIS_TO.name:
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
        service_id = self.service_parameters.device_id
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id(service_id),
                                  forward_to=service_id,
                                  func_input=FuncStopAxisInput(axis_id=self.selected_device_id))
        self.send_msg(msg)
        self._asked_status = 0

    def update_state(self, force_device=True, force_ctrl=True):

        def update_func_local(self, force_device=True, force_ctrl=True):
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
            device: AxisStpMtr = cs.devices[self.selected_device_id]

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

        super(StepMotorsView, self).update_state(force_device, force_ctrl, update_func_local)

    def _run_sets_pos(self, set_values: Dict[str, float]):
        if isinstance(set_values, dict):
            hardware_devices: HardwareDeviceDict = self.service_parameters.device_description.hardware_devices
            for device_id, pos in set_values.items():
                self.ui.comments.setText('Moving...')
                self.ui.radioButton_absolute.setChecked(True)
                self.ui.lineEdit_value.setText(str(pos))
                device: HardwareDevice = hardware_devices[device_id]
                self.ui.spinBox_device_id.setValue(device.device_id_seq)
                self.move_axis()
                sleep(0.5)

        else:
            error_logger(self, self._run_sets_pos, f'set_values are not correctly set: {set_values}.')

    def _update_lcd_screen(self):
        unit = self._get_unit()
        axis: AxisStpMtr = self.device_ctrl_state.devices[self.selected_device_id]
        pos = axis.convert_pos_to_unit(unit)
        if isinstance(pos, int) or isinstance(pos, float):
            self.ui.lcdNumber_position.display(pos)
        else:
            error_logger(self, self._update_lcd_screen, f'Not int or float, but {type(pos)}')

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

    def _incremental_pB_clicked(self, direction: int):
        self.ui.radioButton_relative.setChecked(True)
        self.ui.radioButton_stp.setChecked(True)
        self.ui.lineEdit_value.setText(str(self._increment * direction))
        self.move_axis()

    def _pB_group_clicked(self, direction: int, axis_id: int):
        self.ui.spinBox_device_id.setValue(axis_id)
        if not self.device_ctrl_state.devices[self.selected_device_id].status:
            self.ui.checkBox_device_activate.setChecked(True)
            self.activate_device()
            sleep(0.05)
        self._incremental_pB_clicked(direction)