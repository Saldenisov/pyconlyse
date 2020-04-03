'''
Created on 27 juil. 2015

@author: saldenisov
'''
from abc import abstractmethod
import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from matplotlib.axes import Axes

from matplotlib.figure import Figure

from PyQt5.QtWidgets import QSizePolicy


class MyMplCanvas(FigureCanvas):
    """Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.)."""

    def __init__(self, width=4, height=4, dpi=100, canvas_parent=None):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axis: Axes = self.fig.add_subplot(111)
        self.compute_figure()

        FigureCanvas.__init__(self, self.fig)
        self.parent = canvas_parent

        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']

    @abstractmethod
    def compute_figure(self, *args, **kwargs):
        pass
