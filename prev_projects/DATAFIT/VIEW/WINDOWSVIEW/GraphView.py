from PyQt5.Qt import QMainWindow

from prev_projects.DATAFIT.UTILITY.OBSERVER import GraphObserver
from prev_projects.DATAFIT.UTILITY.META import Meta
from prev_projects.DATAFIT.VIEW.UI import Ui_GraphWindow


class GraphView(QMainWindow, GraphObserver, metaclass=Meta):
    """
    Represents graphical view of experimental data.
    """

    def __init__(self, in_controller, in_parameters=None, parent=None):
        super(QMainWindow, self).__init__(parent)
        self.controller = in_controller
        self.model = self.controller.model

        self.ui = Ui_GraphWindow()
        self.ui.setupUi(self, in_parameters)

        self.model.addObserver(self)
        #
        self.ui.datacanvas.mpl_connect('key_press_event', self.controller.key_pressed)
        self.ui.datacanvas.mpl_connect('key_release_event', self.controller.key_released)
        self.ui.datacanvas.mpl_connect('button_press_event', self.controller.mouse_pressed)
        self.ui.datacanvas.mpl_connect('motion_notify_event', self.controller.mouse_moved)

        self.ui.kinetics_slider.ValueChanged.connect(self.controller.slider_moved_Y)

        self.ui.kineticscanvas.mpl_connect('key_press_event',self.controller.key_pressed_kinetics)

        self.ui.kineticscanvas.mpl_connect('pick_event', self.controller.on_pick_kinetics)
        self.ui.spectracanvas.mpl_connect('pick_event', self.controller.on_pick_spectrum)

        self.ui.spectrum_slider.ValueChanged.connect(self.controller.slider_moved_X)

        self.ui.data_colorbar_slider.ValueChanged.connect(self.controller.slider_colorbar_moved)

        self.ui.spectracanvas.mpl_connect('key_press_event',self.controller.key_pressed_spectra)

        self.ui.button_Fit.clicked.connect(self.controller.fit_clicked)

        self.ui.list_fits.itemDoubleClicked.connect(self.controller.lfits_clicked)

        self.ui.button_Delete.clicked.connect(self.controller.delete_clicked)
        
        self.ui.button_Save.clicked.connect(self.controller.save_clicked)

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def cursorsChanged(self, who=None):
        """
        Called when cursors positions are change
        """
        cursors = self.model.cursors
        if not who:
            self.ui.datacanvas.update_figure()
            self.ui.spectracanvas.update_figure()
            self.ui.kineticscanvas.update_figure()
            self.ui.kinetics_slider.setStart(int(cursors['y1']))
            self.ui.kinetics_slider.setEnd(int(cursors['y2']))
            self.ui.kinetics_slider.update_Sliderpos()
            self.ui.spectrum_slider.setStart(int(cursors['x1']))
            self.ui.spectrum_slider.setEnd(int(cursors['x2']))
            self.ui.spectrum_slider.update_Sliderpos()

        elif who == 'kinetics':
            self.ui.kineticscanvas.update_figure()

        elif who == 'spectra':
            self.ui.spectracanvas.update_figure()
