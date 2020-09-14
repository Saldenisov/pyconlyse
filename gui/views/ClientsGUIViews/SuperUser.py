"""
Created on 15.11.2019

@author: saldenisov
"""
import logging
from copy import deepcopy
from datetime import datetime as dt
from threading import Thread
from time import sleep
from typing import Union
from PyQt5.QtWidgets import QMainWindow, QListWidgetItem

from communication.messaging.messages import MessageInt, MessageExt, MsgComInt, MsgComExt
from devices.devices import Server, Service, Client
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
        self.msg_vis_thread = Thread(target=self.update_msg_list)
        self.msg_vis_thread.start()
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
                superuser: Client = self.model.superuser
                priority_dict = {MsgComInt.HEARTBEAT.msg_name: 1, MsgComInt.ERROR.msg_name: 5,
                                 MsgComInt.DONE_IT.msg_name: 3, MsgComInt.DEVICE_INFO_INT.msg_name: 4}
                superuser._fyi_msg_dict[msg.id] = msg


        except Exception as e:
            error_logger(self, self.model_is_changed, f'{self.name}: {e}')

    def update_msg_list(self):
        superuser: Client = self.model.superuser

        def get_oldest(superuser: Client, older=0):
            timestamp_now = dt.timestamp(dt.now())
            id_msg_oldest = None
            oldest_time = older
            for msg_id, value in superuser._fyi_msg_dict.items():
                a = timestamp_now - (value.time_creation - value.time_bonus)
                if (timestamp_now - (value.time_creation - value.time_bonus)) > oldest_time:
                    id_msg_oldest = msg_id
                    oldest_time = value.time_creation - value.time_bonus

            return id_msg_oldest
        redraw = True
        while superuser.ctrl_status.messaging_on:

            if len(superuser._fyi_msg_dict) > 13:
                id_msg_oldest = get_oldest(superuser)
                if not id_msg_oldest:
                    id_msg_oldest = superuser._fyi_msg_dict.popitem(last=False)[0]
                redraw = True
                del superuser._fyi_msg_dict[id_msg_oldest]

            id_msg_oldest = get_oldest(superuser, older=5)
            if id_msg_oldest:
                del superuser._fyi_msg_dict[id_msg_oldest]
                redraw = True
                if not superuser._fyi_msg_dict:
                    self.ui.listWidget_msg.clear()

            if superuser._fyi_msg_dict:
                if redraw:
                    self.ui.listWidget_msg.clear()
                    for value in superuser._fyi_msg_dict.values():
                        time = dt.fromtimestamp(value.time_creation)
                        self.ui.listWidget_msg.addItem(
                            QListWidgetItem(f'{time.strftime("%H:%M:%S")}_{value.fyi_repr()}'))
                redraw = False

            sleep(0.5)