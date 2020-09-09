"""
Created on 07.09.2020

@author: saldenisov
"""
import copy
import logging
from _functools import partial
from abc import abstractmethod
from typing import Callable, Dict, Union

from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow

from communication.messaging.messages import MessageInt, MessageExt, MsgComExt, MsgComInt
from devices.devices import Device, Client, Service
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceInfoExt, DeviceControllerState,
                                                                        DoneIt, MsgError,
                                                                        FuncActivateInput, FuncActivateOutput,
                                                                        FuncActivateDeviceInput,
                                                                        FuncActivateDeviceOutput,
                                                                        FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput,
                                                                        FuncPowerInput, FuncPowerOutput,
                                                                        HardwareDevice, HardwareDeviceEssentials)
from utilities.myfunc import info_msg, get_local_ip, error_logger

module_logger = logging.getLogger(__name__)


class DeviceControllerView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: DeviceInfoExt, ui_class: Callable, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.device_ctrl_state = DeviceControllerState(devices=service_parameters.device_description.hardware_devices,
                                                       controller_status=service_parameters.controller_status)
        self.name = f'{self.__class__.__name__}:View:{service_parameters.device_id}:{get_local_ip()}'
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.superuser: Client = self.model.superuser
        self.service_parameters: DeviceInfoExt = service_parameters

        self.ui = ui_class()
        self.ui.setupUi(self)
        self.setWindowTitle(service_parameters.device_description.GUI_title)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.spinBox_device_id.valueChanged.connect(partial(self.update_state, *[True, False]))
        self.ui.checkBox_ctrl_activate.clicked.connect(self.activate_controller)
        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.checkBox_device_activate.clicked.connect(self.activate_device)
        self.ui.closeEvent = self.closeEvent
        # Extra ui init
        self.extra_ui_init()

        self.update_state(force_device=True, force_ctrl=True)

        self.get_controller_state()

        info_msg(self, 'INITIALIZED')

    def activate_controller(self):
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_ctrl_activate.isChecked()))
        self.send_msg(msg)
        self._asked_status = 0

    def activate_device(self):
        flag = 1 if self.ui.checkBox_device_activate.isChecked() else 0
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateDeviceInput(device_id=self.selected_device_id,
                                                                     flag=flag))
        self.send_msg(msg)
        self._asked_status = 0

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    @property
    def controller_devices(self) -> Dict[int, HardwareDevice]:
        return self.device_ctrl_state.devices

    @controller_devices.setter
    def controller_devices(self, value: Union[Dict[int, HardwareDeviceEssentials], Dict[int, HardwareDevice],
                                           HardwareDevice, HardwareDeviceEssentials]):
        try:
            if isinstance(value, dict):
                if isinstance(next(iter(value.values())), HardwareDevice):
                    self.device_ctrl_state.devices = value
                else:
                    for device_id, device in value.items():
                        self.device_ctrl_state.devices[device_id].status = device.status
                        self.device_ctrl_state.devices[device_id].position = device.position
            elif isinstance(value, HardwareDevice):
                self.device_ctrl_state.devices[value.device_id_seq] = value
            elif isinstance(value, HardwareDeviceEssentials):
                self.device_ctrl_state.devices[value.device_id_seq].status = value.status
                self.device_ctrl_state.devices[value.device_id_seq].position = value.position
            else:
                raise Exception(f'Unknown value type: {type(value)}.')
        except Exception as e:
            error_logger(self, self.controller_devices, e)

    def get_controller_state(self):
        msg = self.superuser.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.superuser.server_id,
                                          forward_to=self.service_parameters.device_id,
                                          func_input=FuncGetControllerStateInput())
        self.send_msg(msg)

    @property
    def selected_device_id(self) -> int:
        return self.ui.spinBox_device_id.value()

    @abstractmethod
    def extra_ui_init(self):
        pass

    @abstractmethod
    def model_is_changed(self, msg: MessageInt, func_local: Callable):
        try:
            if self.service_parameters.device_id == msg.forwarded_from or \
                    self.service_parameters.device_id == msg.sender_id:
                com = msg.com
                info: Union[DoneIt, MsgError] = msg.info
                if com == MsgComInt.DONE_IT.msg_name:
                    result = info
                    if result.func_success:
                        client = self.superuser
                        if info.com == Service.ACTIVATE.name:
                            result: FuncActivateOutput = result
                            if result.controller_status.active:
                                msg = client.generate_msg(msg_com=MsgComExt.DO_IT,
                                                          receiver_id=self.service_parameters.device_id,
                                                          func_input=FuncGetControllerStateInput())
                                self.send_msg(msg)
                            self.device_ctrl_state.controller_status = result.controller_status
                        elif info.com == Service.ACTIVATE_DEVICE.name:
                            result: FuncActivateDeviceInput = result
                            self.controller_devices = result.device
                        elif info.com == Service.GET_CONTROLLER_STATE.name:
                            result: FuncGetControllerStateOutput = result
                            self.device_ctrl_state.devices = result.devices_hardware
                            self.device_ctrl_state.controller_status = result.controller_status
                        elif info.com == Service.POWER.name:
                            result: FuncPowerOutput = result
                            self.device_ctrl_state.controller_status = result.controller_status
                        result = func_local(info)
                    self.ui.comments.setText(result.comments)
                elif com == MsgComInt.ERROR.msg_name:
                    self.ui.comments.setText(info.comments)
                    client = self.superuser
                    msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                              forward_to=self.service_parameters.device_id,
                                              func_input=FuncGetControllerStateInput())
                    self.send_msg(msg)
                self.update_state()
        except Exception as e:
            error_logger(self, self.model_is_changed, f'{e}:{msg}')

    def power(self):
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncPowerInput(flag=self.ui.checkBox_power.isChecked()))
        client.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_controller_state, delay=1, n_max=1)

        self.send_msg(msg)

    def send_msg(self, msg: MessageExt):
        self.superuser.send_msg_externally(msg)

    @abstractmethod
    def update_state(self, force_device=False, force_ctrl=False):
        device_state = self.device_ctrl_state
        ui = self.ui
        device: HardwareDevice = device_state.devices[self.selected_device_id]
        if device_state.controller_status != device_state.controller_status_previous or force_ctrl:
            ui.checkBox_power.setChecked(device_state.controller_status.power)
            ui.checkBox_ctrl_activate.setChecked(device_state.controller_status.active)
            ui.checkBox_device_activate.setChecked(device.status)
            self.device_ctrl_state.controller_status_previous = copy.deepcopy(self.device_ctrl_state.controller_status)

        if device_state.devices != device_state.devices_previous or force_device:
            device_id_list = list(device_state.devices.keys())
            ui.spinBox_device_id.setMinimum(min(device_id_list))
            ui.spinBox_device_id.setMaximum(max(device_id_list))
            if self.selected_device_id not in device_id_list:
                ui.spinBox_device_id.setValue(min(device_id_list))

            ui.checkBox_device_activate.setChecked(device.status)
            _translate = QtCore.QCoreApplication.translate
            ui.label_device_id.setText('DeviceID')
            if device.friendly_name:
                name = device.friendly_name
            else:
                name = device.name

            ui.label_name.setText(f'Name: {name}')
            ui.checkBox_device_activate.setChecked(device.status)
            self.device_ctrl_state.axes_previous = copy.deepcopy(device_state.devices)
        return device

