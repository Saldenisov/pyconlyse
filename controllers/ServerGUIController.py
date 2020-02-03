'''
Created on 06.08.2019

@author: saldenisov
'''

import os
import logging
import pathlib
from PyQt5.QtWidgets import QApplication

from views.ServerGUIViews import ServerGUIView
from communication.messaging.message_utils import MsgGenerator
from utilities.myfunc import info_msg, error_logger, get_local_ip


module_logger = logging.getLogger(__name__)


class ServerGUIController:

    def __init__(self, in_model):
        """
        """
        self.logger = module_logger
        self.name = 'ServerGUI:controller: ' + get_local_ip()
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.view = ServerGUIView(self, in_model=self.model)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def start_server(self):
        if not self.model.server:
            self.model.start_server()
        else:
            self.model.stop_server()

    def pause_server(self):
        try:
            if self.model.server:
                if self.model.server.device_status.paused:
                    self.model.server.unpause()
                else:
                    self.model.server.pause()
        except Exception as e:
            print(e)

    def exec_user_com(self, widget):
        com = widget.text()
        com_splitted = com.split(';')
        path = self.model.app_folder
        import sys
        pyexec = sys.executable
        for x in com_splitted:
            x = x.split(' ')
            x = [command for command in x if command]
            com = x[0]
            rest = x[1:]
            if com == '-start_service':
                p = str(path / 'bin' / 'service.py')
                exc = f'start cmd /K {pyexec} {p} {" ".join(rest)}'
                os.system(exc)
            elif com == '-start':
                p = str(path / 'bin' / rest[0])
                exc = f'start cmd /K {pyexec} {p}'
                for r in rest[1:]:
                    exc = exc + r
                os.system(exc)

    def check_status(self):
        msg = MsgGenerator.status_server_info_full(device=self.model.server)
        self.model.model_changed.emit(msg)

    def quit_clicked(self, event):
        try:
            self.model.stop_server()
        except Exception as e:
            print(e)
        self.logger.info('Closing')
        self.logger.info('Done')
        QApplication.quit()
