from sys import modules as _refactor_modules

from DeviceServers.control.laser_pointing.laser_pointing_widget_methods_register_ds_min import _bind_laser_pointing_widget_methods_register_ds_min

from DeviceServers.control.laser_pointing.laser_pointing_widget_methods_active_pair_is_ready import _bind_laser_pointing_widget_methods_active_pair_is_ready

from DeviceServers.control.laser_pointing.laser_pointing_widget_methods_update_convergence_plot import _bind_laser_pointing_widget_methods_update_convergence_plot

import json
import math
from collections import OrderedDict
from threading import Thread
from typing import Dict

from _functools import partial
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QMouseEvent
from tango import Database
from taurus import Device
from taurus.core import TaurusDevState as TaurusDevState
from taurus.external.qt import Qt
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueCheckBox

from DeviceServers import class_match as class_match
from DeviceServers import get_class_match
from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType
from DeviceServers.motion.standa.DS_STANDA_LaserPointing_Widget import Standa_LaserPointing
from DeviceServers.control.laser_pointing.automatic_search import optical_point_group
from DeviceServers.control.laser_pointing.widget_helpers import (
    active_point_aperture,
    format_optical_status_value,
    is_other_optical_role,
    manual_alignment_motion_enabled,
)


class OpticalStatusValue(TaurusLabel):
    """Taurus readback label with operator-friendly optical units."""

    def __init__(self, role, parent=None):
        self.optical_role = str(role)
        super().__init__(parent)
        self.setAutoTrim(False)
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def displayValue(self, value):
        return format_optical_status_value(self.optical_role, value)


class LaserPointing(DS_General_Widget):
    point_application_finished = QtCore.pyqtSignal(str, int, bool, str)
    pair_initialization_finished = QtCore.pyqtSignal(bool, str)

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        self.widgets = {}
        self.device_servers = {}
        self._point_apply_busy = False
        self._pair_initialization_busy = False
        self._pair_initialization_supported = False
        self._search_running = False
        self._active_actuator_group = 0
        self.point_button_groups = []
        self.point_buttons_by_state = {}
        self.db = Database()
        super().__init__(device_name, parent, vis_type)
        self.point_application_finished.connect(self._finish_point_application)
        self.pair_initialization_finished.connect(
            self._finish_active_pair_initialization
        )

    def register_DS_full(self, group_number=1):
        super(LaserPointing, self).register_DS_full()
        dev_name = self.dev_name
        optical_points_panel = None
        component_status_panel = None
        ds: Device = getattr(self, f"ds_{self.dev_name}")
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")

        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")
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
            def configure_laser_widget(widget):
                # Absolute X/Y camera traces jump by design when the selected
                # observation diaphragm changes.  The composite controller
                # displays delta-error convergence against time instead.
                if hasattr(widget, "set_position_tracking_visible"):
                    widget.set_position_tracking_visible(False)
                return widget

            def configure_power_mapping(widget):
                if extra is None or not hasattr(widget, "set_recovery_power_device"):
                    return widget
                try:
                    axes = {int(axis) for axis in extra}
                except (TypeError, ValueError):
                    return widget
                if not axes or not (axes <= {1, 2, 3} or axes == {4}):
                    return widget
                property_name = (
                    "backend_three_axes_device"
                    if axes <= {1, 2, 3}
                    else "backend_fourth_axis_device"
                )
                try:
                    values = self.db.get_device_property(dev_path, [property_name]).get(
                        property_name, []
                    )
                    backend_name = str(values[0]).strip() if values else ""
                    if backend_name:
                        widget.set_recovery_power_device(backend_name)
                except Exception:
                    pass
                return widget

            try:
                info = self.db.get_device_info(dev_path)
                ds_class_name = info.class_name
                
                # Use LaserPointing-specific widget for Standa devices
                if ds_class_name == "DS_Standa_Motor":
                    return Standa_LaserPointing(dev_path, self, VisType.MIN)
                
                ds_class_widget = cm.get(ds_class_name)
                if not ds_class_widget:
                    return QtWidgets.QLabel(f"Unknown device class: {ds_class_name} for {dev_path}")
                # Keep the minimal preview/Grab view, with optional camera
                # settings built only when the operator expands them. Creating
                # Width/Height editors at startup reads GenICam nodes that may
                # be unavailable while acquisition is running.
                if ds_class_name == "DS_Basler_camera":
                    camera_widget = ds_class_widget(dev_path, self, VisType.MIN)
                    camera_widget.enable_laser_camera_controls()
                    return configure_laser_widget(camera_widget)
                # Try to instantiate widget; OWIS may require axes (extra)
                if extra is not None:
                    try:
                        return configure_laser_widget(configure_power_mapping(
                            ds_class_widget(dev_path, extra, self, VisType.MIN)
                        ))
                    except Exception:
                        pass
                # Camera preferring full if requested
                if prefer_full:
                    try:
                        return configure_laser_widget(
                            ds_class_widget(dev_path, self, self.vis_type)
                        )
                    except Exception:
                        pass
                # Generic minimal
                return configure_laser_widget(
                    ds_class_widget(dev_path, self, VisType.MIN)
                )
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
            manual_hardware = QtWidgets.QWidget()
            manual_layout = QtWidgets.QVBoxLayout(manual_hardware)
            manual_layout.setContentsMargins(4, 4, 4, 4)
            manual_layout.setSpacing(5)

            other_hardware = QtWidgets.QWidget()
            other_layout = QtWidgets.QVBoxLayout(other_hardware)
            other_layout.setContentsMargins(4, 4, 4, 4)
            other_layout.setSpacing(5)

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

            try:
                for device_role, device_name in self.ds_dict.items():
                    register_ds(device_role, device_name)

                self._actuator_role_groups = [
                    tuple(roles)
                    for name, roles in self.groups.items()
                    if str(name).lower().startswith("actuators")
                    and not isinstance(roles, str)
                ]

                lo_controls.setContentsMargins(4, 4, 4, 4)
                lo_controls.setSpacing(6)
                self.add_automatic_search_controls(lo_controls, ds)
                self.add_pair_initialization_controls(lo_controls, ds)
                self.mount_interlock_status = QtWidgets.QLabel()
                self.mount_interlock_status.setWordWrap(True)
                lo_controls.addWidget(self.mount_interlock_status)
                lo_controls.addStretch(1)
                self.set_active_actuator_group(0)

                # Optical-point presets affect every operating mode, so keep
                # their selector above the tabs instead of nesting it under
                # Manual.
                optical_points_panel = self.set_states("Shared")
                component_status_panel = self.build_component_status_panel()

                def add_widget_loc(lo_group_loc, group_devices):
                    try:
                        if isinstance(group_devices, str):
                            widget = self.widgets[group_devices]
                            lo_group_loc.addWidget(widget)
                        elif isinstance(group_devices, tuple):
                            for device_role in group_devices:
                                widget = self.widgets[device_role]
                                lo_group_loc.addWidget(widget)
                    except KeyError:
                        pass

                def add_control_group(target_layout, group_name, group_devices):
                    group_box = Qt.QGroupBox(group_name)
                    setattr(
                        self,
                        f"groupbox_{group_name}_{self.dev_name}",
                        group_box,
                    )

                    lo_group_loc = Qt.QVBoxLayout()
                    lo_group_loc.setContentsMargins(4, 5, 4, 4)
                    lo_group_loc.setSpacing(3)

                    if isinstance(group_devices, tuple) and len(group_devices) > 1:
                        # The composite client can be narrow when multiple
                        # cameras are open, so keep one device on each row.
                        for device_role in group_devices:
                            row_layout = Qt.QHBoxLayout()
                            try:
                                row_layout.addWidget(self.widgets[device_role])
                            except KeyError:
                                pass
                            row_layout.setSpacing(4)
                            lo_group_loc.addLayout(row_layout)
                    else:
                        add_widget_loc(lo_group_loc, group_devices)

                    group_box.setSizePolicy(
                        QtWidgets.QSizePolicy.Expanding,
                        QtWidgets.QSizePolicy.Maximum,
                    )
                    group_box.setLayout(lo_group_loc)
                    target_layout.addWidget(group_box)

                self._other_optical_roles = []
                camera_device = self.ds_dict.get("Camera", "")
                for group_name, group_devices in self.groups.items():
                    group_name_lower = group_name.lower()
                    roles = (
                        (group_devices,)
                        if isinstance(group_devices, str)
                        else tuple(group_devices)
                    )
                    other_optical_roles = tuple(
                        role
                        for role in roles
                        if is_other_optical_role(role, camera_device)
                    )
                    if other_optical_roles:
                        optical_group_name = (
                            "Main laser optics"
                            if group_name_lower == "laser parameters"
                            else group_name
                        )
                        add_control_group(
                            other_layout,
                            optical_group_name,
                            other_optical_roles,
                        )
                        self._other_optical_roles.extend(other_optical_roles)
                        for role in other_optical_roles:
                            widget = self.widgets.get(role)
                            if hasattr(widget, "set_alignment_motion_enabled"):
                                widget.set_alignment_motion_enabled(
                                    True, "Direct optical control"
                                )

                    is_manual_hardware = (
                        "actuator" in group_name_lower
                        or "translation" in group_name_lower
                        or "stage" in group_name_lower
                        or "owis" in group_name_lower
                    )
                    if is_manual_hardware:
                        add_control_group(manual_layout, group_name, group_devices)

                manual_layout.addStretch(1)
                other_layout.addStretch(1)
            except Exception as e:
                print(e)
            try:
                lo_image.addWidget(self.widgets.get("Camera", QtWidgets.QLabel("No Camera widget")))
                self.add_delta_coordinates_view(lo_image)
            except Exception:
                pass
            try:
                vspacer = QtWidgets.QSpacerItem(
                    20, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
                )
                lo_image.addSpacerItem(vspacer)
            except Exception:
                pass

            control_group = QtWidgets.QGroupBox("Automatic controls")
            control_group.setLayout(lo_controls)
            # Ensure control group expands to fill available space
            control_group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidget(control_group)
            scroll.setWidgetResizable(True)
            # Remove size constraints to allow full expansion
            scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            image_group = QtWidgets.QGroupBox("Image")
            image_group.setObjectName("laserPointingImageGroup")
            image_group.setLayout(lo_image)
            image_group.setMinimumWidth(560)

            manual_scroll = QtWidgets.QScrollArea()
            manual_scroll.setWidget(manual_hardware)
            manual_scroll.setWidgetResizable(True)
            manual_scroll.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )

            other_scroll = QtWidgets.QScrollArea()
            other_scroll.setWidget(other_hardware)
            other_scroll.setWidgetResizable(True)
            other_scroll.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )

            mode_tabs = QtWidgets.QTabWidget()
            mode_tabs.setObjectName("laserPointingModeTabs")
            mode_tabs.setDocumentMode(True)
            mode_tabs.setMinimumWidth(500)
            mode_tabs.addTab(scroll, "Automatic")
            mode_tabs.addTab(manual_scroll, "Manual")
            mode_tabs.addTab(other_scroll, "Other")
            mode_tabs.setCurrentIndex(0)
            # Camera and signed XY error are shared operating views and stay
            # visible in every mode. Manual contains alignment mounts, Other
            # provides direct diaphragm and λ/2 controls, and Automatic owns
            # its point sequence and convergence controls.
            lo_total.addWidget(image_group, 5)
            lo_total.addWidget(mode_tabs, 4)
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

        # LaserPointing is an operational composite view. Parameter refresh is
        # automatic, so duplicated generic "Update param" buttons only add
        # noise. Keep the global widget unchanged and suppress them here.
        Qt.QTimer.singleShot(0, self.hide_update_param_buttons)

        # Status and shared optical presets stay above every operating tab.
        lo_device.addLayout(lo_status)
        if optical_points_panel is not None:
            shared_panel = QtWidgets.QWidget()
            shared_layout = QtWidgets.QHBoxLayout(shared_panel)
            shared_layout.setContentsMargins(0, 0, 0, 0)
            shared_layout.setSpacing(6)
            shared_layout.addWidget(
                optical_points_panel, 0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop
            )
            if component_status_panel is not None:
                shared_layout.addWidget(component_status_panel, 1)
            lo_device.addWidget(shared_panel)
        lo_device.addLayout(lo_total)
        lo_device.addLayout(lo_buttons)
        
        lo_group.addLayout(lo_device)

    _laser_pointing_widget_methods_register_ds_min = _bind_laser_pointing_widget_methods_register_ds_min(_refactor_modules[__name__])
    register_DS_min = _laser_pointing_widget_methods_register_ds_min["register_DS_min"]

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

    set_state_status = _laser_pointing_widget_methods_register_ds_min["set_state_status"]

    set_states = _laser_pointing_widget_methods_register_ds_min["set_states"]

    _component_device_path = (staticmethod)(_laser_pointing_widget_methods_register_ds_min["_component_device_path"])

    _component_caption = (staticmethod)(_laser_pointing_widget_methods_register_ds_min["_component_caption"])

    _status_value_card = _laser_pointing_widget_methods_register_ds_min["_status_value_card"]

    _status_state_card = _laser_pointing_widget_methods_register_ds_min["_status_state_card"]

    build_component_status_panel = _laser_pointing_widget_methods_register_ds_min["build_component_status_panel"]

    _point_tooltip = (staticmethod)(_laser_pointing_widget_methods_register_ds_min["_point_tooltip"])

    point_clicked = _laser_pointing_widget_methods_register_ds_min["point_clicked"]

    _finish_point_application = _laser_pointing_widget_methods_register_ds_min["_finish_point_application"]

    _set_point_buttons_enabled = _laser_pointing_widget_methods_register_ds_min["_set_point_buttons_enabled"]

    _clear_point_selection = _laser_pointing_widget_methods_register_ds_min["_clear_point_selection"]

    _point_buttons = _laser_pointing_widget_methods_register_ds_min["_point_buttons"]

    set_active_actuator_group = _laser_pointing_widget_methods_register_ds_min["set_active_actuator_group"]

    add_pair_initialization_controls = _laser_pointing_widget_methods_register_ds_min["add_pair_initialization_controls"]

    _refresh_pair_initialization_capability = _laser_pointing_widget_methods_register_ds_min["_refresh_pair_initialization_capability"]
    del _laser_pointing_widget_methods_register_ds_min

    _laser_pointing_widget_methods_active_pair_is_ready = _bind_laser_pointing_widget_methods_active_pair_is_ready(_refactor_modules[__name__])
    _active_pair_is_ready = _laser_pointing_widget_methods_active_pair_is_ready["_active_pair_is_ready"]

    _update_pair_initialization_controls = _laser_pointing_widget_methods_active_pair_is_ready["_update_pair_initialization_controls"]

    initialize_active_pair = _laser_pointing_widget_methods_active_pair_is_ready["initialize_active_pair"]

    _finish_active_pair_initialization = _laser_pointing_widget_methods_active_pair_is_ready["_finish_active_pair_initialization"]

    hide_update_param_buttons = _laser_pointing_widget_methods_active_pair_is_ready["hide_update_param_buttons"]

    add_automatic_search_controls = _laser_pointing_widget_methods_active_pair_is_ready["add_automatic_search_controls"]

    add_delta_coordinates_view = _laser_pointing_widget_methods_active_pair_is_ready["add_delta_coordinates_view"]

    start_automatic_search = _laser_pointing_widget_methods_active_pair_is_ready["start_automatic_search"]

    stop_automatic_search = _laser_pointing_widget_methods_active_pair_is_ready["stop_automatic_search"]

    cancel_automatic_search = _laser_pointing_widget_methods_active_pair_is_ready["cancel_automatic_search"]

    pause_automatic_search = _laser_pointing_widget_methods_active_pair_is_ready["pause_automatic_search"]

    resume_automatic_search = _laser_pointing_widget_methods_active_pair_is_ready["resume_automatic_search"]

    accept_alignment_reference = _laser_pointing_widget_methods_active_pair_is_ready["accept_alignment_reference"]

    update_automatic_search_status = _laser_pointing_widget_methods_active_pair_is_ready["update_automatic_search_status"]

    _set_automatic_contour_overlay = _laser_pointing_widget_methods_active_pair_is_ready["_set_automatic_contour_overlay"]
    del _laser_pointing_widget_methods_active_pair_is_ready

    _laser_pointing_widget_methods_update_convergence_plot = _bind_laser_pointing_widget_methods_update_convergence_plot(_refactor_modules[__name__])
    update_convergence_plot = _laser_pointing_widget_methods_update_convergence_plot["update_convergence_plot"]

    rb_clicked = _laser_pointing_widget_methods_update_convergence_plot["rb_clicked"]

    set_the_control_value = _laser_pointing_widget_methods_update_convergence_plot["set_the_control_value"]

    mouseDoubleClickEvent = _laser_pointing_widget_methods_update_convergence_plot["mouseDoubleClickEvent"]
    del _laser_pointing_widget_methods_update_convergence_plot
