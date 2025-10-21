import sys
from pathlib import Path
import tango
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QFont
from taurus import Device
from taurus.external.qt import Qt
from taurus.qt.qtgui.button import TaurusCommandButton
from taurus.qt.qtgui.display import TaurusLabel

from DeviceServers.shared.DS_Widget import DS_General_Widget, VisType

# Import fixes for safe device access
fixes_path = Path(__file__).parents[3] / "fixes"
if str(fixes_path) not in sys.path:
    sys.path.append(str(fixes_path))
from taurus_warnings_fix import (
    check_device_connection,
    suppress_taurus_deprecation_warnings,
)


class ML_Stability(DS_General_Widget):
    def __init__(self, device_name: str, parent=None, vis_type=VisType.FULL):
        suppress_taurus_deprecation_warnings()
        super().__init__(device_name, parent, vis_type)

    def before_ds(self):
        """Initialize device-dependent data before UI is built."""
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")
        
        # Check device connection
        if not check_device_connection(ds):
            print(f"Warning: ML device {dev_name} is not properly connected")

    def register_DS_full(self, group_number=1):
        super(ML_Stability, self).register_DS_full()
        dev_name = self.dev_name
        
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        lo_buttons: Qt.QLayout = getattr(self, f"layout_buttons_{dev_name}")
        
        # State and status
        self.set_state_status(False)
        
        # Create ML-specific UI
        ml_info_group = self.create_ml_info_group()
        ml_controls_group = self.create_ml_controls_group()
        
        # Subscribe to events
        for attr in ("model_version", "zmq_status", "predictions_count", "last_prediction"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.ml_attr_listener
                )
            except Exception as e:
                print(f"Info: couldn't subscribe to '{attr}' for {dev_name}: {e}")
        
        # Layout
        lo_device.addLayout(lo_status)
        lo_device.addWidget(ml_info_group)
        lo_device.addWidget(ml_controls_group)
        lo_device.addLayout(lo_buttons)
        lo_group.addLayout(lo_device)

    def register_DS_min(self, group_number=1):
        super(ML_Stability, self).register_DS_min()
        dev_name = self.dev_name
        
        lo_group: Qt.QHBoxLayout = getattr(self, f"lo_group_{group_number}")
        lo_device: Qt.QLayout = getattr(self, f"layout_main_{dev_name}")
        lo_status: Qt.QLayout = getattr(self, f"layout_status_{dev_name}")
        
        # State and status
        self.set_state_status()
        
        # Minimal ML info
        ml_status_group = self.create_ml_status_minimal()
        
        # Subscribe to key events
        for attr in ("model_version", "zmq_status"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.ml_attr_listener
                )
            except Exception as e:
                print(f"Info: couldn't subscribe to '{attr}' for {dev_name}: {e}")
        
        lo_status.addWidget(ml_status_group)
        lo_device.addLayout(lo_status)
        lo_group.addLayout(lo_device)

    def create_ml_info_group(self):
        """Create ML model information group"""
        dev_name = self.dev_name
        
        group = QtWidgets.QGroupBox("ML Model Information")
        layout = QtWidgets.QGridLayout(group)
        layout.setSpacing(8)
        
        font = QFont()
        font.setPointSize(9)
        
        # Model version
        layout.addWidget(QtWidgets.QLabel("Model Version:"), 0, 0)
        model_version_label = TaurusLabel()
        model_version_label.setModel(f"{dev_name}/model_version")
        model_version_label.setFont(font)
        layout.addWidget(model_version_label, 0, 1)
        setattr(self, f"label_model_version_{dev_name}", model_version_label)
        
        # ZMQ Status
        layout.addWidget(QtWidgets.QLabel("ZMQ Status:"), 1, 0)
        zmq_status_label = TaurusLabel()
        zmq_status_label.setModel(f"{dev_name}/zmq_status")
        zmq_status_label.setFont(font)
        layout.addWidget(zmq_status_label, 1, 1)
        setattr(self, f"label_zmq_status_{dev_name}", zmq_status_label)
        
        # Predictions count
        layout.addWidget(QtWidgets.QLabel("Predictions:"), 2, 0)
        predictions_label = TaurusLabel()
        predictions_label.setModel(f"{dev_name}/predictions_count")
        predictions_label.setFont(font)
        layout.addWidget(predictions_label, 2, 1)
        setattr(self, f"label_predictions_{dev_name}", predictions_label)
        
        # Last prediction
        layout.addWidget(QtWidgets.QLabel("Last Prediction:"), 3, 0)
        last_pred_label = TaurusLabel()
        last_pred_label.setModel(f"{dev_name}/last_prediction")
        last_pred_label.setFont(font)
        layout.addWidget(last_pred_label, 3, 1)
        setattr(self, f"label_last_pred_{dev_name}", last_pred_label)
        
        return group

    def create_ml_controls_group(self):
        """Create ML control buttons group"""
        dev_name = self.dev_name
        
        group = QtWidgets.QGroupBox("ML Server Control")
        layout = QtWidgets.QHBoxLayout(group)
        layout.setSpacing(12)
        
        # Start Server button
        start_button = TaurusCommandButton(command="StartServer")
        start_button.setModel(dev_name)
        start_button.setText("Start Server")
        start_button.setToolTip("Start ZeroMQ prediction server")
        try:
            start_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))
        except Exception:
            pass
        layout.addWidget(start_button)
        setattr(self, f"button_start_{dev_name}", start_button)
        
        # Stop Server button
        stop_button = TaurusCommandButton(command="StopServer")
        stop_button.setModel(dev_name)
        stop_button.setText("Stop Server")
        stop_button.setToolTip("Stop ZeroMQ prediction server")
        try:
            stop_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MediaStop))
        except Exception:
            pass
        layout.addWidget(stop_button)
        setattr(self, f"button_stop_{dev_name}", stop_button)
        
        # Update Models button
        update_button = TaurusCommandButton(command="UpdateModels")
        update_button.setModel(dev_name)
        update_button.setText("Update Models")
        update_button.setToolTip("Reload ML models from configured path")
        try:
            update_button.setIcon(QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        except Exception:
            pass
        layout.addWidget(update_button)
        setattr(self, f"button_update_{dev_name}", update_button)
        
        return group

    def create_ml_status_minimal(self):
        """Create minimal ML status for compact view"""
        dev_name = self.dev_name
        
        group = QtWidgets.QGroupBox("ML Status")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(4)
        
        font = QFont()
        font.setPointSize(8)
        
        # Model version (compact)
        model_label = TaurusLabel()
        model_label.setModel(f"{dev_name}/model_version")
        model_label.setFont(font)
        layout.addWidget(model_label)
        
        # ZMQ Status (compact)
        zmq_label = TaurusLabel()
        zmq_label.setModel(f"{dev_name}/zmq_status")
        zmq_label.setFont(font)
        layout.addWidget(zmq_label)
        
        return group

    def ml_attr_listener(self, evt_src, evt_type, evt_value):
        """Handle ML attribute change events"""
        try:
            if evt_type == tango.EventType.CHANGE_EVENT:
                # Update UI based on attribute changes
                attr_name = evt_src.name.split('/')[-1]
                if attr_name == "zmq_status":
                    self.update_server_buttons_state(evt_value.value)
        except Exception as e:
            print(f"Error in ML attribute listener: {e}")

    def update_server_buttons_state(self, zmq_status):
        """Update server control buttons based on ZMQ status"""
        dev_name = self.dev_name
        try:
            start_button = getattr(self, f"button_start_{dev_name}", None)
            stop_button = getattr(self, f"button_stop_{dev_name}", None)
            
            if start_button and stop_button:
                is_running = "Running" in zmq_status if zmq_status else False
                start_button.setEnabled(not is_running)
                stop_button.setEnabled(is_running)
        except Exception as e:
            print(f"Error updating button states: {e}")

    def register_full_layouts(self):
        super(ML_Stability, self).register_full_layouts()

    def register_min_layouts(self):
        super(ML_Stability, self).register_min_layouts()