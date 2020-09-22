"""
Created on 08.09.2020

@author: saldenisov
"""
import logging
from _functools import partial
from typing import Dict, Union
from PyQt5.QtWidgets import QCheckBox

from communication.messaging.messages import MessageInt, MsgComExt
from devices.datastruct_for_messaging import *
from devices.service_devices.pdu.pdu_controller import PDUController
from gui.views.ClientsGUIViews.DeviceCtrlClient import DeviceControllerView
from gui.views.ui import Ui_PDUs

module_logger = logging.getLogger(__name__)


class PDUsView(DeviceControllerView):

    def __init__(self, **kwargs):
        self.output_checkboxes: Dict[int, QCheckBox] = {}
        kwargs['ui_class'] = Ui_PDUs
        super().__init__(**kwargs)

    def extra_ui_init(self):
        pass

    @property
    def controller_pdus(self):
        return self.controller_devices

    @controller_pdus.setter
    def controller_pdus(self, value: Union[Dict[int, PDUEssentials], Dict[int, PDU],
                                           PDU, PDUEssentials]):
        self.controller_devices = value

    def model_is_changed(self, msg: MessageInt):
        def func_local(info: Union[DoneIt]) -> DoneIt:
            result = info
            if info.com == PDUController.GET_PDU_STATE.name:
                result: FuncGetPDUStateOutput = result
                self.controller_pdus = result.pdu
            elif info.com == PDUController.SET_PDU_STATE.name:
                result: FuncGetPDUStateOutput = result
                self.controller_pdus = result.pdu
            return result
        super(PDUsView, self).model_is_changed(msg, func_local=func_local)

    def set_output(self, output_id: Union[int, str]):
        from copy import deepcopy
        client = self.superuser
        state = int(self.output_checkboxes[output_id].isChecked())
        pdu_output: PDUOutput = deepcopy(self.controller_pdus[self.selected_device_id].outputs[output_id])
        pdu_output.state = state
        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id,
                                  forward_to=self.service_parameters.device_id,
                                  func_input=FuncSetPDUStateInput(pdu_id=self.selected_device_id,
                                                                  pdu_output_id=output_id,
                                                                  output=pdu_output))
        self.send_msg(msg)
        self._asked_status = 0

    def update_state(self, force_device=False, force_ctrl=False):

        def update_func_local(self, force_device=False, force_ctrl=False):
            cs = self.device_ctrl_state
            ui = self.ui
            pdu: PDU = cs.devices[self.selected_device_id]

            if force_device:
                pass

            if cs.devices != cs.devices_previous or force_device:
                for i in reversed(range(ui.horizontalLayout_pdu_outputs.count())):
                    ui.horizontalLayout_pdu_outputs.itemAt(i).widget().deleteLater()

                for output_id, output in pdu.outputs.items():
                    checkbox = QCheckBox(text=output.name)
                    checkbox.setChecked(bool(output.state))
                    checkbox.clicked.connect(partial(self.set_output, output_id))
                    ui.horizontalLayout_pdu_outputs.addWidget(checkbox)
                    self.output_checkboxes[output_id] = checkbox

        pdu: PDU = super(PDUsView, self).update_state(force_device, force_ctrl, func=update_func_local)





