"""
Created on 07.09.2020

@author: saldenisov
"""
import copy
import logging
from _functools import partial
from abc import abstractmethod
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QErrorMessage
from typing import Callable
from communication.messaging.messages import *
from devices.devices import Device, Client
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController
from gui.views.ui import Ui_StpMtrGUI
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.stpmtr_dataclass import *
from utilities.datastructures.mes_independent.stpmtr_dataclass import mm, microstep
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

        msg = self.superuser.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=self.superuser.server_id,
                                          forward_to=self.service_parameters.device_id,
                                          func_input=FuncGetControllerStateInput())
        self.send_msg(msg)
        info_msg(self, 'INITIALIZED')

    def activate_controller(self):
        client = self.superuser
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        client.send_msg(msg)
        self._asked_status = 0

    def activate_device(self):
        flag = 1 if self.ui.checkBox_device_on.isChecked() else 0
        client = self.device
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncActivateDeviceInput(device_id=int(self.ui.spinBox_device_id.value()),
                                                                     flag=flag))
        client.send_msg_externally(msg)
        self._asked_status = 0

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

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
                    self.ui.comments.setText(result.comments)
                    if result.func_success:
                        client = self.superuser
                        if info.com == StpMtrController.ACTIVATE.name:
                            result: FuncActivateOutput = result
                            if result.controller_status.active:
                                msg = client.generate_msg(msg_com=MsgComExt.DO_IT,
                                                          receiver_id=self.service_parameters.device_id,
                                                          func_input=FuncGetControllerStateInput())
                                self.send_msg(msg)
                            self.device_ctrl_state.controller_status = result.controller_status
                        elif info.com == StpMtrController.ACTIVATE_DEVICE.name:
                            result: FuncActivateDeviceInput = result
                            self.controller_axes = result.device
                        elif info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                            result: FuncGetControllerStateOutput = result
                            self.device_ctrl_state.devices = result.devices_hardware
                            self.device_ctrl_state.controller_status = result.controller_status
                        elif info.com == StpMtrController.POWER.name:
                            result: FuncPowerOutput = result
                            self.device_ctrl_state.controller_status = result.co

                        func_local(info)
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
        self.send_msg(msg)

    def send_msg(self, msg: MessageExt):
        self.superuser.send_msg_externally(msg)

    @abstractmethod
    def update_state(self, force_device=False, force_ctrl=False):
        device_state = self.device_ctrl_state
        ui = self.ui
        device_id = ui.spinBox_device_id.value()
        device: HardwareDevice = device_state.devices[device_id]
        if device_state.controller_status != device_state.controller_status_previous or force_ctrl:
            ui.checkBox_power.setChecked(device_state.controller_status.power)
            ui.checkBox_ctrl_activate.setChecked(device_state.controller_status.active)
            ui.checkBox_device_activate.setChecked(device.status)
            self.device_ctrl_state.controller_status_previous = copy.deepcopy(self.device_ctrl_state.controller_status)

        if device_state.devices != device_state.devices_previous or force_device:
            device_id_list = list(device_state.devices.keys())
            ui.spinBox_device_id.setMinimum(min(device_id_list))
            ui.spinBox_device_id.setMaximum(max(device_id_list))
            if ui.spinBox_device_id.value() not in device_id_list:
                ui.spinBox_device_id.setValue(min(device_id_list))

            ui.checkBox_device_activate.setChecked(device.status)
            _translate = QtCore.QCoreApplication.translate
            ui.label_device_id.setText('DeviceID')
            if device.friendly_name:
                name = device.friendly_name
            else:
                name = device.name

            ui.label_name.setText('name')
            self.device_ctrl_state.axes_previous = copy.deepcopy(cs.axes)
        return device

