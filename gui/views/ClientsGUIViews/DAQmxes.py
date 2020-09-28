"""
Created on 22.09.2020

@author: saldenisov
"""
import logging
from _functools import partial
from typing import Dict, Union
from PyQt5.QtWidgets import QCheckBox, QLCDNumber

from communication.messaging.messages import MessageInt, MsgComExt
from devices.datastruct_for_messaging import *
from devices.service_devices.daqmx.datastruct_for_messaging import *
from devices.service_devices.daqmx.daqmx_controller import DAQmxController
from gui.views.ClientsGUIViews.DeviceCtrlClient import DeviceControllerView
from gui.views.ui import Ui_DAQmxs

module_logger = logging.getLogger(__name__)


class DAQmxView(DeviceControllerView):

    def __init__(self, **kwargs):
        self.tasks: Dict[int, Union[QCheckBox, QLCDNumber]] = {}
        kwargs['ui_class'] = Ui_DAQmxs
        super().__init__(**kwargs)

    def extra_ui_init(self):
        pass

    @property
    def controller_daqmxes(self):
        return self.controller_devices

    @controller_daqmxes.setter
    def controller_daqmxes(self, value: Union[Dict[int, DAQmxCard], Dict[int, DAQmxCardEssentials],
                                              DAQmxCard, DAQmxCardEssentials]):
        self.controller_devices = value

    def model_is_changed(self, msg: MessageInt):
        def func_local(info: Union[DoneIt]) -> DoneIt:
            result = info
            if info.com == DAQmxController.READ_CHANNEL.name:
                result: FuncGetPDUStateOutput = result
                self.controller_daqmxes = result.pdu
            elif info.com == DAQmxController.WRITE_CHANNEL.name:
                result: FuncGetPDUStateOutput = result
                self.controller_daqmxes = result.pdu
            return result
        super(DAQmxView, self).model_is_changed(msg, func_local=func_local)

    def set_output(self, task_id: Union[int, str]):
        pass

    def update_state(self, force_device=False, force_ctrl=False):

        def update_func_local(self, force_device=False, force_ctrl=False):
            cs = self.device_ctrl_state
            ui = self.ui
            daqmx: DAQmxCard = cs.devices[self.selected_device_id]

            if force_device:
                pass

            if cs.devices != cs.devices_previous or force_device:
                for i in reversed(range(ui.horizontalLayout_daqmx_channels.count())):
                    ui.horizontalLayout_daqmx_channels.itemAt(i).widget().deleteLater()

                for task_id, task in daqmx.tasks.items():
                    task_type = task.task_type
                    if task_type == 'DigitalOut':
                        widget = QCheckBox(text=task.name)
                        widget.setChecked(task.value)
                        widget.setCheckable(False)

                    elif task_type == 'DigitalIn':
                        widget = QCheckBox(text=task.name)
                        widget.setCheckable(True)
                        widget.setChecked(task.value)
                        widget.clicked.connect(partial(self.set_output, task_id))

                    elif task_type in ['AIVoltage', 'AICurrent']:
                        widget = QLCDNumber()
                    elif task_type in ['CounterInput']:
                        widget = QLCDNumber()

                    ui.horizontalLayout_daqmx_channels.addWidget(widget)
                    self.tasks[task_id] = widget

        daqmx: DAQmxCard = super(DAQmxView, self).update_state(force_device, force_ctrl, func=update_func_local)





