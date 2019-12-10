'''
Created on 15.11.2019

@author: saldenisov
'''
import logging
from _functools import partial

from PyQt5 import QtCore
from PyQt5.QtWidgets import (QWidget, QMainWindow,
                             QPushButton, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QRadioButton,
                             QLabel, QLineEdit, QLayout,
                             QSpacerItem, QSizePolicy, QWidgetItem)

from utilities.myfunc import list_to_str_repr, info_msg, error_logger, get_local_ip
from views.ui.ServerGUI_ui import Ui_ServerGUI
from PyQt5.QtGui import QCloseEvent
from numpy import pad
from errors.myexceptions import CannotTreatLogic, WrongServiceGiven
from utilities.data.messages import Message
from views.ui.Motors_widget import Ui_StepMotorsWidgetWindow
from views.ui.SuperUser_ui import Ui_SuperUser


module_logger = logging.getLogger(__name__)


class SuperUserView(QMainWindow):
    """
    """
    def __init__(self, in_controller, in_model, parent=None):
        super().__init__(parent)
        self.name = 'SuperUserGUI:view: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model

        self.ui = Ui_SuperUser()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        #self.ui.pB_start.clicked.connect(self.controller.connect_to_server)
        self.ui.lW_devices.itemDoubleClicked.connect(self.controller.lW_devices_double_clicked)
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        info = msg.data.info
        if com == 'heartbeat':
            pass
            #widget = self.ui.rB_hb
            #before = widget.isChecked()
            #widget.setChecked(not before)
        elif com == 'available_services_reply':
            widget = self.ui.lW_devices
            names = []
            for key, item in info.running_services.items():
                names.append(f'{item.name}:{key}')
            widget.addItems(names)
            self.model.superuser.running_services = info.running_services

class StepMotorsView(QMainWindow):
    '''
    Created on 11 mai 2017

    @author: saldenisov
    '''
    def __init__(self, in_controller, in_model, parent=None):
        super().__init__(parent)
        self.name = 'StepMotorsClient:view: ' + get_local_ip()
        self.logger = logging.getLogger("StepMotors." + __name__)
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model

        self.ui = Ui_StepMotorsWidgetWindow()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.actionHelp.triggered.connect(self.controller.help_clicked)
        self.ui.actionAuthor.triggered.connect(self.controller.author_clicked)
        self.ui.actionQuit.triggered.connect(partial(self.controller.quit_clicked, event=QCloseEvent()))
        self.ui.listWidget.itemDoubleClicked.connect(self.controller.listwidget_double_clicked)

        self.ui.listWidget.addItems(self.model.config.get('widget').sections())

        info_msg(self, 'INITIALIZED')

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def add_controls(self, stpmtrctrl_name):
        """
        When listwidget containing name of step motors controller is clicked, then
        controls are added to view of StepMotors_widget.
        :param stpmtrctrl_name: name of step motors controller
        :return: None
        """

        var = 'layout_' + stpmtrctrl_name
        setattr(self.ui, var, QVBoxLayout())
        layout: QVBoxLayout = getattr(self.ui, var)
        layout.setObjectName(var)
        self.ui.horizontalLayout.addLayout(layout)

        # Label
        self._add_widget(QLabel, layout, 'label.' + stpmtrctrl_name, stpmtrctrl_name + ': pos, mm')

        # where to move
        self._add_widget(QLineEdit, layout, 'lineedit_where.' + stpmtrctrl_name, '')

        # axis radiobuttons
        axis_number = int(self.model.stpmtrctrl[stpmtrctrl_name].get_general_settings()['axis_number'])
        radiobutton_layout = QHBoxLayout()
        for axis in range(axis_number):
            self._add_widget(QRadioButton, radiobutton_layout, f'radiobutton_axis{axis + 1}.' + stpmtrctrl_name,
                             str(axis + 1))
        widget: QRadioButton = getattr(self.ui, f'radiobutton_axis{1}.' + stpmtrctrl_name)
        widget.setChecked(True)
        layout.addLayout(radiobutton_layout)

        #button move
        self._add_widget(QPushButton, layout, 'button_move.' + stpmtrctrl_name, 'Move')
        widget = getattr(self.ui, 'button_move.' + stpmtrctrl_name)
        widget.setEnabled(False)
        widget.clicked.connect(partial(self.controller.move_stpmtr,
                                       DL_name=widget.objectName().split('.')[1],
                                       axis=1, where=100))
        #button_connect
        self._add_widget(QPushButton, layout, 'button_connect.' + stpmtrctrl_name, 'Service is OFF')
        widget = getattr(self.ui, 'button_connect.' + stpmtrctrl_name)
        widget.clicked.connect(partial(self.controller.connect_stpmtrctrl,
                                       DL_name=widget.objectName().split('.')[1]))
        widget.setEnabled(False)

        #status
        self._add_widget(QLabel, layout, 'label_status.' + stpmtrctrl_name, 'status: ')

        #TextEidt
        self._add_widget(QTextEdit, layout, 'text_edit.' + stpmtrctrl_name, """ """)
        widget = getattr(self.ui, 'text_edit.' + stpmtrctrl_name)
        widget.setText('Lets do some work')
        #Spacer
        spacerItem = QSpacerItem(0, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
        name = 'spacer_' + stpmtrctrl_name
        setattr(self.ui, name, spacerItem)
        layout.addItem(spacerItem)

    def delete_controls(self, stpmtrctrl_name):
        layout = getattr(self.ui, 'layout_' + stpmtrctrl_name)

        def del_from_layout(layout):
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if not isinstance(item, QLayout):
                    if isinstance(item, QWidgetItem):
                        item.widget().close()
                    elif isinstance(item, QSpacerItem):
                        pass
                    layout.removeItem(item)
                else:
                    del_from_layout(item)

        del_from_layout(layout)

        self.ui.horizontalLayout.removeItem(layout)

    def _add_widget(self, widget_cls: QWidget, layout: QLayout, name: str, text: str):
        setattr(self.ui, name, widget_cls(self.ui.centralwidget))
        widget = getattr(self.ui, name)
        widget.setObjectName(name)
        widget.setText(text)
        layout.addWidget(widget)

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        parent = msg.body.sender.split(':')[-1]
        try:
            if com == 'lineedit_update':
                widget_name = msg.data.info.widget_name
                info = msg.data.info.parameters
                axis_number = info['axis_number']
                positions = info['positions']
                widget = getattr(self.ui, f'{widget_name}.{parent}')
                widget.setText(self._set_pos(axis_number, positions))
            elif com == 'status_server':
                status = msg.data.info.active
                if status:
                    text = 'Server status: OK'
                else:
                    text = 'Server status: not OK'
                    try:
                        widget = getattr(self.ui, 'text_edit.' + parent)
                        if widget.toPlainText():
                            widget.setFocus()
                            widget.clear()
                            widget.setText("")
                    except:
                        pass
                widget = getattr(self.ui, 'label_status.' + parent)
                widget.setText(text)
                widget = getattr(self.ui, 'button_connect.' + parent)
                widget.setEnabled(status)
            elif com == 'status_service':
                if msg.data.info.service_name in self.model.dlines.keys():
                    active = msg.data.info.active
                    on = msg.data.info.on
                    if on:
                        text = 'stepmotors is ON'
                        status = True
                    else:
                        status = False
                        if active:
                            text = 'Service is ON'
                        else:
                            text = 'Service is OFF'
                    widget = getattr(self.ui, 'button_connect.' + parent)
                    widget.setText(text)
                    widget = getattr(self.ui, 'button_move.' + parent)
                    widget.setEnabled(status)


                else:
                    raise WrongServiceGiven(msg.data.info.service_name)

            elif com == 'available_services':
                self._update_text_edit(parent, msg['data']['services'])
            elif com == 'activate_service':
                if isinstance(msg['data']['status'], bool):
                    pass
                elif isinstance(msg['data']['status'], str):
                    self._update_text_edit(parent, msg['data']['status'])
                else:
                    raise CannotTreatLogic('activate_service')
        except (WrongServiceGiven, CannotTreatLogic) as e:
            error_logger(self, self.model_is_changed, e)

    @staticmethod
    def _set_pos(axis_number: int, positions: list) -> str:
        if positions:
            text = ''
            if axis_number > len(positions):
                diff = axis_number - len(positions)
                positions = pad(positions, (0, diff), 'constant')
            i = 1
            for pos in positions:
                text = text + f'axis{i}={pos}; '
                i += 1
            return text
        else:
            return 'axis1=0; axis2=0;'

    def _update_text_edit(self, name_dl: str, text: str):
        try:
            widget = getattr(self.ui, 'text_edit.' + name_dl)
            widget.setFocus()
            widget.clear()
            widget.setText(text)
        except Exception as e:
            error_logger(self, self._update_text_edit, e)















