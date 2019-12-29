'''
Created on 17.11.2019

@author: saldenisov
'''
import logging
import sqlite3 as sq3
from time import sleep
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from utilities.data.messages import Message
from communication.messaging.message_utils import gen_msg
from errors.myexceptions import MsgComNotKnown, DeviceError
from utilities.myfunc import info_msg, error_logger, get_local_ip
from utilities.configurations import configurationSD
from DB import create_connectionDB, executeDBcomm, close_connDB
from communication.logic.thinkers import StpMtrClientCmdLogic
from devices.devices import DeviceFactory, Server
from errors.myexceptions import MsgComNotKnown
from devices.devices import Client
from devices.devices import DeviceFactory

module_logger = logging.getLogger(__name__)


class SuperUserGUIModel(QObject):

    model_changed = pyqtSignal(Message, name='SuperUser_model_changed')

    def __init__(self, app_folder: Path):
        super().__init__(parent=None)
        self.name = 'SuperUserGUI:model: ' + get_local_ip()
        self.app_folder = app_folder
        self.observers = []
        self.logger = module_logger
        self.db_path = Path(app_folder / 'DB' / 'Devices.db')
        info_msg(self, 'INITIALIZING')
        self.superuser = DeviceFactory.make_device(device_id="37cc841a6f8f907deaa49f117aa1a2f9",
                                                   db_path=self.db_path,
                                                   pyqtslot=self.treat_pyqtsignals,
                                                   logger_new=False)
        self.superuser.start()
        info_msg(self, 'INITIALIZED')

    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def start_server(self):
        pass

    def stop_server(self):
        pass

    def treat_pyqtsignals(self, msg: Message):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)


class StepMotorsGUIModel(QObject):

    model_changed = pyqtSignal(Message, name='SuperUser_model_changed')

    def __init__(self, app_folder: Path):
        super().__init__(parent=None)
        self.name = 'SuperUserGUI:model: ' + get_local_ip()
        self.app_folder = app_folder
        self.observers = []
        self.logger = module_logger
        self.db_path = Path(app_folder / 'DB' / 'Devices.db')
        info_msg(self, 'INITIALIZING')
        self.superuser = DeviceFactory.make_device(device_id="37cc841a6f8f907deaa49f117aa1a2f9",
                                                   db_path=self.db_path,
                                                   pyqtslot=self.treat_pyqtsignals,
                                                   logger_new=False)
        self.superuser.start()
        info_msg(self, 'INITIALIZED')

    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def start_server(self):
        pass

    def stop_server(self):
        pass

    def treat_pyqtsignals(self, msg: Message):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)
