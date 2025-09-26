from collections import OrderedDict
from typing import Dict

from _functools import partial
from PyQt5 import QtWidgets
from PyQt5.QtGui import QMouseEvent
from tango import Database
from taurus import Device
from taurus.core import TaurusDevState
from taurus.external.qt import Qt

from DeviceServers import *
from DeviceServers import get_class_match
from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class LaserPointing(DS_General_Widget):
    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.widgets = {}
        self.device_servers = {}
        self.db = Database()
        super().__init__(device_name, parent, vis_type)

    def register_DS_full(self, group_number=1):
        super(LaserPointing, self).register_DS_full()
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{self.dev_name}")
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")

        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")
        lo_states: Qt.QLayout = getattr(self, f"layout_states_{dev_name}")
        lo_controls: Qt.QLayout = getattr(self, f"layout_controls_{dev_name}")
        lo_image: Qt.QLayout = getattr(self, f"layout_image_{dev_name}")
        lo_total: Qt.QLayout = getattr(self, f"layout_total_{dev_name}")

        # Try to load class mappings for subwidgets
        cm = {}
        try:
            cm = get_class_match()
        except Exception:
            pass

        def create_widget_for_device(dev_path, extra=None, prefer_full=False):
            try:
                info = self.db.get_device_info(dev_path)
                ds_class_name = info.class_name
                ds_class_widget = cm.get(ds_class_name)
                if not ds_class_widget:
                    return QtWidgets.QLabel(f"Unknown device class: {ds_class_name} for {dev_path}")
                # Try to instantiate widget; OWIS may require axes (extra)
                if extra is not None:
                    try:
                        return ds_class_widget(dev_path, extra, self, VisType.MIN)
                    except Exception:
                        pass
                # Camera preferring full if requested
                if prefer_full:
                    try:
                        return ds_class_widget(dev_path, self, self.vis_type)
                    except Exception:
                        pass
                # Generic minimal
                return ds_class_widget(dev_path, self, VisType.MIN)
            except Exception as e:
                return QtWidgets.QLabel(f"Failed to create widget for {dev_path}: {e}")

        # Controller mode: if controller exposes composition attributes, use them
        used_controller_mode = False
        try:
            self.groups: OrderedDict = eval(ds.get_groups)
            self.ds_dict: Dict = eval(ds.get_ds_dict)
            self.rules: Dict = eval(ds.get_rules)
            used_controller_mode = True
        except Exception:
            used_controller_mode = False

        if used_controller_mode:
            def register_ds(device_role, device_name):
                extra = None
                if isinstance(device_name, tuple):
                    extra = device_name[1]
                    device_name = device_name[0]
                # Always try to create widget regardless of current device state
                ds_widget = create_widget_for_device(device_name, extra=extra, prefer_full=True)
                self.widgets[device_role] = ds_widget
                try:
                    self.device_servers[device_role] = Device(device_name)
                except Exception:
                    self.device_servers[device_role] = None

            # States
            try:
                group = self.set_states()
                lo_states.addWidget(group)
            except Exception:
                pass

            try:
                for device_role, device_name in self.ds_dict.items():
                    register_ds(device_role, device_name)

                def add_widget_loc(lo_group_loc, group_devices):
                    try:
                        if isinstance(group_devices, str):
                            lo_group_loc.addWidget(self.widgets[group_devices])
                        if isinstance(group_devices, tuple):
                            for device_role in group_devices:
                                lo_group_loc.addWidget(self.widgets[device_role])
                    except KeyError:
                        pass

                for group_name, group_devices in self.groups.items():
                    group_box = Qt.QGroupBox(group_name)
                    setattr(self, f"groupbox_{group_name}_{self.dev_name}", group_box)
                    lo_group_loc = Qt.QHBoxLayout()
                    add_widget_loc(lo_group_loc, group_devices)
                    try:
                        hspacer = QtWidgets.QSpacerItem(
                            0, 40, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
                        )
                        lo_group_loc.addSpacerItem(hspacer)
                    except Exception:
                        pass
                    group_box.setLayout(lo_group_loc)
                    lo_controls.addWidget(group_box)
            except Exception as e:
                print(e)
            try:
                lo_image.addWidget(self.widgets.get("Camera", QtWidgets.QLabel("No Camera widget")))
            except Exception:
                pass
            try:
                vspacer = QtWidgets.QSpacerItem(
                    20, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
                )
                lo_image.addSpacerItem(vspacer)
            except Exception:
                pass

            control_group = QtWidgets.QGroupBox("Controls")
            control_group.setLayout(lo_controls)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidget(control_group)
            scroll.setWidgetResizable(True)
            try:
                scroll.setFixedHeight(800)
                scroll.setFixedWidth(700)
            except Exception:
                pass
            image_group = QtWidgets.QGroupBox("Image")
            image_group.setLayout(lo_image)
            lo_total.addWidget(image_group)
            lo_total.addWidget(scroll)
        else:
            # Direct mode: if controller is not available, try to create a widget for this device itself
            ds_widget = create_widget_for_device(self.dev_name, prefer_full=True)
            try:
                lo_image.addWidget(ds_widget)
            except Exception:
                lo_total.addWidget(ds_widget)

        # State and status
        try:
            self.set_state_status(False)
        except Exception:
            pass

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_total)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_states)
        lo_group.addLayout(lo_device)

        # State and status
        self.set_state_status(False)

        lo_device.addLayout(lo_status)
        lo_device.addLayout(lo_total)
        lo_device.addLayout(lo_buttons)
        lo_device.addLayout(lo_states)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        self.register_DS_full(group_number)

    def register_full_layouts(self):
        super(LaserPointing, self).register_full_layouts()
        setattr(self, f"layout_controls_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_image_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_total_{self.dev_name}", Qt.QHBoxLayout())
        setattr(self, f"layout_states_{self.dev_name}", Qt.QHBoxLayout())

    def register_min_layouts(self):
        super(LaserPointing, self).register_min_layouts()
        setattr(self, f"layout_controls_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_image_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_total_{self.dev_name}", Qt.QHBoxLayout())
        setattr(self, f"layout_states_{self.dev_name}", Qt.QHBoxLayout())

    def set_states(self):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        lo_states = Qt.QHBoxLayout()
        self.rules: OrderedDict = eval(ds.get_rules)
        group = QtWidgets.QGroupBox("States")
        for state, param in self.rules.items():
            rb = Qt.QRadioButton(text=str(state))
            lo_states.addWidget(rb)
            rb.toggled.connect(partial(self.rb_clicked, param))
        group.setLayout(lo_states)
        return group

    def rb_clicked(self, parameters: OrderedDict):
        for ds_role, state in parameters.items():
            ds_widget: DS_General_Widget = self.widgets[ds_role]
            if ds_widget and not isinstance(ds_widget, QtWidgets.QLabel):
                ds_widget.set_the_control_value(state)

    def set_the_control_value(self, value):
        pass

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.parent.active_widget = self.dev_name
        self.parent.update_active_widget()
