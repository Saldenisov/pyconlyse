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
from taurus.core import TaurusDevState
from taurus.external.qt import Qt
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueCheckBox

from DeviceServers import *
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

    def set_state_status(self, short=True):
        """Build a readable controller header for the composite client.

        The generic DS header is intentionally very compact.  In the two-column
        LaserPointing panel its Taurus labels could therefore shrink to their
        minimum size, leaving only the LED and an ellipsis.  The controller is
        the top-level safety boundary, so keep its identity and state visible.
        """
        dev_name = self.dev_name
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")

        header = QtWidgets.QFrame()
        header.setObjectName("laserPointingControllerHeader")
        header.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        header.setMinimumHeight(54)
        header.setMaximumHeight(62)
        header.setStyleSheet(
            """
            QFrame#laserPointingControllerHeader {
                background-color: #F4F7FA;
                border: 1px solid #C7D1DC;
                border-radius: 5px;
            }
            QLabel#laserPointingPath {
                color: #5B6570;
                font-size: 10px;
                border: none;
                background: transparent;
            }
            QLabel#laserPointingStateCaption {
                color: #5B6570;
                border: none;
                background: transparent;
            }
            """
        )
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(8)

        name_label = TaurusLabel()
        state_led = TaurusLed()
        state_label = TaurusLabel()
        always_on = TaurusValueCheckBox()
        name_label.model = f"{dev_name}/device_friendly_name"
        state_led.model = f"{dev_name}/state"
        state_label.model = f"{dev_name}/state"
        always_on.model = f"{dev_name}/always_on_value"

        # Preserve the conventional attribute names used by DS widgets and by
        # recovery/test helpers.
        setattr(self, f"s1_{dev_name}", name_label)
        setattr(self, f"s2_{dev_name}", state_led)
        setattr(self, f"s3_{dev_name}", state_label)
        setattr(self, f"s4_{dev_name}", always_on)

        state_led.setMinimumSize(28, 28)
        state_led.setMaximumSize(28, 28)
        state_led.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )

        name_label.setWordWrap(False)
        name_label.bgRole = ""
        name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        name_label.setMinimumWidth(145)
        name_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        name_label.setToolTip(dev_name)

        path_label = QtWidgets.QLabel(dev_name)
        path_label.setObjectName("laserPointingPath")
        path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        identity = QtWidgets.QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(0)
        identity.addWidget(name_label)
        identity.addWidget(path_label)

        state_caption = QtWidgets.QLabel("State")
        state_caption.setObjectName("laserPointingStateCaption")
        state_label.setAlignment(QtCore.Qt.AlignCenter)
        state_label.setMinimumWidth(64)
        state_label.setMaximumWidth(90)
        state_label.setToolTip(f"{dev_name}/state")
        state_block = QtWidgets.QVBoxLayout()
        state_block.setContentsMargins(0, 0, 0, 0)
        state_block.setSpacing(0)
        state_block.addWidget(state_caption, 0, QtCore.Qt.AlignHCenter)
        state_block.addWidget(state_label)

        try:
            always_on.setChecked(bool(self.ds.always_on_value == 1))
        except (AttributeError, TypeError):
            always_on.setChecked(False)

        row.addWidget(state_led)
        row.addLayout(identity, 1)
        row.addLayout(state_block)
        row.addWidget(always_on)
        lo_status.setContentsMargins(0, 0, 0, 4)
        lo_status.addWidget(header)

        recovery = getattr(self, "_device_recovery", None)
        if recovery is not None:
            for recovery_target in (
                header,
                state_led,
                name_label,
                path_label,
                state_label,
            ):
                recovery.install_on(recovery_target)

        self.controller_header = header

    def set_states(self, mode=""):
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        self.rules: OrderedDict = eval(ds.get_rules)
        group = QtWidgets.QGroupBox("Optical points")
        mode_name = str(mode).strip()
        group.setObjectName(
            f"laserPointingOpticalPoints{mode_name}" if mode_name
            else "laserPointingOpticalPoints"
        )
        group.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        group.setMinimumWidth(300)
        group.setMaximumWidth(340)
        group.setMinimumHeight(82)
        group.setMaximumHeight(92)
        layout = QtWidgets.QGridLayout(group)
        layout.setContentsMargins(5, 3, 5, 4)
        layout.setHorizontalSpacing(3)
        layout.setVerticalSpacing(2)

        numbered = []
        working = []
        for state, parameters in self.rules.items():
            state_text = str(state)
            suffix = state_text.lower().replace("point", "")
            if suffix.isdigit():
                numbered.append((int(suffix), state_text, parameters))
            else:
                working.append((state_text, parameters))

        has_translation = any(
            "TranslationStage1" in parameters for _, _, parameters in numbered
        )
        self.has_translation_planes = has_translation
        planes = ((1, 2, 3), (4, 5, 6))
        button_group = QtWidgets.QButtonGroup(self)
        button_group.setExclusive(True)
        self.point_button_groups.append(button_group)

        for row, point_numbers in enumerate(planes):
            if has_translation:
                plane_label = "Near" if row == 0 else "Far"
            else:
                plane_label = "D1" if row == 0 else "D2"
            label = QtWidgets.QLabel(plane_label)
            label.setStyleSheet("font-size: 10px; font-weight: 600; color: #465568;")
            label.setToolTip(
                "Near plane · stage 0" if row == 0 and has_translation
                else (
                    "Far plane · stage −700" if has_translation
                    else f"Diaphragm {row + 1}"
                )
            )
            layout.addWidget(label, row, 0)

            for column, point_number in enumerate(point_numbers):
                entry = next((item for item in numbered if item[0] == point_number), None)
                if entry is None:
                    continue
                _, state, parameters = entry
                aperture = active_point_aperture(parameters)
                detail = (
                    f"{aperture:g}%" if aperture is not None else ""
                )
                button = QtWidgets.QPushButton(f"P{point_number} {detail}".rstrip())
                button.setCheckable(True)
                button.setFixedHeight(25)
                button.setMinimumWidth(54)
                button.setSizePolicy(
                    QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
                )
                button.setToolTip(self._point_tooltip(state, parameters))
                button.clicked.connect(
                    partial(self.point_clicked, state, parameters, point_number)
                )
                button_group.addButton(button)
                self.point_buttons_by_state.setdefault(state, []).append(button)
                layout.addWidget(button, row, column + 1)

        if working:
            state, parameters = working[0]
            button = QtWidgets.QPushButton("Working")
            button.setCheckable(True)
            button.setFixedSize(68, 52)
            button.setToolTip(self._point_tooltip(state, parameters))
            button.clicked.connect(partial(self.point_clicked, state, parameters, 0))
            button_group.addButton(button)
            self.point_buttons_by_state.setdefault(state, []).append(button)
            layout.addWidget(button, 0, 4, 2, 1)

        return group

    @staticmethod
    def _component_device_path(specification):
        if isinstance(specification, (tuple, list)):
            return str(specification[0]) if specification else ""
        return str(specification or "")

    @staticmethod
    def _component_caption(role):
        text = str(role or "")
        lowered = text.lower()
        digits = "".join(character for character in text if character.isdigit())
        if "shutter" in lowered or "flipper" in lowered:
            return f"Flipper {digits}".rstrip()
        if "mainlaserdiaphragm" in lowered:
            return f"Main D{digits}".rstrip()
        if "crimpingdiaphragm" in lowered:
            return f"Diaphragm {digits}".rstrip()
        if "halfwaveplate" in lowered or "lambda" in lowered:
            return "λ/2"
        if "translation" in lowered:
            return "DL"
        return text

    def _status_value_card(self, role, device_name, attribute_name="position"):
        card = QtWidgets.QFrame()
        card.setObjectName("laserComponentStatusCard")
        card.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        card.setMinimumWidth(96)
        card.setFixedHeight(25)
        row = QtWidgets.QHBoxLayout(card)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(3)

        led = TaurusLed()
        led.model = f"{device_name}/state"
        led.setFixedSize(13, 13)
        led.setToolTip(device_name)
        caption = QtWidgets.QLabel(self._component_caption(role))
        caption.setObjectName("laserComponentStatusCaption")
        caption.setToolTip(device_name)
        is_flipper = "shutter" in role.lower() or "flipper" in role.lower()
        status_attribute = "commanded_flipper_state" if is_flipper else attribute_name
        value = OpticalStatusValue(role)
        value.model = f"{device_name}/{status_attribute}"
        value.bgRole = ""
        value.setObjectName("laserComponentStatusValue")
        value.setToolTip(
            f"{device_name}/{status_attribute}"
            + (
                " · last completed command: −1 = UP / blocked, +1 = DOWN / clear"
                if is_flipper
                else ""
            )
        )

        row.addWidget(led)
        row.addWidget(caption)
        row.addStretch(1)
        row.addWidget(value)
        return card

    def _status_state_card(self, caption_text, devices):
        card = QtWidgets.QFrame()
        card.setObjectName("laserComponentStatusCard")
        card.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        card.setMinimumWidth(96)
        card.setFixedHeight(25)
        row = QtWidgets.QHBoxLayout(card)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(3)
        caption = QtWidgets.QLabel(caption_text)
        caption.setObjectName("laserComponentStatusCaption")
        row.addWidget(caption)
        row.addStretch(1)
        for axis_name, device_name in devices:
            axis = QtWidgets.QLabel(axis_name)
            axis.setObjectName("laserComponentStatusAxis")
            led = TaurusLed()
            led.model = f"{device_name}/state"
            led.setFixedSize(13, 13)
            led.setToolTip(device_name)
            row.addWidget(axis)
            row.addWidget(led)
        return card

    def build_component_status_panel(self):
        """Create a compact, passive overview of LaserPointing hardware."""

        group = QtWidgets.QGroupBox("Main components · live status")
        group.setObjectName("laserPointingComponentStatus")
        group.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        group.setMinimumHeight(82)
        group.setMaximumHeight(92)
        grid = QtWidgets.QGridLayout(group)
        grid.setContentsMargins(5, 3, 5, 4)
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)

        cards = []
        camera_name = self._component_device_path(self.ds_dict.get("Camera", ""))
        if camera_name:
            cards.append(self._status_state_card("Camera", (("", camera_name),)))

        for index, roles in enumerate(self._actuator_role_groups, start=1):
            devices = []
            for role in roles:
                device_name = self._component_device_path(self.ds_dict.get(role, ""))
                if device_name:
                    axis = "X" if "x" in str(role).lower() else "Y"
                    devices.append((axis, device_name))
            if devices:
                cards.append(self._status_state_card(f"Standa {index}", devices))

        status_devices = dict(self.ds_dict)
        shutter1 = self._component_device_path(status_devices.get("Shutter1", ""))
        if (
            shutter1
            and "Shutter2" not in status_devices
            and shutter1.lower().endswith("/s1")
        ):
            status_devices["Shutter2"] = shutter1[:-1] + "2"

        optical_roles = []
        for role, specification in status_devices.items():
            lowered = str(role).lower()
            if any(
                marker in lowered
                for marker in (
                    "shutter",
                    "flipper",
                    "diaphragm",
                    "halfwaveplate",
                    "lambda",
                    "translation",
                )
            ):
                attribute_name = "position"
                if "translation" in lowered and isinstance(
                    specification, (tuple, list)
                ):
                    axes = specification[1] if len(specification) > 1 else ()
                    if not isinstance(axes, (tuple, list)):
                        axes = (axes,)
                    if axes:
                        attribute_name = f"pos{int(axes[0])}"
                optical_roles.append(
                    (
                        str(role),
                        self._component_device_path(specification),
                        attribute_name,
                    )
                )
        optical_roles.sort(
            key=lambda item: (
                0
                if "shutter" in item[0].lower()
                or "flipper" in item[0].lower()
                else 1,
                item[0].lower(),
            )
        )
        for role, device_name, attribute_name in optical_roles:
            if device_name:
                cards.append(
                    self._status_value_card(role, device_name, attribute_name)
                )

        columns = max(1, math.ceil(len(cards) / 2.0))
        for index, card in enumerate(cards):
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)

        group.setStyleSheet(
            """
            QGroupBox#laserPointingComponentStatus {
                font-weight: 600;
            }
            QFrame#laserComponentStatusCard {
                background: #f4f7fa;
                border: 1px solid #d5dde6;
                border-radius: 3px;
            }
            QLabel#laserComponentStatusCaption {
                color: #465568;
                font-size: 9px;
                border: none;
                background: transparent;
            }
            QLabel#laserComponentStatusAxis {
                color: #738092;
                font-size: 8px;
                border: none;
                background: transparent;
            }
            QLabel#laserComponentStatusValue {
                color: #172b44;
                font-size: 9px;
                font-weight: 700;
                border: none;
                background: transparent;
            }
            """
        )
        return group

    @staticmethod
    def _point_tooltip(state, parameters):
        settings = ", ".join(f"{role}={value}" for role, value in parameters.items())
        return f"Apply {state}: {settings}"

    def point_clicked(self, state, parameters, point_number, checked=False):
        """Apply a point through the controller, then unlock its mount pair."""

        if not checked or self._point_apply_busy or self._pair_initialization_busy:
            return
        self._point_apply_busy = True
        self._set_point_buttons_enabled(False)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(False)
        self.set_active_actuator_group(
            0, f"Applying {state}; alignment mounts are locked until readback completes"
        )
        if hasattr(self, "search_status"):
            self.search_status.setText(f"Applying {state}…")

        def apply():
            try:
                ds = getattr(self, f"ds_{self.dev_name}")
                result = ds.apply_controller_point(state)
                if result not in (None, 0):
                    raise RuntimeError(f"controller returned {result}")
                self.point_application_finished.emit(state, point_number, True, "")
            except Exception as error:
                self.point_application_finished.emit(
                    state, point_number, False, str(error)
                )

        Thread(target=apply, name=f"{self.dev_name}-apply-{state}", daemon=True).start()

    def _finish_point_application(self, state, point_number, success, message):
        self._point_apply_busy = False
        self._set_point_buttons_enabled(True)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(True)
        if success:
            group_index = optical_point_group(f"point{point_number}")
            for button in self._point_buttons(state):
                button.setChecked(True)
            self.set_active_actuator_group(group_index)
            if hasattr(self, "search_status"):
                self.search_status.setText(f"Applied {state}")
        else:
            self._clear_point_selection()
            self.set_active_actuator_group(
                0, f"Could not apply {state}; both mount pairs remain locked"
            )
            if hasattr(self, "search_status"):
                self.search_status.setText(f"Could not apply {state}: {message}")

    def _set_point_buttons_enabled(self, enabled):
        for group in getattr(self, "point_button_groups", ()):
            for button in group.buttons():
                button.setEnabled(bool(enabled))

    def _clear_point_selection(self):
        for group in getattr(self, "point_button_groups", ()):
            group.setExclusive(False)
            for button in group.buttons():
                button.setChecked(False)
            group.setExclusive(True)

    def _point_buttons(self, state):
        buttons = getattr(self, "point_buttons_by_state", {}).get(state, ())
        if isinstance(buttons, (list, tuple)):
            return list(buttons)
        return [buttons] if buttons is not None else []

    def set_active_actuator_group(self, group_index, reason=""):
        """Expose every ready manual axis unless the controller owns motion."""

        group_index = int(group_index or 0)
        self._active_actuator_group = group_index
        role_groups = tuple(getattr(self, "_actuator_role_groups", ()))
        ready_groups = {
            index: self._active_pair_is_ready(index)
            for index in range(1, len(role_groups) + 1)
        }
        controller_owns_motion = (
            self._point_apply_busy
            or self._pair_initialization_busy
            or self._search_running
        )
        if not reason:
            if group_index in (1, 2):
                optical_name = (
                    ("Near plane" if group_index == 1 else "Far plane")
                    if getattr(self, "has_translation_planes", False)
                    else f"Diaphragm {group_index}"
                )
                reason = (
                    f"{optical_name} selected — all initialized Standa "
                    "actuators remain available in Manual"
                )
            else:
                reason = (
                    "Manual mode — all initialized Standa actuators are available"
                )

        for index, roles in enumerate(
            role_groups, start=1
        ):
            pair_ready = ready_groups.get(index, False)
            enabled = manual_alignment_motion_enabled(
                pair_ready,
                point_application_busy=self._point_apply_busy,
                pair_initialization_busy=self._pair_initialization_busy,
                automatic_search_running=self._search_running,
            )
            for role in roles:
                widget = self.widgets.get(role)
                if widget is None:
                    continue
                lock_reason = (
                    "Manual alignment control is available"
                    if enabled
                    else (
                        reason
                        if controller_owns_motion
                        else f"Standa pair {index} is not initialized"
                    )
                )
                if hasattr(widget, "set_alignment_motion_enabled"):
                    widget.set_alignment_motion_enabled(enabled, lock_reason)
                else:
                    widget.setEnabled(enabled)

        label = getattr(self, "mount_interlock_status", None)
        if label is not None:
            label.setText(f"Mount interlock: {reason}")
            if ready_groups and all(ready_groups.values()) and not controller_owns_motion:
                label.setStyleSheet(
                    "background: #e4f4e8; color: #195c2b; "
                    "border: 1px solid #9bc9a6; border-radius: 4px; padding: 5px;"
                )
            else:
                label.setStyleSheet(
                    "background: #fff4d6; color: #775000; "
                    "border: 1px solid #e2bd68; border-radius: 4px; padding: 5px;"
                )
        self._update_pair_initialization_controls()

    def add_pair_initialization_controls(self, layout, ds):
        panel = QtWidgets.QWidget()
        panel_layout = QtWidgets.QHBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(5)
        self.initialize_pair_button = QtWidgets.QPushButton(
            "Initialize active pair"
        )
        self.initialize_pair_button.clicked.connect(self.initialize_active_pair)
        self.initialize_pair_status = QtWidgets.QLabel(
            "Select an optical point first"
        )
        self.initialize_pair_status.setWordWrap(True)
        self.initialize_pair_status.setStyleSheet(
            "color: #59687a; font-size: 9px;"
        )
        panel_layout.addWidget(self.initialize_pair_button)
        panel_layout.addWidget(self.initialize_pair_status, 1)
        layout.addWidget(panel)

        self._refresh_pair_initialization_capability(ds)
        self._update_pair_initialization_controls()

    def _refresh_pair_initialization_capability(self, ds):
        try:
            commands = {
                str(name).lower()
                for name in ds.getDeviceProxy().get_command_list()
            }
            self._pair_initialization_supported = (
                "initialize_active_pair" in commands
            )
        except Exception:
            self._pair_initialization_supported = False

    def _active_pair_is_ready(self, group_index):
        if group_index not in (1, 2):
            return False
        role_groups = getattr(self, "_actuator_role_groups", ())
        if group_index > len(role_groups):
            return False
        for role in role_groups[group_index - 1]:
            widget = self.widgets.get(role)
            device = getattr(widget, "ds", None)
            if device is None:
                return False
            try:
                connection = str(device.hardware_connection_state).strip().upper()
                initialization = str(device.initialization_state).strip().upper()
                state = str(device.getDeviceProxy().state()).strip().upper()
                state = state.rsplit(".", 1)[-1]
            except Exception:
                return False
            if (
                connection != "READY"
                and initialization != "SUCCEEDED"
                and state not in {"ON", "MOVING", "RUNNING"}
            ):
                return False
        return True

    def _update_pair_initialization_controls(self, status=None):
        button = getattr(self, "initialize_pair_button", None)
        label = getattr(self, "initialize_pair_status", None)
        if button is None:
            return
        group_index = getattr(self, "_active_actuator_group", 0)
        ready = self._active_pair_is_ready(group_index)
        button.setText(
            f"Initialize Standa pair {group_index}"
            if group_index in (1, 2)
            else "Initialize active pair"
        )
        button.setEnabled(
            self._pair_initialization_supported
            and group_index in (1, 2)
            and not self._pair_initialization_busy
            and not self._point_apply_busy
            and not self._search_running
        )
        if label is not None:
            if status:
                label.setText(str(status))
            elif not self._pair_initialization_supported:
                label.setText("Restart DS_LaserPointing to enable this command")
            elif group_index not in (1, 2):
                label.setText("Select point 1–3 or 4–6 first")
            elif ready:
                label.setText(f"Pair {group_index} is initialised")
            elif not self._pair_initialization_busy:
                label.setText(
                    f"Pair {group_index} selected; axes will initialise X then Y"
                )

    def initialize_active_pair(self):
        group_index = self._active_actuator_group
        if group_index not in (1, 2) or self._pair_initialization_busy:
            return
        self._pair_initialization_busy = True
        self._set_point_buttons_enabled(False)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(False)
        self._update_pair_initialization_controls(
            f"Initialising pair {group_index} sequentially…"
        )
        self.set_active_actuator_group(
            group_index,
            f"Initialising Standa pair {group_index}; movement is locked",
        )

        def initialise():
            try:
                result = getattr(
                    self, f"ds_{self.dev_name}"
                ).initialize_active_pair()
                if result not in (None, 0):
                    raise RuntimeError(f"controller returned {result}")
                self.pair_initialization_finished.emit(True, "")
            except Exception as error:
                self.pair_initialization_finished.emit(False, str(error))

        Thread(
            target=initialise,
            name=f"{self.dev_name}-initialize-pair-{group_index}",
            daemon=True,
        ).start()

    def _finish_active_pair_initialization(self, success, message):
        self._pair_initialization_busy = False
        self._set_point_buttons_enabled(not self._search_running)
        if hasattr(self, "search_start"):
            self.search_start.setEnabled(not self._search_running)
        group_index = self._active_actuator_group
        if success:
            self._update_pair_initialization_controls(
                f"Standa pair {group_index} initialised"
            )
            self.set_active_actuator_group(group_index)
        else:
            self._update_pair_initialization_controls(
                f"Initialisation failed: {message}"
            )
            self.set_active_actuator_group(
                group_index,
                f"Standa pair {group_index} failed to initialise; movement remains locked",
            )

    def hide_update_param_buttons(self):
        for button in self.findChildren(QtWidgets.QAbstractButton):
            if button.text().strip().lower() == "update param":
                button.hide()

    def add_automatic_search_controls(self, layout, ds):
        """Add non-blocking controls for the controller-side search worker."""
        group = QtWidgets.QGroupBox("Automatic alignment")
        form = QtWidgets.QGridLayout(group)

        self.search_mode = QtWidgets.QComboBox()
        self.search_mode.addItem("Staged: 2/5 then 3/6", "staged")
        self.search_mode.addItem("Sensitive: 3/6", "sensitive")
        self.search_mode.addItem("Medium: 2/5", "medium")

        def double_spin(value, minimum, maximum, decimals=2):
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(minimum, maximum)
            widget.setDecimals(decimals)
            widget.setValue(value)
            widget.setMaximumWidth(60)
            return widget

        defaults = {}
        try:
            defaults = json.loads(str(ds.automatic_search_config))
        except Exception:
            pass

        mode_index = self.search_mode.findData(defaults.get("mode", "sensitive"))
        self.search_mode.setCurrentIndex(max(0, mode_index))
        schedule = list(defaults.get("step_schedule", [10.0, 6.0, 2.0]))
        if len(schedule) != 3:
            schedule = [10.0, 6.0, 2.0]
        self.search_step_coarse = double_spin(schedule[0], 0.1, 50.0, 2)
        self.search_step_middle = double_spin(schedule[1], 0.1, 50.0, 2)
        self.search_step_fine = double_spin(schedule[2], 0.1, 50.0, 2)
        self.search_radius = double_spin(defaults.get("radius", 30.0), 0.1, 100.0, 2)
        self.search_tolerance = double_spin(
            defaults.get("roundness_tolerance_pct", 7.0), 0.0, 100.0, 2
        )

        self.search_evaluations = QtWidgets.QSpinBox()
        self.search_evaluations.setRange(1, 500)
        self.search_evaluations.setValue(defaults.get("max_evaluations", 16))
        self.search_samples = QtWidgets.QSpinBox()
        self.search_samples.setRange(1, 5)
        self.search_samples.setValue(defaults.get("samples", 3))
        self.search_max_cycles = max(1, int(defaults.get("max_cycles", 2)))

        self.search_evaluations.setMaximumWidth(60)
        self.search_samples.setMaximumWidth(60)

        form.addWidget(QtWidgets.QLabel("Sequence"), 0, 0)
        form.addWidget(self.search_mode, 0, 1, 1, 3)
        form.addWidget(QtWidgets.QLabel("Steps"), 1, 0)
        form.addWidget(self.search_step_coarse, 1, 1)
        form.addWidget(self.search_step_middle, 1, 2)
        form.addWidget(self.search_step_fine, 1, 3)
        form.addWidget(QtWidgets.QLabel("Radius"), 2, 0)
        form.addWidget(self.search_radius, 2, 1)
        form.addWidget(QtWidgets.QLabel("Round err. %"), 2, 2)
        form.addWidget(self.search_tolerance, 2, 3)
        form.addWidget(QtWidgets.QLabel("Evals"), 3, 0)
        form.addWidget(self.search_evaluations, 3, 1)
        form.addWidget(QtWidgets.QLabel("Frames"), 3, 2)
        form.addWidget(self.search_samples, 3, 3)

        self.search_start = QtWidgets.QPushButton("Start automatic search")
        self.search_stop = QtWidgets.QPushButton("Stop")
        self.search_stop.setEnabled(False)
        self.search_status = QtWidgets.QLabel("idle")
        self.search_status.setWordWrap(True)
        form.addWidget(self.search_start, 4, 0, 1, 2)
        form.addWidget(self.search_stop, 4, 2, 1, 2)
        form.addWidget(self.search_status, 5, 0, 1, 4)

        self.convergence_plot = pg.PlotWidget()
        self.convergence_plot.setBackground("#ffffff")
        self.convergence_plot.setMinimumHeight(145)
        self.convergence_plot.setMaximumHeight(185)
        self.convergence_plot.setTitle(
            "Convergence over time", color="#24364b", size="10pt"
        )
        self.convergence_plot.setLabel("left", "Roundness error", units="%")
        self.convergence_plot.setLabel("bottom", "Elapsed time", units="s")
        self.convergence_plot.showGrid(x=True, y=True, alpha=0.2)
        self.convergence_plot.addLegend(offset=(8, 8), labelTextColor="#24364b")
        group1_label = (
            "Near plane · Standa 1"
            if getattr(self, "has_translation_planes", False)
            else "Diaphragm 1 · Standa 1"
        )
        group2_label = (
            "Far plane · Standa 2"
            if getattr(self, "has_translation_planes", False)
            else "Diaphragm 2 · Standa 2"
        )
        self.convergence_line = self.convergence_plot.plot(
            [], [], pen=pg.mkPen("#7b8794", width=1.5)
        )
        self.convergence_group1 = self.convergence_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#2378c3", symbolPen="#174f82",
            name=group1_label,
        )
        self.convergence_group2 = self.convergence_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#e38b2c", symbolPen="#985916",
            name=group2_label,
        )
        self.convergence_tolerance = pg.InfiniteLine(
            pos=self.search_tolerance.value(), angle=0,
            pen=pg.mkPen("#2f9e44", width=1, style=QtCore.Qt.DashLine),
        )
        self.convergence_plot.addItem(self.convergence_tolerance)
        form.addWidget(self.convergence_plot, 6, 0, 1, 4)

        self.search_start.clicked.connect(self.start_automatic_search)
        self.search_stop.clicked.connect(self.stop_automatic_search)
        layout.addWidget(group)

        self.search_timer = Qt.QTimer(self)
        self.search_timer.timeout.connect(self.update_automatic_search_status)
        self.search_timer.start(500)

    def add_delta_coordinates_view(self, layout):
        """Place the directional centroid mismatch directly below the camera."""

        group = QtWidgets.QGroupBox("Centroid diagnostic")
        group.setObjectName("laserPointingCentroidDiagnostic")
        group.setToolTip(
            "ΔX and ΔY compare the current contour centre with the first "
            "measurement at this point. Automatic alignment optimizes "
            "concentric-contour symmetry, not this displacement."
        )
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(6, 5, 6, 6)
        group_layout.setSpacing(4)

        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(6)
        self.delta_x_value = QtWidgets.QLabel("ΔX  — px")
        self.delta_y_value = QtWidgets.QLabel("ΔY  — px")
        self.delta_norm_value = QtWidgets.QLabel("|Δ|  — px")
        for label, colour in (
            (self.delta_x_value, "#1f6fb2"),
            (self.delta_y_value, "#c56f15"),
            (self.delta_norm_value, "#7a2e8e"),
        ):
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setStyleSheet(
                "background: #f4f7fa; border: 1px solid #d6dde6; "
                f"border-radius: 4px; color: {colour}; font-weight: 600; padding: 4px;"
            )
            metrics.addWidget(label)
        group_layout.addLayout(metrics)

        self.delta_plot = pg.PlotWidget()
        self.delta_plot.setBackground("#ffffff")
        self.delta_plot.setMinimumHeight(210)
        self.delta_plot.setMaximumHeight(280)
        self.delta_plot.setLabel("bottom", "ΔX", units="px")
        self.delta_plot.setLabel("left", "ΔY", units="px")
        self.delta_plot.showGrid(x=True, y=True, alpha=0.18)
        self.delta_plot.setAspectLocked(True, ratio=1)
        self.delta_plot.addLegend(offset=(8, 8), labelTextColor="#24364b")
        self.delta_plot.addItem(
            pg.InfiniteLine(
                pos=0, angle=90, pen=pg.mkPen("#aeb7c2", width=1)
            )
        )
        self.delta_plot.addItem(
            pg.InfiniteLine(
                pos=0, angle=0, pen=pg.mkPen("#aeb7c2", width=1)
            )
        )
        self.delta_tolerance_curve = self.delta_plot.plot(
            [], [], pen=pg.mkPen("#2f9e44", width=1.5, style=QtCore.Qt.DashLine),
            name="2 px display guide",
        )
        self.delta_trajectory = self.delta_plot.plot(
            [], [], pen=pg.mkPen("#7b8794", width=1.5)
        )
        self.delta_group1 = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#2378c3", symbolPen="#174f82", name="Pair 1",
        )
        self.delta_group2 = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=7,
            symbolBrush="#e38b2c", symbolPen="#985916", name="Pair 2",
        )
        self.delta_current_vector = self.delta_plot.plot(
            [], [], pen=pg.mkPen("#b3261e", width=2)
        )
        self.delta_current_point = self.delta_plot.plot(
            [], [], pen=None, symbol="o", symbolSize=11,
            symbolBrush="#ffffff", symbolPen=pg.mkPen("#b3261e", width=2),
        )
        group_layout.addWidget(self.delta_plot)

        hint = QtWidgets.QLabel(
            "Display only · alignment minimizes beam roundness error"
        )
        hint.setAlignment(QtCore.Qt.AlignCenter)
        hint.setStyleSheet("color: #647386; font-size: 9px;")
        group_layout.addWidget(hint)
        layout.addWidget(group)
        self.update_convergence_plot([], {})

    def start_automatic_search(self):
        if self._point_apply_busy or self._pair_initialization_busy:
            self.search_status.setText("Wait until the optical point has finished applying")
            return
        step_schedule = [
            self.search_step_coarse.value(),
            self.search_step_middle.value(),
            self.search_step_fine.value(),
        ]
        if not step_schedule[0] > step_schedule[1] > step_schedule[2]:
            self.search_status.setText(
                "Coarse, middle, and fine steps must be strictly decreasing"
            )
            return
        config = {
            "mode": self.search_mode.currentData(),
            "initial_step": step_schedule[0],
            "minimum_step": step_schedule[-1],
            "step_schedule": step_schedule,
            "radius": self.search_radius.value(),
            "roundness_tolerance_pct": self.search_tolerance.value(),
            "max_evaluations": self.search_evaluations.value(),
            "samples": self.search_samples.value(),
            "max_cycles": self.search_max_cycles,
        }
        previous_group = self._active_actuator_group
        try:
            self._search_running = True
            self.set_active_actuator_group(
                0, "Automatic search owns both mount pairs; manual movement is locked"
            )
            self._set_point_buttons_enabled(False)
            result = getattr(self, f"ds_{self.dev_name}").start_automatic_search(
                json.dumps(config)
            )
            if result not in (None, 0):
                self.search_status.setText("Search is already running or configuration is invalid")
                self._search_running = False
                self.set_active_actuator_group(previous_group)
                self._set_point_buttons_enabled(True)
        except Exception as error:
            self._search_running = False
            self.set_active_actuator_group(previous_group)
            self.search_status.setText(f"Could not start: {error}")
        self.update_automatic_search_status()

    def stop_automatic_search(self):
        try:
            getattr(self, f"ds_{self.dev_name}").stop_automatic_search()
        except Exception as error:
            self.search_status.setText(f"Could not stop: {error}")
        self.update_automatic_search_status()

    def update_automatic_search_status(self):
        try:
            ds = getattr(self, f"ds_{self.dev_name}")
            if not self._pair_initialization_supported:
                self._refresh_pair_initialization_capability(ds)
            status = str(ds.automatic_search_status)
            progress = json.loads(str(ds.automatic_search_progress) or "{}")
            try:
                history = json.loads(str(ds.automatic_search_history) or "[]")
            except Exception:
                history = []
            self.update_convergence_plot(history, progress)
            detail = ""
            if progress.get("group"):
                detail = (
                    f" — {progress.get('stage')} {progress.get('group')}, "
                    f"step {progress.get('motor_step', '?')}, "
                    f"roundness error "
                    f"{progress.get('roundness_error_pct', progress.get('error_px', 0)):.2f}%"
                )
            elif progress.get("message"):
                detail = f" — {progress['message']}"
            self.search_status.setText(status + detail)
            running = status in ("running", "stopping")
            self._search_running = running
            self.search_start.setEnabled(not running and not self._point_apply_busy)
            self.search_stop.setEnabled(running)
            self._set_point_buttons_enabled(not running and not self._point_apply_busy)
            if running:
                self.set_active_actuator_group(
                    0,
                    "Automatic search owns both mount pairs; manual movement is locked",
                )
            elif not self._point_apply_busy:
                try:
                    active_point = str(ds.active_point)
                except Exception:
                    active_point = ""
                buttons = self._point_buttons(active_point)
                if buttons:
                    for button in buttons:
                        button.setChecked(True)
                else:
                    self._clear_point_selection()
                self.set_active_actuator_group(optical_point_group(active_point))
        except Exception:
            # The controller may be temporarily unavailable during server restart.
            pass

    def update_convergence_plot(self, history, progress=None):
        """Render roundness error and a non-controlling centroid diagnostic."""

        valid = []
        for observation in history if isinstance(history, list) else []:
            try:
                elapsed = float(observation["elapsed_s"])
                error = float(
                    observation.get(
                        "roundness_error_pct", observation["error_px"]
                    )
                )
                group = int(observation.get("actuator_group", 0))
                delta_x, delta_y = (
                    float(value) for value in observation["delta_px"][:2]
                )
            except (KeyError, TypeError, ValueError):
                continue
            valid.append((elapsed, error, group, delta_x, delta_y))

        if not valid and isinstance(progress, dict):
            try:
                delta_x, delta_y = (
                    float(value) for value in progress["delta_px"][:2]
                )
                error = float(
                    progress.get(
                        "roundness_error_pct",
                        progress.get("error_px", math.hypot(delta_x, delta_y)),
                    )
                )
                group_name = str(progress.get("group", ""))
                group = 0
                for index, name in enumerate(getattr(self, "pid_groups", ()), start=1):
                    if str(name) == group_name:
                        group = index
                        break
                valid.append((0.0, error, group, delta_x, delta_y))
            except (KeyError, TypeError, ValueError):
                pass

        times = [item[0] for item in valid]
        errors = [item[1] for item in valid]
        self.convergence_line.setData(times, errors)
        for group_index, curve in (
            (1, self.convergence_group1),
            (2, self.convergence_group2),
        ):
            points = [item for item in valid if item[2] == group_index]
            curve.setData(
                [item[0] for item in points], [item[1] for item in points]
            )
        self.convergence_tolerance.setPos(self.search_tolerance.value())

        if not hasattr(self, "delta_plot"):
            return

        deltas_x = [item[3] for item in valid]
        deltas_y = [item[4] for item in valid]
        self.delta_trajectory.setData(deltas_x, deltas_y)
        for group_index, curve in (
            (1, self.delta_group1),
            (2, self.delta_group2),
        ):
            points = [item for item in valid if item[2] == group_index]
            curve.setData(
                [item[3] for item in points], [item[4] for item in points]
            )

        # This circle is only a visual centroid-displacement guide. The search
        # tolerance above is a percentage shape error and must not control it.
        tolerance = 2.0
        angles = [2 * math.pi * index / 100 for index in range(101)]
        self.delta_tolerance_curve.setData(
            [tolerance * math.cos(angle) for angle in angles],
            [tolerance * math.sin(angle) for angle in angles],
        )
        limit = max(
            5.0,
            tolerance * 1.25,
            *(abs(value) * 1.15 for value in deltas_x + deltas_y),
        )
        self.delta_plot.setXRange(-limit, limit, padding=0)
        self.delta_plot.setYRange(-limit, limit, padding=0)

        if valid:
            delta_x, delta_y = valid[-1][3], valid[-1][4]
            error = math.hypot(delta_x, delta_y)
            self.delta_x_value.setText(f"ΔX  {delta_x:+.2f} px")
            self.delta_y_value.setText(f"ΔY  {delta_y:+.2f} px")
            self.delta_norm_value.setText(f"|Δ|  {error:.2f} px")
            self.delta_current_vector.setData([0.0, delta_x], [0.0, delta_y])
            self.delta_current_point.setData([delta_x], [delta_y])
        else:
            self.delta_x_value.setText("ΔX  — px")
            self.delta_y_value.setText("ΔY  — px")
            self.delta_norm_value.setText("|Δ|  — px")
            self.delta_current_vector.setData([], [])
            self.delta_current_point.setData([], [])

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
