from typing import Union

import numpy as np
from gui.views.matplotlib_canvas import MyMplCanvas
from datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


class KineticsCanvas(MyMplCanvas):

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)

    def compute_figure(self):
        self.axis.axhline(y=0, color='black')
        self.draw_cursors(False, self.calc_cursors())
        self.axis.grid(True)
        self.axis.plot(self._get_x_values(), self._form_data(), color='red', marker='o', linewidth=2)
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

    def _form_data(self) -> Union[np.array, np.ndarray]:
        beginning = self.cursors.x1[0]
        end = self.cursors.x2[0]
        data = self.measurement.data[:, beginning:end]
        return np.mean(data, axis=1)

    def new_data(self, measurement: Measurement, cursors: Cursors2D, external_call=True):
        if measurement:
            self.measurement = measurement
        if external_call:
            self.draw_cursors(False, cursors)

        lines = self.axis.lines
        if len(lines) > 1:
            for _ in range(len(lines) - 3):
                self.axis.lines[-1].remove()

        self.axis.plot(self._get_x_values(), self._form_data(), color='red', marker='o', markersize=2,
                       linewidth=2)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurement.time_scale}')

        self.update_limits()

    def _set_labels(self):
        self._x_text = 'Time Delay'
        self._title = 'Kinetics'

    def update_data(self, measurement: Measurement = None, cursors: Cursors2D = None):
        self.new_data(measurement, cursors)

    def update_limits(self):
        self.axis.relim()
        self.axis.autoscale_view(True, True, True)
        self.draw()



