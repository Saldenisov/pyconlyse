from typing import Union

import numpy
import numpy as np
from matplotlib.image import AxesImage

from treatment_gui.views.matplotlib_canvas.MyMplCanvases import MyMplCanvas
from treatment_gui.views.matplotlib_canvas.DraggableCursors import ToggleableCursor
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


class DataCanvas(MyMplCanvas):
    """
    Represents 2D datastructures map using matplotlib imshow
    Enhanced with transparent background and larger fonts
    """
    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        self.toolbar = NavigationToolbar(self, self.parent)
        self.draggable_cursor = None
        self.cursor_callback = None

    def compute_figure(self, figure_name='Test'):
        self.cursors: Cursors2D = self.calc_cursors()
        self.maxv = np.max(self.measurement.data)
        self.minv = np.min(self.measurement.data)

        self.image: AxesImage = self.axis.imshow(self.measurement.data.transpose(),
                                                 extent=[self.measurement.wavelengths[0],
                                                        self.measurement.wavelengths[-1],
                                                        self.measurement.timedelays[-1],
                                                        self.measurement.timedelays[0]],
                                                 aspect='auto',
                                                 vmin=self.minv,
                                                 vmax=self.maxv,
                                                 interpolation='none')
        self.axis.grid(True, alpha=0.3)
        
        # Set label font sizes
        self.axis.set_xlabel('Wavelength, nm', fontsize=16)
        self.axis.set_ylabel(f'Time delay, {self.measurement.time_scale}', fontsize=16)
        if figure_name:
            self.axis.set_title(figure_name, fontsize=18)
        
        # Create colorbar with larger font
        cbar = self.fig.colorbar(self.image, ax=self.axis)
        cbar.ax.tick_params(labelsize=12)
        
        self.draw_cursors()

    def enable_draggable_cursors(self, callback=None):
        """
        Enable draggable cursor lines for region selection.
        
        Parameters
        ----------
        callback : callable, optional
            Function to call when cursor positions change
        """
        self.cursor_callback = callback
        if self.draggable_cursor is not None:
            self.draggable_cursor.remove()
        
        self.draggable_cursor = ToggleableCursor(
            self.axis,
            on_change_callback=self._on_cursor_change,
            initial_cursors=self.cursors
        )
        self.draw()
    
    def _on_cursor_change(self, x1, x2, y1, y2):
        """Internal callback when draggable cursors move."""
        if self.cursor_callback:
            self.cursor_callback(x1, x2, y1, y2)
    
    def draw_cursors(self, cursors=None, draw=False):
        """Update cursor positions (used by draggable cursor system)."""
        if cursors:
            self.cursors = cursors
            if self.draggable_cursor:
                self.draggable_cursor.update_from_cursors(cursors)
        
        if draw:
            self.draw()

    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        return self.measurement.data.transpose()

    def new_data(self, measurement: Measurement, cursors: Cursors2D, map_index=0):
        self.measurement = measurement
        self.image.set_data(self.measurement.data.transpose())
        self.image.set_extent(extent=[self.measurement.wavelengths[0], self.measurement.wavelengths[-1],
                                      self.measurement.timedelays[-1], self.measurement.timedelays[0]])
        self.axis.set_title(f'Map index={map_index}', fontsize=18)
        self.draw_cursors(cursors=cursors)
        self.update_limits()

    def _set_labels(self):
        pass

    def update_data(self, measurement: Measurement = None, cursors: Cursors2D = None, map_index=0):
        if measurement:
            draw = False
            self.measurement = measurement
            self.image.set_data(self.measurement.data.transpose())
            self.axis.set_title(f'Map index={map_index}', fontsize=18)
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
