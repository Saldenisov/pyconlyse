"""
Created on 17.11.2019

@author: saldenisov
"""
import logging
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Union
from enum import Enum, auto
from PyQt5.QtCore import QObject, pyqtSignal
from communication.messaging.messages import MessageInt, MessageExt
from datastructures.mes_independent.measurments_dataclass import Measurement, Hamamatsu, Cursors2D
from devices.devices import DeviceFactory
from devices.service_devices.project_treatment.openers import HamamatsuFileOpener, CriticalInfoHamamatsu
from utilities.errors.myexceptions import MsgComNotKnown
from utilities.myfunc import info_msg, error_logger, get_local_ip

module_logger = logging.getLogger(__name__)


class SuperUserGUIModel(QObject):

    model_changed = pyqtSignal(MessageInt, name='SuperUser_model_changed')

    def __init__(self, app_folder: Path):
        super().__init__(parent=None)
        self.name = 'SuperUserGUI:model: ' + get_local_ip()
        self.app_folder = app_folder
        self.observers = []
        self.logger = module_logger
        self.db_path = Path(app_folder / 'utilities' / 'database' / 'Devices.db')
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

    def treat_pyqtsignals(self, msg: Union[MessageInt, MessageExt]):
        self.model_changed.emit(msg)


class StepMotorsGUIModel(QObject):

    model_changed = pyqtSignal(MessageInt, name='StepMotorsGUI_model_changed')

    def __init__(self, parameters: dict = {}):
        super().__init__(parent=None)
        self.name = 'StepMotorsGUI:model: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.parameters = parameters
        info_msg(self, 'INITIALIZED')

    def treat_pyqtsignals(self, msg: Union[MessageInt, MessageExt]):
        try:
            self.model_changed.emit(msg)
        except MsgComNotKnown as e:
            error_logger(self, self.treat_pyqtsignals, e)


class VD2TreatmentModel(QObject):

    class ExpDataStruct(Enum):
        HIS = 'HIS'
        HIS_NOISE = 'HIS+NOISE'
        ABS_BASE_NOISE = 'ABS+BASE+NOISE'

    class DataTypes(Enum):
        ABS = 'ABS'
        BASE = 'BASE'
        NOISE = 'NOISE'
        ABS_BASE = 'ABS+BASE'
        ABS_BASE_NOISE = 'ABS+BASE+NOISE'

    def __init__(self, app_folder: Path, parameters: Dict[str, Any]={}):
        super().__init__(parent=None)
        self.app_folder = app_folder
        self.name = 'VD2TreatmentModel:model: '
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.parameters = parameters
        self.measurements_observers = []
        self.ui_observers = []
        self.opener = HamamatsuFileOpener(logger=self.logger)

        self.paths: Dict[VD2TreatmentModel.DataTypes, Path] = {}
        self.noise_averaged = False
        self.noise_averaged_data: np.ndarray = None
        self.cursors_data = Cursors2D()
        info_msg(self, 'INITIALIZED')

    def add_data_path(self, file_path: Path, exp_data_type: DataTypes):
        res, comments = self.opener.fill_critical_info(file_path)
        if res:
            self.paths[exp_data_type] = file_path
            if exp_data_type is VD2TreatmentModel.DataTypes.NOISE:
                self.notify_ui_observers({'lineedit_noise_set': str(file_path)})
            elif exp_data_type in [VD2TreatmentModel.DataTypes.ABS, VD2TreatmentModel.DataTypes.ABS_BASE, VD2TreatmentModel.DataTypes.ABS_BASE_NOISE] :
                self.save_path: Path = file_path.parent / f'{file_path.stem}.dat'
                self.notify_ui_observers({'lineedit_data_set': str(file_path),
                                          'lineedit_save_file_name': str(self.save_path)})
            self.read_data(file_path, new=True)

    def add_measurement_observer(self, inObserver):
        self.measurements_observers.append(inObserver)

    def average_noise(self):
        if self.noise_path:
            info: CriticalInfoHamamatsu = self.opener.paths[self.noise_path]
            data_averaged = np.zeros(shape=(info.timedelays_length, info.wavelengths_length), dtype=np.float)
            for measurement in self.opener.give_all_maps(self.noise_path):
                data_averaged += measurement.data
            self.noise_averaged_data = data_averaged / info.number_maps
            self.noise_averaged = True
            self.notify_ui_observers({'checkbox_noise_averaged': True})

    def calc_abs(self, exp: str, how: str, exp_data_structr: ExpDataStruct, first_map_with_electrons: bool):
        info: CriticalInfoHamamatsu = self.opener.paths[self.data_path]
        map_index = 0
        if how == 'individual':
            od_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
            for measurements in self.opener.give_pair_maps(self.data_path):
                map_index += 1
                if first_map_with_electrons:
                    abs = measurements[0].data
                    base = measurements[1].data
                else:
                    abs = measurements[1].data
                    base = measurements[0].data
                abs = (base-self.noise_averaged_data) / (abs - self.noise_averaged_data)
                od_data += np.log10(abs)
                self.progressbar.setValue(int(map_index/info.number_maps * 2 * 100))
                #self.notify_ui_observers({'progressbar_calc': (map_index, info.number_maps / 2)})
                if map_index == 10:  # TODO: this could be removed later
                    # break
                    pass
            od_data = od_data / info.number_maps
        elif how == 'averaged':
            abs_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
            base_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
            for measurements in self.opener.give_pair_maps(self.data_path):
                map_index += 1
                if first_map_with_electrons:
                    abs = measurements[0].data
                    base = measurements[1].data
                else:
                    abs = measurements[1].data
                    base = measurements[0].data
                abs_data += abs
                base_data += base
                #self.notify_ui_observers({'progressbar_calc': (map_index, info.number_maps / 2)})
                self.progressbar.setValue(int(map_index / info.number_maps * 2 * 100))
            abs_data = abs_data / info.number_maps
            base_data = base_data / info.number_maps
            od_data = (base_data - self.noise_averaged_data) / (abs_data - self.noise_averaged_data)

        self.od = Measurement(type='Pump-Probe', comments='', author='SD',timestamp=datetime.timestamp(datetime.now()),
                              data=od_data, wavelengths=info.wavelengths, timedelays=info.timedelays,
                              time_scale=info.scaling_yunit)
        self.notify_measurement_observers(self.od)

    def notify_measurement_observers(self, measurement: Measurement = None, map_index: int=0,
                                     critical_info: CriticalInfoHamamatsu = None, new=False,
                                     cursors: Cursors2D = None):
        for x in self.measurements_observers:
            x.modelIsChanged(measurement, map_index, critical_info, new, cursors)

    def add_ui_observer(self, inObserver):
        self.ui_observers.append(inObserver)

    def notify_ui_observers(self, ui: dict):
        for x in self.ui_observers:
            x.modelIsChanged_ui(ui)

    def remove_observer(self, inObserver):
        self.measurements_observers.remove(inObserver)

    def read_data(self, data_path: Path, map_index=0, new=False):
        measurement = self.opener.read_map(data_path, map_index)
        if not isinstance(measurement, Measurement):
            measurement = None
        if new:
            self.cursors_data = self.make_default_cursor(data_path)
            cursors = self.cursors_data
        else:
            cursors = None
        self.notify_measurement_observers(measurement, map_index, self.opener.paths[data_path], new=new,
                                          cursors=cursors)

    def save(self):
        try:
            info = self.opener.paths[self.data_path]
            data = self.od.data
            wavelengths= info.wavelengths
            final_data = np.vstack((wavelengths, data))
            final_data = final_data.transpose()
            timedelays = np.insert(info.timedelays, 0, 0)
            final_data = np.vstack((timedelays, final_data))
            np.savetxt(self.save_path, final_data, delimiter='\t', fmt='%.4f')
        except Exception as e:
            self.logger.error(e)

    def save_file_path_change(self, file_name: str):
        try:
            self.save_path = Path(file_name)
        except Exception as e:  # TODO: to change
            self.logger.error(e)
            self.notify_ui_observers({'lineedit_save_file_name': str(self.save_path)})

    def update_data_cursors(self, data_path: Path, x1=None, x2=None, y1=None, y2=None, pixels=False):
        info: Hamamatsu = self.opener.paths[data_path]
        waves = info.wavelengths
        times = info.timedelays
        if not pixels:
            if x1 > x2:
                temp = x2
                x2 = x1
                x1 = temp
            if y1 > y2:
                temp = y2
                y2 = y1
                y1 = temp
            x1 = np.searchsorted(waves, x1)
            y1 = np.searchsorted(times, y1)
            x2 = np.searchsorted(waves, x2)
            y2 = np.searchsorted(times, y2)
        if not x1:
            x1 = self.cursors_data.x1[0]
        if not x2:
            x2 = self.cursors_data.x2[0]
        if not y1:
            y1 = self.cursors_data.y1[0]
        if not y2:
            y2 = self.cursors_data.y2[0]
        cursors = Cursors2D((x1, waves[x1]), (x2, waves[x2]), (y1, times[y1]), (y2, times[y2]))
        self.cursors_data = cursors
        self.notify_measurement_observers(cursors=cursors)

    def make_default_cursor(self, data_path: Path) -> Cursors2D:
        info: Hamamatsu = self.opener.paths[data_path]
        waves_l = len(info.wavelengths)
        times_l = len(info.timedelays)
        waves = info.wavelengths
        times = info.timedelays
        x1 = int(waves_l*.2)
        x2 = int(waves_l*.8)
        y1 = int(times_l*.2)
        y2 = int(times_l*.8)
        return Cursors2D(x1=(x1, waves[x1]), x2=(x2, waves[x2]), y1=(y1, times[y1]), y2=(y2, times[y2]))

