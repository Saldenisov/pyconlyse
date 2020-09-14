"""
Created on 15.11.2019

@author: saldenisov
"""
import logging
from typing import Union

from PyQt5.QtWidgets import QMainWindow

from communication.messaging.messages import MessageInt, MessageExt, MsgComInt, MsgComExt
from devices.devices import Server, Service
from gui.views.ui.SuperUser import Ui_SuperUser
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.myfunc import info_msg, get_local_ip, error_logger

module_logger = logging.getLogger(__name__)


class SuperUserView(QMainWindow):

    def __init__(self, in_controller, in_model, parent=None):
        super().__init__()
        self.name = 'SuperUserGUI:view: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model
        self._hb_counter = 0

        self.ui = Ui_SuperUser()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.pB_connection.clicked.connect(self.controller.create_service_gui)
        self.ui.lW_devices.itemDoubleClicked.connect(self.controller.lW_devices_double_clicked)
        self.ui.pB_checkServices.clicked.connect(self.controller.pB_checkServices_clicked)
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')

    def closeEvent(self, event):
        info_msg(self,'INFO', f'{self.name} is closing.')
        self.controller.quit_clicked(event, total_close=True)

    def model_is_changed(self, msg: Union[MessageInt, MessageExt]):
        com = msg.com
        info = msg.info
        try:
            if com == MsgComInt.HEARTBEAT.msg_name:
                hB1 = self.ui.radioButton_hB
                hB2 = self.ui.radioButton_hB2
                hb_s = hB1.isChecked()
                if hb_s:
                   hB2.setChecked(True)
                else:
                   hB1.setChecked(True)
            elif com == MsgComInt.DONE_IT.msg_name:
                info: Union[DoneIt, MsgError] = info
                if info.com == Server.GET_AVAILABLE_SERVICES.name:
                    result: FuncAvailableServicesOutput = info
                    widget = self.ui.lW_devices
                    widget.clear()
                    names = []
                    for key, item in result.device_available_services.items():
                        names.append(f'{key}')
                        client = self.model.superuser
                        msg = client.generate_msg(msg_com=MsgComExt.DO_IT, receiver_id=client.server_id, forward_to=key,
                                                  func_input=FuncServiceInfoInput())
                        client.send_msg_externally(msg)
                    widget.addItems(names)
                    self.model.superuser.running_services = result.device_available_services
                elif info.com == Service.SERVICE_INFO.name:
                    info: FuncServiceInfoOutput = info
                    self.model.service_parameters[info.device_id] = info.service_info
                    self.ui.tE_info.setText(str(info.service_info))
                    self.controller.create_service_gui(info.device_id)
            elif com == MsgComInt.FYI.msg_name:
                if msg.sender_id == self.model.superuser.id:
                    text = f'SENDING: {msg.fyi_repr()}.'
                else:
                    text = f'RECEIVED: {msg.fyi_repr()}.'
                self.model.superuser._fyi_msg_dict[msg.id] = msg
                self.ui.lineEdit_msg.setText(text)
        except Exception as e:
            error_logger(self, self.model_is_changed, f'{self.name}: {e}')
