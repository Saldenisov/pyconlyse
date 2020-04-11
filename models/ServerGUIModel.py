'''
Created on 06.08.2019

@author: saldenisov
'''
import logging
from time import sleep
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from utilities.data.messages import Message
from communication.messaging.message_utils import MsgGenerator
from errors.myexceptions import MsgComNotKnown, DeviceError
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
        self.db_path = Path(app_folder / 'database' / 'Devices.db')
        info_msg(self, 'INITIALIZING')
        self.server = None
        info_msg(self, 'INITIALIZED')

    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def start_server(self):
        if not self.server:
            try:
                from devices.devices import DeviceFactory, Server
                self.server = DeviceFactory.make_device(cls=Server,
                                                        name='Server',
                                                        db_path=self.db_path,
                                                        pyqtslot=self.treat_pyqtsignals,
                                                        logger_new=False,
                                                        id="Server:Main:sfqvtyjsdf23qa23xcv")
                self.server.start()
            except DeviceError as e:
                self.logger.error(e)
        else:
            if not self.server.active:
                self.server.start()

    def stop_server(self):
        if self.server:
            try:
                # TODO: when stopped dictionary changed size during iteration after second server start
                self.server.stop()
            except (DeviceError, Exception) as e:
                self.logger.error(f'func: stop_server {e}')
            finally:
                self.server = None

    def treat_pyqtsignals(self, msg: Message):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)
