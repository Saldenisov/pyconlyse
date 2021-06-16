"""
Created on 06.08.2019

@author: saldenisov
"""
import logging
from _functools import partial

from PyQt5 import QtCore
from PyQt5.QtWidgets import (QMainWindow)

from communication.messaging.messages import MsgComInt, MessageInt, MessageExt
from gui.views.ui.ServerGUI_ui import Ui_ServerGUI
from devices.devices_dataclass import *
from utilities.myfunc import info_msg, list_to_str_repr, get_local_ip

module_logger = logging.getLogger(__name__)


class ServerGUIView(QMainWindow):
    """
    """
    def __init__(self, in_controller, in_model, parent=None):
        # TODO: all queues should be added to GUI and tracked
        super().__init__(parent)
        self.name = 'ServerGUI:view: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model

        self.ui = Ui_ServerGUI()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.pB_start.clicked.connect(self.controller.start_server)
        self.ui.pB_pause.clicked.connect(self.controller.pause_server)
        self.ui.pB_execute.clicked.connect(partial(self.controller.exec_user_com, widget=self.ui.lE_execute))
        self.ui.pB_status.clicked.connect(self.controller.check_status)
        self.ui.lE_execute.setText('-start_service StpMtrCtrl_emulate:b8b10026214c373bffe2b2847a9538dd Devices.db')  # ; -start StepMotorsGUI.py')
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def model_is_changed(self, msg: Union[MessageInt, MessageExt]):
        com = msg.com
        info = msg.info
        if com == MsgComInt.DEVICE_INFO_INT.msg_name:
            info: DeviceInfoInt = info
            if info.device_status.messaging_on:
                text_widget = "Click to stop..."
                color = 'background-color: green'
                self.ui.pB_pause.setEnabled(True)
            else:
                text_widget = "Click to start"
                color = 'background-color: red'
                self.ui.pB_pause.setEnabled(False)
                self.ui.rB_hb.setChecked(False)
            widget = self.ui.pB_start
            _translate = QtCore.QCoreApplication.translate
            widget.setText((_translate("ServerMainWindow", text_widget)))
            widget.setStyleSheet(color)

            if info.device_status.messaging_paused:
                text_widget = "click to unpause..."
                color = 'background-color: yellow'
            else:
                text_widget = "click to pause"
                color = 'background-color: blue'
            widget = self.ui.pB_pause
            _translate = QtCore.QCoreApplication.translate
            widget.setText((_translate("ServerMainWindow", text_widget)))
            widget.setStyleSheet(color)
            text_info = f'{info.device_status}'
            self.ui.lE_serverinfo.setText(text_info)

            # setting info on running services, clients, events
            # TODO: Make if work
            self.ui.tE_services_running.setText(list_to_str_repr(info.active_connections))
            self.ui.tE_events_running.setText(list_to_str_repr(info.events_running))
        elif com == 'server_queues_tasks_keys':
            # TODO: change MsgGenerator naming
            self.ui.tE_queue_in.setText(list_to_str_repr(list(info.queue_in_keys)))
            self.ui.tE_queue_out.setText(list_to_str_repr(list(info.queue_out_keys)))
            self.ui.tE_queue_in_pending.setText(list_to_str_repr(list(info.queue_in_pending_keys)))
        elif com == MsgComInt.HEARTBEAT.msg_name and msg.sender_id == self.model.server.id:
            widget = self.ui.rB_hb
            before = widget.isChecked()
            widget.setChecked(not before)
