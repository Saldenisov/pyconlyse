"""
OD Calculator Module
====================

Optical Density calculation with background correction.
"""

import numpy as np
import logging


class ODCalculator:
    """Calculate optical density from dual-channel spectrometer data."""
    
    def __init__(self):
        self.reference_ch1 = None
        self.reference_ch2 = None
        self.background_ch1 = None
        self.background_ch2 = None
        self.has_reference = False
        self.has_background = False
        self.logger = logging.getLogger(__name__)
    
    def set_reference(self, ch1_data: np.ndarray, ch2_data: np.ndarray):
        """Set reference spectra (lamp ON).
        
        Parameters
        ----------
        ch1_data : np.ndarray
            Channel 1 reference spectrum
        ch2_data : np.ndarray
            Channel 2 reference spectrum
        """
        self.reference_ch1 = ch1_data
        self.reference_ch2 = ch2_data
        self.has_reference = True
        self.logger.info("OD_CALC: Reference spectra set")
    
    def set_background(self, ch1_data: np.ndarray, ch2_data: np.ndarray):
        """Set background spectra (lamp OFF).
        
        Parameters
        ----------
        ch1_data : np.ndarray
            Channel 1 background spectrum
        ch2_data : np.ndarray
            Channel 2 background spectrum
        """
        self.background_ch1 = ch1_data
        self.background_ch2 = ch2_data
        self.has_background = True
        self.logger.info("OD_CALC: Background spectra set")
    
    def calculate_od(self, ch1_data: np.ndarray, ch2_data: np.ndarray) -> np.ndarray:
        """Calculate optical density with background correction.
        
        OD = log10((I0_ch1 - BG_ch1) / (I0_ch2 - BG_ch2) / (I_ch1 - BG_ch1) / (I_ch2 - BG_ch2))
        
        Parameters
        ----------
        ch1_data : np.ndarray
            Current channel 1 spectrum
        ch2_data : np.ndarray
            Current channel 2 spectrum
            
        Returns
        -------
        np.ndarray
            Optical density spectrum, or None if prerequisites not met
        """
        if not self.can_calculate_od():
            return None
        
        try:
            # Background-corrected signals
            I_ch1 = ch1_data - self.background_ch1
            I_ch2 = ch2_data - self.background_ch2
            I0_ch1 = self.reference_ch1 - self.background_ch1
            I0_ch2 = self.reference_ch2 - self.background_ch2
            
            # Avoid division by zero
            epsilon = 1e-10
            I_ch1 = np.maximum(I_ch1, epsilon)
            I_ch2 = np.maximum(I_ch2, epsilon)
            I0_ch1 = np.maximum(I0_ch1, epsilon)
            I0_ch2 = np.maximum(I0_ch2, epsilon)
            
            # Calculate OD
            od = np.log10((I0_ch1 / I0_ch2) / (I_ch1 / I_ch2))
            
            return od
            
        except Exception as e:
            self.logger.error(f"OD_CALC: Calculation failed - {str(e)}")
            return None
    
    def can_calculate_od(self) -> bool:
        """Check if OD calculation is possible.
        
        Returns
        -------
        bool
            True if both reference and background are set
        """
        return self.has_reference and self.has_background
    
    def reset(self):
        """Reset all reference and background data."""
        self.reference_ch1 = None
        self.reference_ch2 = None
        self.background_ch1 = None
        self.background_ch2 = None
        self.has_reference = False
        self.has_background = False
        self.logger.info("OD_CALC: Reset complete")
    
    def get_od_at_wavelength(self, od_spectrum: np.ndarray, wavelengths: np.ndarray, 
                            target_wavelength: float) -> float:
        """Extract OD value at specific wavelength.
        
        Parameters
        ----------
        od_spectrum : np.ndarray
            Full OD spectrum
        wavelengths : np.ndarray
            Wavelength array
        target_wavelength : float
            Target wavelength in nm
            
        Returns
        -------
        float
            OD value at target wavelength
        """
        if od_spectrum is None or wavelengths is None:
            return np.nan
        
        # Find closest wavelength index
        idx = np.argmin(np.abs(wavelengths - target_wavelength))
        return od_spectrum[idx]
