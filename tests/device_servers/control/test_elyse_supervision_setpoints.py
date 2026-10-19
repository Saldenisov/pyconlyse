"""Golden, non-hardware checks against saved Supervision LabVIEW Print frames."""

import math

import pytest

from DeviceServers.control.elyse_acq.legacy_supervision_setpoints import (
    adjust_beam_setpoint,
    adjust_hf_attenuation,
    adjust_hf_phase,
    adjust_ht_setpoint,
    adjust_preamp_setpoint,
    beam_group,
)


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "direct",
            {
                0: "dipole_triplet",
                1: "focale",
                2: "phase_hf_laser",
                3: "corrector",
                4: "corrector",
                5: "corrector",
                6: "corrector",
                7: "dipole_triplet",
                8: "dipole_triplet",
                9: "corrector",
                10: "corrector",
            },
        ),
        (
            "deviated",
            {
                0: "dipole_triplet",
                1: "dipole_triplet",
                2: "dipole_triplet",
                3: "dipole_triplet",
                4: "corrector",
                5: "corrector",
                6: "dipole_triplet",
                7: "corrector",
                8: "corrector",
            },
        ),
    ],
)
def test_beam_ui_row_groups_cover_each_legacy_row(line, expected):
    assert {index: beam_group(line, index) for index in expected} == expected
    with pytest.raises(ValueError):
        beam_group(line, len(expected))


@pytest.mark.parametrize(
    "line,row,coarse,fine,minimum,maximum",
    [
        ("direct", 1, (10.0, 1.0), (1.0, 0.1), 0.0, 120.0),
        ("direct", 2, (50.0, 5.0), (5.0, 1.0), 0.0, 360.0),
        ("direct", 0, (1.0, 0.1), (0.1, 0.01), -16.0, 16.0),
        ("direct", 3, (1.0, 0.1), (0.1, 0.01), -5.0, 5.0),
        ("deviated", 0, (1.0, 0.1), (0.1, 0.01), -16.0, 16.0),
        ("deviated", 4, (1.0, 0.1), (0.1, 0.01), -5.0, 5.0),
    ],
)
def test_beam_arrows_steps_and_bounds(line, row, coarse, fine, minimum, maximum):
    center = (minimum + maximum) / 2.0
    for action, choices, direction in (
        (128, coarse, -1),
        (256, fine, -1),
        (512, fine, 1),
        (1024, coarse, 1),
    ):
        for step in choices:
            assert adjust_beam_setpoint(line, row, center, action, step) == pytest.approx(
                center + direction * step
            )
        assert adjust_beam_setpoint(line, row, minimum, action, choices[0]) >= minimum
        assert adjust_beam_setpoint(line, row, maximum, action, choices[0]) <= maximum


@pytest.mark.parametrize(
    "function,current,actions,minimum,maximum",
    [
        (adjust_ht_setpoint, 10.0, {1: -1.0, 2: -0.1, 4: 0.1, 8: 1.0}, 6.0, 20.0),
        (
            adjust_preamp_setpoint,
            300.0,
            {16: -5.0, 32: -1.0, 64: 1.0, 128: 5.0},
            200.0,
            400.0,
        ),
        (
            adjust_hf_attenuation,
            10.0,
            {1: -5.0, 2: -1.0, 4: 1.0, 8: 1.0},
            0.0,
            20.0,
        ),
        (
            adjust_hf_phase,
            0.0,
            {16: -10.0, 32: -1.0, 64: 1.0, 128: 10.0},
            -180.0,
            180.0,
        ),
    ],
)
def test_ht_hf_native_steps_and_clamps(function, current, actions, minimum, maximum):
    for action, delta in actions.items():
        assert function(current, action) == pytest.approx(current + delta)
        assert function(minimum, action) >= minimum
        assert function(maximum, action) <= maximum


def test_hf_coarse_increase_preserves_legacy_plus_one_asymmetry():
    # Print d301 shows +1 for selector 8, just like selector 4 in d300.
    assert adjust_hf_attenuation(10.0, 4) == 11.0
    assert adjust_hf_attenuation(10.0, 8) == 11.0


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf, True, "bad"])
def test_non_finite_or_non_numeric_setpoints_are_rejected(invalid):
    with pytest.raises(ValueError):
        adjust_ht_setpoint(invalid, 1)
    with pytest.raises(ValueError):
        adjust_beam_setpoint("direct", 0, 0.0, 128, invalid)


def test_unresolved_or_non_adjustment_inputs_fail_closed():
    with pytest.raises(ValueError):
        adjust_beam_setpoint("direct", 0, 0.0, 1, 1.0)
    with pytest.raises(ValueError):
        adjust_beam_setpoint("direct", 0, 0.0, 128, 999.0)
    with pytest.raises(ValueError):
        beam_group("unknown", 0)
    with pytest.raises(ValueError):
        beam_group("direct", True)
    with pytest.raises(ValueError):
        adjust_beam_setpoint("direct", 0, 0.0, True, 1.0)
    with pytest.raises(ValueError):
        adjust_hf_attenuation(5.0, 999)
    with pytest.raises(ValueError):
        adjust_hf_attenuation(5.0, True)
