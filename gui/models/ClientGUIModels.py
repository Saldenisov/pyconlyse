"""
Created on 17.11.2019

@author: saldenisov
"""
import logging
import sys
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Union, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QErrorMessage

from communication.messaging.messages import MessageInt, MessageExt
from devices.devices import DeviceFactory
from devices.service_devices.project_treatment.openers import (ASCIIOpener, HamamatsuFileOpener, CriticalInfoHamamatsu,
                                                               Opener, OpenersTypes, OPENER_ACCRODANCE, CriticalInfo)
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Hamamatsu, Cursors2D
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


class TreatmentModel(QObject):

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
        SAVE = 'SAVE'
        DATA = 'DATA'

    def __init__(self, app_folder: Path, data_folder: Union[Path, str], parameters: Dict[str, Any]={}):
        super().__init__(parent=None)
        self.data_folder = Path(data_folder)
        self.save_folder = Path(data_folder)
        self.app_folder = app_folder
        self.name = 'VD2Treatment:model: '
        self.logger = logging.getLogger('VD2Treatment')
        info_msg(self, 'INITIALIZING')
        self.parameters = parameters
        self.processes_pool = ProcessPoolExecutor(max_workers=6)
        self.measurements_observers = []
        self.ui_observers = []
        self.openers = {OpenersTypes.Hamamatsu: HamamatsuFileOpener(logger=self.logger),
                        OpenersTypes.ASCII: ASCIIOpener(logger=self.logger)}

        self.paths: Dict[TreatmentModel.DataTypes, Path] = {}
        self.noise_averaged_data: np.ndarray = np.zeros(shape=(1, 1))
        self.cursors_data = Cursors2D()
        info_msg(self, 'INITIALIZED')

    def add_ui_observer(self, inObserver):
        self.ui_observers.append(inObserver)

    def add_data_path(self, file_path: Path, exp_data_type: DataTypes):
        opener = self.get_opener(file_path)
        if opener:
            res, comments = opener.fill_critical_info(file_path)
            if res:
                file_paths = []
                self.paths[exp_data_type] = file_path

                if exp_data_type is TreatmentModel.DataTypes.NOISE:
                    self.noise_averaged_data: np.ndarray = np.zeros(shape=(1, 1))
                    self.notify_ui_observers({'lineedit_noise_set': [str(file_path)]})

                elif exp_data_type in [TreatmentModel.DataTypes.ABS, TreatmentModel.DataTypes.ABS_BASE,
                                       TreatmentModel.DataTypes.ABS_BASE_NOISE]:
                    self.paths[TreatmentModel.DataTypes.DATA] = file_path
                    save_path: Path = self.save_folder / f'{file_path.stem}.dat'
                    self.paths[TreatmentModel.DataTypes.SAVE] = save_path
                    #self.notify_ui_observers({'lineedit_save_file_name': f'{file_path.stem}.dat'})

                if exp_data_type is TreatmentModel.DataTypes.ABS:
                    file_paths.append(str(file_path))
                    if TreatmentModel.DataTypes.BASE in self.paths:
                        file_paths.append(str(self.paths[TreatmentModel.DataTypes.BASE]))
                    self.notify_ui_observers({'lineedit_data_set': file_paths})

                elif exp_data_type is TreatmentModel.DataTypes.BASE:
                    if TreatmentModel.DataTypes.ABS in self.paths:
                        file_paths.append(str(self.paths[TreatmentModel.DataTypes.ABS]))
                    file_paths.append(str(file_path))
                    self.notify_ui_observers({'lineedit_data_set': file_paths})

                elif exp_data_type in [TreatmentModel.DataTypes.ABS_BASE,
                                       TreatmentModel.DataTypes.ABS_BASE_NOISE]:
                    file_paths.append(str(file_path))
                    self.notify_ui_observers({'lineedit_data_set': file_paths})

                self.read_data(file_path, new=True)

    def add_measurement_observer(self, inObserver):
        self.measurements_observers.append(inObserver)

    def average_range(self, line: str, file_path: Path, user_type: str = 'kinetics', n=0) -> Union[List[str], None]:
        def analyze_line(line: str) -> Union[Dict[float, int], None]:
            if line:
                line_elements = line.split(';')
                res = {}
                for elem in line_elements:
                    elem = ' '.join(elem.strip().split())
                    elem_parts = elem.split()
                    try:
                        if len(elem_parts) == 1:
                            res[float(elem_parts[0])] = 3
                        elif len(elem_parts) == 2:
                            res[float(elem_parts[0])] = float(elem_parts[1])
                        else:
                            pass
                    except ValueError:
                        pass
                return res
            else:
                return None
        line_elements = analyze_line(line)
        if not line_elements:
            self.show_error(self.average_range, f'First fill the required ranges using format: value range;... e.g., '
                                              f'"500+-10; 600+-5". The values and ranges should be given in nm.')
        else:
            opener = self.get_opener(file_path)
            if opener:
                line_elements_copy = deepcopy(line_elements)
                info: CriticalInfo = opener.paths[file_path]
                if user_type == 'kinetics':
                    variables = info.wavelengths
                    x = info.timedelays
                    file_save = Path(file_path.parent / f'{file_path.stem}_kinetics.txt')
                    axis = 1
                elif user_type == 'spectra':
                    variables: np.array() = info.timedelays
                    x = info.wavelengths
                    file_save = Path(file_path.parent / f'{file_path.stem}_spectra.txt')
                    axis = 0
                averaged_ranges = []
                data = opener.read_map(file_path, n)[0].data
                for key, value in line_elements_copy.items():
                    key_index = np.searchsorted(variables, key)
                    if key_index != 0 and key_index != len(variables)-1:
                        key_upper_index = np.searchsorted(variables, key+value)
                        key_lower_index = np.searchsorted(variables, key-value)
                        key_upper = variables[key_upper_index]
                        key_lower = variables[key_lower_index]
                        value = round((key_upper-key_lower) / 2, 1)
                        line_elements[key] = value
                        if user_type == 'kinetics':
                            data_cut = data[:, key_lower_index:key_upper_index]
                        elif user_type == 'spectra':
                            data_cut = data[key_lower_index:key_upper_index]
                        averaged = np.mean(data_cut, axis=axis)
                        averaged_ranges.append(np.insert(x, 0, value))
                        averaged_ranges.append(np.insert(averaged, 0, key))
                    else:
                        del line_elements[key]
                to_save = np.array(averaged_ranges)
                to_save = np.transpose(to_save)
                np.savetxt(file_save, to_save, delimiter='\t', fmt='%1.3f')
                return line_elements
            else:
                self.show_error(self.average_range, f'File {file_path} cannot be open.')
                return None

    def average_noise(self) -> Tuple[bool, str]:
        info_msg(self, 'INFO', 'Averaging Noise')
        if TreatmentModel.DataTypes.NOISE in self.paths:
            noise_path = self.paths[TreatmentModel.DataTypes.NOISE]
            opener = self.get_opener(noise_path)
            if opener:
                self.noise_averaged_data = opener.average_map(noise_path, self._callback_average)
                res, comments = True, ''
            else:
                self.show_error(self.average_noise, f'Could not average NOISE')
                res, comments = False, f'Could not average NOISE:'
        else:
            res, comments = False, f'First add noise path, before averaging'
        return res, comments

    def _callback_average(self, map_index, number_maps):
        self.notify_ui_observers({'progressbar_calc': (map_index, number_maps)})

    def calc_abs(self, exp_type: ExpDataStruct, how: str, first_map_with_electrons: bool):
        res = False
        res_local = True
        if TreatmentModel.DataTypes.NOISE not in self.paths:
            self.show_error(self.calc_abs, f'Set NOISE pass first.')
            res_local = False

        if exp_type is TreatmentModel.ExpDataStruct.HIS:
            pass
        elif exp_type is TreatmentModel.ExpDataStruct.HIS_NOISE:
            map_index = 0
            res_local = True
            if TreatmentModel.DataTypes.ABS_BASE not in self.paths:
                self.show_error(self.calc_abs, f'Set ABS_BASE first.')
                res_local = False
            if res_local:
                data_path = self.paths[TreatmentModel.DataTypes.ABS_BASE]
                opener = self.get_opener(data_path)
                if opener:
                    info: CriticalInfoHamamatsu = opener.paths[data_path]
                    od_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
                    if len(self.noise_averaged_data) < 2:
                        res, comments = self.average_noise()
                        if not res:
                            self.show_error(self.calc_abs, comments)
                    if how == 'individual':
                        for measurements in opener.give_pair_maps(data_path):
                            map_index += 1
                            if first_map_with_electrons:
                                abs = measurements[0].data
                                base = measurements[1].data
                            else:
                                abs = measurements[1].data
                                base = measurements[0].data
                            try:
                                transmission = (base - self.noise_averaged_data) / (abs - self.noise_averaged_data)
                                od_data += np.log10(transmission)
                            except (RuntimeError, RuntimeWarning):
                                pass
                            self.notify_ui_observers({'progressbar_calc': (map_index, info.number_maps / 2)})
                        od_data = od_data / info.number_maps
                    elif how == 'averaged':
                        abs_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
                        base_data = np.zeros(shape=(info.timedelays_length, info.wavelengths_length))
                        for measurements in opener.give_pair_maps(data_path):
                            map_index += 1
                            if first_map_with_electrons:
                                abs = measurements[0].data
                                base = measurements[1].data
                            else:
                                abs = measurements[1].data
                                base = measurements[0].data
                            abs_data += abs
                            base_data += base
                            self.notify_ui_observers({'progressbar_calc': (map_index, info.number_maps / 2)})
                        abs_data = abs_data / info.number_maps
                        base_data = base_data / info.number_maps
                        od_data = (base_data - self.noise_averaged_data) / (abs_data - self.noise_averaged_data)
                    res = True
        elif exp_type is TreatmentModel.ExpDataStruct.ABS_BASE_NOISE:
            if TreatmentModel.DataTypes.ABS not in self.paths:
                self.show_error(self.calc_abs, f'Set ABS pass first.')
                res_local = False
            if TreatmentModel.DataTypes.BASE not in self.paths:
                self.show_error(self.calc_abs, f'Set BASE pass first.')
                res_local = False
            if res_local:
                abs_path = self.paths[TreatmentModel.DataTypes.ABS]
                base_path = self.paths[TreatmentModel.DataTypes.BASE]
                noise_path = self.paths[TreatmentModel.DataTypes.NOISE]
                opener = self.get_opener(abs_path)
                if opener:
                    info: CriticalInfoHamamatsu = opener.paths[abs_path]
                    abs_path = self.paths[TreatmentModel.DataTypes.ABS]
                    base_path = self.paths[TreatmentModel.DataTypes.BASE]
                    noise_path = self.paths[TreatmentModel.DataTypes.NOISE]
                    opener = self.get_opener(abs_path)
                    #abs_data = base_data = noise_data = np.zeros(shape=(info.timedelays_length,
                                                                        #info.wavelengths_length))
                    #data_path = [abs_path, base_path, noise_path]
                    #data = {abs_path: abs_data, base_path: base_data, noise_path: noise_data}
                    #with ProcessPoolExecutor() as executor:
                        #for path, res_calc in zip(data_path, executor.map(opener.average_map, data_path)):
                            #data[path] = res_calc

                    abs_data = opener.average_map(file_path=abs_path, call_back_func=self._callback_average)
                    #abs_data = data[abs_path]
                    base_data = opener.average_map(file_path=base_path, call_back_func=self._callback_average)
                    #base_data = data[base_path]
                    noise_data = opener.average_map(file_path=noise_path, call_back_func=self._callback_average)
                    #noise_data = data[noise_path]
                    self.noise_averaged_data = noise_data
                    od_data = (base_data - noise_data) / (abs_data - noise_data)
                    res = True


        if res:
            od_data = np.log10(od_data)
            self.od = Measurement(type='Pump-Probe', comments='', author='SD',
                                  timestamp=datetime.timestamp(datetime.now()), data=od_data,
                                  wavelengths=info.wavelengths, timedelays=info.timedelays,
                                  time_scale=info.scaling_yunit)
            self.notify_measurement_observers(self.od)

    def get_opener(self, file_path) -> Union[Opener, None]:
        opener = None
        try:
            opener = self.openers[OPENER_ACCRODANCE[file_path.suffix]]
        except KeyError as e:
            self.show_error(self.get_opener, e)
        finally:
            return opener

    def make_default_cursor(self, file_path: Path) -> Cursors2D:
        opener = self.get_opener(file_path)
        if opener:
            info: Hamamatsu = opener.paths[file_path]
            waves_l = len(info.wavelengths)
            times_l = len(info.timedelays)
            waves = info.wavelengths
            times = info.timedelays
            x1 = int(waves_l * .2)
            x2 = int(waves_l * .8)
            y1 = int(times_l * .2)
            y2 = int(times_l * .8)
            return Cursors2D(x1=(x1, waves[x1]), x2=(x2, waves[x2]), y1=(y1, times[y1]), y2=(y2, times[y2]))

    def notify_measurement_observers(self, measurement: Measurement = None, map_index: int=0,
                                     critical_info: CriticalInfoHamamatsu = None, new=False,
                                     cursors: Cursors2D = None):
        for x in self.measurements_observers:
            x.modelIsChanged(measurement, map_index, critical_info, new, cursors)

    def notify_ui_observers(self, ui: dict):
        for x in self.ui_observers:
            x.modelIsChanged_ui(ui)

    def remove_observer(self, inObserver):
        self.measurements_observers.remove(inObserver)

    def read_data(self, file_path: Path, map_index=0, new=False):
        opener = self.get_opener(file_path)
        if opener:
            measurement, comments = opener.read_map(file_path, map_index)
            if not isinstance(measurement, Measurement):
                measurement = None
                self.show_error(self.read_data, comments)
            else:
                if new:
                    self.cursors_data = self.make_default_cursor(file_path)
                    cursors = self.cursors_data
                else:
                    cursors = None
                self.notify_measurement_observers(measurement, map_index, opener.paths[file_path], new=new,
                                                  cursors=cursors)

    def save(self):
        try:
            data_path = self.paths[TreatmentModel.DataTypes.DATA]
            save_path = self.paths[TreatmentModel.DataTypes.SAVE]
            opener = self.get_opener(data_path)
            info = opener.paths[data_path]
            data = self.od.data
            wavelengths = info.wavelengths
            final_data = np.vstack((wavelengths, data))
            final_data = final_data.transpose()
            timedelays = np.insert(info.timedelays, 0, 0)
            final_data = np.vstack((timedelays, final_data))
            np.savetxt(str(save_path), final_data, delimiter='\t', fmt='%.4f')
        except (KeyError, Exception) as e:
            self.show_error(self.save, e)

    def save_file_path_change(self, folder: str, file_name: str):
        save_path = Path(folder) / Path(file_name)
        info_msg(self, 'INFO', f'save file updated {save_path}')
        self.paths[TreatmentModel.DataTypes.SAVE] = save_path
        self.notify_ui_observers({'lineedit_save_file_name': str(Path(file_name))})
        self.notify_ui_observers({'lineedit_save_folder': str(Path(folder))})

    def show_error(self, func, error):
        error_logger(self, func, error)
        error_dialog = QErrorMessage()
        error_dialog.showMessage(str(error))
        error_dialog.exec_()

    def update_data_cursors(self, data_path: Path, x1=None, x2=None, y1=None, y2=None, pixels=False):
        opener = self.get_opener(data_path)
        if opener:
            info: CriticalInfo = opener.paths[data_path]
            waves = info.wavelengths
            times = info.timedelays
            if not pixels:
                if x1 > x2:
                    x1, x2 = x2, x1
                if y1 > y2:
                    y1, y2 = y2, y1
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

