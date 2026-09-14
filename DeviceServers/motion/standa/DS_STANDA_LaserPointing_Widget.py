from _functools import partial

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtCore import Qt
from taurus import Device
from taurus.qt.qtgui.display import TaurusLabel

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType


class Standa_LaserPointing(DS_General_Widget):
    """Minimal Standa motor widget for LaserPointing applications."""

    def __init__(self, device_name: str, parent=None, vis_type=VisType.MIN):
        self.relative_shift = 1.0
        self._alignment_motion_enabled = False
        self._alignment_lock_reason = "Select an optical point to unlock this mount pair"
        self._alignment_recovery_level = ""
        self._alignment_recovery_message = ""
        self._alignment_connection_unavailable = False
        super().__init__(device_name, parent, vis_type)
        
    def register_DS_full(self, group_number=1):
        # Use MIN layout even for FULL vis_type in LaserPointing context
        self.register_DS_min(group_number)
        
    def register_DS_min(self, group_number=1):
        # The generic MIN row includes "Always on" and "Update param".  Those
        # controls are useful in a standalone motor client but make the four
        # alignment axes unnecessarily tall, so this view owns its layout.
        self.register_min_layouts()
        dev_name = self.dev_name
        
        try:
            ds: Device = getattr(self, f"ds_{self.dev_name}")
            lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
            
            # Get device properties safely
            friendly_name = dev_name.split('/')[-1]
            try:
                friendly_name = ds.get_property("friendly_name")["friendly_name"][0]
            except Exception:
                pass
            
            # Get layouts
            lo_device = getattr(self, f"layout_main_{dev_name}")

            # One compact row: state, name, live position, decrement, step,
            # increment. The step label keeps its existing context menu.
            widget = QtWidgets.QWidget()
            widget.setObjectName("laserPointingStandaRow")
            widget.setStyleSheet(
                "#laserPointingStandaRow { background: #f7f9fc; "
                "border: 1px solid #d7dee8; border-radius: 4px; }"
            )
            layout = QtWidgets.QHBoxLayout(widget)
            layout.setContentsMargins(4, 3, 4, 3)
            layout.setSpacing(4)

            state_led = QtWidgets.QLabel()
            state_led.setFixedSize(14, 14)
            state_led.setToolTip(dev_name)
            layout.addWidget(state_led)
            self._alignment_state_led = state_led
            self._alignment_disconnected = False

            name_label = QtWidgets.QLabel(friendly_name)
            name_label.setFixedWidth(55)
            name_label.setToolTip(dev_name)
            name_label.setStyleSheet("font-size: 10px; font-weight: 600; border: none;")
            layout.addWidget(name_label)
            self._alignment_name_label = name_label
            
            # Position
            pos_label = TaurusLabel()
            pos_label.model = f"{dev_name}/position"
            pos_label.setAlignment(Qt.AlignCenter)
            pos_label.setStyleSheet(
                "background: white; border: 1px solid #aeb8c5; "
                "border-radius: 3px; font-size: 10px;"
            )
            pos_label.setFixedSize(55, 22)
            layout.addWidget(pos_label)

            # The compact LaserPointing row bypasses the generic status-row
            # builder, so attach the common recovery menu explicitly to the
            # visible state, name, and readback controls.
            recovery = getattr(self, "_device_recovery", None)
            if recovery is not None:
                for recovery_target in (widget, state_led, name_label, pos_label):
                    recovery.install_on(recovery_target)

            btn_left = QtWidgets.QPushButton("−")
            btn_left.setFixedSize(22, 22)
            btn_left.clicked.connect(partial(self.move_step, -1))
            
            step_label = QtWidgets.QLabel(f"{self.relative_shift}")
            step_label.setAlignment(Qt.AlignCenter)
            step_label.setStyleSheet(
                "background: #e9edf3; border: 1px solid #c8d0db; "
                "border-radius: 3px; font-size: 9px;"
            )
            step_label.setFixedSize(32, 22)
            step_label.setToolTip("Right-click to choose the relative step")

            btn_right = QtWidgets.QPushButton("+")
            btn_right.setFixedSize(22, 22)
            btn_right.clicked.connect(partial(self.move_step, 1))
            
            # Context menu for step size
            step_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            step_label.customContextMenuRequested.connect(self.show_step_menu)
            
            layout.addWidget(btn_left)
            layout.addWidget(step_label)
            layout.addWidget(btn_right)
            
            # Store references
            setattr(self, f"step_label_{dev_name}", step_label)
            self._alignment_row = widget
            self._alignment_motion_controls = (btn_left, step_label, btn_right)
            
            # Add to main layout
            lo_device.addWidget(widget)
            lo_group.addLayout(lo_device)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            # The inherited connection/recovery labels stay hidden for this
            # compact widget. Recovery is rendered in the row itself, so its
            # geometry remains stable while Tango temporarily unregisters.
            self.setFixedHeight(42)
            self.set_alignment_motion_enabled(False, self._alignment_lock_reason)
            self._alignment_state_timer = QtCore.QTimer(self)
            self._alignment_state_timer.timeout.connect(
                self.update_alignment_hardware_state
            )
            self._alignment_state_timer.start(750)
            self.update_alignment_hardware_state()
            
        except Exception as e:
            print(f"Error creating Standa LaserPointing widget for {dev_name}: {e}")
            # Fallback: create simple error label
            error_label = QtWidgets.QLabel(f"Error: {dev_name}")
            lo_group.addWidget(error_label)
    
    def move_step(self, direction: int):
        """Move motor by step size in given direction"""
        if not self._alignment_motion_enabled:
            return
        try:
            current_pos = self.ds.position
            new_pos = current_pos + (self.relative_shift * direction)
            # Use non-blocking execute_action
            self.execute_action(new_pos, self.ds, "move_axis_abs", True)
        except Exception as e:
            print(f"Error moving {self.dev_name}: {e}")

    def set_alignment_motion_enabled(self, enabled: bool, reason: str = ""):
        """Apply the LaserPointing diaphragm-to-mount safety interlock."""

        self._alignment_motion_enabled = bool(enabled)
        self._alignment_lock_reason = str(reason or "")
        for control in getattr(self, "_alignment_motion_controls", ()):
            control.setEnabled(self._alignment_motion_enabled)
            control.setToolTip(
                "Right-click to choose the relative step"
                if self._alignment_motion_enabled and isinstance(control, QtWidgets.QLabel)
                else (
                    "Alignment mount is active"
                    if self._alignment_motion_enabled
                    else self._alignment_lock_reason
                )
            )

        self._refresh_alignment_row_style()

    def _render_recovery_status(self, message: str, level: str) -> bool:
        """Render restart progress without inserting a height-consuming banner."""

        self._alignment_recovery_level = str(level or "working").lower()
        self._alignment_recovery_message = str(message or "")
        self._refresh_alignment_row_style()
        self._refresh_alignment_state_led()

        if self._alignment_recovery_level == "success":
            expected_message = self._alignment_recovery_message
            QtCore.QTimer.singleShot(
                4000,
                partial(self._clear_recovery_status, expected_message),
            )
        return True

    def _render_connection_status(self, available: bool, error_text: str = "") -> bool:
        """Keep the compact row visible while the DS is unregistered/restarting."""

        self._alignment_connection_unavailable = not bool(available)
        if not available:
            self._alignment_disconnected = True
            self._alignment_hardware_detail = (
                f"Tango DS temporarily unavailable: {error_text}"
            ).strip()
        self._refresh_alignment_row_style()
        self._refresh_alignment_state_led()
        return True

    def _clear_recovery_status(self, expected_message: str):
        if self._alignment_recovery_message != expected_message:
            return
        self._alignment_recovery_level = ""
        self._alignment_recovery_message = ""
        self.update_alignment_hardware_state()

    def _refresh_alignment_state_led(self):
        recovery_level = getattr(self, "_alignment_recovery_level", "")
        if recovery_level == "working":
            colour = "#2f80ed"
        elif recovery_level == "error":
            colour = "#d43f45"
        elif recovery_level == "success":
            colour = "#22a447"
        else:
            colour = getattr(self, "_alignment_hardware_colour", "#e0a100")

        led = getattr(self, "_alignment_state_led", None)
        if led is not None:
            led.setStyleSheet(
                f"background: {colour}; border: 1px solid #536170; border-radius: 7px;"
            )
            led.setToolTip(
                self._alignment_recovery_message
                or getattr(self, "_alignment_hardware_detail", "")
            )

    def _refresh_alignment_row_style(self):
        row = getattr(self, "_alignment_row", None)
        if row is not None:
            recovery_level = getattr(self, "_alignment_recovery_level", "")
            if recovery_level == "working":
                background, border = "#e8f1fd", "#2f80ed"
            elif recovery_level == "error":
                background, border = "#fdebec", "#d43f45"
            elif recovery_level == "success":
                background, border = "#edf7ef", "#22a447"
            elif getattr(self, "_alignment_disconnected", False):
                background, border = "#fdebec", "#d43f45"
            elif self._alignment_motion_enabled:
                background, border = "#edf7ef", "#69a878"
            else:
                background, border = "#f0f2f5", "#c9cfd8"
            row.setStyleSheet(
                "#laserPointingStandaRow { "
                f"background: {background}; border: 1px solid {border}; "
                "border-radius: 4px; }"
            )
            row.setToolTip(
                self._alignment_recovery_message
                if recovery_level
                else (
                    getattr(self, "_alignment_hardware_detail", "Disconnected axis")
                    if getattr(self, "_alignment_disconnected", False)
                    else (
                        "Active alignment mount pair"
                        if self._alignment_motion_enabled
                        else self._alignment_lock_reason
                    )
                )
            )

    def update_alignment_hardware_state(self):
        """Prefer physical lifecycle state over Tango's passive STANDBY colour."""

        try:
            connection = str(self.ds.hardware_connection_state).strip().upper()
            initialization = str(self.ds.initialization_state).strip().upper()
            detail = str(self.ds.hardware_lifecycle_status).strip()
            state = str(self.ds.getDeviceProxy().state()).strip().upper()
            state = state.rsplit(".", 1)[-1]
        except Exception as error:
            connection = "DISCONNECTED"
            initialization = "UNKNOWN"
            detail = f"Could not read axis state: {error}"
            state = "UNKNOWN"

        disconnected = connection in {
            "DISCONNECTED",
            "POWER_OFF",
            "POWER_STATUS_UNAVAILABLE",
        } or state in {"FAULT", "OFF", "UNKNOWN", "UNREACHABLE", "NOTREADY"}
        ready = not disconnected and (
            connection == "READY"
            or initialization == "SUCCEEDED"
            or state in {"ON", "MOVING", "RUNNING"}
        )
        colour = "#22a447" if ready else ("#d43f45" if disconnected else "#e0a100")
        self._alignment_disconnected = disconnected
        self._alignment_hardware_colour = colour
        self._alignment_hardware_detail = detail or (
            f"Connection {connection}; initialisation {initialization}"
        )
        self._refresh_alignment_state_led()
        self._refresh_alignment_row_style()
    
    def show_step_menu(self, pos):
        """Show context menu for step size selection"""
        sender = self.sender()
        menu = QtWidgets.QMenu()
        
        step_sizes = [0.1, 0.5, 1, 2, 5, 10, 20, 50]
        
        for step in step_sizes:
            action = menu.addAction(f"{step}")
            action.triggered.connect(partial(self.set_step_size, step))
            
        menu.exec_(sender.mapToGlobal(pos))
    
    def set_step_size(self, step):
        """Set the step size"""
        self.relative_shift = step
        step_label = getattr(self, f"step_label_{self.dev_name}")
        step_label.setText(f"{step}")
        
    def set_the_control_value(self, value):
        """Set position from external control (e.g., states)"""
        try:
            # Use non-blocking execute_action like the original widget
            self.execute_action(float(value), self.ds, "move_axis_abs", True)
        except Exception as e:
            print(f"Error setting control value for {self.dev_name}: {e}")
            
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click selection"""
        if self.parent:
            print(f"{self.dev_name} is selected.")
            self.setStyleSheet("background-color: lightgreen; border: 1px solid black;")
            self.parent.active_widget = self.dev_name
            self.parent.update_active_widget()
