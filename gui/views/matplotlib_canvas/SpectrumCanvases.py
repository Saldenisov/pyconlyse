from typing import Union

import numpy as np

from gui.views.matplotlib_canvas.KineticsCanvases import KineticsCanvas
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement


class SpectrumCanvas(KineticsCanvas):

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)

    def draw_cursors(self, draw=True, cursors=None):
        if cursors:
            self.cursors = cursors
            lines = self.axis.lines
            for _ in range(len(lines) - 1):
                self.axis.lines[-1].remove()
            self.axis.axvline(x=cursors.x1[1], color='r')
            self.axis.axvline(x=cursors.x2[1], color='r')
            self.new_data(measurement=None, cursors=cursors, external_call=False)

    def _get_x_values(self) -> np.array:
        return self.measurement.wavelengths

    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        beginning = self.cursors.y1[0]
        end = self.cursors.y2[0]
        data = self.measurement.data[:, beginning:end]
        return np.mean(data, axis=1)

    def _set_labels(self):
        self._x_text = 'Wavelengths'
        self._title = 'Spectrum'


