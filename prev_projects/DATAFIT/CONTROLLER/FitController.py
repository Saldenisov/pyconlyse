from VIEW import FitView
from HELPFUL import ndarray_tostring

from os import path
from PyQt5.QtWidgets import QApplication
from numpy import vstack, transpose, savetxt
import logging
module_logger = logging.getLogger(__name__)


class FitController():
    """
    Class FitController is a controller which coordinates work between
    view and model.
    """

    def __init__(self, in_model):
        self.logger = logging.getLogger("MAIN." + __name__)
        self.model = in_model
        self.clipboard = QApplication.clipboard()

        self.view = FitView(self)
        self.view.show()

    def key_pressed_canvas(self, event):
        if event.key == 'ctrl+c':
            var = transpose(self.model.copy_data())
            s = ndarray_tostring(var)
            self.clipboard.setText(s)

    def lin_log_changed(self):
        """
        Notifies model Observers when lin/log scale is changed in view.
        """
        self.model.notifyObservers()

    def norm_real_changed(self):
        """
        Notifies model when Normalization is selected.
        """
        self.model.notifyObservers()

    def fit_clicked(self):
        """
        Handles the event, when the button fit pressed.
        """
        variables = self.model.parameters['variables']
        bounds = {}
        guess = {}

        for var in variables:
            bounds[var] = (self.view.ui.table_var_map[var + 'min'].value(),
                           self.view.ui.table_var_map[var + 'max'].value())
            guess[var] = self.view.ui.table_var_map[var + 'guess'].value()

        self.model.parameters['bounds'] = bounds
        self.model.parameters['guess'] = guess
        self.model.parameters['Norm'] = self.view.ui.radiobutton_Norm.isChecked()
        self.model.parameters['method'] = self.view.ui.combobox_Method.currentText()

        try:
            self.model.do_fit()
        except Exception as e:
            self.logger.error(e)

    def save_clicked(self):
        cursors = self.model.parameters['cursors']
        y1 = cursors['y1']
        y2 = cursors['y2']
        x1 = cursors['x1']
        x2 = cursors['x2']

        file_path = self.model.parameters['filepath']
        file_path = path.splitext(file_path)[0]

        out1 = transpose(self.model.copy_data())

        variables = self.model.parameters['variables']
        fit_coeffs = []

        for i in variables:
            fit_coeffs.append(self.model.coeffs[i])

        out2 = transpose(vstack([variables, fit_coeffs]))

        if self.view.ui.radiobutton_Norm.isChecked():
            temp = 'Norm'
        else:
            temp = 'Real'

        model = self.model.form_model_name()
        save_to1 = file_path + \
            '-'.join(('-', model, 'y', str(y1),
                      str(y2), 'x', str(x1), str(x2), temp, '.txt'))

        save_to2 = file_path + '-'.join(('-', model, 'y', str(
            y1), str(y2), 'x', str(x1), str(x2), temp, 'param, .txt'))
        try:
            savetxt(save_to1, out1, delimiter='\t', fmt="%s")
            savetxt(save_to2, out2, delimiter='\t', fmt="%s")
        except Exception as e:
            print(e)
