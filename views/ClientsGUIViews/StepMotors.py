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

from typing import List, Union, Dict
from utilities.myfunc import info_msg, error_logger, get_local_ip
from PyQt5.QtGui import QCloseEvent
from numpy import pad
from devices.devices import Device
from errors.myexceptions import CannotTreatLogic, WrongServiceGiven
from utilities.data.messages import Message, ServiceInfoMes, DoneIt, Error
from utilities.data.datastructures.mes_independent import *
from communication.messaging.message_utils import MsgGenerator
from views.ui.Motors_widget import Ui_StepMotorsWidgetWindow
from views.ui.widget_stpmtr_axis_simple import Ui_StpMtrGUI
from devices.realdevices.stepmotors.stpmtr_controller import StpMtrController


module_logger = logging.getLogger(__name__)


class StepMotorsView(QMainWindow):

    def __init__(self, in_controller, in_model, service_parameters: ServiceInfoMes, parent=None):
        super().__init__(parent)
        self._asked_status = 0
        self.controller = in_controller
        self.controller_status = StpMtrCtrlStatusMultiAxes(axes=service_parameters.device_description.axes,
                                                           axes_previous=service_parameters.device_description.axes,
                                                           device_status=service_parameters.device_status,
                                                           device_status_previous=service_parameters.device_status)
        if not self.controller_status.start_stop:
            self.controller_status.start_stop = [[0, 0]] * len(self.controller_status.axes)
        self.name = f'StepMotorsClient:view: {service_parameters.device_id} {get_local_ip()}'
        self.logger = logging.getLogger("StepMotors." + __name__)
        info_msg(self, 'INITIALIZING')
        self.model = in_model
        self.device: Device = self.model.superuser
        self.service_parameters: ServiceInfoMes = service_parameters

        self.ui = Ui_StpMtrGUI()
        self.ui.setupUi(self, service_parameters)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.checkBox_activate.clicked.connect(self.activate)
        self.ui.checkBox_power.clicked.connect(self.power)
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.pushButton_stop.clicked.connect(self.stop_axis)
        self.ui.checkBox_On.clicked.connect(self.activate_axis)
        self.ui.spinBox_axis.valueChanged.connect(self.update_state)
        self.ui.closeEvent = self.closeEvent

        self.update_state()
        info_msg(self, 'INITIALIZED')

    def activate(self):
        com = StpMtrController.ACTIVATE.name
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 service_id=self.service_parameters.device_id,
                                 input=FuncActivateInput(flag=self.ui.checkBox_activate.isChecked()))
        self.device.send_msg_externally(msg)
        self._asked_status = 0

    def activate_axis(self):
        com = StpMtrController.ACTIVATE_AXIS.name
        flag = 1 if self.ui.checkBox_On.isChecked() else 0
        msg = MsgGenerator.do_it(device=self.device, com=com,
                                 service_id=self.service_parameters.device_id,
                                 input=FuncActivateAxisInput(axis_id=int(self.ui.spinBox_axis.value()),
                                                             flag=flag))
        self.device.send_msg_externally(msg)
        self._asked_status = 0

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def get_pos(self, axis_id=None, with_return=False):
        if axis_id is None:
            axis_id = int(self.ui.spinBox_axis.value())
        com = StpMtrController.GET_POS.name
        msg = MsgGenerator.do_it(com=com, device=self.device, service_id=self.service_parameters.device_id,
                                 input=FuncGetPosInput())
        self.device.send_msg_externally(msg)
        if with_return:
            return True if self.controller_status.axes[axis_id].status == 2 else False

    def move_axis(self):
        if self.ui.radioButton_absolute.isChecked():
            how = 'absolute'
        else:
            how = 'relative'
        com = StpMtrController.MOVE_AXIS_TO.name
        axis_id = int(self.ui.spinBox_axis.value())
        pos = float(self.ui.lineEdit_value.text())
        msg = MsgGenerator.do_it(com=com, device=self.device, service_id=self.service_parameters.device_id,
                                 input=FuncMoveAxisToInput(axis_id=axis_id, pos=pos, how=how))
        self.controller_status.start_stop[axis_id] = [self.controller_status.axes[axis_id].position, pos]
        self.device.send_msg_externally(msg)
        self.controller_status.axes[axis_id].status = 2
        self.ui.progressBar_movement.setValue(0)
        self.device.add_to_executor(Device.exec_mes_every_n_sec, f=self.get_pos, delay=1, n_max=25,
                                    specific={'axis_id': axis_id, 'with_return': True})
        self._asked_status = 0

    def model_is_changed(self, msg: Message):
        try:
            com = msg.data.com
            info: Union[DoneIt, Error] = msg.data.info
            if self.service_parameters.device_id in msg.body.sender_id:

                if com == MsgGenerator.DONE_IT.mes_name:
                    info: DoneIt = msg.data.info
                    result: Union[FuncActivateOutput,
                                  FuncActivateAxisOutput,
                                  FuncGetStpMtrControllerStateOutput,
                                  FuncMoveAxisToOutput,
                                  FuncGetPosOutput,
                                  FuncStopAxisOutput,
                                  FuncPowerOutput] = info.result
                    self.ui.comments.setText(result.comments)
                    if info.com == StpMtrController.ACTIVATE.name:
                        result: FuncActivateOutput = result
                        self.controller_status.device_status = result.device_status
                    elif info.com == StpMtrController.ACTIVATE_AXIS.name:
                        result: FuncActivateAxisOutput = result
                        self.controller_status.axes = result.axes
                        self.ui.retranslateUi(self, self.controller_status)
                    elif info.com == StpMtrController.MOVE_AXIS_TO.name:
                        result: FuncMoveAxisToOutput = result
                        self.controller_status.axes = result.axes
                    elif info.com == StpMtrController.GET_POS.name:
                        result: FuncGetPosOutput = result
                        self.controller_status.axes = result.axes
                    elif info.com == StpMtrController.GET_CONTROLLER_STATE.name:
                        result: FuncGetStpMtrControllerStateOutput = result
                        self.controller_status.axes = result.axes
                        self.controller_status.device_status = result.device_status
                        if not self.controller_status.start_stop:
                            self.controller_status.start_stop = [[0.0, 0.0]] * len(self.controller_status.axes)
                    elif info.com == StpMtrController.STOP_AXIS.name:
                        result: FuncStopAxisOutput = result
                        self.controller_status.axes = result.axes
                    elif info.com == StpMtrController.POWER.name:
                        result: FuncPowerOutput = result
                        self.controller_status.device_status = result.device_status

                elif com == MsgGenerator.ERROR.mes_name:
                    self.ui.comments.setText(info.comments)
                    com = StpMtrController.GET_CONTROLLER_STATE.name
                    msg = MsgGenerator.do_it(com=com, device=self.device,
                                             service_id=self.service_parameters.device_id,
                                             input=FuncGetStpMtrControllerStateInput())
                    self.device.send_msg_externally(msg)

                self.update_state()
        except Exception as e:
            self.logger.error(e)

    def stop_axis(self):
        axis_id = int(self.ui.spinBox_axis.value())
        com = StpMtrController.STOP_AXIS.name
        msg = MsgGenerator.do_it(com=com, device=self.device,
                                 service_id=self.service_parameters.device_id,
                                 input=FuncStopAxisInput(axis_id=axis_id))
        self.device.send_msg_externally(msg)
        self._asked_status = 0

    def power(self):
        com = StpMtrController.POWER.name
        msg = MsgGenerator.do_it(device=self.device, com=com, service_id=self.service_parameters.device_id,
                                 input=FuncPowerInput(device_id=self.service_parameters.device_id,
                                                      flag=self.ui.checkBox_power.isChecked()))
        self.device.send_msg_externally(msg)

    def update_state(self):
        cs = self.controller_status
        ui = self.ui
        if cs.axes != cs.axes_previous:
            for now, then in zip(cs.axes.items(), cs.axes_previous.items()):
                if now != then:
                    axis: AxisStpMtrEssentials = now[1]
                    ui.checkBox_On.setChecked(axis.status)
 #                   ui.ax

            self.controller_status.axes_previous = self.controller_status.axes

        if cs.device_status != cs.device_status_previous:
            ui.checkBox_power.setChecked(cs.device_status.power)
            ui.checkBox_activate.setChecked(cs.device_status.active)
            ui.lcdNumber_position.display(axis.position)

            self.controller_status.device_status_previous = self.controller_status.device_status


    def _update_progessbar_pos(self, axis: int, pos: Union[float, int]):
        if self.controller_status.axes[axis].status == 2 and self.ui.spinBox_axis.value() == axis:
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
