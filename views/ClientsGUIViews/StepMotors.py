'''
Created on 15.11.2019

@author: saldenisov
'''
import logging
from _functools import partial

from PyQt5.QtWidgets import (QWidget, QMainWindow,
                             QPushButton, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QRadioButton,
                             QLabel, QLineEdit, QLayout,
                             QSpacerItem, QSizePolicy, QWidgetItem)

from typing import List, Union
from utilities.myfunc import info_msg, error_logger, get_local_ip
from PyQt5.QtGui import QCloseEvent
from numpy import pad
from devices.devices import Device
from errors.myexceptions import CannotTreatLogic, WrongServiceGiven
from utilities.data.messages import Message
from communication.messaging.message_utils import MsgGenerator
from views.ui.Motors_widget import Ui_StepMotorsWidgetWindow
from views.ui.widget_stpmtr_axis_simple import Ui_StpMtrGUI
from dataclasses import dataclass, field
from devices.realdevices.stepmotors.stpmtr_controller import StpMtrController
from utilities.data.datastructures.mes_independent import DeviceStatus


module_logger = logging.getLogger(__name__)


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    device_status: DeviceStatus = DeviceStatus()
    axes_status: list = field(default_factory=list)
    positions: list = field(default_factory=list)
    start_stop: list = field(default_factory=list)


class StepMotorsView(QMainWindow):

    def __init__(self, in_controller, in_model, parameters, parent=None):
        super().__init__(parent)
        self.name = f'StepMotorsClient:view: {parameters.device_id} {get_local_ip()}'
        self.parameters = parameters
        self.controller_status = StpMtrCtrlStatusMultiAxes()
        self.logger = logging.getLogger("StepMotors." + __name__)
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model
        self.device: Device = self.model.superuser
        self._axes_status: List[int] = []
        self._asked_status = 0

        self.ui = Ui_StpMtrGUI()
        self.ui.setupUi(self, parameters)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.checkBox_activate.clicked.connect(self.activate)
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.pushButton_stop.clicked.connect(self.stop_axis)
        self.ui.checkBox_On.clicked.connect(self.activate_axis)
        self.ui.spinBox_axis.valueChanged.connect(self.axis_value_change)
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')


    def axis_value_change(self):
        self.ui.retranslateUi(self, self.controller_status)
        self.ui.progressBar_movement.setValue(0)
        if not self._asked_status:
            msg = MsgGenerator.do_it(com='get_controller_state', device=self.device, service_id=self.parameters.device_id,
                                 parameters={})
            self.device.send_msg_externally(msg)
            self._asked_status = 1

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def activate(self):
        com = StpMtrController.ACTIVATE.name
        msg = MsgGenerator.do_it(device=self.device, com=com, service_id=self.parameters.device_id,
                                 parameters={'flag': self.ui.checkBox_activate.isChecked()})
        self.device.send_msg_externally(msg)
        print(msg)
        self._asked_status = 0

    def activate_axis(self):
        com = StpMtrController.ACTIVATE_AXIS.name
        flag = 1 if self.ui.checkBox_On.isChecked() else 0
        msg = MsgGenerator.do_it(device=self.device, com=com, service_id=self.parameters.device_id,
                                 parameters={'axis': int(self.ui.spinBox_axis.value()),
                                             'flag': flag})
        self.device.send_msg_externally(msg)
        self._asked_status = 0

    def move_axis(self):
        if self.ui.radioButton_absolute.isChecked():
            how = 'absolute'
        else:
            how = 'relative'
        com = StpMtrController.MOVE_AXIS_TO.name
        axis = int(self.ui.spinBox_axis.value())
        pos = float(self.ui.lineEdit_value.text())
        msg = MsgGenerator.do_it(com=com, device=self.device, service_id=self.parameters.device_id,
                                 parameters={'axis': axis,
                                             'pos': pos,
                                             'how': how})
        self.controller_status.start_stop[axis] = [self.controller_status.positions[axis], pos]
        self.device.send_msg_externally(msg)
        self.controller_status.axes_status[axis] = 2
        self.ui.progressBar_movement.setValue(0)
        try:
            self.device.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos, delay=1, n_max=25,
                                        specific={'axis': axis, 'with_return': True})
            self._asked_status = 0
        except Exception as e:
            print(e)

    def get_pos(self, axis=None, with_return=False):
        if axis == None:
            axis = int(self.ui.spinBox_axis.value())
        com = StpMtrController.GET_POS.name
        msg = MsgGenerator.do_it(com=com, device=self.device, service_id=self.parameters.device_id,
                                 parameters={'axis': axis})
        self.device.send_msg_externally(msg)
        if with_return:
            if self.controller_status.axes_status[axis] == 2:
                return True
            else:
                return False

    def stop_axis(self):
        axis = int(self.ui.spinBox_axis.value())
        com = StpMtrController.STOP_AXIS.name
        msg = MsgGenerator.do_it(com=com, device=self.device, service_id=self.parameters.device_id,
                                 parameters={'axis': axis})
        self.device.send_msg_externally(msg)
        self._asked_status = 0

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        info = msg.data.info
        if com == MsgGenerator.DONE_IT.mes_name:
            if info.com == StpMtrController.ACTIVATE.name:
                self.ui.comments.setText(info.comments)
                self.ui.checkBox_activate.setChecked(info.result['flag'])
                self.controller_status.device_status.active = info.result['flag']
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == StpMtrController.ACTIVATE_AXIS.name:
                flag = info.result['flag']
                self.ui.comments.setText(info.comments)
                self.ui.checkBox_On.setChecked(flag)
                self.controller_status.axes_status[info.result['axis']] = flag
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == StpMtrController.MOVE_AXIS_TO.name:
                axis = info.result['axis']
                pos = info.result['pos']
                self._update_progessbar_pos(axis, pos)
                self.ui.comments.setText(info.comments)
                self.ui.lcdNumber_position.display(pos)
                self.controller_status.positions[axis] = pos
                self.controller_status.axes_status[axis] = 1
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == StpMtrController.STOP_AXIS.name:
                self.ui.comments.setText(info.comments)
                pos = info.result['pos']
                axis = info.result['axis']
                self.ui.lcdNumber_position.display(pos)
                self.controller_status.positions[axis] = pos
                self.controller_status.axes_status[axis] = 1
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == StpMtrController.GET_POS.name:
                axis = info.result['axis']
                pos = info.result['pos']
                self._update_progessbar_pos(axis, pos)
                self.controller_status.positions[axis] = pos
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                self.controller_status = StpMtrCtrlStatusMultiAxes(**info.result)
                if not self.controller_status.start_stop:
                    self.controller_status.start_stop = [[0, 0]] * len(self.controller_status.axes_status)
                self.ui.retranslateUi(self, self.controller_status)
        elif com == MsgGenerator.ERROR.mes_name:
            self.ui.comments.setText(info.comments)
            com = StpMtrController.GET_CONTROLLER_STATE.name
            msg = MsgGenerator.do_it(com=com, device=self.device,
                                     service_id=self.parameters.device_id,
                                     parameters={})
            self.device.send_msg_externally(msg)

    def _update_progessbar_pos(self, axis: int, pos: Union[float, int]):
        if self.controller_status.axes_status[axis] == 2 and self.ui.spinBox_axis.value() == axis:
            start = self.controller_status.start_stop[axis][0]
            stop = self.controller_status.start_stop[axis][1]
            per = int((pos - start) / (stop - start) * 100.0)
            self.ui.progressBar_movement.setValue(per)
            self.ui.lcdNumber_position.display(pos)


class StepMotorsView_old(QWidget):
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
