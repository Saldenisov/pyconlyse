'''
Created on 27 juil. 2015

@author: saldenisov
'''
from abc import abstractmethod

import matplotlib

matplotlib.use('Qt5Agg')
import numpy as np
from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from typing import Union, List
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


class MyMplCanvas(FigureCanvas):
    """Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.)."""

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        self.parent = canvas_parent
        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        FigureCanvas.__init__(self, self.fig)
        self.axis: Axes = self.fig.add_subplot(111)
        if not measurement:
            data = np.ndarray(shape=(100, 100))
            data.fill(1)
            waves = np.arange(100)
            times = np.arange(100)
            timestamp = datetime.timestamp(datetime.now())
            measurement = Measurement('', 'default', 'sd', timestamp, data, waves, times, 'none')
        self.measurement = measurement
        self._set_labels()
        self.compute_figure()

    @abstractmethod
    def compute_figure(self, figure_name='Test'):
        pass

    def calc_cursors(self, x1=None, x2=None, y1=None, y2=None) -> Cursors2D:
        if not x1:
            x1 = int(len(self.measurement.wavelengths) * 0.2)
        x1r = self.measurement.wavelengths[x1]
        if not x2:
            x2 = int(len(self.measurement.wavelengths) * 0.8)
        x2r = self.measurement.wavelengths[x2]
        if not y1:
            y1 = int(len(self.measurement.timedelays) * 0.2)
        y1r = self.measurement.timedelays[y1]
        if not y2:
            y2 = int(len(self.measurement.timedelays) * 0.8)
        y2r = self.measurement.timedelays[y2]
        return Cursors2D((x1, x1r), (x2, x2r), (y1, y1r), (y2, y2r))

    @abstractmethod
    def draw_cursors(self, cursors=None, draw=False):
        pass

    @abstractmethod
    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        pass

    @abstractmethod
    def new_data(self, measurement: Measurement, cursors: Cursors2D):
        pass

    @abstractmethod
    def _set_labels(self):
        pass

    @abstractmethod
    def update_data(self, measurement: Measurement=None, cursors: Cursors2D=None):
        pass

    @abstractmethod
    def update_limits(self):
        pass


class AverageCanvas(FigureCanvas):
    """Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.)."""

    def __init__(self, width: int, height: int, dpi: int, canvas_parent,
                 measurements: List[Measurement] = None):
        self.parent = canvas_parent
        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        FigureCanvas.__init__(self, self.fig)
        self.axis: Axes = self.fig.add_subplot(111)
        if not measurements:
            measurements = []
            data = np.ndarray(shape=(100, 100))
            data.fill(1)
            waves = np.arange(100)
            times = np.arange(100)
            timestamp = datetime.timestamp(datetime.now())
            measurement = Measurement('', 'default', 'sd', timestamp, data, waves, times, 'none')
            measurements.append(measurement)

        self.measurements = measurements
        self._form_data()
        self._set_labels()
        self.compute_figure()

    @abstractmethod
    def compute_figure(self, figure_name='Test'):
        pass

    @abstractmethod
    def _form_data(self) -> Union[np.array, np.ndarray]:
        pass

    @abstractmethod
    def new_data(self, measurements: List[Measurement]):
        pass

    @abstractmethod
    def _set_labels(self):
        pass

    @abstractmethod
    def update_data(self, measurements: List[Measurement]):
        pass

    @abstractmethod
    def update_limits(self):
        pass
