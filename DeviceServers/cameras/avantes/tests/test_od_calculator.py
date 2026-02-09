"""
Unit Tests for OD Calculator
=============================

Tests for optical density calculation with background correction.
"""

import unittest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dual_od_app.core.od_calculator import ODCalculator


class TestODCalculator(unittest.TestCase):
    """Test cases for ODCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.calculator = ODCalculator()
        self.wavelengths = np.linspace(200, 1100, 2048)
        
    def test_initialization(self):
        """Test that calculator initializes with no data."""
        self.assertIsNone(self.calculator.reference_ch1)
        self.assertIsNone(self.calculator.reference_ch2)
        self.assertIsNone(self.calculator.background_ch1)
        self.assertIsNone(self.calculator.background_ch2)
        self.assertFalse(self.calculator.has_reference)
        self.assertFalse(self.calculator.has_background)
        self.assertFalse(self.calculator.can_calculate_od())
    
    def test_set_reference(self):
        """Test setting reference spectra."""
        ref_ch1 = np.ones(2048) * 1000
        ref_ch2 = np.ones(2048) * 900
        
        self.calculator.set_reference(ref_ch1, ref_ch2)
        
        self.assertTrue(self.calculator.has_reference)
        np.testing.assert_array_equal(self.calculator.reference_ch1, ref_ch1)
        np.testing.assert_array_equal(self.calculator.reference_ch2, ref_ch2)
    
    def test_set_background(self):
        """Test setting background spectra."""
        bg_ch1 = np.ones(2048) * 100
        bg_ch2 = np.ones(2048) * 90
        
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        self.assertTrue(self.calculator.has_background)
        np.testing.assert_array_equal(self.calculator.background_ch1, bg_ch1)
        np.testing.assert_array_equal(self.calculator.background_ch2, bg_ch2)
    
    def test_cannot_calculate_without_reference(self):
        """Test that OD calculation requires reference."""
        bg_ch1 = np.ones(2048) * 100
        bg_ch2 = np.ones(2048) * 90
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        self.assertFalse(self.calculator.can_calculate_od())
        
        ch1 = np.ones(2048) * 800
        ch2 = np.ones(2048) * 700
        od = self.calculator.calculate_od(ch1, ch2)
        
        self.assertIsNone(od)
    
    def test_cannot_calculate_without_background(self):
        """Test that OD calculation requires background."""
        ref_ch1 = np.ones(2048) * 1000
        ref_ch2 = np.ones(2048) * 900
        self.calculator.set_reference(ref_ch1, ref_ch2)
        
        self.assertFalse(self.calculator.can_calculate_od())
        
        ch1 = np.ones(2048) * 800
        ch2 = np.ones(2048) * 700
        od = self.calculator.calculate_od(ch1, ch2)
        
        self.assertIsNone(od)
    
    def test_od_calculation_no_absorption(self):
        """Test OD calculation with no absorption (sample = reference)."""
        # Set up reference and background
        ref_ch1 = np.ones(2048) * 1000
        ref_ch2 = np.ones(2048) * 900
        bg_ch1 = np.ones(2048) * 100
        bg_ch2 = np.ones(2048) * 90
        
        self.calculator.set_reference(ref_ch1, ref_ch2)
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        # Sample = reference (no absorption)
        ch1 = ref_ch1.copy()
        ch2 = ref_ch2.copy()
        
        od = self.calculator.calculate_od(ch1, ch2)
        
        self.assertIsNotNone(od)
        # OD should be ~0 for no absorption
        np.testing.assert_array_almost_equal(od, np.zeros(2048), decimal=6)
    
    def test_od_calculation_with_absorption(self):
        """Test OD calculation with known absorption."""
        # Set up reference and background
        ref_ch1 = np.ones(2048) * 1000  # I0_ch1
        ref_ch2 = np.ones(2048) * 900   # I0_ch2
        bg_ch1 = np.ones(2048) * 100
        bg_ch2 = np.ones(2048) * 90
        
        self.calculator.set_reference(ref_ch1, ref_ch2)
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        # Sample with 50% transmission in ch1
        ch1 = np.ones(2048) * 550  # (550-100)/(1000-100) = 0.5
        ch2 = ref_ch2.copy()
        
        od = self.calculator.calculate_od(ch1, ch2)
        
        self.assertIsNotNone(od)
        # OD = log10((I0_ch1/I0_ch2) / (I_ch1/I_ch2))
        # OD = log10((1000-100)/(900-90) / (550-100)/(900-90))
        # OD = log10(900/810 / 450/810) = log10(2) ≈ 0.301
        expected_od = np.ones(2048) * 0.301
        np.testing.assert_array_almost_equal(od, expected_od, decimal=3)
    
    def test_get_od_at_wavelength(self):
        """Test extracting OD at specific wavelength."""
        wavelengths = np.linspace(200, 1100, 2048)
        od_spectrum = np.sin(wavelengths / 100)  # Variable OD spectrum
        
        # Test at 500nm
        od_value = self.calculator.get_od_at_wavelength(od_spectrum, wavelengths, 500.0)
        
        # Find expected value
        idx = np.argmin(np.abs(wavelengths - 500.0))
        expected = od_spectrum[idx]
        
        self.assertAlmostEqual(od_value, expected, places=6)
    
    def test_get_od_at_wavelength_with_none(self):
        """Test that get_od_at_wavelength returns NaN for None input."""
        wavelengths = np.linspace(200, 1100, 2048)
        
        od_value = self.calculator.get_od_at_wavelength(None, wavelengths, 500.0)
        self.assertTrue(np.isnan(od_value))
        
        od_spectrum = np.zeros(2048)
        od_value = self.calculator.get_od_at_wavelength(od_spectrum, None, 500.0)
        self.assertTrue(np.isnan(od_value))
    
    def test_reset(self):
        """Test resetting calculator state."""
        # Set up complete state
        ref_ch1 = np.ones(2048) * 1000
        ref_ch2 = np.ones(2048) * 900
        bg_ch1 = np.ones(2048) * 100
        bg_ch2 = np.ones(2048) * 90
        
        self.calculator.set_reference(ref_ch1, ref_ch2)
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        self.assertTrue(self.calculator.can_calculate_od())
        
        # Reset
        self.calculator.reset()
        
        # Check all state is cleared
        self.assertIsNone(self.calculator.reference_ch1)
        self.assertIsNone(self.calculator.reference_ch2)
        self.assertIsNone(self.calculator.background_ch1)
        self.assertIsNone(self.calculator.background_ch2)
        self.assertFalse(self.calculator.has_reference)
        self.assertFalse(self.calculator.has_background)
        self.assertFalse(self.calculator.can_calculate_od())
    
    def test_division_by_zero_protection(self):
        """Test that calculator handles near-zero values safely."""
        # Set up with very low signals
        ref_ch1 = np.ones(2048) * 10
        ref_ch2 = np.ones(2048) * 10
        bg_ch1 = np.ones(2048) * 9.99  # Nearly equal to reference
        bg_ch2 = np.ones(2048) * 9.99
        
        self.calculator.set_reference(ref_ch1, ref_ch2)
        self.calculator.set_background(bg_ch1, bg_ch2)
        
        ch1 = np.ones(2048) * 9.999
        ch2 = np.ones(2048) * 9.999
        
        # Should not raise exception
        od = self.calculator.calculate_od(ch1, ch2)
        
        self.assertIsNotNone(od)
        # Should not contain inf or nan
        self.assertFalse(np.any(np.isinf(od)))
        self.assertFalse(np.any(np.isnan(od)))


if __name__ == '__main__':
    unittest.main()
