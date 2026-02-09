"""
Measurement Thread Module
=========================

Background thread for parallel spectrometer measurements.
"""

from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import sys

# Add project path for imports
project_root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project_root))

from DeviceServers.cameras.avantes.avantes_parallel import (
    parallel_prepare_measure,
    parallel_measure,
    parallel_poll_and_get_data
)


class MeasurementThread(QThread):
    """Background thread for parallel spectrometer measurements."""
    
    measurement_complete = pyqtSignal(dict)  # Signal with results
    measurement_error = pyqtSignal(str)  # Signal with error message
    
    def __init__(self, spectrometers, configs, num_measurements=1):
        super().__init__()
        self.spectrometers = spectrometers
        self.configs = configs
        self.num_measurements = num_measurements
        self.running = True
        
    def run(self):
        """Execute parallel measurement in background thread."""
        try:
            # Prepare
            prep_results = parallel_prepare_measure(self.spectrometers, self.configs)
            if not all(prep_results.values()):
                self.measurement_error.emit("Failed to prepare measurements")
                return
            
            # Measure
            meas_results = parallel_measure(self.spectrometers, self.num_measurements)
            if not all(meas_results.values()):
                self.measurement_error.emit("Failed to start measurements")
                return
            
            # Poll and get data
            data_results = parallel_poll_and_get_data(
                self.spectrometers, 
                timeout=10.0, 
                poll_interval=0.001
            )
            
            self.measurement_complete.emit(data_results)
            
        except Exception as e:
            self.measurement_error.emit(f"Measurement error: {str(e)}")
    
    def stop(self):
        """Stop the measurement thread."""
        self.running = False
