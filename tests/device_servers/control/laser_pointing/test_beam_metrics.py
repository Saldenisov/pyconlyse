import numpy as np

import pytest

from DeviceServers.control.laser_pointing.beam_metrics import (
    CAM2_CONTOUR_RELATIVE_HEIGHTS,
    beam_contour_symmetry,
    beam_roundness,
    beam_threshold_contours,
    beam_visibility,
    camera_contour_profile,
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


def test_broad_room_light_is_not_accepted_as_a_laser_centroid():
    yy, xx = np.indices((108, 108), dtype=float)
    room_light = 125.0 + 0.35 * xx + 0.20 * yy
    image = np.repeat(room_light[..., None], 3, axis=2)

    diagnosis = beam_visibility(image, threshold=50)

    assert diagnosis["ambient_light_high"] is True
    assert diagnosis["beam_visible"] is False
    assert diagnosis["status"] == "ambient_light_high"
    assert "Switch off or reduce the room light" in diagnosis["message"]
    with pytest.raises(ValueError, match="Room/background light is too high"):
        beam_contour_symmetry([image] * 3, threshold=50)


def test_dark_margin_beam_remains_visible_with_adaptive_diagnosis():
    image = _gaussian(16.0, 16.0)

    diagnosis = beam_visibility(image, threshold=20)

    assert diagnosis["ambient_light_high"] is False
    assert diagnosis["beam_visible"] is True
    assert diagnosis["centroid"] == pytest.approx((40, 40), abs=0.5)


def test_display_contours_are_recalculated_from_each_current_frame():
    first = _gaussian(8.0, 8.0)
    second = np.roll(np.roll(first, 11, axis=0), -7, axis=1)

    first_paths = beam_threshold_contours(first, threshold=10)
    second_paths = beam_threshold_contours(second, threshold=10)

    assert len(first_paths) == len(second_paths) == 9
    first_centres = np.array([
        np.mean(path["points"][:-1], axis=0) for path in first_paths
    ])
    second_centres = np.array([
        np.mean(path["points"][:-1], axis=0) for path in second_paths
    ])
    assert np.mean(second_centres - first_centres, axis=0) == pytest.approx(
        (-7, 11), abs=0.5
    )
    assert [path["relative_height"] for path in first_paths] == [
        0.10, 0.16, 0.23, 0.31, 0.40, 0.50, 0.61, 0.72, 0.82
    ]


def test_display_contours_are_smooth_circles_from_the_scoring_fit():
    paths = beam_threshold_contours(_gaussian(7.0, 10.0), threshold=10)

    assert len(paths) == 9
    for path in paths:
        points = np.asarray(path["points"])
        radii = np.linalg.norm(
            points - np.asarray(path["centre"]), axis=1
        )
        assert len(points) == 181
        assert points[0] == pytest.approx(points[-1])
        assert radii == pytest.approx(path["radius_px"], abs=1.0e-9)
        assert path["ellipticity_error_pct"] > 0


def test_cam2_uses_lower_wider_roundness_threshold_profile():
    profile = camera_contour_profile("manip/V0/Cam2_V0", 50)
    image = _gaussian(5.0, 5.0)
    generic_paths = beam_threshold_contours(image, threshold=50)
    cam2_paths = beam_threshold_contours(image, **profile)

    assert profile == {
        "threshold": 20.0,
        "relative_heights": CAM2_CONTOUR_RELATIVE_HEIGHTS,
    }
    assert len(cam2_paths) == 9
    generic_span = (
        generic_paths[0]["radius_px"] - generic_paths[-1]["radius_px"]
    )
    cam2_span = cam2_paths[0]["radius_px"] - cam2_paths[-1]["radius_px"]
    assert cam2_span > generic_span + 1.0

    measured = beam_contour_symmetry([image], **profile)
    assert measured["contour_floor_threshold"] == pytest.approx(20.0)
    assert measured["contour_relative_heights"] == list(
        CAM2_CONTOUR_RELATIVE_HEIGHTS
    )


@pytest.mark.parametrize(
    "relative_heights",
    [(), (0.1, 0.2), (0.0, 0.2, 0.4), (0.2, 0.1, 0.4), (0.1, 0.4, 1.0)],
)
def test_invalid_contour_height_profiles_are_rejected(relative_heights):
    with pytest.raises(ValueError):
        beam_threshold_contours(
            _gaussian(8.0, 8.0),
            threshold=10,
            relative_heights=relative_heights,
        )
