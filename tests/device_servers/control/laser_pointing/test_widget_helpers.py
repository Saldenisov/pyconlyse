from DeviceServers.control.laser_pointing.widget_helpers import (
    STANDA_STEP_SIZES,
    is_other_optical_role,
)


def test_compact_standa_step_sizes_match_operator_choices():
    assert STANDA_STEP_SIZES == (0.5, 1.0, 2.0, 5.0)


def test_other_optics_include_diaphragms_and_half_wave_plate():
    assert is_other_optical_role("MainLaserDiaphragm1")
    assert is_other_optical_role("CrimpingDiaphragm2")
    assert is_other_optical_role("HalfWavePlate1")
    assert is_other_optical_role("Lambda_2_Exp")
    assert not is_other_optical_role("ActuatorX1")
    assert is_other_optical_role("Shutter1", "manip/V0/Cam1_V0")
    assert not is_other_optical_role("Shutter2", "manip/V0/Cam1_V0")
    assert is_other_optical_role("Shutter2", "manip/V0/Cam2_V0")
    assert not is_other_optical_role("Shutter1", "manip/V0/Cam2_V0")
