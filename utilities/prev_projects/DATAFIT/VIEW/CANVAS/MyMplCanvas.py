'''
Created on 27 juil. 2015

@author: saldenisov
'''

import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from matplotlib.figure import Figure

from PyQt5.QtWidgets import QSizePolicy


class MyMplCanvas(FigureCanvas):
    """Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.)."""

    def __init__(self, parent=None, width=4, height=4, dpi=100, LP=None,
                 **kwargs):
        self.Fig = Figure(figsize=(width, height), dpi=dpi)
        #
        FigureCanvas.__init__(self, self.Fig)
        self.setParent(parent)
        #
        if LP:
            self.toolbar = NavigationToolbar(self, LP)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self._colors = ['g', 'c', 'm', 'y', 'k', 'w', 'b']

        self.compute_initial_figure(**kwargs)


    def compute_initial_figure(self, *args, **kwargs):
        pass
