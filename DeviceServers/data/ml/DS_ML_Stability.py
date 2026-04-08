#!/usr/bin/env python

import os
import sys
from pathlib import Path
from typing import List, Tuple, Union
import threading
import time
import json
import numpy as np
import zmq
import joblib
from datetime import datetime

# Add the pyconlyse directory to Python path to enable DeviceServers imports
_PYCONLYSE_ROOT = Path(__file__).parent.parent.parent.parent  # Go up 4 levels to the root of pyconlyse
if str(_PYCONLYSE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYCONLYSE_ROOT))

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, command, device_property
from DeviceServers.base.general import DS_General


class DS_ML_Stability(DS_General):
    """Device Server (Tango) which controls ML Stability Prediction using XGBoost models."""
    
    _version_ = "0.1"
    _model_ = "ML Stability Predictor"
    polling = 1000
    
    # Device Properties - following NETIO pattern
    ip_address = device_property(dtype=str)
    zmq_port = device_property(dtype=str)
    model_path = device_property(dtype=str)
    scaler_filename = device_property(dtype=str, default_value="UV1_scaler.joblib")
    model_filename = device_property(dtype=str, default_value="UV1_xgb.joblib")
    data_path = device_property(dtype=str)
    calibration_path = device_property(dtype=str)
    friendly_name = device_property(dtype=str)
    
    @attribute(
        label="Model Version",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Date and version of loaded ML model",
        polling_period=polling,
    )
    def model_version(self):
        return self._model_version
        
    @attribute(
        label="ZMQ Status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Status of ZeroMQ server",
        polling_period=polling,
    )
    def zmq_status(self):
        return self._zmq_status
        
    @attribute(
        label="Predictions Count",
        dtype=int,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Number of predictions made",
        polling_period=polling,
    )
    def predictions_count(self):
        return self._predictions_count
        
    @attribute(
        label="Last Prediction",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        doc="Last stability prediction value",
        polling_period=polling,
    )
    def last_prediction(self):
        return self._last_prediction

    def init_device(self):
        """Initialize the device"""
        # Initialize instance variables BEFORE super().init_device()
        # because the base class calls find_device() which loads models/calibration.
        # Initializing after super() would reset everything that was just loaded.
        self._model_version = "No model loaded"
        self._zmq_status = "Stopped"
        self._predictions_count = 0
        self._last_prediction = 0.0
        self._server_thread = None
        self._server_running = False
        self._context = None
        self._socket = None
        self._scaler = None
        self._model = None
        self._wavelength = None
        self._from_pixel = 0
        self._to_pixel = 0
        
        super().init_device()
        
        self.register_variables_for_archive()
        self.turn_on()

    def find_device(self) -> Tuple[int, str]:
        """Find and connect to ZMQ service - following NETIO pattern"""
        arg_return = -1, ""
        self.info(f"Searching for ML device {self.device_name}", True)
        
        # Load calibration and models
        self._load_calibration()
        self._load_models()
        
        if getattr(self, "_model", None) is not None:
            arg_return = 1, f"ML_Stability_{self.friendly_name}"
            
        self._device_id_internal, self._uri = arg_return
        return arg_return

    def _load_calibration(self):
        """Load wavelength calibration data"""
        try:
            cal_path = getattr(self, "calibration_path", "") or ""
            if not cal_path:
                # Fallback to default calibration in repo if not provided
                default_cal = Path(__file__).parent / "calibrations" / "calibrationUV-VIS140324.txt"
                if default_cal.exists():
                    cal_path = str(default_cal.resolve())
                    self.warn(f"calibration_path not set; using default: {cal_path}")
            if cal_path and os.path.exists(cal_path):
                self._wavelength = np.loadtxt(cal_path)
                self._from_pixel = np.argmin(np.abs(self._wavelength - 380.0))  # UV start
                self._to_pixel = np.argmin(np.abs(self._wavelength - 700.0))   # UV end
                self.info(f"Calibration loaded from {cal_path}: 380-700 nm ({self._from_pixel}-{self._to_pixel} pixels)", True)
            else:
                self.warn(f"Calibration file not found: {cal_path}")
        except Exception as e:
            self.error(f"Error loading calibration: {str(e)}")

    def _load_models(self):
        """Load ML models and scaler"""
        try:
            # Ensure attributes exist even if loading fails
            self._scaler = None
            self._model = None

            # Resolve model directory and filenames
            model_dir = self.model_path if getattr(self, "model_path", None) else str((Path(__file__).parent / "models").resolve())
            scaler_name = getattr(self, "scaler_filename", "UV1_scaler.joblib")
            model_name = getattr(self, "model_filename", "UV1_xgb.joblib")
            scaler_path = os.path.join(model_dir, scaler_name)
            model_path = os.path.join(model_dir, model_name)
            
            if os.path.exists(scaler_path) and os.path.exists(model_path):
                self._scaler = joblib.load(scaler_path)
                self._model = joblib.load(model_path)
                
                # Get model creation date from file
                model_time = datetime.fromtimestamp(os.path.getmtime(model_path))
                self._model_version = f"XGBoost v0.1 ({model_time.strftime('%Y-%m-%d %H:%M')})"
                
                self.info(f"ML models loaded: scaler={scaler_path}, model={model_path}", True)
            else:
                self.warn(f"Model files not found at {model_dir}: expected {scaler_name} and {model_name}; use UpdateModels command to load them")
                self._model_version = "Models not found"
        except Exception as e:
            self.error(f"Error loading models: {str(e)}")
            self._model_version = f"Error: {str(e)}"

    def _start_zmq_server(self):
        """Start ZMQ server in separate thread"""
        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.REP)
            bind_address = f"tcp://{self.ip_address}:{self.zmq_port}"
            self._socket.bind(bind_address)
            
            self.info(f"ZMQ server started on {bind_address}", True)
            self._zmq_status = f"Running on {bind_address}"
            
            while self._server_running:
                try:
                    if self._socket.poll(1000):  # 1 second timeout
                        message = self._socket.recv()
                        data = json.loads(message.decode('utf-8'))
                        
                        if 'stop' in data:
                            self._server_running = False
                            response = {'status': 'stopping'}
                        else:
                            response = self._process_prediction_request(data)
                            self._predictions_count += 1
                        
                        self._socket.send(json.dumps(response).encode('utf-8'))
                        
                except zmq.Again:
                    continue
                except Exception as e:
                    self.error(f"Error in ZMQ server loop: {str(e)}")
                    
        except Exception as e:
            self.error(f"Error starting ZMQ server: {str(e)}")
            self._zmq_status = f"Error: {str(e)}"
        finally:
            if self._socket:
                self._socket.close()
            if self._context:
                self._context.term()
            self._zmq_status = "Stopped"
            self.info("ZMQ server stopped", True)

    def _process_prediction_request(self, data):
        """Process a prediction request"""
        try:
            if self._model is None:
                return {'error': 'Models not loaded'}
            
            # Convert input data for prediction
            array1 = np.array(data['array1'])[:, self._from_pixel:self._to_pixel]
            array2 = np.array(data['array2'])[:, self._from_pixel:self._to_pixel]
            
            # Apply binning (100 bins as in notebook)
            step_size = array1.shape[1] // 100
            array1 = array1[:, ::step_size]
            array2 = array2[:, ::step_size]
            
            # Compute ratio
            result_array = array1 / array2
            
            # Scale and predict
            scaled_array = self._scaler.transform(result_array)
            prediction = self._model.predict(scaled_array)
            
            self._last_prediction = float(prediction[0]) if len(prediction) > 0 else 0.0
            
            return {'prediction': prediction.tolist()}
            
        except Exception as e:
            self.error(f"Error processing prediction: {str(e)}")
            return {'error': str(e)}

    def turn_on_local(self) -> Union[int, str]:
        """Turn on device - following NETIO pattern"""
        if self._device_id_internal == -1:
            self.info(f"Searching for device: {self.friendly_name}", True)
            self.find_device()
            
        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f"Could NOT turn on {self.device_name}: Device could not be found."
            
        self.set_state(DevState.ON)
        
        # Auto-start ZMQ server when device turns on (matches notebook behaviour)
        if self._model is not None and not self._server_running:
            self.StartServer()
        
        return 0

    def turn_off_local(self) -> Union[int, str]:
        """Turn off device - following NETIO pattern"""
        if self._server_running:
            self._stop_zmq_server()
        self.set_state(DevState.OFF)
        return 0

    def get_controller_status_local(self) -> Union[int, str]:
        """Get controller status - following NETIO pattern"""
        # Update ZMQ status
        if self._server_running and self._server_thread and self._server_thread.is_alive():
            # Server is running
            return 0
        elif self._server_running and (not self._server_thread or not self._server_thread.is_alive()):
            # Server should be running but thread is dead
            self._server_running = False
            self._zmq_status = "Thread died"
            return "ZMQ server thread died"
        else:
            # Server is not supposed to be running
            return 0

    def register_variables_for_archive(self):
        """Register variables for archiving - following NETIO pattern"""
        super().register_variables_for_archive()
        extra = {}
        extra["model_version"] = (lambda: self._model_version, "string")
        extra["zmq_status"] = (lambda: self._zmq_status, "string") 
        extra["predictions_count"] = (lambda: self._predictions_count, "int32")
        extra["last_prediction"] = (lambda: self._last_prediction, "float64")
        self.archive_state.update(extra)

    # Commands
    @command(
        display_level=DispLevel.OPERATOR,
        doc_in="Start ZeroMQ prediction server"
    )
    def StartServer(self):
        """Start the ZMQ prediction server"""
        if self._server_running:
            self.info("ZMQ server is already running", True)
            return
            
        if self._model is None:
            self.error("Cannot start server - models not loaded")
            return
        
        self._server_running = True
        self._server_thread = threading.Thread(target=self._start_zmq_server)
        self._server_thread.daemon = True
        self._server_thread.start()
        
        self.info("ZMQ prediction server started", True)

    @command(
        display_level=DispLevel.OPERATOR,
        doc_in="Stop ZeroMQ prediction server"
    )
    def StopServer(self):
        """Stop the ZMQ prediction server"""
        self._stop_zmq_server()

    def _stop_zmq_server(self):
        """Internal method to stop ZMQ server"""
        if self._server_running:
            self._server_running = False
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5)
            self._zmq_status = "Stopped"
            self.info("ZMQ prediction server stopped", True)

    @command(
        display_level=DispLevel.OPERATOR,
        doc_in="Update ML models from default path"
    )
    def UpdateModels(self):
        """Update/reload ML models from configured path"""
        was_running = self._server_running
        if was_running:
            self._stop_zmq_server()
            
        self._load_models()
        
        if was_running and self._model is not None:
            self.StartServer()
            
        self.info(f"Models updated from {self.model_path}", True)


    @command(
        display_level=DispLevel.OPERATOR,
        doc_in="Retrain ML model from configured data_path"
    )
    def RetrainModel(self):
        """Retrain the ML model using data_path, then reload it."""
        from DeviceServers.data.ml.ml_retrain import retrain_model

        data_path = getattr(self, "data_path", "") or ""
        model_dir = self.model_path if getattr(self, "model_path", None) else str((Path(__file__).parent / "models").resolve())
        scaler_name = getattr(self, "scaler_filename", "UV1_scaler.joblib")
        model_name = getattr(self, "model_filename", "UV1_xgb.joblib")

        if not data_path or not os.path.exists(data_path):
            self.error(f"Cannot retrain: data_path not set or missing ({data_path})")
            return

        def _progress(msg, pct):
            self.info(f"Retrain [{pct}%] {msg}", True)

        self.info("Starting model retraining…", True)
        was_running = self._server_running
        if was_running:
            self._stop_zmq_server()

        try:
            result = retrain_model(
                data_path=data_path,
                model_dir=model_dir,
                scaler_filename=scaler_name,
                model_filename=model_name,
                progress_callback=_progress,
            )
            self._load_models()
            self.info(
                f"Retrain complete – R² train={result['r2_train']:.3f} test={result['r2_test']:.3f}",
                True,
            )
        except Exception as e:
            self.error(f"Retrain failed: {e}")

        if was_running and self._model is not None:
            self.StartServer()


if __name__ == "__main__":
    DS_ML_Stability.run_server()
