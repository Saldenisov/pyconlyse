'''
Created on 15.11.2019

@author: saldenisov
'''
import logging

from PyQt5.QtWidgets import QMainWindow

from utilities.myfunc import info_msg,  get_local_ip
from utilities.data.messages import Message
from communication.messaging.message_utils import MsgGenerator

from views.ui.SuperUser_ui import Ui_SuperUser


module_logger = logging.getLogger(__name__)


class SuperUserView(QMainWindow):

    def __init__(self, in_controller, in_model, parent=None):
        super().__init__(parent)
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
        self.logger.info('Closing')
        self.controller.quit_clicked(event, total_close=True)

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        info = msg.data.info
        if com == MsgGenerator.HEARTBEAT.mes_name:
            widget1 = self.ui.rB_hb
            widget2 = self.ui.rB_hb2
            widget1v = widget1.isChecked()
            if widget1v:
                widget2.setChecked(True)
            else:
                widget1.setChecked(True)
        elif com == MsgGenerator.AVAILABLE_SERVICES_REPLY.mes_name:
            widget = self.ui.lW_devices
            widget.clear()
            names = []
            for key, item in info.running_services.items():
                names.append(f'{key}')
            widget.addItems(names)
            self.model.superuser.running_services = info.running_services
        elif com == MsgGenerator.INFO_SERVICE_REPLY.mes_name:
            self.ui.tE_info.setText(str(info))
            self.model.service_parameters[info.device_id] = info
        elif com == MsgGenerator.ERROR.mes_name:
            self.ui.tE_info.setText(info.comments)
