from abc import abstractmethod
from enum import Enum
from threading import Thread
from typing import Optional

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QSizePolicy
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel, TaurusLed
from taurus.qt.qtgui.input import TaurusValueCheckBox

from DeviceServers.shared.device_recovery import (
    get_power_cycle_config,
    power_cycle_device,
    restart_device_server,
)


class VisType(Enum):
    MIN = "min"
    FULL = "full"


class DeviceRecoveryController(QtCore.QObject):
    """Right-click recovery actions shared by normal and unavailable widgets."""

    operation_finished = QtCore.pyqtSignal(str, bool, str)

    def __init__(self, device_name: str, owner, status_label: QtWidgets.QLabel):
        super().__init__(owner)
        self.device_name = str(device_name)
        self.power_mapping_device = self.device_name
        self.owner = owner
        self.status_label = status_label
        self.busy = False
        self.operation_finished.connect(self._finish_operation)

    def install_on(self, widget):
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda point, source=widget: self.show_menu(source, point)
        )
        current_tooltip = str(widget.toolTip() or "").strip()
        recovery_hint = "Right-click for DS recovery"
        if recovery_hint not in current_tooltip:
            widget.setToolTip(
                f"{current_tooltip}\n{recovery_hint}".strip()
            )

    def _set_status(self, message: str, level: str = "working"):
        compact_renderer = getattr(self.owner, "_render_recovery_status", None)
        if callable(compact_renderer):
            try:
                if compact_renderer(message, level):
                    # Compact device rows render recovery in-place so a
                    # temporary multi-line banner cannot consume their fixed
                    # height and collapse the actual device controls.
                    self.status_label.hide()
                    return
            except Exception:
                pass

        styles = {
            "working": (
                "background-color: #E8F1FD; color: #174A7E; "
                "border: 1px solid #B6D4FE; border-radius: 4px; padding: 4px 6px;"
            ),
            "success": (
                "background-color: #DFF3E4; color: #155724; "
                "border: 1px solid #B7DFBF; border-radius: 4px; padding: 4px 6px;"
            ),
            "error": (
                "background-color: #FDE2E1; color: #8B1E1E; "
                "border: 1px solid #F2B8B5; border-radius: 4px; padding: 4px 6px;"
            ),
        }
        self.status_label.setStyleSheet(styles[level])
        self.status_label.setText(message)
        self.status_label.show()

    def show_menu(self, source, point):
        menu = QtWidgets.QMenu(source)
        restart_action = menu.addAction("Restart Tango DS…")
        restart_action.setEnabled(not self.busy)

        power_config = None
        power_config_error = ""
        try:
            power_config = get_power_cycle_config(self.power_mapping_device)
        except Exception as error:
            power_config_error = str(error)
            power_config = None

        if power_config is not None:
            power_action = menu.addAction(
                f"Power cycle {power_config.pdu_device} output "
                f"{power_config.output_id}…"
            )
            power_action.setEnabled(not self.busy)
        else:
            power_target = self.power_mapping_device.rsplit("/", 1)[-1]
            power_action = menu.addAction(
                f"Power cycle unavailable for {power_target}"
            )
            power_action.setToolTip(
                power_config_error
                or f"{self.power_mapping_device} has no configured PDU mapping"
            )
            power_action.setEnabled(False)

        if self.busy:
            menu.addSeparator()
            busy_action = menu.addAction("Recovery is already running")
            busy_action.setEnabled(False)

        selected = menu.exec_(source.mapToGlobal(point))
        if selected == restart_action:
            self._confirm_restart()
        elif selected == power_action and power_config is not None:
            self._confirm_power_cycle(power_config)

    def _confirm_restart(self):
        answer = QtWidgets.QMessageBox.question(
            self.owner,
            "Restart Tango device server",
            f"Restart the Tango device server for:\n\n{self.device_name}\n\n"
            "The server will be stopped gracefully through Tango Starter and then "
            "started again. No hardware power will be removed.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self._start_operation("restart", None)

    def _confirm_power_cycle(self, config):
        answer = QtWidgets.QMessageBox.warning(
            self.owner,
            "Power cycle hardware",
            f"Remove and restore hardware power for:\n\n{self.device_name}\n\n"
            f"PDU: {config.pdu_device}\nOutput: {config.output_id}\n"
            f"OFF time: {config.off_seconds:.1f} s\n"
            f"Settle time: {config.settle_seconds:.1f} s\n\n"
            "WARNING: this PDU output may supply other devices. Every device on "
            "the same output will lose power. Other PDU outputs will not be changed.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self._start_operation("power_cycle", config)

    def _start_operation(self, operation: str, power_config):
        if self.busy:
            return
        self.busy = True
        label = "Restarting Tango DS…" if operation == "restart" else "Cycling hardware power…"
        self._set_status(f"{label}  {self.device_name}", "working")

        def worker():
            try:
                if operation == "restart":
                    result = restart_device_server(self.device_name)
                    message = (
                        f"Restarted {result['server']} through {result['starter']}."
                    )
                else:
                    result = power_cycle_device(
                        self.power_mapping_device,
                        config=power_config,
                    )
                    message = (
                        f"Power restored: {result['pdu_device']} output "
                        f"{result['output_id']}."
                    )
                self.operation_finished.emit(operation, True, message)
            except Exception as error:
                try:
                    self.operation_finished.emit(operation, False, str(error))
                except RuntimeError:
                    pass

        Thread(target=worker, daemon=True).start()

    def _finish_operation(self, operation: str, success: bool, message: str):
        self.busy = False
        if success:
            self._set_status(message, "success")
            QtWidgets.QMessageBox.information(self.owner, "Recovery completed", message)
            if operation == "restart":
                reconnect = getattr(self.owner, "_try_reconnect_device", None)
                if callable(reconnect):
                    QTimer.singleShot(500, reconnect)
        else:
            self._set_status(f"Recovery failed: {message}", "error")
            QtWidgets.QMessageBox.critical(
                self.owner,
                "Recovery failed",
                f"{self.device_name}\n\n{message}",
            )


class DS_General_Widget(Qt.QWidget):
    connection_check_interval_ms = 3000

    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        """width: number of devices in a row"""
        super().__init__(parent)
        self.dev_name = device_name
        print(f"Creating widget for {self.dev_name}...")
        self.parent = parent
        self.vis_type = vis_type
        self.layout_main = Qt.QVBoxLayout()
        self._device_available = True
        self._last_connection_error = ""
        self._connection_banner = QtWidgets.QLabel()
        self._connection_banner.setWordWrap(True)
        self._connection_banner.setStyleSheet(
            """
            QLabel {
                background-color: #FFF3CD;
                color: #856404;
                border: 1px solid #FFEEBA;
                border-radius: 4px;
                padding: 4px 6px;
            }
        """
        )
        self._connection_banner.hide()
        self.layout_main.addWidget(self._connection_banner)
        self._recovery_banner = QtWidgets.QLabel()
        self._recovery_banner.setWordWrap(True)
        self._recovery_banner.hide()
        self.layout_main.addWidget(self._recovery_banner)
        self._device_recovery = DeviceRecoveryController(
            self.dev_name,
            self,
            self._recovery_banner,
        )
        self._device_recovery.install_on(self)
        self._device_recovery.install_on(self._connection_banner)
        setattr(self, f"ds_{self.dev_name}", Device(self.dev_name))
        setattr(self, f"lo_group_{1}", Qt.QHBoxLayout())
        self.layout_main.addLayout(getattr(self, f"lo_group_{1}"))
        self.setLayout(self.layout_main)
        self.widget_active = False

        self.before_ds()

        if self.vis_type == VisType.FULL:
            self.register_DS_full()
        elif self.vis_type == VisType.MIN:
            self.register_DS_min()

        # self.ds_sync = Device('elyse/clocks/sync_main')
        # self.ds_sync.subscribe_event("sync", tango.EventType.CHANGE_EVENT, self.sync_listener)

        self._connection_timer = QTimer(self)
        self._connection_timer.setInterval(self.connection_check_interval_ms)
        self._connection_timer.timeout.connect(self._monitor_device_connection)
        self._connection_timer.start()

        print(f"Widget for {self.dev_name} is created.")

    def before_ds(self):
        pass

    @abstractmethod
    def register_DS_full(self, group_number=1):
        self.register_full_layouts()

    @abstractmethod
    def register_DS_min(self, group_number=1):
        self.register_min_layouts()

    def set_state_status(self, short=True):
        dev_name = self.dev_name
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        
        # Compact horizontal layout: LED + Device name + Always on checkbox + Update button
        widgets = [TaurusLabel(), TaurusLed(), TaurusLabel(), TaurusValueCheckBox()]
        i = 1
        for s in widgets:
            setattr(self, f"s{i}_{dev_name}", s)
            i += 1
        s1: TaurusLabel = getattr(self, f"s1_{dev_name}")  # Device name
        s2 = getattr(self, f"s2_{dev_name}")  # LED
        _s3 = getattr(self, f"s3_{dev_name}")  # Status text (unused)
        s4: TaurusValueCheckBox = getattr(self, f"s4_{dev_name}")  # Always on

        s1.model = f"{dev_name}/device_friendly_name"
        s2.model = f"{dev_name}/state"
        s4.model = f"{dev_name}/always_on_value"
        self._device_recovery.install_on(s1)
        self._device_recovery.install_on(s2)
        try:
            always_on = True if self.ds.always_on_value == 1 else False
        except AttributeError:
            always_on = False
        s4.setChecked(always_on)
        
        # Make device name compact but readable
        try:
            s1.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            s1.setWordWrap(True)
            s1.setToolTip(self.dev_name)
        except Exception:
            pass
        
        # Make LED fixed size
        try:
            s2.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        except Exception:
            pass
        
        # Single compact horizontal line: LED + Name + Always On + Update button
        line = QtWidgets.QHBoxLayout()
        line.setSpacing(8)
        try:
            line.setContentsMargins(0, 2, 0, 2)
        except Exception:
            pass
        
        line.addWidget(s2)  # LED first
        line.addWidget(s1)  # Device name next to LED
        line.addWidget(s4)  # Always on checkbox
        
        # Update button
        setattr(
            self,
            f"button_update_param_{dev_name}",
            TaurusCommandButton(text="Update param"),
        )
        button_update_param: TaurusCommandButton = getattr(
            self, f"button_update_param_{dev_name}"
        )
        button_update_param.clicked.connect(self.update_param)
        line.addWidget(button_update_param)
        
        line.addStretch()  # Push everything to the left
        
        # Single-line compact layout only (no textual status label)
        lo_status.addLayout(line)

    @abstractmethod
    def register_full_layouts(self):
        setattr(self, f"layout_main_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_status_{self.dev_name}", Qt.QHBoxLayout())
        setattr(self, f"layout_info_{self.dev_name}", Qt.QHBoxLayout())
        setattr(self, f"layout_error_info_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_buttons_{self.dev_name}", Qt.QHBoxLayout())

    @abstractmethod
    def register_min_layouts(self):
        setattr(self, f"layout_main_{self.dev_name}", Qt.QVBoxLayout())
        setattr(self, f"layout_status_{self.dev_name}", Qt.QHBoxLayout())

    @property
    def ds(self):
        ds: Device = getattr(self, f"ds_{self.dev_name}")
        return ds

    def set_recovery_power_device(self, device_name: str):
        """Use another DS's explicit power mapping for this virtual widget."""
        self._device_recovery.power_mapping_device = str(device_name)

    def _set_connection_banner(self, available: bool, error_text: str = ""):
        compact_renderer = getattr(self, "_render_connection_status", None)
        if callable(compact_renderer):
            try:
                if compact_renderer(available, error_text):
                    self._connection_banner.hide()
                    return
            except Exception:
                pass

        if available:
            self._connection_banner.hide()
            return

        details = error_text or self._last_connection_error or "Unknown connection error"
        self._connection_banner.setText(
            f"Device is unavailable and will retry automatically.\nLast error: {details}"
        )
        self._connection_banner.show()

    def _probe_device_connection(self, device: Optional[Device] = None):
        device = device or getattr(self, f"ds_{self.dev_name}", None)
        if device is None:
            raise RuntimeError("No device object is attached")

        last_error = None
        probe_calls = (
            lambda: getattr(device, "state"),
            lambda: getattr(device, "device_friendly_name"),
            lambda: getattr(device, "always_on_value"),
        )

        for probe in probe_calls:
            try:
                probe()
                return
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise RuntimeError("Device probe failed")

    def _mark_device_unavailable(self, error_text: str, notify_hook: bool = True):
        self._device_available = False
        self._last_connection_error = error_text
        self._set_connection_banner(False, error_text)
        if notify_hook:
            try:
                self.on_device_lost(error_text)
            except Exception:
                pass

    def _mark_device_available(self):
        self._device_available = True
        self._last_connection_error = ""
        self._set_connection_banner(True)
        try:
            self.on_device_reconnected()
        except Exception:
            pass

    def _request_parent_widget_rebuild(self) -> bool:
        retry_callback = getattr(self.parent, "_retry_device_widget", None)
        slots = getattr(self.parent, "_widget_slots", None)
        if callable(retry_callback) and isinstance(slots, dict):
            if self.dev_name in slots:
                return bool(retry_callback(self.dev_name))
        return False

    def _try_reconnect_device(self) -> bool:
        try:
            new_device = Device(self.dev_name)
            self._probe_device_connection(new_device)
        except Exception as exc:
            self._set_connection_banner(False, str(exc))
            self._last_connection_error = str(exc)
            return False

        if self._request_parent_widget_rebuild():
            return True

        setattr(self, f"ds_{self.dev_name}", new_device)
        self._mark_device_available()
        return True

    def _monitor_device_connection(self):
        try:
            self._probe_device_connection()
        except Exception as exc:
            first_disconnect = self._device_available
            self._mark_device_unavailable(str(exc), notify_hook=first_disconnect)
            self._try_reconnect_device()
            return

        if not self._device_available:
            self._mark_device_available()

    def on_device_lost(self, error_text: str):
        """Hook for subclasses that need to react when the device becomes unavailable."""

    def on_device_reconnected(self):
        """Hook for subclasses that need to refresh local state after reconnection."""

    @abstractmethod
    def set_the_control_value(self, value):
        pass

    def execute_action(self, value, device: Device, func_name, threaded=False):
        if threaded:
            ex_thread = Thread(
                target=self.execute_action, args=[value, device, func_name]
            )
            ex_thread.start()
        else:
            func = getattr(device, func_name)
            func(value)

    def update_param(self):
        pass
