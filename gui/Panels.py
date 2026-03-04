from functools import partial

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5.QtWidgets import QAction

from DeviceServers.cameras.andor.DS_ANDOR_CCD_Widget import ANDOR_CCD
from DeviceServers.cameras.avantes.DS_AVANTES_CCD_Widget import AVANTES_CCD
from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera
from DeviceServers.control.experiment.DS_Experiment_Widget import Experiment
from DeviceServers.control.laser_pointing.DS_LaserPointing_Widget import LaserPointing
from DeviceServers.data.archive.DS_ARCHIVE_Widget import Archive
from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor
from DeviceServers.motion.standa.DS_STANDA_Widget import Standa_motor
from DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget import TopDirect_Motor
from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu
from DeviceServers.power.iTest.DS_iTest_PSU_Tabs import Itest_PSU
from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType
from DeviceServers.spectrographs.avantes.DS_AVANTES_SPECTRO_Widget import (
    AVANTES_SPECTRO,
)


class GeneralPanel(QtWidgets.QWidget):
    def __init__(
        self,
        choice,
        widget_class: DS_General_Widget,
        title="",
        icon: QIcon = None,
        width=2,
        vis_type=VisType.FULL,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.vis_type = vis_type
        self.widgets = {}
        self._widget_slots = {}

        if title:
            self.setWindowTitle(title)
        if icon:
            self.setWindowIcon(icon)

        self.layout_main = QtWidgets.QVBoxLayout()

        self.width = width
        self.number_ds = len(choice)
        self.active_widget = ""

        number_lo = 1 if self.number_ds // self.width == 0 else self.number_ds // width

        for lo_i in range(number_lo):
            setattr(self, f"lo_DS_widget_{lo_i}", QtWidgets.QHBoxLayout())
            lo: QtWidgets.QLayout = getattr(self, f"lo_DS_widget_{lo_i}")
            self.layout_main.addLayout(lo)
            separator = QtWidgets.QFrame()
            separator.setFrameShape(QtWidgets.QFrame.HLine)
            separator.setSizePolicy(
                QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
            )
            separator.setLineWidth(3)
            self.layout_main.addWidget(separator)

        self.widget_creation(choice, widget_class)
        self.label_active_widget = QtWidgets.QLabel(
            f"Active widget: {self.active_widget}"
        )
        self.layout_main.addWidget(self.label_active_widget)
        self.setLayout(self.layout_main)
        
        # Add fullscreen functionality
        self.is_fullscreen = False
        self.setup_fullscreen_actions()

    def _build_unavailable_widget(self, dev_name: str, error_text: str):
        return UnavailableDeviceWidget(
            dev_name,
            error_text,
            retry_callback=partial(self._retry_device_widget, dev_name),
            parent=self,
        )

    def _replace_widget(self, dev_name: str, widget):
        slot = self._widget_slots[dev_name]
        layout: QtWidgets.QLayout = slot["layout"]
        old_widget = slot["widget"]
        index = layout.indexOf(old_widget)

        try:
            layout.removeWidget(old_widget)
        except Exception:
            pass

        if index >= 0:
            layout.insertWidget(index, widget)
        else:
            layout.addWidget(widget)

        try:
            old_widget.hide()
            old_widget.setParent(None)
            old_widget.deleteLater()
        except Exception:
            pass

        slot["widget"] = widget
        setattr(self, f"{dev_name}", widget)
        self.add_widget(dev_name, widget)

    def _retry_device_widget(self, dev_name: str):
        slot = self._widget_slots.get(dev_name)
        if not slot:
            return False

        try:
            widget = slot["factory"]()
        except Exception as e:
            current_widget = slot["widget"]
            if isinstance(current_widget, UnavailableDeviceWidget):
                current_widget.set_error_text(str(e))
            return False

        self._replace_widget(dev_name, widget)
        return True

    def _add_device_widget(self, dev_name: str, layout, factory, add_spacer: bool = True):
        try:
            widget = factory()
        except Exception as e:
            widget = self._build_unavailable_widget(dev_name, str(e))

        self._widget_slots[dev_name] = {
            "layout": layout,
            "factory": factory,
            "widget": widget,
        }

        setattr(self, f"{dev_name}", widget)
        self.add_widget(dev_name, widget)
        layout.addWidget(widget)

        if add_spacer:
            hspacer = QtWidgets.QSpacerItem(
                20,
                40,
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Minimum,
            )
            layout.addSpacerItem(hspacer)

        return widget

    def add_widget(self, name, widget):
        self.widgets[name] = widget

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f"lo_DS_widget_{group_number}")
                self._add_device_widget(
                    dev_name,
                    lo,
                    lambda dev_name=dev_name: widget_class(
                        dev_name, self, self.vis_type
                    ),
                )
            i += 1

    def update_active_widget(self):
        self.label_active_widget.setText(self.active_widget)
    
    def setup_fullscreen_actions(self):
        """Setup fullscreen toggle actions"""
        # F11 key for fullscreen toggle
        fullscreen_action = QAction(self)
        fullscreen_action.setShortcut(Qt.Key_F11)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(fullscreen_action)
        
        # Also allow Escape to exit fullscreen
        escape_action = QAction(self)
        escape_action.setShortcut(Qt.Key_Escape)
        escape_action.triggered.connect(self.exit_fullscreen)
        self.addAction(escape_action)
    
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()
    
    def enter_fullscreen(self):
        """Enter fullscreen mode"""
        if not self.is_fullscreen:
            self.showFullScreen()
            self.is_fullscreen = True
    
    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False


class StandaPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != Standa_motor:
            raise Exception(f"Wrong widget class {widget_class} is passed.")

        super().__init__(
            choice=choice,
            widget_class=widget_class,
            title=title,
            icon=icon,
            width=width,
            *args,
            **kwargs,
        )
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
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != TopDirect_Motor:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(
            choice=choice,
            widget_class=widget_class,
            title=title,
            icon=icon,
            width=width,
            *args,
            **kwargs,
        )
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
                ds_real = getattr(ds_widget, f"ds_{self.active_widget}")
                ds_real.move_axis_abs(pos)

    def update_background_widgets(self):
        for w_name, widget in self.widgets.items():
            if w_name != self.active_widget:
                widget.setStyleSheet("")


class OWISPanel(GeneralPanel):
    """This class determines the panel for OWIS PS90 multi-axes controller."""

    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=1,
        *args,
        **kwargs,
    ):
        if widget_class != OWIS_motor:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(
            choice=choice,
            widget_class=widget_class,
            title=title,
            icon=icon,
            width=width,
            *args,
            **kwargs,
        )
        self.move_step = 1
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)

    def widget_creation(self, choice, widget_class):
        i = 0
        for dev_name, axes in choice:
            group_number = i // self.width
            if dev_name:
                lo: Qt.QLayout = getattr(self, f"lo_DS_widget_{group_number}")
                self._add_device_widget(
                    dev_name,
                    lo,
                    lambda dev_name=dev_name, axes=axes: widget_class(
                        dev_name, axes, self, self.vis_type
                    ),
                    add_spacer=False,
                )
            i += 1

    def context_menu(self):
        pass


class NetioPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != Netio_pdu:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ExperimentPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != Experiment:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class BaslerPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != Basler_camera:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ANDOR_CCDPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != ANDOR_CCD:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class AVANTES_CCDPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != AVANTES_CCD:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class AVANTES_SPECTROPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != AVANTES_SPECTRO:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class LaserPointingPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != LaserPointing:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ArchivePanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=2,
        *args,
        **kwargs,
    ):
        if widget_class != Archive:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class ITestPanel(GeneralPanel):
    def __init__(
        self,
        choice,
        widget_class,
        title="",
        icon: QIcon = None,
        width=1,
        *args,
        **kwargs,
    ):
        if widget_class != Itest_PSU:
            raise Exception(f"Wrong widget class {widget_class} is passed.")
        super().__init__(choice, widget_class, title, icon, width, *args, **kwargs)


class UnavailableDeviceWidget(QtWidgets.QFrame):
    def __init__(
        self,
        dev_name: str,
        error_text: str,
        retry_callback=None,
        parent=None,
        retry_interval_ms: int = 5000,
    ):
        super().__init__(parent)
        self._retry_callback = retry_callback
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QtWidgets.QLabel(f"Unavailable: {dev_name}")
        title.setWordWrap(True)
        layout.addWidget(title)

        self._details = QtWidgets.QLabel()
        self._details.setWordWrap(True)
        layout.addWidget(self._details)
        self.set_error_text(error_text)

        if retry_callback is not None:
            retry_button = QtWidgets.QPushButton("Retry")
            retry_button.clicked.connect(retry_callback)
            layout.addWidget(retry_button)

            self._retry_timer = QTimer(self)
            self._retry_timer.setInterval(retry_interval_ms)
            self._retry_timer.timeout.connect(retry_callback)
            self._retry_timer.start()

    def set_error_text(self, error_text: str):
        self._details.setText(
            "The device widget could not be created.\n"
            f"Last error: {error_text}"
        )
