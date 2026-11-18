"""Regression checks for VD2 wavelength selection and pointwise precision."""
import numpy as np
import pytest

from vd2_paired_kinetics import KineticAnalysis, SpectralBand
from vd2_paired_spectral import SpectralPairAnalysis


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


def test_pair_cubic_corrects_each_shot_and_preserves_post_reference_signal():
    wavelengths = np.arange(590., 601.)[::-1]
    time = np.arange(5.) / 4
    dark = np.full((11, 5), 10.)
    band = SpectralBand(595, 2, 2)
    result = SpectralPairAnalysis(dark, wavelengths, time, band, (.5, .75), "both", (1, 9))
    counts = np.full_like(dark, 200.)
    signal = np.array([0., 0., 4., 8., 10.])
    for scale in (.8, 1.2, 1.05):
        gain = scale + .01 * (wavelengths - 595)
        absorption = dark + counts * gain[:, None] * 10 ** (-signal / 1000)
        result.add(absorption, dark + counts)
    result.calculate()
    np.testing.assert_array_equal(result.time, [.5, .75])
    np.testing.assert_allclose(result.values, [4., 8.], atol=.01)
    np.testing.assert_allclose(result.spectrum, 6., atol=.01)
    np.testing.assert_allclose(result.corrected_map()[1:10] * 1000, np.broadcast_to(signal, (9, 5)), atol=.01)
    assert np.isnan(result.corrected_map()[[0, 10]]).all()
    with pytest.raises(ValueError, match="positive counts"):
        result.add(dark, dark + counts)
    assert result.pairs_used == 3


@pytest.mark.parametrize(("axis", "stops"), [("kinetics", True), ("spectrum", False), ("both", False)])
def test_precision_target_applies_to_selected_traces(axis, stops):
    wavelengths = np.arange(590., 601.)
    delays = np.arange(3.)
    dark = np.zeros((11, 3))
    result = SpectralPairAnalysis(dark, wavelengths, delays, SpectralBand(595, 1, 1), precision_axis=axis)
    base = np.full_like(dark, 1000.)
    for pair in range(160):
        absorption = base.copy()
        difference = 100 if (pair // 40) % 2 else -100
        absorption[4, 1:] += difference
        absorption[6, 1:] -= difference
        result.add(absorption, base)
    result.calculate()
    assert result.kinetics_error_mod == pytest.approx(0.)
    assert result.spectrum_error_mod > 1.
    assert (result.error_mod <= 1.) is stops
