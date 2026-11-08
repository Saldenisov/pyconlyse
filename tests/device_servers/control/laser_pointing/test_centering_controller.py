"""Fake-controller integration only: no Tango device proxies are constructed."""
from threading import Event

import numpy as np
import pytest

from DeviceServers.control.laser_pointing.DS_LaserPointing import DS_LaserPointing, SearchCancelled, LaserNotVisible


def config(**values):
    return DS_LaserPointing._normalise_search_config({
        "alignment_objective": "centering", "adaptive_learning": False,
        "aperture_sweep_enabled": False, "samples": 3,
        "step_schedule": [0.5], "max_evaluations": 5,
        **values,
    })


def shape(error=.2):
    return {"centering_error_px": error, "ellipticity_error_pct": 25.,
            "roundness_error_pct": 20., "roundness_pct": 80.,
            "shape_centroid": [40., 40.], "alignment_centroid": [40., 40.],
            "sigma_major_px": 10., "aperture_pair_checked": True}


def test_legacy_defaults_remain_staged_while_new_objective_is_explicit():
    assert DS_LaserPointing._normalise_search_config({})["alignment_objective"] == "roundness"
    assert config()["alignment_objective"] == "centering"


@pytest.mark.parametrize("values", [
    {"measurement_repetitions": 1}, {"measurement_repetitions": 3.1},
    {"measurement_repetitions": True}, {"centering_tolerance_px": float("nan")},
    {"confirmation_noise_multiplier": -1}, {"alignment_objective": "unknown"},
    {"centering_check_aperture_pair": "false"},
])
def test_invalid_centering_settings_are_rejected(values):
    with pytest.raises((ValueError, TypeError)):
        config(**values)


def test_aperture_endpoints_are_checked_even_without_a_full_sweep():
    c = object.__new__(DS_LaserPointing)
    c.controller_rules = {"point1": {"Diaphragm": 10.}, "point3": {"Diaphragm": 5.}}
    c._search_progress = {}
    c._search_stop = Event()
    c._raise_if_cancelled = lambda: None
    c._device_for_role = lambda _: "iris"
    position = [5.]
    moves = []

    def move(_device, value, _config):
        moves.append(value)
        position[0] = value

    c._move_single_axis = move
    c._measure_point = lambda _point, _config: (40. + position[0] - 5., 40.)
    c._read_beam_shape = shape
    DS_LaserPointing._measure_aperture_cycle(c, ("point1", "point3"), config())
    assert moves == [10., 5.]
    assert position[0] == 5.
    assert c._last_beam_shape["centering_aperture_error_px"] == 5.
    assert c._last_beam_shape["centering_error_px"] == 5.
    assert c._last_beam_shape["aperture_pair_checked"] is True


def test_verification_does_not_accept_missing_aperture_pair_evidence():
    c = object.__new__(DS_LaserPointing)
    c._raise_if_cancelled = lambda: None
    c._measure_aperture_cycle = lambda *_: None
    c._read_beam_shape = lambda: {**shape(), "aperture_pair_checked": False}
    with pytest.raises(RuntimeError, match="open/closed"):
        c._verify_centering_pair(("point1", "point3"), config())


def test_worker_reports_centering_and_ellipticity_separately():
    c = object.__new__(DS_LaserPointing)
    c.devices = {"camera": type("Camera", (), {"isgrabbing": True})()}
    c.ds_dict = {"Camera": "camera"}
    c._search_stop = Event()
    c._search_pause = Event()
    c._search_progress = {}
    c._search_history = []
    c._search_session_id = "offline"
    c._capture_alignment_state = lambda: {"actuators": {}, "optics": {}}
    c._raise_if_cancelled = lambda: None
    c._validate_camera_verified_roles = lambda *_: None
    c._point_stages = lambda _: [("sensitive", [
        ("near", ("point1", "point3")), ("far", ("point4", "point6"))])]
    c._optimise_group = lambda *_: {}
    calls, saved = [], []
    c._measure_aperture_cycle = lambda pair, _: calls.append(pair)
    c._read_beam_shape = shape
    c._store_pending_reference = saved.append
    c._accept_pending_alignment_reference = lambda _: 3
    c._record_alignment_event = lambda *_args, **_kwargs: None
    c._pause_active = False
    c.cgc = True
    c._automatic_search_worker(config())
    assert c._search_status == "finished"
    assert c._search_progress["centering_converged"] is True
    assert c._search_progress["ellipticity_passed"] is False
    assert len(calls) == 6
    assert len(saved[0]["verification"]) == 2
    assert all(v["measurement_repetitions"] == 3 for v in saved[0]["verification"])


def test_controller_retains_only_a_reconfirmed_candidate_not_cached_stage_minimum():
    c = object.__new__(DS_LaserPointing)
    c.pid_groups = {"near": ("point1", "point3")}
    c.groups = {"Actuators 1": ("x", "y")}
    c._search_stop = Event()
    c._search_history = []
    c._search_started_at = None
    c._search_stage_bests = {("sensitive", "near"): {"position": (99., 99.), "score": 0.}}
    c._raise_if_cancelled = lambda: None
    c._device_for_role = lambda role: role
    position = [0., 0.]
    c._fresh_position_and_state = lambda role: (position[0] if role == "x" else position[1], "ON")
    c._search_bounds = lambda *_: ((-1., 1.), (-1., 1.))
    c._move_pair = lambda _devices, target, _config: position.__setitem__(slice(None), target)
    c._measure_aperture_cycle = lambda *_: None
    c._read_beam_shape = lambda: shape(.2 if tuple(position) == (.5, 0.) else 2.)
    result = c._optimise_group("near", ("point1", "point3"), "sensitive", 1, .5, config(), {})
    assert result["best_position"] == [.5, 0.]
    assert result["quality"]["centering_passed"] is True
    assert result["quality"]["ellipticity_passed"] is False
    assert any(v["confirmed"] and v.get("confirmation", {}).get("fresh_confirmation", {}).get("accepted")
               for v in c._search_history)


def test_controller_cancellation_retains_last_confirmed_position():
    c = object.__new__(DS_LaserPointing)
    c.pid_groups = {"near": ("point1", "point3")}
    c.groups = {"Actuators 1": ("x", "y")}
    c._search_stop = Event()
    c._search_history = []
    c._search_started_at = None
    c._restore_on_cancel = False
    c._raise_if_cancelled = lambda: None
    c._device_for_role = lambda role: role
    position, count = [0., 0.], [0]
    c._fresh_position_and_state = lambda role: (position[0] if role == "x" else position[1], "ON")
    c._search_bounds = lambda *_: ((-1., 1.), (-1., 1.))
    c._move_pair = lambda _devices, target, _config: position.__setitem__(slice(None), target)

    def measure(*_):
        count[0] += 1
        if count[0] == 4:
            c._search_stop.set()

    c._measure_aperture_cycle = measure
    c._read_beam_shape = lambda: shape(2.)
    with pytest.raises(SearchCancelled):
        c._optimise_group("near", ("point1", "point3"), "sensitive", 1, .5, config(), {})
    assert position == [0., 0.]
    assert c._search_stop.is_set()


@pytest.mark.parametrize("frozen", [False, True])
def test_repeated_camera_transfer_cannot_supply_confirmation_frames(frozen):
    yy, xx = np.indices((81, 81), dtype=float)
    gaussian = 210 * np.exp(-.5 * (((xx - 40) / 9) ** 2 + ((yy - 40) / 12) ** 2))
    frames = []
    for value in (1, 1, 2, 3):
        frame = gaussian.copy()
        frame[0, 0] = value
        frames.append(frame)

    class Camera:
        width = height = 81
        center_gravity_threshold = 20
        isgrabbing = True
        reads = 0

        @property
        def image(self):
            index = 0 if frozen else min(self.reads, len(frames) - 1)
            self.reads += 1
            return frames[index]

    c = object.__new__(DS_LaserPointing)
    cam = Camera()
    c.ds_dict = {"Camera": "camera"}
    c.devices = {"camera": cam}
    c._active_point = "point3"
    c._raise_if_cancelled = lambda: None
    c._interruptible_sleep = lambda _: None
    settings = config(samples=3, invalid_frame_retries=1)
    if frozen:
        with pytest.raises(LaserNotVisible, match="duplicate camera frame"):
            c._measure_point("point3", settings)
    else:
        assert c._measure_point("point3", settings) == pytest.approx((40., 40.), abs=.1)
        assert cam.reads == 4
        assert len(c._alignment_frame_hashes) == 3
