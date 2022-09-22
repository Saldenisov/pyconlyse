from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon, QMouseEvent, QKeyEvent
from PyQt5.QtCore import Qt
from abc import abstractmethod
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor
from DeviceServers.BASLER.DS_BASLER_Widget import Basler_camera
from DeviceServers.ANDOR_CCD.DS_ANDOR_CCD_Widget import ANDOR_CCD
from DeviceServers.AVANTES_CCD.DS_AVANTES_CCD_Widget import AVANTES_CCD
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu
from DeviceServers.Experiment.DS_Experiment_Widget import Experiment
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor
from DeviceServers.TopDirect.DS_TOPDIRECT_Widget import TopDirect_Motor
from DeviceServers.LaserPointing.DS_LaserPointing_Widget import LaserPointing
from DeviceServers.ARCHIVE.DS_ARCHIVE_Widget import Archive
from DeviceServers.DS_Widget import DS_General_Widget
from DeviceServers.DS_Widget import VisType


class GeneralPanel(QtWidgets.QWidget):

    def __init__(self, choice, widget_class: DS_General_Widget, title='', icon: QIcon = None, width=2,
                 vis_type=VisType.FULL, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vis_type = vis_type
        self.widgets = {}

        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(icon)

        self.layout_main = QtWidgets.QVBoxLayout()

        self.width = width
        self.number_ds = len(choice)
        self.active_widget = ''

        number_lo = 1 if self.number_ds // self.width == 0 else self.number_ds // width

        for lo_i in range(number_lo):
            setattr(self, f'lo_DS_widget_{lo_i}', QtWidgets.QHBoxLayout())
            lo: QtWidgets.QLayout = getattr(self, f'lo_DS_widget_{lo_i}')
            self.layout_main.addLayout(lo)
            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.HLine)
            separator.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            separator.setLineWidth(3)
            self.layout_main.addWidget(separator)

        self.widget_creation(choice, widget_class)
        self.label_active_widget = QtWidgets.QLabel(f'Active widget: {self.active_widget}') 
        self.layout_main.addWidget(self.label_active_widget)
        self.setLayout(self.layout_main)

    def add_widget(self, name, widget):
        self.widgets[name] = widget

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_widget_{group_number}')
                setattr(self, f'{dev_name}', widget_class(dev_name, self, self.vis_type))
                s_m = getattr(self, f'{dev_name}')
                self.add_widget(f'{dev_name}', s_m)
                hspacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
                lo.addWidget(s_m)
                lo.addSpacerItem(hspacer)
            i += 1

    def update_active_widget(self):
        self.label_active_widget.setText(self.active_widget)


class StandaPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Standa_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')

        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1

    def update_active_widget(self):
        super(StandaPanel, self).update_active_widget()
        for w_name, widget in self.widgets.items():
            if w_name != self.active_widget:
                widget.setStyleSheet("")
                widget.widget_active = False
            else:
                widget.widget_active = True


class TopDirectPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != TopDirect_Motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1

    def keyPressEvent(self, event: QKeyEvent):
        if self.active_widget:
            ds_widget = self.widgets[self.active_widget]
            pos = float(ds_widget.pos_widget.text())
            if event.key() in [Qt.Key_Left, Qt.Key_Down, Qt.Key_Right, Qt.Key_Up]:
                if event.key() in [Qt.Key_Left, Qt.Key_Down]:
                    pos = pos - self.move_step
                elif event.key() in [Qt.Key_Right, Qt.Key_Up]:
                    pos = pos + self.move_step
                ds_widget.wheel.setValue(pos)
                ds_real = getattr(ds_widget, f'ds_{self.active_widget}')
                ds_real.move_axis_abs(pos)

    def update_background_widgets(self):
        for w_name, widget in self.widgets.items():
            if w_name != self.active_widget:
                widget.setStyleSheet("")


class OWISPanel(GeneralPanel):
    """
    This class determines the panel for OWIS PS90 multi-axes controller.
    """

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=1, *args, **kwargs):
        if widget_class != OWIS_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width, *args, **kwargs)
        self.move_step = 1
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name, axes in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_widget_{group_number}')
                setattr(self, f'{dev_name}', widget_class(dev_name, axes, self, self.vis_type))
                s_m = getattr(self, f'{dev_name}')
                self.add_widget(f'{dev_name}', s_m)
                lo.addWidget(s_m)
            i += 1

    def context_menu(self):
        pass


class NetioPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Netio_pdu:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ExperimentPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Experiment:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class BaslerPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Basler_camera:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ANDOR_CCDPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != ANDOR_CCD:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class AVANTES_CCDPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != AVANTES_CCD:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class LaserPointingPanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != LaserPointing:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ArchivePanel(GeneralPanel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Archive:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)
