import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.image import AxesImage
from matplotlib.patches import Circle
from typing import List, Tuple
from utilities.datastructures.mes_independent.measurments_dataclass import CameraReadings
matplotlib.use('Qt5Agg')


class DataCanvasCamera(FigureCanvas):
    """
    Represents 2D datastructures map using matplotlib imshow
    """
    def __init__(self, width: int, height: int, dpi: int, canvas_parent, camera_reading: CameraReadings = None):
        self.parent = canvas_parent
        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        FigureCanvas.__init__(self, self.fig)
        self.axis: Axes = self.fig.add_subplot(111)
        if not camera_reading:
            data = np.random.randn(400, 512)
            timestamp = datetime.timestamp(datetime.now())
            self.camera_reading = CameraReadings(data, timestamp, '')
        else:
            self.camera_reading = camera_reading
        self.axis.set_xlabel('Width, pixel')
        self.axis.set_ylabel(f'Height, pixel')
        self.image: AxesImage = None
        self.compute_figure()

        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        self.toolbar = NavigationToolbar(self, self.parent)

    def add_points(self, points: List[Tuple[int]]):
        circles = []
        c_map = DataCanvasCamera.get_cmap(n=len(points))
        for coordinate, n in zip(points, range(len(points))):
            #x, y = np.random.randint(200, 300, 1), np.random.randint(200, 300, 1)
            #coordinate = (x, y)
            circles.append(Circle(coordinate, radius=1, color=c_map(n), zorder=n+1))

        if self.image:
            [p.remove() for p in reversed(self.axis.patches)]
            for circle in circles:
                self.axis.add_patch(circle)
            self.draw()

    def compute_figure(self, figure_name=''):
        self.image: AxesImage = self.axis.imshow(self.camera_reading.data,
                                                 extent=[self.camera_reading.Y[0],
                                                         self.camera_reading.Y[-1],
                                                         self.camera_reading.X[-1],
                                                         self.camera_reading.X[0]],
                                                 aspect='auto',
                                                 vmin=np.min(self.camera_reading.data),
                                                 vmax=np.max(self.camera_reading.data),
                                                 cmap='gray',
                                                 interpolation='none')
        self.axis.grid(True)
        self.axis.set_title(self.camera_reading.description)
        self.fig.colorbar(self.image, ax=self.axis)

    @staticmethod
    def get_cmap(n, name='hsv'):
        '''Returns a function that maps each index in 0, 1, ..., n-1 to a distinct
        RGB color; the keyword argument name must be a standard mpl colormap name.'''
        return plt.cm.get_cmap(name, n)

    def update_data(self, camera_reading: CameraReadings = None, offsets:Tuple[int] = None):
        self.camera_reading = camera_reading
        self.image.set_data(self.camera_reading.data)
        if offsets:
            extent = [offsets[0], camera_reading.X[-1] + offsets[0], camera_reading.Y[-1],  camera_reading.Y[0] + offsets[1]]
        else:
            extent = [camera_reading.X[0], camera_reading.X[-1], camera_reading.Y[-1], camera_reading.Y[0]]
        print(f'EXTENT: {extent}. OFFSET: {offsets}')
        self.image.set_extent(extent=extent)
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
