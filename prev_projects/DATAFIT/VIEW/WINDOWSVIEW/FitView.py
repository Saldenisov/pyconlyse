from PyQt5.Qt import QMainWindow, QWidget

from UTILITY.OBSERVER import FitObserver
from UTILITY.META import Meta
from VIEW.UI import Ui_FitWindow


class FitView(QMainWindow, FitObserver, metaclass=Meta):
    """
    Represents graphical view of experimental data fit.
    """

    def __init__(self, inController, parent=None):
        super(QWidget, self).__init__(parent)
        self.controller = inController
        self.model = self.controller.model

        self.ui = Ui_FitWindow()
        self.ui.setupUi(self)

        self.model.addObserver(self)

        self.ui.radiobutton_X_lin.clicked.connect(
            self.controller.lin_log_changed)
        self.ui.radiobutton_X_log.clicked.connect(
            self.controller.lin_log_changed)
        self.ui.radiobutton_Y_lin.clicked.connect(
            self.controller.lin_log_changed)
        self.ui.radiobutton_Y_log.clicked.connect(
            self.controller.lin_log_changed)
        self.ui.radiobutton_Norm.clicked.connect(
            self.controller.norm_real_changed)
        self.ui.radiobutton_Real.clicked.connect(
            self.controller.norm_real_changed)
        self.ui.button_FIT.clicked.connect(self.controller.fit_clicked)
        self.ui.button_SAVE.clicked.connect(self.controller.save_clicked)
        self.ui.fitcanvas.mpl_connect('key_press_event',
                                          self.controller.key_pressed_canvas)

    def modelIsChanged(self):
        """
        Method is called when modelIsChanges
        """
        logX = self.ui.radiobutton_X_log.isChecked()
        logY = self.ui.radiobutton_Y_log.isChecked()
        Norm = self.ui.radiobutton_Norm.isChecked()

        self.ui.fitcanvas.update_figure(logX=logX, logY=logY, Norm=Norm)

        guess = self.model.parameters['guess']
        bounds = self.model.parameters['bounds']

        if self.model.parameters['fitmodel']['constrained']:
            for param in self.model.coeffs:
                self.ui.table_var_map[
                    param + 'fit'].setText('%.2f' % self.model.coeffs[param])
                try:
                    self.ui.table_var_map[param + 'guess'].setValue(guess[param])
                    self.ui.table_var_map[param + 'min'].setValue(bounds[param][0])
                    self.ui.table_var_map[param + 'max'].setValue(bounds[param][1])
                except Exception as e:
                    print(e)

        if not self.model.parameters['fitmodel']['constrained']:
            for param in self.model.coeffs:
                self.ui.table_var_map[
                    param + 'fit'].setText('%.2f' %
                                           self.model.coeffs[param])
                self.ui.table_var_map[
                    param + 'guess'].setValue(guess[param])
                self.ui.table_var_map[param + 'min'].setDisabled(True)
                self.ui.table_var_map[param + 'max'].setDisabled(True)
