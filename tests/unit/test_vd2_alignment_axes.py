import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
from vd2_alignment import read_alignment_axes, image_alignment_settings, image_intensity_settings, alignment_calibration_key, alignment_measurement_key


def test_measurement_identity_ignores_only_automatic_per_frame_lut_limits():
    header = '[Acquisition],NrExposure=1,ExposureTime=10 ms[DisplayLUT],LowerValue=506,UpperValue=18637,Gamma=1,AutoLutInLiveMode=-1[ExternalDevices],MCP Gain="0"'
    changed = header.replace('506', '511').replace('18637', '19099')
    settings = image_intensity_settings(header)
    other = image_intensity_settings(changed)
    assert alignment_calibration_key(settings,640,508) != alignment_calibration_key(other,640,508)
    assert alignment_measurement_key(settings,640,508) == alignment_measurement_key(other,640,508)
    for old,new in [('10 ms','20 ms'),('Gamma=1','Gamma=2'),('MCP Gain="0"','MCP Gain="1"')]:
        assert alignment_measurement_key(settings,640,508) != alignment_measurement_key(image_intensity_settings(header.replace(old,new)),640,508)
    manual = lambda text: image_intensity_settings(text.replace('AutoLutInLiveMode=-1','AutoLutInLiveMode=0'))
    assert alignment_measurement_key(manual(header),640,508) != alignment_measurement_key(manual(changed),640,508)
    assert alignment_measurement_key(settings,640,508,{'enabled':True,'frames':2}) != alignment_measurement_key(settings,640,508,{'enabled':True,'frames':5})


def test_intensity_reference_identity_tracks_native_lut_and_exposure_not_frame_clock():
    header = '[Application],Time="16:00"[Acquisition],ExposureTime=10 ms,SubType=0[DisplayLUT],LowerValue=300,UpperValue=500,Gamma=1[ExternalDevices],MCP Gain="0"'
    key = lambda text: alignment_calibration_key(image_intensity_settings(text), 640, 508)
    assert key(header) == key(header.replace('16:00', '16:01'))
    for old, new in [('10 ms', '20 ms'), ('UpperValue=500', 'UpperValue=600'), ('MCP Gain="0"', 'MCP Gain="1"')]:
        assert key(header) != key(header.replace(old, new))
    with pytest.raises(ValueError, match="missing display LUT"):
        image_intensity_settings('[Acquisition],ExposureTime=10 ms')


def test_live_calibration_identity_ignores_frame_clock_but_tracks_optical_settings():
    header = ('[Application],Time="16:00",Time Range="1 us",Wavelength="600",Grating="150 g/mm",'
              'ScalingXScale=1,ScalingYScale=1,ScalingXUnit="nm",ScalingYUnit="us",'
              'ScalingXScalingFile="Spec.",ScalingYScalingFile="time.scl",')
    settings = image_alignment_settings(header)
    key = alignment_calibration_key(settings, 640, 508)
    assert key == alignment_calibration_key(image_alignment_settings(header.replace('16:00', '16:01')), 640, 508)
    assert key != alignment_calibration_key(image_alignment_settings(header.replace('600', '700')), 640, 508)
    assert key != alignment_calibration_key(settings, 320, 508)
    with pytest.raises(ValueError, match="missing ScalingYUnit"):
        image_alignment_settings(header.replace('ScalingYUnit="us",', ''))


def test_current_img_calibration_keeps_nonlinear_axes_and_acquired_settings(monkeypatch):
    info = SimpleNamespace(wavelengths_length=3, timedelays_length=3,
        wavelengths=np.array([490., 599., 701.]), timedelays=np.array([0.1, 0.3, 0.9]),
        scaling_xunit="nm", scaling_yunit="us",
        header='Time Range="1 us",Wavelength="600",Grating="150 g/mm",')
    monkeypatch.setattr(HamamatsuFileOpener, "read_critical_info", lambda *_: info)
    axes = read_alignment_axes(Path("synthetic.img"))
    assert axes["wavelengths"] == [490., 599., 701.]
    assert axes["timedelays"] == [0.1, 0.3, 0.9]
    assert axes["time_unit"] == "us"
    assert axes["acquisition_settings"] == {"time_range": "1 us", "wavelength_nm": "600", "grating": "150 g/mm"}


@pytest.mark.parametrize("values", [[0, 0, 2], [0, np.nan, 2], [2, 0, 1]])
def test_bad_axes_are_never_labeled_as_calibrated(monkeypatch, values):
    info = SimpleNamespace(wavelengths_length=3, timedelays_length=3,
        wavelengths=np.asarray(values), timedelays=np.array([0.1, 0.3, 0.9]),
        scaling_xunit="nm", scaling_yunit="us", header="")
    monkeypatch.setattr(HamamatsuFileOpener, "read_critical_info", lambda *_: info)
    with pytest.raises(ValueError, match="calibration is invalid"):
        read_alignment_axes(Path("synthetic.img"))
