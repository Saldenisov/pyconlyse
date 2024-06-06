from typing import Union, List

import numpy as np

from gui.views.matplotlib_canvas.MyMplCanvases import MyMplCanvas, AverageCanvas
from gui.controllers.openers import (H5Opener, ASCIIOpener, HamamatsuFileOpener, CriticalInfoHamamatsu,
                                     Opener, OpenersTypes, OPENER_ACCRODANCE, CriticalInfo)
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


class KineticsCanvas(MyMplCanvas):

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)

    def compute_figure(self):
        self.axis.axhline(y=0, color='black')
        self.draw_cursors(False, self.calc_cursors())
        self.axis.grid(True)
        self.axis.plot(self._get_x_values(), self._form_average_data(), color='red', marker='o', linewidth=2)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurement.time_scale}')
        self.axis.set_ylabel('Intensity')
        self.axis.set_title(self._title)
        self.draw()

    def _get_x_values(self) -> np.array:
        return self.measurement.timedelays

    def draw_cursors(self, draw=True, cursors=None):
        if cursors:
            self.cursors = cursors
            lines = self.axis.lines
            for _ in range(len(lines) - 1):
                self.axis.lines[-1].remove()
            self.axis.axvline(x=cursors.y1[1], color='r')
            self.axis.axvline(x=cursors.y2[1], color='r')
            self.new_data(measurement=None, cursors=cursors, external_call=False)

    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        beginning = self.cursors.x1[0]
        end = self.cursors.x2[0]
        data = self.measurement.data[beginning:end]
        return np.mean(data, axis=0)

    def new_data(self, measurement: Measurement, cursors: Cursors2D, external_call=True):
        if measurement:
            self.measurement = measurement
        if external_call:
            self.draw_cursors(False, cursors)

        lines = self.axis.lines
        if len(lines) > 1:
            for _ in range(len(lines) - 3):
                self.axis.lines[-1].remove()
        x, y = self._get_x_values(), self._form_average_data()
        self.axis.plot(x, y, color='red', marker='o', markersize=2,
                       linewidth=2)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurement.time_scale}')

        self.update_limits()

    def update_data(self, measurement: Measurement = None, cursors: Cursors2D = None):
        self.new_data(measurement, cursors)

    def _set_labels(self):
        self._x_text = 'Time Delay'
        self._title = 'Kinetics'

    def update_limits(self):
        self.axis.relim()
        self.axis.autoscale_view(True, True, True)
        self.draw()


class KineticsAverage(AverageCanvas):

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurements: List[Measurement] = None):
        super().__init__(width, height, dpi, canvas_parent, measurements)
        self.spectral_angles = []

    def compute_figure(self, figure_name='Test'):
        self.axis.axhline(y=0, color='black')
        self.axis.grid(True)
        for kinetics in self.measurements_formed:
            t, data = self._get_x_values(), kinetics
            self.axis.plot(t, data, linewidth=1)
        self.axis.plot(self._get_x_values(), self._form_average_data(), color='red', marker='o', linewidth=3)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurements[0].time_scale}')
        self.axis.set_ylabel('Intensity')
        self.axis.set_title(f'{self._title}: {self.measurements_formed.shape}')
        self.axis.set_yscale('log')
        self.draw()

    def _get_x_values(self):
        return self.timedelays

    def _form_data(self) -> Union[np.array, np.ndarray]:
        self.timedelays = self.measurements[0].timedelays
        maps = np.array([map.data for map in self.measurements])
        self.measurements_formed = np.mean(maps, axis=1)
        self.average_surface = np.sum(np.mean(self.measurements_formed, axis=0))

    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        spectra = np.mean(self.measurements_formed, axis=0)
        return spectra

    def new_data(self, critical_info: CriticalInfo = None, measurements: List[Measurement] = None):
        if measurements:
            self.measurements = measurements
        else:
            self.critical_info = critical_info
            file_path = critical_info.file_path
            if file_path.suffix in ['.his', '.img']:
                o = HamamatsuFileOpener()
            elif file_path.suffix == '.h5':
                o = H5Opener()
            self.measurements = list(o.give_all_maps(file_path))
        self._form_data()

        lines = self.axis.lines
        if len(lines) > 1:
            for _ in range(len(lines) - 1):
                self.axis.lines[-1].remove()

        self.compute_figure()
        self.update_limits()

    def _set_labels(self):
        self._x_text = 'Time Delay'
        self._title = 'Kinetics'

    def update_data(self, measurements: List[Measurement]):
        self.new_data(measurements)

    def update_limits(self):
        self.axis.relim()
        self.axis.autoscale_view(True, True, True)
        self.draw()
