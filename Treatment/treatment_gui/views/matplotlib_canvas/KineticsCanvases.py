from typing import Union, List

import logging
import numpy as np

from treatment_gui.views.matplotlib_canvas.MyMplCanvases import MyMplCanvas, AverageCanvas
from gui.controllers.openers import (H5Opener, ASCIIOpener, HamamatsuFileOpener, CriticalInfoHamamatsu,
                                     Opener, OpenersTypes, OPENER_ACCRODANCE, CriticalInfo)
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement, Cursors2D


module_logger = logging.getLogger(__name__)


class KineticsCanvas(MyMplCanvas):

    def __init__(self, width: int, height: int, dpi: int, canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent, measurement)

    def compute_figure(self):
        self.axis.axhline(y=0, color='black', linewidth=1.5)
        self.draw_cursors(False, self.calc_cursors())
        self.axis.grid(True, alpha=0.3)
        self.axis.plot(self._get_x_values(), self._form_average_data(), color='red', marker='o', 
                      linewidth=2.5, markersize=5)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurement.time_scale}', fontsize=16)
        self.axis.set_ylabel('Intensity', fontsize=16)
        self.axis.set_title(self._title, fontsize=18)
        self.draw()

    def _get_x_values(self) -> np.array:
        return self.measurement.timedelays

    def draw_cursors(self, draw=True, cursors=None):
        if cursors:
            self.cursors = cursors
            lines = self.axis.lines
            for _ in range(len(lines) - 1):
                self.axis.lines[-1].remove()
            self.axis.axvline(x=cursors.y1[1], color='r', linewidth=2)
            self.axis.axvline(x=cursors.y2[1], color='r', linewidth=2)
            self.new_data(measurement=None, cursors=cursors, external_call=False)

    def _form_average_data(self) -> Union[np.array, np.ndarray]:
        """Return kinetics: intensity vs time averaged over wavelength range.

        For Hamamatsu/H5 data we use ``Measurement.data`` with shape
        (wavelengths, timedelays). The cursor x1/x2 indices select a wavelength
        *range* along axis 0, so we slice that axis and average over it to get a
        vector with length equal to the number of time delays.
        """
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

        x = self._get_x_values()
        y = self._form_average_data()

        # Detailed logging to diagnose potential dimension mismatches
        try:
            if len(x) != len(y):
                module_logger.error(
                    "KineticsCanvas: x/y length mismatch before plot: "
                    "len(x)=%d, len(y)=%d, data.shape=%s, "
                    "timedelays.shape=%s, wavelengths.shape=%s, "
                    "cursors=%s, measurement.type=%s, time_scale=%s",
                    len(x),
                    len(y),
                    getattr(self.measurement.data, "shape", None),
                    getattr(self.measurement.timedelays, "shape", None),
                    getattr(self.measurement.wavelengths, "shape", None),
                    getattr(self, "cursors", None),
                    getattr(self.measurement, "type", None),
                    getattr(self.measurement, "time_scale", None),
                )

            self.axis.plot(x, y, color='red', marker='o', markersize=4,
                           linewidth=2.5)
        except ValueError:
            module_logger.exception(
                "KineticsCanvas: matplotlib ValueError during plot. "
                "x.shape=%s, y.shape=%s, data.shape=%s, "
                "timedelays.shape=%s, wavelengths.shape=%s, "
                "cursors=%s, measurement.type=%s, time_scale=%s",
                np.shape(x),
                np.shape(y),
                getattr(self.measurement.data, "shape", None),
                getattr(self.measurement.timedelays, "shape", None),
                getattr(self.measurement.wavelengths, "shape", None),
                getattr(self, "cursors", None),
                getattr(self.measurement, "type", None),
                getattr(self.measurement, "time_scale", None),
            )
            # Re-raise so the caller still sees the error, but with extra context in logs
            raise

        self.axis.set_xlabel(f'{self._x_text}, {self.measurement.time_scale}', fontsize=16)

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
        self.axis.axhline(y=0, color='black', linewidth=1.5)
        self.axis.grid(True, alpha=0.3)
        for kinetics in self.measurements_formed:
            t, data = self._get_x_values(), kinetics
            self.axis.plot(t, data, linewidth=1.5, alpha=0.7)
        self.axis.plot(self._get_x_values(), self._form_average_data(), color='red', marker='o', 
                      linewidth=3, markersize=5)
        self.axis.set_xlabel(f'{self._x_text}, {self.measurements[0].time_scale}', fontsize=16)
        self.axis.set_ylabel('Intensity', fontsize=16)
        self.axis.set_title(f'{self._title}: {self.measurements_formed.shape}', fontsize=18)
        self.axis.set_yscale('log')
        self.draw()

    def _get_x_values(self):
        return self.timedelays

    def _form_data(self) -> Union[np.array, np.ndarray]:
        """Prepare kinetics data for a set of measurements.

        Each measurement.data has shape (wavelengths, timedelays). We average
        over the *wavelength* axis (axis=1 in the stacked array) so that each
        row in ``self.measurements_formed`` is a kinetics trace: intensity vs time.
        """
        self.timedelays = self.measurements[0].timedelays
        maps = np.array([map.data for map in self.measurements])
        # maps.shape -> (n_maps, wavelengths, timedelays)
        # Average over wavelengths → (n_maps, timedelays)
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
