import sys
from pathlib import Path
import tango
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QThread, pyqtSignal
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


class _RetrainWorker(QThread):
    """Background worker that runs model retraining off the GUI thread."""
    progress = pyqtSignal(str, int)   # (message, percent)
    finished = pyqtSignal(dict)       # result dict or {'error': str}

    def __init__(self, data_path: str, model_dir: str,
                 scaler_filename: str, model_filename: str):
        super().__init__()
        self.data_path = data_path
        self.model_dir = model_dir
        self.scaler_filename = scaler_filename
        self.model_filename = model_filename

    def run(self):
        try:
            from DeviceServers.data.ml.ml_retrain import retrain_model
            result = retrain_model(
                data_path=self.data_path,
                model_dir=self.model_dir,
                scaler_filename=self.scaler_filename,
                model_filename=self.model_filename,
                progress_callback=lambda msg, pct: self.progress.emit(msg, pct),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit({"error": str(exc)})


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
        ml_retrain_group = self.create_ml_retrain_group()
        
        # Subscribe to events (fall back to PERIODIC_EVENT when
        # CHANGE_EVENT fails – e.g. when abs_change / rel_change are not set)
        for attr in ("model_version", "zmq_status", "predictions_count", "last_prediction"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.ml_attr_listener
                )
            except Exception:
                try:
                    getattr(self, f"ds_{dev_name}").subscribe_event(
                        attr, tango.EventType.PERIODIC_EVENT, self.ml_attr_listener
                    )
                except Exception as e:
                    print(f"Info: couldn't subscribe to '{attr}' for {dev_name}: {e}")
        
        # Layout
        lo_device.addLayout(lo_status)
        lo_device.addWidget(ml_info_group)
        lo_device.addWidget(ml_controls_group)
        lo_device.addWidget(ml_retrain_group)
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
        
        # Subscribe to key events (fall back to PERIODIC_EVENT)
        for attr in ("model_version", "zmq_status"):
            try:
                getattr(self, f"ds_{dev_name}").subscribe_event(
                    attr, tango.EventType.CHANGE_EVENT, self.ml_attr_listener
                )
            except Exception:
                try:
                    getattr(self, f"ds_{dev_name}").subscribe_event(
                        attr, tango.EventType.PERIODIC_EVENT, self.ml_attr_listener
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

    def ml_attr_listener(self, event):
        """Handle ML attribute change events.

        Tango delivers a single :class:`tango.EventData` object to the
        callback registered with :meth:`subscribe_event`.
        """
        try:
            if event.err:
                return
            attr_name = event.attr_value.name.split('/')[-1]
            if attr_name == "zmq_status":
                self.update_server_buttons_state(event.attr_value.value)
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

    # ------------------------------------------------------------------
    # Retrain panel
    # ------------------------------------------------------------------

    def create_ml_retrain_group(self):
        """Create the 'Model Training' group box with a retrain button, progress bar, and status."""
        dev_name = self.dev_name
        self._retrain_worker = None

        group = QtWidgets.QGroupBox("Model Training")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(8)

        # --- row 1: button -------------------------------------------------
        btn_row = QtWidgets.QHBoxLayout()
        retrain_button = QtWidgets.QPushButton("Retrain Model")
        retrain_button.setToolTip(
            "Retrain the XGBoost model from the configured data file "
            "and reload it into the device server"
        )
        retrain_button.clicked.connect(self._on_retrain_clicked)
        btn_row.addWidget(retrain_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        setattr(self, f"button_retrain_{dev_name}", retrain_button)

        # --- row 2: progress bar -------------------------------------------
        progress = QtWidgets.QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(True)
        layout.addWidget(progress)
        setattr(self, f"progress_retrain_{dev_name}", progress)

        # --- row 3: status label -------------------------------------------
        status_label = QtWidgets.QLabel("Ready")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)
        setattr(self, f"label_retrain_status_{dev_name}", status_label)

        return group

    def _on_retrain_clicked(self):
        """Handle the Retrain button click."""
        dev_name = self.dev_name
        ds: Device = getattr(self, f"ds_{dev_name}")

        # Read device properties from the Tango device
        try:
            data_path = ds.get_property("data_path")["data_path"][0]
            model_path = ds.get_property("model_path")["model_path"][0]
            scaler_fn = ds.get_property("scaler_filename")["scaler_filename"][0]
            model_fn = ds.get_property("model_filename")["model_filename"][0]
        except Exception as exc:
            self._retrain_set_status(f"Error reading device properties: {exc}")
            return

        if not data_path:
            self._retrain_set_status("data_path property not configured on device")
            return

        # Disable button while running
        btn = getattr(self, f"button_retrain_{dev_name}", None)
        if btn:
            btn.setEnabled(False)

        self._retrain_set_status("Starting…")
        self._retrain_set_progress(0)

        worker = _RetrainWorker(data_path, model_path, scaler_fn, model_fn)
        worker.progress.connect(self._on_retrain_progress)
        worker.finished.connect(self._on_retrain_finished)
        self._retrain_worker = worker
        worker.start()

    def _on_retrain_progress(self, message: str, percent: int):
        self._retrain_set_status(message)
        self._retrain_set_progress(percent)

    def _on_retrain_finished(self, result: dict):
        dev_name = self.dev_name

        if "error" in result:
            self._retrain_set_status(f"FAILED: {result['error']}")
        else:
            r2_train = result.get("r2_train", 0)
            r2_test = result.get("r2_test", 0)
            self._retrain_set_status(
                f"Done \u2013 R\u00b2 train={r2_train:.3f}  test={r2_test:.3f}"
            )
            self._retrain_set_progress(100)

            # Tell the device server to reload the freshly trained model
            try:
                ds: Device = getattr(self, f"ds_{dev_name}")
                ds.command_inout("UpdateModels")
            except Exception as exc:
                self._retrain_set_status(
                    f"Trained OK but UpdateModels failed: {exc}"
                )

        # Re-enable button
        btn = getattr(self, f"button_retrain_{dev_name}", None)
        if btn:
            btn.setEnabled(True)
        self._retrain_worker = None

    def _retrain_set_status(self, text: str):
        lbl = getattr(self, f"label_retrain_status_{self.dev_name}", None)
        if lbl:
            lbl.setText(text)

    def _retrain_set_progress(self, value: int):
        bar = getattr(self, f"progress_retrain_{self.dev_name}", None)
        if bar:
            bar.setValue(value)

    # ------------------------------------------------------------------
    # Layout registration
    # ------------------------------------------------------------------

    def register_full_layouts(self):
        super(ML_Stability, self).register_full_layouts()

    def register_min_layouts(self):
        super(ML_Stability, self).register_min_layouts()
