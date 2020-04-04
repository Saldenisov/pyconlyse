import numpy as np
from datetime import datetime
from matplotlib.axes import Axes
from matplotlib.image import AxesImage
from views.matplotlib_canvas import MyMplCanvas
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement
from typing import Union


class DataCanvas(MyMplCanvas):
    """
    Represents 2D data map using matplotlib imshow
    """
    def __init__(self, width: int, height: int, dpi: int,
                 canvas_parent, measurement: Measurement=None):
        if not measurement:
            data = np.ndarray(shape=(100, 100))
            data.fill(1)
            waves = np.arange(100)
            times = np.arange(100)
            timestamp = datetime.timestamp(datetime.now())
            measurement = Measurement('', 'default', 'sd', timestamp, data, waves, times, 'none')
        self.measurement = measurement

        super().__init__(width, height, dpi, canvas_parent)

        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        self.toolbar = NavigationToolbar(self, self.parent)


    def compute_figure(self, figure_name='Test'):
        self.maxv = np.max(self.measurement.data)
        self.minv = np.min(self.measurement.data)

        image: AxesImage = self.axis.imshow(self.measurement.data,
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

        self.fig.colorbar(image, ax=self.axis)

    def update_figure(self):
        k = len(self.axis.lines)
        if k > 2:
            for _ in range(k):
                self.dataplot.lines[-1].remove()
        cur = self.model.cursors
        self.axis.axhline(y=self.measurement.timedelays[cur['y1']], color='r')
        self.axis.axhline(y=self.measurement.timedelays[cur['y2']-1], color='r')
        self.axis.axvline(x=self.measurement.wavelengths[cur['x1']], color='r')
        self.axis.axvline(x=self.measurement.wavelengths[cur['x2']-1], color='r')

        self.draw()

    def update_limits(self, minv, maxv):
        """
        update vmin and vmax of imshow
        """
        self.image.set_clim(vmin=minv, vmax=maxv)

        self.draw()