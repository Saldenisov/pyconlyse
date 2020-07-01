from typing import Union

import numpy as np
from matplotlib.image import AxesImage

from gui.views.matplotlib_canvas import MyMplCanvases
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


class DataCanvas(MyMplCanvases):
    """
    Represents 2D datastructures map using matplotlib imshow
    """
    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        self.toolbar = NavigationToolbar(self, self.parent)


    def compute_figure(self, figure_name='Test'):
        self.cursors: Cursors2D = self.calc_cursors()
        self.maxv = np.max(self.measurement.data)
        self.minv = np.min(self.measurement.data)

        self.image: AxesImage = self.axis.imshow(self.measurement.data,
                                            extent=[self.measurement.wavelengths[0],
                                                    self.measurement.wavelengths[-1],
                                                    self.measurement.timedelays[-1],
                                                    self.measurement.timedelays[0]],
                                            aspect='auto',
                                            vmin=self.minv,
                                            vmax=self.maxv,
                                            interpolation='none')
        self.axis.grid(True)
        self.axis.set_xlabel('Wavelength, nm')
        self.axis.set_ylabel(f'Time delay, {self.measurement.time_scale}')
        if figure_name:
            self.axis.set_title(figure_name)
        self.fig.colorbar(self.image, ax=self.axis)
        self.draw_cursors()

    def draw_cursors(self, cursors=None, draw=False):
        k = len(self.axis.lines)
        if k > 2:
            for _ in range(k):
                self.axis.lines[-1].remove()
        if cursors:
            self.cursors = cursors
        cur = self.cursors
        self.axis.axhline(y=cur.y1[1], color='r')
        self.axis.axhline(y=cur.y2[1], color='r')
        self.axis.axvline(x=cur.x1[1], color='r')
        self.axis.axvline(x=cur.x2[1], color='r')

        if draw:
            self.draw()

    def _form_data(self) -> Union[np.array, np.ndarray]:
        return self.measurement.data

    def new_data(self, measurement: Measurement, cursors: Cursors2D, map_index=0):
        self.measurement = measurement
        self.image.set_data(self._form_data())
        self.image.set_extent(extent=[self.measurement.wavelengths[0], self.measurement.wavelengths[-1],
                                      self.measurement.timedelays[-1], self.measurement.timedelays[0]])
        self.axis.set_title(f'Map index={map_index}')
        self.draw_cursors(cursors=cursors)
        self.update_limits()

    def _set_labels(self):
        pass

    def update_data(self, measurement: Measurement = None, cursors: Cursors2D = None, map_index=0):
        if measurement:
            draw = False
            self.measurement = measurement
            self.image.set_data(self.measurement.data)
            self.axis.set_title(f'Map index={map_index}')
        else:
            draw = True

        if cursors:
            self.draw_cursors(draw=draw, cursors=cursors)

        if not draw:
            self.update_limits()

    def update_limits(self):
        """
        update vmin and vmax of imshow
        """
        maxv = np.max(self.measurement.data)
        minv = np.min(self.measurement.data)
        self.image.set_clim(vmin=minv, vmax=maxv)
        self.draw()
        #print("Datacanvas redrawn")