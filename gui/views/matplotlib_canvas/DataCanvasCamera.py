from abc import abstractmethod

import matplotlib

matplotlib.use('Qt5Agg')
import numpy as np
from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.axes import Axes
from matplotlib.image import AxesImage
from matplotlib.figure import Figure
from utilities.datastructures.mes_independent.measurments_dataclass import CameraReadings


class DataCanvasCamera(FigureCanvas):
    """
    Represents 2D datastructures map using matplotlib imshow
    """
    def __init__(self, width: int, height: int, dpi: int, canvas_parent, camera_reading: CameraReadings=None):
        self.parent = canvas_parent
        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        FigureCanvas.__init__(self, self.fig)
        self.axis: Axes = self.fig.add_subplot(111)
        if not camera_reading:
            data = np.random.randn(400, 512)
            timestamp = datetime.timestamp(datetime.now())
            measurement = CameraReadings(data, timestamp, '')
        self.camera_reading = measurement
        self.axis.set_xlabel('Width, pixel')
        self.axis.set_ylabel(f'Height, pixel')
        self.compute_figure()

        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        self.toolbar = NavigationToolbar(self, self.parent)

    def compute_figure(self, figure_name=''):
        self.maxv = np.max(self.camera_reading.data)
        self.minv = np.min(self.camera_reading.data)

        self.image: AxesImage = self.axis.imshow(self.camera_reading.data,
                                                 extent=[self.camera_reading.X[0],
                                                         self.camera_reading.X[-1],
                                                         self.camera_reading.Y[-1],
                                                         self.camera_reading.Y[0]],
                                                 aspect='auto',
                                                 vmin=self.minv,
                                                 vmax=self.maxv,
                                                 cmap='gray',
                                                 interpolation='none')
        self.axis.grid(True)
        self.axis.set_title(self.camera_reading.description)
        self.fig.colorbar(self.image, ax=self.axis)

    def update_data(self, camera_readings: CameraReadings = None):
        self.camera_reading = camera_readings
        self.image.set_data(self.camera_reading.data)
        self.image.set_extent(extent=[self.camera_reading.Y[0], self.camera_reading.Y[-1],
                                      self.camera_reading.X[-1], self.camera_reading.X[0]])
        self.axis.set_title(self.camera_reading.description)

        self.update_limits()

    def update_limits(self):
        """
        update vmin and vmax of imshow
        """
        maxv = np.max(self.camera_reading.data)
        minv = np.min(self.camera_reading.data)
        self.image.set_clim(vmin=minv, vmax=maxv)
        self.draw()
        #print("Datacanvas redrawn")