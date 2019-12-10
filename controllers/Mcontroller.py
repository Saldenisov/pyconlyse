'''
Created on 7 juin 2016

@author: saldenisov
'''

import logging
import subprocess

from PyQt5.QtWidgets import (QMessageBox, QApplication)

from controllers.SettingsWidgetcontroller import SettingsContoller
from views import Mview

module_logger = logging.getLogger(__name__)



class Mcontroller():
    """
    Class MainController is tests_hardware controller
    which coordinates work between
    MainView and MainModel
    """

    def __init__(self, in_model):
        """
        """
        self.logger = logging.getLogger("MAIN." + __name__)
        self.model = in_model

        self.view = Mview(self, in_model=self.model)
        self.view.show()
        
        self.settingscontroller = SettingsContoller(Settingsmodel(self.model))


    def help_clicked(self):
        QMessageBox.information(self.view,
                                'Help',
                                """For any help contact:\n
                                Dr. Sergey A. Denisov\n
                                sergey.denisov@u-psud.fr""")

    def author_clicked(self):
        QMessageBox.information(self.view,
                                'Author information',
                                """Author: Dr. Sergey A. Denisov\n
                                e-mail: sergey.denisov@u-psud.fr\n
                                telephone: +33625252159""")

    def quit_clicked(self, event):
        if not self.model.developing:
            reply = QMessageBox.question(self.view, 'MessageOld',
                                     "Are you sure to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.logger.info('Closing')
                self.model.DL_off()
                QApplication.quit()
            else:
                event.ignore()
        else:
            self.logger.info('Closing')
            self.model.DL_off()
            QApplication.quit()

    def settings_clicked(self):
        self.settingscontroller.view.show()

    def connect_DL(self):
        subprocess.Popen(["python", "C:/Users/Sergey Denisov/Documents/REPS/pytlyse/StepMotorsGUI.py"],
                         close_fds=True)
