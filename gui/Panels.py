from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon, QMouseEvent, QKeyEvent
from PyQt5.QtCore import Qt
from abc import abstractmethod
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor
from DeviceServers.DS_Widget import DS_General_Widget


class General_Panel(QtWidgets.QWidget):

    def __init__(self, choice, widget_class: DS_General_Widget, title='', icon: QIcon = None, width=2, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(icon)

        self.width = width
        self.number_ds = len(choice)
        self.active_ds = ''

        self.layout_main = QtWidgets.QVBoxLayout()
        number_lo = 1 if self.number_ds // self.width == 0 else self.number_ds // width

        for lo_i in range(number_lo):
            setattr(self, f'lo_DS_{lo_i}', QtWidgets.QHBoxLayout())
            lo: QtWidgets.QLayout = getattr(self, f'lo_DS_{lo_i}')
            self.layout_main.addLayout(lo)
            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.HLine)
            separator.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            separator.setLineWidth(3)
            self.layout_main.addWidget(separator)

        self.widget_creation(choice, widget_class)

        self.setLayout(self.layout_main)

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_{group_number}')
                setattr(self, f'DS_{dev_name}', widget_class(dev_name, self))
                s_m = getattr(self, f'DS_{dev_name}')
                lo.addWidget(s_m)
            i += 1


class Standa_Panel(General_Panel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2):
        if widget_class != Standa_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')

        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width)
        self.move_step = 1

    def keyPressEvent(self, event: QKeyEvent):
        if self.active_ds:
            ds = getattr(self, f'DS_{self.active_ds}')
            pos = ds.pos_widget.value
            if event.key() in [Qt.Key_Left, Qt.Key_Down, Qt.Key_Right, Qt.Key_Up]:
                if event.key() in [Qt.Key_Left, Qt.Key_Down]:
                    pos = pos - self.move_step
                elif event.key() in [Qt.Key_Right, Qt.Key_Up]:
                    pos = pos + self.move_step

                ds.pos_widget.setValue(pos)

                ds_real = getattr(ds, f'ds_{self.active_ds}')
                
                ds_real.move_axis_abs(pos)


class OWIS_Panel(General_Panel):
    """
    This class determines the panel for OWIS PS90 multi-axes controller.
    """

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=1):
        if widget_class != OWIS_motor:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice=choice, widget_class=widget_class, title=title, icon=icon, width=width)
        self.move_step = 1

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name, axes in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f'lo_DS_{group_number}')
                setattr(self, f'DS_{dev_name}', widget_class(dev_name, axes, self))
                s_m = getattr(self, f'DS_{dev_name}')
                lo.addWidget(s_m)
            i += 1


class Netio_Panel(General_Panel):

    def __init__(self, choice, widget_class, title='', icon: QIcon = None, width=2, *args, **kwargs):
        if widget_class != Netio_pdu:
            raise Exception(f'Wrong widget class {widget_class} is passed.')
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)
