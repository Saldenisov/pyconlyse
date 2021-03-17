"""
Created on 06.08.2019
@author: saldenisov
"""
import logging
from pathlib import Path
from typing import Union

from PyQt5.QtCore import QObject, pyqtSignal

from communication.interfaces import Message
from communication.messaging.messages import MessageInt, MessageExt
from utilities.errors.myexceptions import MsgComNotKnown, DeviceError
from utilities.myfunc import info_msg, error_logger, get_local_ip

module_logger = logging.getLogger(__name__)


class ServerGUIModel(QObject):

    model_changed = pyqtSignal(Message, name='Server_model_changed')

    def __init__(self, app_folder: Path):
        super().__init__(parent=None)
        self.name = 'ServerGUI:model: ' + get_local_ip()
        self.app_folder = app_folder
        self.observers = []
        self.logger = module_logger
        self.db_path = Path(app_folder / 'utilities' / 'database' / 'Devices.db')
        info_msg(self, 'INITIALIZING')
        self.server = None
        info_msg(self, 'INITIALIZED')

    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def start_server(self, test=True):
        if not self.server:
            try:
                from devices.devices import DeviceFactory, Server
                if test:
                    device_id = "Server:Main:sfqvtyjsdf23qa23xcvTEST"
                else:
                    device_id = "Server:Main:sfqvtyjsdf23qa23xcv"
                self.server = DeviceFactory.make_device(device_id=device_id,
                                                        db_path=self.db_path, pyqtslot=self.treat_pyqtsignals,
                                                        logger_new=False)
                self.server.start()
            except DeviceError as e:
                self.logger.error(e)
        else:
            if not self.server.active:
                self.server.start()

    def stop_server(self):
        if self.server:
            try:
                self.server.stop()
            except (DeviceError, Exception) as e:
                error_logger(self, self.stop_server, f'{e}')
            finally:
                self.server = None

    def treat_pyqtsignals(self, msg: Union[MessageInt, MessageExt]):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)
