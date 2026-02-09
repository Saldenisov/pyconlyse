"""
Spectrometer Manager Module
===========================

Handles Avantes spectrometer connections and configuration.
"""

import logging
from pathlib import Path
import sys
from typing import Optional, Tuple

import numpy as np

# Add project path for imports
project_root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(project_root))

from msl.equipment import Backend, ConnectionRecord, EquipmentRecord


class SpectrometerManager:
    """Manages connection and configuration for a single Avantes spectrometer."""
    
    def __init__(self, spec_id: int, serial_number: str):
        """Initialize spectrometer manager.
        
        Parameters
        ----------
        spec_id : int
            Spectrometer identifier (1 or 2)
        serial_number : str
            Serial number of the spectrometer
        """
        self.spec_id = spec_id
        self.serial_number = serial_number
        self.spec = None
        self.wavelengths = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self, dll_path: Path) -> bool:
        """Connect to the spectrometer.
        
        Parameters
        ----------
        dll_path : Path
            Path to avaspecx64.dll
            
        Returns
        -------
        bool
            True if connection successful
        """
        try:
            record = EquipmentRecord(
                manufacturer="Avantes",
                model="AvaSpec-2048L",
                serial=self.serial_number,
                connection=ConnectionRecord(
                    address=f"SDK::{dll_path}"
                ),
            )
            
            self.spec = record.connect(demo=False)
            self.spec.use_high_res_adc(True)
            
            # Get wavelength calibration
            self.wavelengths = self.spec.get_lambda()
            num_pixels = self.spec.get_num_pixels()
            
            self.logger.info(
                f"SPEC{self.spec_id}: Connected - Serial={self.serial_number}, "
                f"Pixels={num_pixels}, λ={self.wavelengths[0]:.1f}-{self.wavelengths[-1]:.1f} nm"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"SPEC{self.spec_id}: Connection failed - {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the spectrometer."""
        if self.spec:
            try:
                self.spec.disconnect()
                self.logger.info(f"SPEC{self.spec_id}: Disconnected")
            except Exception as e:
                self.logger.error(f"SPEC{self.spec_id}: Disconnect error - {str(e)}")
            finally:
                self.spec = None
                self.wavelengths = None
    
    def is_connected(self) -> bool:
        """Check if spectrometer is connected.
        
        Returns
        -------
        bool
            True if connected
        """
        return self.spec is not None
    
    def get_measurement_config(self, integration_time_ms: float, 
                              num_averages: int, trigger_mode: int):
        """Create measurement configuration.
        
        Parameters
        ----------
        integration_time_ms : float
            Integration time in milliseconds
        num_averages : int
            Number of averages
        trigger_mode : int
            Trigger mode (0=Software, 1=Hardware, 2=Synchronous)
            
        Returns
        -------
        MeasConfigType
            Measurement configuration object, or None if not connected
        """
        if not self.spec:
            return None
        
        try:
            cfg = self.spec.MeasConfigType()
            cfg.m_StopPixel = self.spec.get_num_pixels() - 1
            cfg.m_IntegrationTime = float(integration_time_ms)
            cfg.m_NrAverages = num_averages
            
            trigger = self.spec.TriggerType()
            trigger.m_Mode = trigger_mode
            trigger.m_Source = 0
            trigger.m_SourceType = 0
            cfg.m_Trigger = trigger
            
            return cfg
            
        except Exception as e:
            self.logger.error(f"SPEC{self.spec_id}: Failed to create config - {str(e)}")
            # Mark as disconnected on error
            self.spec = None
            return None
    
    def get_info(self) -> dict:
        """Get spectrometer information.
        
        Returns
        -------
        dict
            Dictionary with num_pixels, wavelength_range, serial
        """
        if not self.is_connected():
            return {
                "num_pixels": None,
                "wavelength_range": None,
                "serial": self.serial_number
            }
        
        return {
            "num_pixels": self.spec.get_num_pixels(),
            "wavelength_range": (self.wavelengths[0], self.wavelengths[-1]),
            "serial": self.serial_number
        }
