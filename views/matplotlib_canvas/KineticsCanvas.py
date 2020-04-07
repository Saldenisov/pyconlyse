import matplotlib.pyplot as plt
import numpy as np
from itertools import islice
from views.matplotlib_canvas import MyMplCanvas
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement



class KineticsCanvas(MyMplCanvas):

    def __init__(self, width: int, height: int, dpi: int,
                 canvas_parent, measurement: Measurement=None):
        super().__init__(width, height, dpi, canvas_parent)

    def compute_figure(self):
        self.axis.axhline(y=0, color='black')
        self.axis.grid(True)
        begining = self.cursors.x1[0]
        end = self.cursors.x2[0]
        data = self.measurement.data[:, begining:end]
        data = np.mean(data, axis=1)
        self.axis.plot(self.measurement.timedelays, data, color='red', marker='o', linewidth=2)
        self.axis.set_xlabel(f'Time Delay, {self.measurement.time_scale}')
        self.axis.set_ylabel('Intensity')
        self.axis.set_title('Kinetics')
        self.draw_cursors(False)
        self.draw()

    def draw_cursors(self, draw=True, cursors=None):
        if cursors:
            self.cursors = cursors
        pass

    def new_data(self):
        self.calc_cursors()
        begining = self.cursors.x1[0]
        end = self.cursors.x2[0]
        data = self.measurement.data[:, begining:end]
        data = np.mean(data, axis=1)
        a = self.axis.lines
        for _ in range(len(self.axis.lines) - 1):
            self.axis.lines[-1].remove()
        self.axis.plot(self.measurement.timedelays, data, color='red', marker='o', linewidth=2)
        self.axis.set_xlabel(f'Time Delay, {self.measurement.time_scale}')
        self.draw_cursors(False)
        self.update_limits()

    def update_data(self, cursors=None):
        if cursors:
            self.draw_cursors(False, cursors=cursors)
        self.new_data()

    def update_limits(self):
        self.axis.relim()
        self.axis.autoscale_view(True, True, True)
        self.draw()



