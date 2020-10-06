"""
Created on 22.09.2020

@author: saldenisov
"""
import logging
from _functools import partial
from typing import Dict, Union
from PyQt5.QtWidgets import QCheckBox, QLCDNumber, QLayout

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

            def set_new_widgets(layout: QLayout, daqmx_tasks: Dict[Union[int, str], DAQmxTask],
                                tasks: Dict[int, Union[QCheckBox, QLCDNumber]]):
                for task_id, task in daqmx_tasks.items():
                    task_type = task.task_type
                    if task_type == 'DigitalOut':
                        widget = QCheckBox(text=task.name)
                        widget.setChecked(task.value)
                        widget.setCheckable(True)
                    elif task_type == 'DigitalIn':
                        widget = QCheckBox(text=task.name)
                        widget.setChecked(task.value)
                        widget.setCheckable(False)
                        widget.clicked.connect(partial(self.set_output, task_id))
                    elif task_type in ['AIVoltage', 'AICurrent']:
                        widget = QLCDNumber()
                        if type(task.value) in [int, float]:
                            widget.display(str(task.value))
                    elif task_type in ['CounterInput']:
                        widget = QLCDNumber()
                        if type(task.value) in [int, float]:
                            widget.display(str(task.value))
                    layout.addWidget(widget)
                    tasks[task_id] = widget

            def set_widgets(daqmx_tasks: Dict[Union[int, str], DAQmxTask],
                            tasks: Dict[int, Union[QCheckBox, QLCDNumber]]):
                for task_id, task in daqmx_tasks.items():
                    widget = tasks[task_id]
                    if isinstance(widget, QCheckBox):
                        widget.setChecked(bool(task.value))
                    elif isinstance(widget, QLCDNumber):
                        if type(task.value) in [int, float]:
                            widget.display(str(task.value))

            if cs.devices != cs.devices_previous or force_device:
                if force_device:
                    self.clean_layout(ui.horizontalLayout_daqmx_channels)
                    set_new_widgets(ui.horizontalLayout_daqmx_channels, daqmx.tasks, self.tasks)
                else:
                    if not (set(daqmx.tasks.keys()) - set(self.output_checkboxes.keys())):
                        set_widgets(ui.horizontalLayout_pdu_outputs, daqmx.tasks, self.tasks)
                    else:
                        self.clean_layout(ui.horizontalLayout_daqmx_channels)
                        set_new_widgets(ui.horizontalLayout_daqmx_channels, daqmx.tasks, self.tasks)


        daqmx: DAQmxCard = super(DAQmxView, self).update_state(force_device, force_ctrl, func=update_func_local)
