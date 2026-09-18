import numpy as np

import pytest

from DeviceServers.control.laser_pointing.beam_metrics import (
    beam_contour_symmetry,
    beam_roundness,
)


def _gaussian(width_x, width_y, offset_lobe=False):
    yy, xx = np.indices((81, 81), dtype=float)
    image = 220.0 * np.exp(
        -0.5 * (((xx - 40.0) / width_x) ** 2 + ((yy - 40.0) / width_y) ** 2)
    )
    if offset_lobe:
        image += 55.0 * np.exp(
            -0.5 * (((xx - 49.0) / 5.0) ** 2 + ((yy - 40.0) / 5.0) ** 2)
        )
    return np.repeat(image[..., None], 3, axis=2)


def test_round_beam_scores_better_than_elongated_beam():
    round_metric = beam_roundness(_gaussian(8.0, 8.0), threshold=10)
    elongated_metric = beam_roundness(_gaussian(5.0, 10.0), threshold=10)

    assert round_metric["roundness_pct"] > 99.0
    assert elongated_metric["roundness_error_pct"] > 35.0
    assert (
        round_metric["roundness_error_pct"]
        < elongated_metric["roundness_error_pct"]
    )


def test_asymmetric_beam_scores_worse_than_symmetric_beam():
    symmetric = beam_roundness(_gaussian(8.0, 8.0), threshold=10)
    asymmetric = beam_roundness(
        _gaussian(8.0, 8.0, offset_lobe=True), threshold=10
    )

    assert asymmetric["asymmetry"] > symmetric["asymmetry"]
    assert asymmetric["roundness_error_pct"] > symmetric["roundness_error_pct"]


def test_basler_stacked_rgb_transfer_has_same_roundness():
    image = _gaussian(7.0, 9.0)
    stacked = image.transpose(2, 0, 1).reshape(-1, image.shape[1])

    normal = beam_roundness(image, threshold=10)
    transferred = beam_roundness(
        stacked,
        threshold=10,
        width=image.shape[1],
        height=image.shape[0],
    )

    assert transferred["roundness_error_pct"] == normal["roundness_error_pct"]


def test_concentric_score_is_independent_of_camera_centre():
    yy, xx = np.indices((121, 121), dtype=float)
    centred = 220 * np.exp(-0.5 * (((xx - 60) / 10) ** 2
                                     + ((yy - 60) / 10) ** 2))
    displaced = 220 * np.exp(-0.5 * (((xx - 78) / 10) ** 2
                                      + ((yy - 42) / 10) ** 2))

    first = beam_contour_symmetry([centred] * 3, threshold=10)
    second = beam_contour_symmetry([displaced] * 3, threshold=10)

    assert first["roundness_error_pct"] == pytest.approx(
        second["roundness_error_pct"], abs=0.05
    )
    assert second["shape_centroid"] == pytest.approx((78, 42), abs=0.2)
    assert second["contour_count"] >= 6


def test_shifted_inner_rings_score_worse_even_with_similar_spot_position():
    yy, xx = np.indices((121, 121), dtype=float)
    outer = 160 * np.exp(-0.5 * (((xx - 60) / 10) ** 2
                                   + ((yy - 60) / 10) ** 2))
    concentric = outer + 90 * np.exp(-0.5 * (((xx - 60) / 3) ** 2
                                             + ((yy - 60) / 3) ** 2))
    displaced_core = outer + 90 * np.exp(-0.5 * (((xx - 67) / 3) ** 2
                                                 + ((yy - 60) / 3) ** 2))

    good = beam_contour_symmetry([concentric] * 3, threshold=10)
    bad = beam_contour_symmetry([displaced_core] * 3, threshold=10)

    assert bad["contour_centre_drift_px"] > good["contour_centre_drift_px"] + 0.7
    assert bad["roundness_error_pct"] > good["roundness_error_pct"] + 4.0


def test_median_of_three_frames_suppresses_one_hot_pixel():
    yy, xx = np.indices((101, 101), dtype=float)
    clean = 220 * np.exp(-0.5 * (((xx - 50) / 8) ** 2
                                   + ((yy - 50) / 8) ** 2))
    noisy = clean.copy()
    noisy[8, 10] = 1000

    measured = beam_contour_symmetry([clean, noisy, clean], threshold=10)

    assert measured["sample_count"] == 3
    assert measured["shape_centroid"] == pytest.approx((50, 50), abs=0.2)
    assert measured["roundness_error_pct"] < 3


def test_profile_preview_is_the_exact_median_measurement_frame():
    yy, xx = np.indices((101, 101), dtype=float)
    frame = 220 * np.exp(-0.5 * (((xx - 61) / 8) ** 2
                                  + ((yy - 37) / 8) ** 2))

    measured = beam_contour_symmetry(
        [frame] * 3, threshold=10, include_preview=True
    )

    assert measured["preview_data_url"].startswith("data:image/png;base64,")
    assert measured["preview_width"] == 101
    assert measured["preview_height"] == 101
    assert measured["preview_centroid"] == pytest.approx((61, 37), abs=0.2)


def test_clipped_contours_are_not_accepted_as_alignment():
    yy, xx = np.indices((81, 81), dtype=float)
    clipped = 220 * np.exp(-0.5 * (((xx - 2) / 10) ** 2
                                     + ((yy - 40) / 10) ** 2))

    with pytest.raises(ValueError, match="clipped by the camera frame"):
        beam_contour_symmetry([clipped] * 3, threshold=10)
