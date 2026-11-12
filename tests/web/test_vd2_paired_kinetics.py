"""Regression checks for VD2 wavelength selection and pointwise precision."""
import numpy as np
import pytest

from vd2_paired_kinetics import KineticAnalysis, SpectralBand


def test_lamp_matching_uses_reference_rows_separate_from_kinetics():
    wavelengths = np.array([580., 595., 600., 605., 620.])
    time = np.arange(3.)
    dark = np.ones((5, 3))
    band = SpectralBand(600, 5, 1)
    matching = KineticAnalysis(dark, wavelengths, time, band, "lamp_matched", 3)
    adjacent = KineticAnalysis(dark, wavelengths, time, band, "mean_pair_od", 3)
    for a, b in ((100, 200), (100, 200), (200, 100)):
        absorption, base = dark + a, dark + b
        matching.add(absorption, base)
        adjacent.add(absorption, base)
    matching.calculate()
    adjacent.calculate()
    np.testing.assert_allclose(matching.values, 0, atol=1e-10)
    assert adjacent.estimate_mod > 90
    np.testing.assert_array_equal(matching.time, time[1:])


def test_precision_checks_every_time_point_when_mean_od_cancels():
    wavelengths = np.array([590., 600., 610.])
    time = np.arange(3.)
    dark = np.full((3, 3), 10.)
    band = SpectralBand(600, 5, 1)
    result = KineticAnalysis(dark, wavelengths, time, band, "mean_pair_od", 3, [dark] * 4)
    for block in range(8):
        sign = (1 if block % 4 < 2 else -1)
        for _ in range(20):
            absorption = dark + 100
            base = dark + 100 * 10 ** (np.array([0, 10, -10]) * sign / 1000)
            result.add(absorption, base)
    result.calculate()
    assert result.estimate_mod == pytest.approx(0, abs=1e-10)
    assert result.error_mod == np.max(result.errors) and result.error_mod > 1
    with pytest.raises(ValueError, match="outside"):
        SpectralBand(650, 5, 1).columns(wavelengths)
