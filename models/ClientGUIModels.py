'''
Created on 17.11.2019

@author: saldenisov
'''
import logging
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from utilities.data.messages import Message
from utilities.myfunc import info_msg, error_logger, get_local_ip
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
from typing import Any, Dict, Union
from errors.myexceptions import MsgComNotKnown
from devices.devices import DeviceFactory
from devices.service_devices.project_treatment.openers import HamamatsuFileOpener

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
        self.superuser = DeviceFactory.make_device(device_id="SuperUser:37cc841a6f8f907deaa49f117aa1a2f9",
                                                   db_path=self.db_path,
                                                   pyqtslot=self.treat_pyqtsignals,
                                                   logger_new=False)
        self.superuser.start()
        self.service_parameters = {}
        info_msg(self, 'INITIALIZED')

    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def treat_pyqtsignals(self, msg: Message):
        self.model_changed.emit(msg)


class StepMotorsGUIModel(QObject):

    model_changed = pyqtSignal(Message, name='StepMotorsGUI_model_changed')

    def __init__(self, parameters: dict = {}):
        super().__init__(parent=None)
        self.name = 'StepMotorsGUI:model: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.parameters = parameters
        info_msg(self, 'INITIALIZED')

    def treat_pyqtsignals(self, msg: Message):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)


class VD2Treatment(QObject):

    def __init__(self, app_folder: Path, parameters: Dict[str, Any]={}):
        super().__init__(parent=None)
        self.app_folder = app_folder
        self.name = 'VD2Treatment:model: '
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.parameters = parameters
        self.observers = []
        self.opener = HamamatsuFileOpener(logger=self.logger)
        info_msg(self, 'INITIALIZED')

        self.data_path: Path = None
        self.noise_path: Path = None


    def add_observer(self, inObserver):
        self.observers.append(inObserver)

    def notify_observers(self, measurement: Measurement, new=False):
        for x in self.observers:
            x.modelIsChanged(measurement, new)

    def remove_observer(self, inObserver):
        self.observers.remove(inObserver)

    def read_data(self, map_index=0, new=False):
        measurement = self.opener.read_map(self.data_path, map_index)
        if not isinstance(measurement, Measurement):
            measurement = None
        self.notify_observers(measurement, new)
