'''
Created on 12 May 2017

@author: Sergey Denisov
'''

from PyQt5.Qt import  QWidget,QLineEdit, QSignalMapper

from _functools import partial

from utilities.observers.observers import SettingsObserver
from utilities.meta.meta import Meta
from gui.views.ui.settings_general_widget import Ui_settings_general_widget


class SettingsView(QWidget, SettingsObserver, metaclass=Meta):
    """
    """

    def __init__(self, in_controller, in_model, parent=None):
        """

        """
        super(QWidget, self).__init__(parent)
        self.controller = in_controller
        self.model = in_model

        self.ui = Ui_settings_general_widget()
        self.ui.setupUi(self)

        self.model.add_measurement_observer(self)

        self.mapper = QSignalMapper(self)

        widgets = self.findChildren(QLineEdit)

        self.ui.save_settingsButton.clicked.connect(partial(self.controller.buttonsavesettings_clicked,
                                                            widgets=widgets))
        

    def model_is_changed(self):
        pass

