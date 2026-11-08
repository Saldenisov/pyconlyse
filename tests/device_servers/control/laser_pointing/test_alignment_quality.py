import numpy as np
import pytest

from DeviceServers.control.laser_pointing.alignment_quality import (
    centering_verification, confirm_improvement, contour_centering,
)
from DeviceServers.control.laser_pointing.automatic_search import SearchParameters
from DeviceServers.control.laser_pointing.beam_metrics import beam_contour_symmetry
from DeviceServers.control.laser_pointing.confirmed_search import (
    CenteringSearchCancelled, confirmed_centering_search,
)


def quality(score, ellipticity=20.0):
    return {"centering_error_px": score, "ellipticity_error_pct": ellipticity,
            "roundness_error_pct": 25.0}


def test_concentric_ellipse_passes_centering_without_passing_ellipticity():
    yy, xx = np.indices((151, 151), dtype=float)
    image = 210 * np.exp(-.5 * (((xx - 73) / 9) ** 2 + ((yy - 77) / 16) ** 2))
    shape = beam_contour_symmetry([image], threshold=10)
    result = centering_verification([shape] * 3, tolerance_px=1.0)
    assert shape["alignment_centroid"] == pytest.approx((73, 77), abs=.15)
    assert result["centering_passed"] is True
    assert result["ellipticity_passed"] is False
    assert shape["ellipticity_error_pct"] > 30
    assert shape["roundness_error_pct"] > 7


def test_shifted_core_fails_centering_even_for_a_round_outer_beam():
    yy, xx = np.indices((151, 151), dtype=float)
    outer = 100 * np.exp(-.5 * (((xx - 75) / 13) ** 2 + ((yy - 75) / 13) ** 2))
    core = 140 * np.exp(-.5 * (((xx - 75) / 4) ** 2 + ((yy - 84) / 4) ** 2))
    shape = beam_contour_symmetry([outer + core], threshold=10)
    assert centering_verification([shape] * 3, 1.0)["centering_passed"] is False


def test_centering_is_translation_invariant():
    contours = [{"ellipse_centre": [x, y]} for x, y in [(20, 30), (20.5, 30), (20, 30.5)]]
    shifted = [{"ellipse_centre": [c["ellipse_centre"][0] + 19, c["ellipse_centre"][1] - 8]} for c in contours]
    assert contour_centering(contours)["centering_error_px"] == pytest.approx(
        contour_centering(shifted)["centering_error_px"])


def test_one_lucky_low_measurement_is_not_an_improvement():
    result = confirm_improvement([2.0, 2.1, 1.9], [.1, 2.2, 2.3])
    assert result["accepted"] is False


def test_gain_below_repeat_scatter_is_not_an_improvement():
    assert confirm_improvement([1.8, 2., 2.2], [1.7, 1.9, 2.1])["accepted"] is False


def test_stable_repeated_gain_is_confirmed():
    assert confirm_improvement([2., 2.05, 1.95], [.8, .85, .75])["accepted"] is True


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_nonfinite_or_negative_quality_is_rejected(bad):
    with pytest.raises(ValueError):
        confirm_improvement([2, 2, 2], [bad, 1, 1])


def test_every_final_repeat_must_pass_not_just_the_median():
    result = centering_verification([quality(.1), quality(.2), quality(1.1)], 1.0)
    assert result["centering_passed"] is False
    assert result["centering_worst_px"] == 1.1


def test_search_confirms_a_real_improvement_after_reference_and_candidate_return():
    calls, restored, observations = [], [], []

    def measure(position):
        calls.append(tuple(position))
        return quality(.2 if position == (1., 0.) else 2.)

    result, evidence = confirmed_centering_search(
        measure, restored.append, (0., 0.), ((-1., 1.), (-1., 1.)),
        SearchParameters(initial_step=1, minimum_step=1, tolerance_px=.5,
                         max_evaluations=5, minimum_improvement_px=.1, step_schedule=(1,)),
        on_observation=observations.append)
    assert result.best_position == (1., 0.)
    assert result.converged
    assert calls[:12] == [(0., 0.)] * 3 + [(1., 0.)] * 3 + [(0., 0.)] * 3 + [(1., 0.)] * 3
    assert any(o.get("fresh_confirmation", {}).get("accepted") for o in observations)
    assert evidence["measurement_count"] <= 5 * 9 + 3


def test_candidate_that_deteriorates_after_return_is_not_retained():
    visits = {"candidate": 0}

    def measure(position):
        if position == (1., 0.):
            visits["candidate"] += 1
            return quality(.1 if visits["candidate"] <= 3 else 2.5)
        return quality(2.)

    result, evidence = confirmed_centering_search(
        measure, lambda _: None, (0., 0.), ((-1., 1.), (-1., 1.)),
        SearchParameters(initial_step=1, minimum_step=1, tolerance_px=.5,
                         max_evaluations=2, minimum_improvement_px=.1, step_schedule=(1,)))
    assert result.best_position == (0., 0.)
    assert not result.converged
    assert evidence["decisions"][0]["confirmed"] is False


def test_final_recheck_prevents_false_convergence_from_an_old_good_measurement():
    count = [0]

    def measure(_position):
        count[0] += 1
        return quality(.2 if count[0] <= 3 else 2.)

    result, _ = confirmed_centering_search(
        measure, lambda _: None, (0., 0.), ((-1., 1.), (-1., 1.)),
        SearchParameters(tolerance_px=.5, max_evaluations=2))
    assert result.reason == "verification_failed"
    assert not result.converged


def test_cancellation_interrupts_confirmation_without_extra_measurements():
    calls = []

    def measure(position):
        calls.append(position)
        return quality(2.)

    with pytest.raises(CenteringSearchCancelled):
        confirmed_centering_search(measure, lambda _: None, (0., 0.), ((-1., 1.), (-1., 1.)),
                                   SearchParameters(), cancelled=lambda: len(calls) >= 2)
    assert len(calls) == 2
