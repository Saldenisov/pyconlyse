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
        Device.init_device(self)
        
        self.info_stream("Initializing DS_ML_Stability...")
        
        # Initialize instance variables
        self._server_status = "Stopped"
        self._model_loaded = False
        self._predictions_count = 0
        self._last_prediction = []
        self._server_thread = None
        self._server_running = False
        self._context = None
        self._socket = None
        self._scaler = None
        self._model_uv = None
        self._model_ir = None
        self._wavelength = None
        self._from_pixel = 0
        self._to_pixel = 0
        
        # Create models directory if it doesn't exist
        os.makedirs(self.model_path, exist_ok=True)
        
        # Load calibration data
        self._load_calibration()
        
        # Try to load existing models
        self._load_models()
        
        self.set_state(DevState.ON)
        self.info_stream("DS_ML_Stability initialized successfully")

    def delete_device(self):
        """Clean up when device is deleted"""
        self.info_stream("Deleting DS_ML_Stability...")
        if self._server_running:
            self.stop_server()
        Device.delete_device(self)

    def _load_calibration(self):
        """Load wavelength calibration data"""
        try:
            if os.path.exists(self.calibration_file):
                self._wavelength = np.loadtxt(self.calibration_file)
                self._from_pixel = np.argmin(np.abs(self._wavelength - self.from_wavelength))
                self._to_pixel = np.argmin(np.abs(self._wavelength - self.to_wavelength))
                self.info_stream(f"Calibration loaded: {self.from_wavelength}-{self.to_wavelength} nm "
                               f"({self._from_pixel}-{self._to_pixel} pixels)")
            else:
                self.warn_stream(f"Calibration file not found: {self.calibration_file}")
        except Exception as e:
            self.error_stream(f"Error loading calibration: {str(e)}")

    def _load_models(self):
        """Load ML models and scaler"""
        try:
            scaler_path = os.path.join(self.model_path, "ELYSE_scaler.joblib")
            model_path = os.path.join(self.model_path, "ELYSE_xgb.joblib")
            
            if os.path.exists(scaler_path) and os.path.exists(model_path):
                self._scaler = joblib.load(scaler_path)
                self._model_uv = joblib.load(model_path)
                self._model_loaded = True
                self._server_status = "Models loaded"
                self.info_stream("ML models loaded successfully")
            else:
                self.warn_stream("Model files not found, use UpdateModels command to load them")
                self._model_loaded = False
                self._server_status = "Models not found"
        except Exception as e:
            self.error_stream(f"Error loading models: {str(e)}")
            self._model_loaded = False
            self._server_status = f"Error loading models: {str(e)}"

    def _run_server(self):
        """Run the ZMQ server in a separate thread"""
        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.REP)
            self._socket.bind(self.zmq_address)
            
            self.info_stream(f"ML server started on {self.zmq_address}")
            self._server_status = "Running"
            
            while self._server_running:
                try:
                    # Set timeout to allow checking _server_running periodically
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
                    # Timeout occurred, continue loop
                    continue
                except Exception as e:
                    self.error_stream(f"Error in server loop: {str(e)}")
                    error_response = {'error': str(e)}
                    try:
                        self._socket.send(json.dumps(error_response).encode('utf-8'))
                    except:
                        pass
                        
        except Exception as e:
            self.error_stream(f"Error starting server: {str(e)}")
            self._server_status = f"Server error: {str(e)}"
        finally:
            if self._socket:
                self._socket.close()
            if self._context:
                self._context.term()
            self._server_status = "Stopped"
            self.info_stream("ML server stopped")

    def _process_prediction_request(self, data):
        """Process a prediction request"""
        try:
            if not self._model_loaded:
                return {'error': 'Models not loaded'}
            
            # Determine which model to use
            model = self._model_uv  # Default to UV model
            if 'model' in data:
                model_type = data['model']
                if model_type == 'UV':
                    model = self._model_uv
                elif model_type == 'IR' and self._model_ir is not None:
                    model = self._model_ir
            
            # Convert lists to numpy arrays and apply wavelength selection
            array1 = np.array(data['array1'])[:, self._from_pixel:self._to_pixel]
            array2 = np.array(data['array2'])[:, self._from_pixel:self._to_pixel]
            
            # Apply binning
            step_size = array1.shape[1] // self.n_bins
            array1 = array1[:, ::step_size]
            array2 = array2[:, ::step_size]
            
            # Compute ratio
            result_array = array1 / array2
            
            # Scale the data
            scaled_array = self._scaler.transform(result_array)
            
            # Make prediction
            prediction = model.predict(scaled_array)
            
            # Store last prediction
            self._last_prediction = prediction.tolist()
            
            return {'prediction': prediction.tolist()}
            
        except Exception as e:
            self.error_stream(f"Error processing prediction: {str(e)}")
            return {'error': str(e)}

    # Attribute read methods
    def read_server_status(self):
        return self._server_status

    def read_model_loaded(self):
        return self._model_loaded

    def read_predictions_count(self):
        return self._predictions_count

    def read_last_prediction(self):
        return self._last_prediction

    def read_server_thread_alive(self):
        return self._server_thread is not None and self._server_thread.is_alive()

    # Commands
    @command
    def StartServer(self):
        """Start the ML prediction server"""
        if self._server_running:
            self.info_stream("Server is already running")
            return
            
        if not self._model_loaded:
            tango.Except.throw_exception("Models not loaded", 
                                       "Cannot start server without loaded models",
                                       "StartServer")
        
        self._server_running = True
        self._server_thread = threading.Thread(target=self._run_server)
        self._server_thread.daemon = True
        self._server_thread.start()
        
        self.info_stream("ML prediction server started")

    @command
    def StopServer(self):
        """Stop the ML prediction server"""
        self.stop_server()

    def stop_server(self):
        """Internal method to stop the server"""
        if self._server_running:
            self._server_running = False
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5)
            self._server_status = "Stopped"
            self.info_stream("ML prediction server stopped")

    @command(dtype_in=str, doc_in="Path to model files directory")
    def UpdateModels(self, model_path=None):
        """Update/reload ML models from specified path"""
        if model_path:
            self.model_path = model_path
            
        # Stop server if running
        was_running = self._server_running
        if was_running:
            self.stop_server()
            
        # Reload models
        self._load_models()
        
        # Restart server if it was running
        if was_running and self._model_loaded:
            self.StartServer()
            
        self.info_stream(f"Models updated from {self.model_path}")

    @command
    def ResetCounters(self):
        """Reset prediction counters"""
        self._predictions_count = 0
        self._last_prediction = []
        self.info_stream("Counters reset")

    @command(dtype_out=str)
    def GetModelInfo(self):
        """Get information about loaded models"""
        info = {
            'model_loaded': self._model_loaded,
            'model_path': self.model_path,
            'calibration_file': self.calibration_file,
            'wavelength_range': f"{self.from_wavelength}-{self.to_wavelength} nm",
            'pixel_range': f"{self._from_pixel}-{self._to_pixel}",
            'n_bins': self.n_bins,
            'predictions_count': self._predictions_count
        }
        return json.dumps(info, indent=2)

    @command(dtype_in=(float,), doc_in="Test prediction with dummy data")
    def TestPrediction(self, test_data):
        """Test prediction with provided data"""
        if not self._model_loaded:
            tango.Except.throw_exception("Models not loaded", 
                                       "Cannot test prediction without loaded models",
                                       "TestPrediction")
        
        try:
            # Create dummy arrays based on test_data
            n_pixels = self._to_pixel - self._from_pixel
            array1 = np.random.random((1, n_pixels)) * test_data[0] if test_data else np.random.random((1, n_pixels))
            array2 = np.random.random((1, n_pixels)) * 0.8 if len(test_data) > 1 else np.random.random((1, n_pixels)) * 0.8
            
            # Apply binning
            step_size = array1.shape[1] // self.n_bins
            array1 = array1[:, ::step_size]
            array2 = array2[:, ::step_size]
            
            # Compute ratio
            result_array = array1 / array2
            
            # Scale and predict
            scaled_array = self._scaler.transform(result_array)
            prediction = self._model_uv.predict(scaled_array)
            
            self._last_prediction = prediction.tolist()
            self.info_stream(f"Test prediction completed: {prediction[0]:.6f}")
            
        except Exception as e:
            tango.Except.throw_exception("Test failed", 
                                       f"Test prediction failed: {str(e)}",
                                       "TestPrediction")


def main():
    """Main function to run the device server"""
    try:
        # Start the device server
        run([DS_ML_Stability])
    except Exception as e:
        print(f"Error starting device server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()