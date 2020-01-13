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

from concurrent.futures import ThreadPoolExecutor
from utilities.myfunc import info_msg, error_logger, get_local_ip
from PyQt5.QtGui import QCloseEvent
from numpy import pad
from devices.devices import Device
from errors.myexceptions import CannotTreatLogic, WrongServiceGiven
from utilities.data.messages import Message
from communication.messaging.message_utils import MsgGenerator
from views.ui.Motors_widget import Ui_StepMotorsWidgetWindow
from views.ui.widget_stpmtr_axis_simple import Ui_StpMtrGUI
from views.ui.SuperUser_ui import Ui_SuperUser


module_logger = logging.getLogger(__name__)


class SuperUserView(QMainWindow):

    def __init__(self, in_controller, in_model, parent=None):
        super().__init__(parent)
        self.name = 'SuperUserGUI:view: ' + get_local_ip()
        self.logger = module_logger
        info_msg(self, 'INITIALIZING')
        self.controller = in_controller
        self.model = in_model
        self._hb_counter = 0

        self.ui = Ui_SuperUser()
        self.ui.setupUi(self)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.pB_connection.clicked.connect(self.controller.create_service_gui)
        self.ui.lW_devices.itemDoubleClicked.connect(self.controller.lW_devices_double_clicked)
        self.ui.pB_checkServices.clicked.connect(self.controller.pB_checkServices_clicked)
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')

    def closeEvent(self, event):
        self.logger.info('Closing')
        self.controller.quit_clicked(event, total_close=True)

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        info = msg.data.info
        if com == MsgGenerator.HEARTBEAT.mes_name:
            widget1 = self.ui.rB_hb
            widget2 = self.ui.rB_hb2
            widget1v = widget1.isChecked()
            if widget1v:
                widget2.setChecked(True)
            else:
                widget1.setChecked(True)
        elif com == MsgGenerator.AVAILABLE_SERVICES_REPLY.mes_name:
            widget = self.ui.lW_devices
            widget.clear()
            names = []
            for key, item in info.running_services.items():
                names.append(f'{item}:{key}')
            widget.addItems(names)
            self.model.superuser.running_services = info.running_services
        elif com == MsgGenerator.ERROR.mes_name:
            self.ui.tE_info.setText(info.comments)
        elif com == MsgGenerator.INFO_SERVICE_REPLY.mes_name:
            self.ui.tE_info.setText(str(info))
            self.model.service_parameters[info.device_id] = info


from dataclasses import dataclass, field
from utilities.data.datastructures.mes_independent import DeviceStatus
@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    device_status: DeviceStatus = DeviceStatus()
    axes_status: list = field(default_factory=list)
    positions: list = field(default_factory=list)

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

        self.ui = Ui_StpMtrGUI()
        self.ui.setupUi(self, parameters)

        self.model.add_observer(self)
        self.model.model_changed.connect(self.model_is_changed)
        self.ui.pushButton_move.clicked.connect(self.move_axis)
        self.ui.checkBox_On.clicked.connect(self.activate_axis)
        self.ui.spinBox_axis.valueChanged.connect(self.axis_value_change)
        self.ui.closeEvent = self.closeEvent
        info_msg(self, 'INITIALIZED')

    def test(self):
        #partial(self.controller.send_request_to_server, self.gen_activate_axis())
        print(self.ui.checkBox_On.isChecked())

    def axis_value_change(self):
        self.ui.retranslateUi(self, self.controller_status)

    def closeEvent(self, event):
        self.controller.quit_clicked(event)

    def activate_axis(self) -> Message:
        msg = MsgGenerator.do_it(device=self.device, com='activate_axis', service_id=self.parameters.device_id,
                                  parameters={'axis': int(self.ui.spinBox_axis.value()),
                                              'flag': self.ui.checkBox_On.isChecked()})
        self.device.send_msg_externally(msg)

    def move_axis(self) -> Message:
        if self.ui.radioButton_absolute.isChecked():
            how = 'absolute'
        else:
            how = 'relative'
        msg = MsgGenerator.do_it(com='move_to', device=self.device, service_id=self.parameters.device_id,
                                 parameters={'axis': int(self.ui.spinBox_axis.value()),
                                             'pos': float(self.ui.lineEdit_value.text()),
                                             'how': how})
        self.device.send_msg_externally(msg)
        self._moving = True
        # TODO: need to find a way to stop this executor
        self.device.add_to_executor(self.device.exec_mes_every_n_sec, f=self.get_pos,
                                    flag=self._moving, delay=1, n_max=5,
                                    specific={'axis': int(self.ui.spinBox_axis.value())})


    def get_pos(self, axis=None) -> Message:
        if not axis:
            axis = int(self.ui.spinBox_axis.value())
        msg = MsgGenerator.do_it(com='get_pos', device=self.device, service_id=self.parameters.device_id,
                                 parameters={'axis': axis})
        self.device.send_msg_externally(msg)


    def stop_axis(self) -> Message:
        pass
        #return gen_msg(com='move_pos', device=self.device, where=None, how=None)

    def model_is_changed(self, msg: Message):
        com = msg.data.com
        info = msg.data.info
        if com == MsgGenerator.DONE_IT.mes_name:
            if info.com == 'activate_axis':
                flag = info.result['flag']
                self.ui.checkBox_On.setChecked(flag)
                self.controller_status.axes_status[info.result['axis']] = flag
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == 'move_to':
                self._moving = False
                pos = info.result['pos']
                self.ui.lcdNumber_position.display(pos)
                self.controller_status.positions[info.result['axis']] = pos
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == 'get_pos':
                pos = info.result['pos']
                self.ui.lcdNumber_position.display(pos)
                self.controller_status.positions[info.result['axis']] = pos
                self.ui.retranslateUi(self, self.controller_status)
            elif info.com == 'get_controller_state':
                self.controller_status = StpMtrCtrlStatusMultiAxes(**info.result)
                self.ui.retranslateUi(self, self.controller_status)
        elif com == MsgGenerator.ERROR.mes_name:
            #self.ui.tE_info.setText(info.comments)
            msg = MsgGenerator.do_it(com='get_controller_state', device=self.device,
                                     service_id=self.parameters.device_id,
                                     parameters={})
            self.device.send_msg_externally(msg)


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















