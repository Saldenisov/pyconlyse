"""
Created on 15.11.2019

@author: saldenisov
"""
import logging

from PyQt5.QtWidgets import QMainWindow
from typing import Union

from communication.messaging.messages import MessageInt, MessageExt, MsgComInt, MsgComExt
from datastructures.mes_independent.devices_dataclass import *
from devices.devices import Server, Service
from gui.views.ui.SuperUser_ui import Ui_SuperUser
from utilities.myfunc import info_msg,  get_local_ip, error_logger

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
        a = 2

    def closeEvent(self, event):
        info_msg(self,'INFO', f'{self.name} is closing.')
        self.controller.quit_clicked(event, total_close=True)

    def model_is_changed(self, msg: Union[MessageInt, MessageExt]):
        com = msg.com
        info = msg.info
        try:
            if com == MsgComInt.HEARTBEAT.msg_name:
                widget1 = self.ui.rB_hb
                widget2 = self.ui.rB_hb2
                widget1v = widget1.isChecked()
                if widget1v:
                    widget2.setChecked(True)
                else:
                    widget1.setChecked(True)
            elif com == MsgComInt.DONE_IT.msg_name:
                info: Union[DoneIt, MsgError] = info
                if info.com == Server.GET_AVAILABLE_SERVICES.name:
                    result: FuncAvailableServicesOutput = info
                    widget = self.ui.lW_devices
                    widget.clear()
                    names = []
                    for key, item in result.device_available_services.items():
                        names.append(f'{key}')
                    widget.addItems(names)
                    self.model.superuser.running_services = result.device_available_services
                elif info.com == Service.SERVICE_INFO.name:
                    info: FuncServiceInfoOutput = info
                    self.model.service_parameters[info.device_id] = info.service_description
                    self.ui.tE_info.setText(str(info.service_description))
                else:
                    error_logger(self, self.model_is_changed, f'DONE_IT com {info.com} is not known.')
            elif com == MsgComExt.ERROR.msg_name:
                self.ui.tE_info.setText(info.comments)

        except Exception as e:
            error_logger(self, self.model_is_changed, f'{self.name}: {e}')
