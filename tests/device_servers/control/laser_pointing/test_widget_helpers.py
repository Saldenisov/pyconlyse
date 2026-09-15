from DeviceServers.control.laser_pointing.widget_helpers import (
    STANDA_STEP_SIZES,
    format_optical_status_value,
    is_other_optical_role,
    manual_alignment_motion_enabled,
)


def test_compact_standa_step_sizes_match_operator_choices():
    assert STANDA_STEP_SIZES == (0.5, 1.0, 2.0, 5.0, 20.0, 50.0, 100.0)


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


def test_compact_status_formats_flippers_from_hardware_end_switches():
    assert format_optical_status_value("Shutter1", "RIGHT") == "DOWN"
    assert format_optical_status_value("Flipper2", "LEFT") == "UP · BLOCKED"
    assert format_optical_status_value("Shutter1", "BETWEEN") == "BETWEEN"
    assert format_optical_status_value("Shutter1", "UNKNOWN") == "UNKNOWN"


def test_compact_status_does_not_mislabel_numeric_flipper_position():
    assert format_optical_status_value("Shutter1", -1) == "−1"
    assert format_optical_status_value("Flipper2", 1) == "+1"
    assert format_optical_status_value("Shutter1", 0) == "UNKNOWN"


def test_compact_status_formats_optical_opening_as_percentage():
    assert format_optical_status_value("CrimpingDiaphragm1", 40) == "40%"
    assert format_optical_status_value("HalfWavePlate1", 20.5) == "20.5%"
    assert format_optical_status_value("MainLaserDiaphragm1", None) == "—"


def test_ready_manual_alignment_axes_are_available_without_selected_point():
    assert manual_alignment_motion_enabled(True)
    assert not manual_alignment_motion_enabled(False)


def test_controller_owned_operations_lock_manual_alignment_axes():
    assert not manual_alignment_motion_enabled(True, point_application_busy=True)
    assert not manual_alignment_motion_enabled(True, pair_initialization_busy=True)
    assert not manual_alignment_motion_enabled(True, automatic_search_running=True)
