'''
Created on 15.11.2019

@author: saldenisov
'''

import os
import logging
import pathlib
from time import sleep
from PyQt5.QtWidgets import QMessageBox, QApplication, QListWidgetItem
from communication.messaging.message_utils import gen_msg
from utilities.myfunc import info_msg, get_local_ip
from views.ClientGUIViews import SuperUserView, StepMotorsView


module_logger = logging.getLogger(__name__)


class SuperClientGUIcontroller():

    def __init__(self, in_model):
        """
        """
        self.logger = module_logger
        self.name = 'ServerGUI:controller: ' + get_local_ip()
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.view = SuperUserView(self, in_model=self.model)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def exec_user_com(self, widget):
        com = widget.text()
        com_splitted = com.split(';')
        path = self.model.app_folder
        pyexec = str(pathlib.Path(path.parent / 'python_env\mypy37\Scripts' / 'python.exe'))
        for x in com_splitted:
            x = x.split(' ')
            x = [command for command in x if command]
            com = x[0]
            rest = x[1:]
            if com == '-start_service':
                p = str(path / 'bin' / 'service.py')
                exc = f'start cmd /K {pyexec} {p} {rest[0]} {rest[1]}'
                os.system(exc)
            elif com == '-start':
                p = str(path / 'bin' / rest[0])
                exc = f'start cmd /K {pyexec} {p}'
                for r in rest[1:]:
                    exc = exc + r
                os.system(exc)

    def lW_devices_double_clicked(self, item: QListWidgetItem):
        service_id = item.text().split(':')[2]
        client = self.model.superuser
        msg = gen_msg(com='info_service_demand', device=client,
                      service_id=service_id, rec_id=client.server_msgn_id)
        self.model.superuser.thinker.add_task_out(msg)

    def pB_checkServices_clicked(self):
        msg = gen_msg('available_services', device=self.model.superuser)
        self.model.superuser.thinker.add_task_out(msg)

    def quit_clicked(self, event):
        try:
            self.model.superuser.stop()
        except Exception as e:
            print(e)
        self.logger.info('Closing')
        QApplication.quit()


class StepMotorsController:
    '''
    Created on 7 juin 2016

    @author: saldenisov
    '''

    def __init__(self, in_model):
        """
        """
        self.logger = logging.getLogger('StepMotors' + '.' + __name__)
        self.name = 'StepMotorsClient:controller: ' + get_local_ip()
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.view = StepMotorsView(self, in_model=self.model)
        self.view.show()
        info_msg(self, 'INITIALIZED')

    def help_clicked(self):
        QMessageBox.information(self.view,
                                'Help',
                                """For any help contact:\n
                                Sergey A. Denisov\n
                                sergey.denisov@u-psud.fr""")

    def author_clicked(self):
        QMessageBox.information(self.view,
                                'Author information',
                                """Author: Sergey A. Denisov\n
                                e-mail: sergey.denisov@u-psud.fr\n
                                telephone: +33625252159""")

    def quit_clicked(self, event):
        reply = QMessageBox.question(self.view, 'Quiting',
                                     "Are you sure to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info('Closing')
            QApplication.quit()
        else:
            event.ignore()

    def listwidget_double_clicked(self, item: QListWidgetItem):
        motor_controller_name = item.text()
        if not motor_controller_name in self.model.stpmtrctrl:
            try:
                self.model.add_stpmtrctrl(motor_controller_name)
                self.view.add_controls(motor_controller_name)
            except Exception as e:
                self.logger.error(e)
        else:
            self.model.remove_stpmtrctrl(motor_controller_name)
            self.view.delete_controls(motor_controller_name)

    def connect_stpmtrctrl(self, motor_controller_name: str):
        on = self.model.dlines[motor_controller_name].on
        active = self.model.dlines[motor_controller_name].active
        if not active:
            self.model.dlines[motor_controller_name].check()
        elif not on:
            self.model.dlines[motor_controller_name].turn_on()

    def move_stpmtr(self, motor_controller_name: str, axis: int, where: int):
        pass
