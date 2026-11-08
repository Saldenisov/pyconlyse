"""Cases collected through test_automatic_search.py."""

from importlib import import_module

if __package__:
    from .test_automatic_search import (
        DS_LaserPointing,
        Enum,
        Event,
        LaserNotVisible,
        SearchCancelled,
        SimpleNamespace,
        pytest,
    )
else:
    from test_automatic_search import (
        DS_LaserPointing,
        Enum,
        Event,
        LaserNotVisible,
        SearchCancelled,
        SimpleNamespace,
        pytest,
    )


laser_pointing_module = import_module("DeviceServers.control.laser_pointing.DS_LaserPointing")


def test_failed_optical_probe_restores_last_visible_mount_position(monkeypatch):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"group1": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._search_history = []
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = {
        "ActuatorX1": "x",
        "ActuatorY1": "y",
    }.__getitem__
    controller._fresh_position_and_state = lambda device: (
        5.0 if device == "x" else 7.0,
        "ON",
    )
    controller._search_bounds = lambda _devices, _start, _radius: (
        (-30.0, 30.0),
        (-30.0, 30.0),
    )
    moves = []
    current_position = [5.0, 7.0]

    def move_pair(_devices, position, _config):
        current_position[:] = position
        moves.append(tuple(position))

    controller._move_pair = move_pair

    def measure(point_name, _config):
        if tuple(current_position) == (6.0, 7.0):
            raise RuntimeError("laser left the visible path")
        return (10.0, 10.0) if point_name == "point1" else (8.0, 10.0)

    controller._measure_point = measure
    controller._read_beam_shape = lambda: {
        "roundness_pct": 98.0,
        "roundness_error_pct": 2.0,
    }

    def failed_pattern_search(objective, **_kwargs):
        assert objective((5.0, 7.0)) == 2.0
        objective((6.0, 7.0))

    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search",
        failed_pattern_search,
    )
    config = {
        "radius": 30.0,
        "tolerance_px": 2.0,
        "roundness_tolerance_pct": 7.0,
        "max_evaluations": 16,
        "minimum_improvement_px": 0.1,
        "probe_repetitions": 3,
        "unchanged_response_tolerance_px": 0.25,
    }

    with pytest.raises(RuntimeError, match="laser left the visible path"):
        DS_LaserPointing._optimise_group(
            controller,
            "group1",
            ("point1", "point3"),
            "sensitive",
            1,
            2.0,
            config,
            {},
        )

    assert moves == [(5.0, 7.0), (6.0, 7.0), (5.0, 7.0)]

def test_invisible_directional_probe_is_rejected_without_aborting_search(
    monkeypatch,
):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"group1": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._search_history = []
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = {
        "ActuatorX1": "x",
        "ActuatorY1": "y",
    }.__getitem__
    controller._fresh_position_and_state = lambda device: (
        5.0 if device == "x" else 7.0,
        "ON",
    )
    controller._search_bounds = lambda *_args: ((-30.0, 30.0), (-30.0, 30.0))
    controller._search_stage_bests = {}
    moves = []
    position = [5.0, 7.0]

    def move_pair(_devices, target, _config):
        position[:] = target
        moves.append(tuple(target))

    controller._move_pair = move_pair

    def measure(_point_name, _config):
        if tuple(position) == (6.0, 7.0):
            raise LaserNotVisible("beam left the camera")
        return (10.0, 10.0)

    controller._measure_point = measure
    controller._read_beam_shape = lambda: {
        "roundness_pct": 98.0,
        "roundness_error_pct": 2.0,
        "contour_centre_drift_px": 0.0,
    }

    def search(objective, **_kwargs):
        assert objective((5.0, 7.0)) == 2.0
        assert objective((6.0, 7.0)) == 100.0
        assert tuple(position) == (5.0, 7.0)
        return SimpleNamespace(
            best_position=(5.0, 7.0),
            best_score=2.0,
            evaluations=2,
            reason="minimum_step",
        )

    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search",
        search,
    )
    config = {
        "radius": 30.0,
        "roundness_tolerance_pct": 7.0,
        "max_evaluations": 16,
        "minimum_improvement_px": 0.1,
        "probe_repetitions": 3,
        "unchanged_response_tolerance_px": 0.25,
    }

    result = DS_LaserPointing._optimise_group(
        controller,
        "group1",
        ("point1", "point3"),
        "sensitive",
        1,
        2.0,
        config,
        {},
    )

    assert result["best_position"] == [5.0, 7.0]
    assert controller._search_history[-1]["roundness_error_pct"] == 100.0
    assert controller._search_history[-1]["message"].startswith(
        "Beam disappeared; rejecting probe"
    )

def test_worse_probe_returns_to_last_good_actuator_position(monkeypatch):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"near": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._search_history = []
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = {
        "ActuatorX1": "x", "ActuatorY1": "y"
    }.__getitem__
    controller._fresh_position_and_state = lambda _device: (0.0, "ON")
    controller._search_bounds = lambda *_args: ((-2, 2), (-2, 2))
    moves = []
    movement_messages = []
    position = [0.0, 0.0]

    def move(_devices, target, _config):
        position[:] = target
        moves.append(tuple(target))
        movement_messages.append(
            controller._search_progress.get("message", "")
        )

    controller._move_pair = move
    measured_points = []
    controller._measure_point = lambda point, _config: (
        measured_points.append(point) or (40.0, 40.0)
    )
    scores = {(0.0, 0.0): 10.0, (1.0, 0.0): 20.0, (0.0, 1.0): 5.0}
    controller._read_beam_shape = lambda: {
        "roundness_error_pct": scores[tuple(position)],
        "roundness_pct": 100.0 - scores[tuple(position)],
        "contour_centre_drift_px": 0.0,
    }

    def fake_search(objective, **_kwargs):
        assert objective((0.0, 0.0)) == 10.0
        assert objective((1.0, 0.0)) == 20.0
        assert tuple(position) == (0.0, 0.0)
        assert objective((0.0, 1.0)) == 5.0
        return SimpleNamespace(
            best_position=(0.0, 1.0), best_score=5.0,
            evaluations=3, reason="tolerance",
        )

    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search", fake_search,
    )
    config = {
        "radius": 2.0, "roundness_tolerance_pct": 7.0,
        "max_evaluations": 3, "minimum_improvement_px": 0.1,
        "probe_repetitions": 1, "unchanged_response_tolerance_px": 0.25,
    }

    result = DS_LaserPointing._optimise_group(
        controller, "near", ("point1", "point3"), "sensitive", 1,
        1.0, config, {},
    )

    assert result["best_position"] == [0.0, 1.0]
    assert measured_points == ["point3", "point3", "point3"]
    assert moves[:4] == [
        (0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 1.0)
    ]
    assert movement_messages[1] == (
        "Moving near: ActuatorX1 to 1.000 (+1.000), "
        "ActuatorY1 to 0.000 (+0.000)"
    )

def test_noisier_fine_pass_retains_better_position_from_coarse_pass(monkeypatch):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"near": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._search_history = []
    controller._search_started_at = None
    controller._search_stage_bests = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = {
        "ActuatorX1": "x", "ActuatorY1": "y"
    }.__getitem__
    position = [0.0, 0.0]
    controller._fresh_position_and_state = lambda device: (
        position[0] if device == "x" else position[1], "ON"
    )
    controller._search_bounds = lambda *_args: ((-3, 3), (-3, 3))
    moves = []

    def move(_devices, target, _config):
        position[:] = target
        moves.append(tuple(target))

    controller._move_pair = move
    results = iter([
        SimpleNamespace(
            best_position=(1.0, 0.0), best_score=5.0,
            evaluations=5, reason="minimum_step",
        ),
        SimpleNamespace(
            best_position=(2.0, 0.0), best_score=8.0,
            evaluations=5, reason="minimum_step",
        ),
    ])
    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search",
        lambda *_args, **_kwargs: next(results),
    )
    config = {
        "radius": 3.0, "roundness_tolerance_pct": 7.0,
        "max_evaluations": 5, "minimum_improvement_px": 0.1,
        "probe_repetitions": 1, "unchanged_response_tolerance_px": 0.25,
    }

    coarse = DS_LaserPointing._optimise_group(
        controller, "near", ("point1", "point3"), "sensitive", 1,
        2.0, config, {},
    )
    fine = DS_LaserPointing._optimise_group(
        controller, "near", ("point1", "point3"), "sensitive", 1,
        1.0, config, {},
    )

    assert coarse["best_position"] == [1.0, 0.0]
    assert fine["best_position"] == [1.0, 0.0]
    assert fine["best_roundness_error_pct"] == 5.0
    assert moves[-1] == (1.0, 0.0)

def test_cancelled_search_does_not_issue_a_rollback_move(monkeypatch):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"group1": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._search_history = []
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = {
        "ActuatorX1": "x",
        "ActuatorY1": "y",
    }.__getitem__
    controller._fresh_position_and_state = lambda device: (
        5.0 if device == "x" else 7.0,
        "ON",
    )
    controller._search_bounds = lambda _devices, _start, _radius: (
        (-30.0, 30.0),
        (-30.0, 30.0),
    )
    moves = []
    controller._move_pair = (
        lambda _devices, position, _config: moves.append(tuple(position))
    )

    def cancelled_pattern_search(*_args, **_kwargs):
        raise SearchCancelled()

    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search",
        cancelled_pattern_search,
    )
    config = {
        "radius": 30.0,
        "tolerance_px": 2.0,
        "roundness_tolerance_pct": 7.0,
        "max_evaluations": 16,
        "minimum_improvement_px": 0.1,
        "probe_repetitions": 3,
        "unchanged_response_tolerance_px": 0.25,
    }

    with pytest.raises(SearchCancelled):
        DS_LaserPointing._optimise_group(
            controller,
            "group1",
            ("point1", "point3"),
            "sensitive",
            1,
            2.0,
            config,
            {},
        )

    assert moves == []

def test_plain_cancel_retains_last_measured_good_position(monkeypatch):
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {"group1": ("point1", "point3")}
    controller.groups = {"Actuators 1": ("ActuatorX1", "ActuatorY1")}
    controller._search_stop = Event()
    controller._restore_on_cancel = False
    controller._search_history = []
    controller._search_progress = {}
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._adaptive_search_model = {}
    controller._device_for_role = {
        "ActuatorX1": "x", "ActuatorY1": "y"
    }.__getitem__
    position = [0.0, 0.0]
    controller._fresh_position_and_state = lambda device: (
        position[0] if device == "x" else position[1], "ON"
    )
    controller._search_bounds = lambda *_args: ((-10, 10), (-10, 10))
    moves = []

    def move(_devices, target, _config):
        position[:] = target
        moves.append(tuple(target))

    controller._move_pair = move
    controller._measure_point = lambda _point, _config: (40.0, 40.0)
    controller._read_beam_shape = lambda: {
        "roundness_error_pct": 5.0,
        "roundness_pct": 95.0,
        "contour_centre_drift_px": 0.0,
    }

    def interrupted_search(objective, **_kwargs):
        assert objective((0.0, 0.0)) == 5.0
        # Represent a cancellation received after a command began but before
        # the new position obtained a valid camera measurement.
        position[:] = (4.0, -3.0)
        controller._search_stop.set()
        raise SearchCancelled()

    monkeypatch.setattr(
        laser_pointing_module,
        "bounded_pattern_search",
        interrupted_search,
    )
    config = DS_LaserPointing._normalise_search_config({
        "step_schedule": [2.0],
    })

    with pytest.raises(SearchCancelled):
        DS_LaserPointing._optimise_group(
            controller,
            "group1",
            ("point1", "point3"),
            "sensitive",
            1,
            2.0,
            config,
            {},
        )

    assert position == [0.0, 0.0]
    assert moves[-1] == (0.0, 0.0)
    assert controller._search_stop.is_set()

def test_parallel_pair_move_preserves_cancellation_signal():
    controller = object.__new__(DS_LaserPointing)
    controller._move_single_axis = lambda *_args: (_ for _ in ()).throw(
        SearchCancelled()
    )

    with pytest.raises(SearchCancelled):
        DS_LaserPointing._move_pair(
            controller, ("x", "y"), (1.0, 2.0), {}
        )

def test_measurement_retries_a_transient_invalid_camera_frame():
    import numpy as np

    class Camera:
        def __init__(self):
            self.frame_reads = 0
            self.isgrabbing = True
            self.width = 81
            self.height = 81
            self.center_gravity_threshold = 10

        @property
        def image(self):
            self.frame_reads += 1
            if self.frame_reads == 1:
                return None
            yy, xx = np.indices((81, 81), dtype=float)
            return 220 * np.exp(-0.5 * (((xx - 34) / 7) ** 2
                                           + ((yy - 42) / 7) ** 2))

    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "camera"}
    controller.devices = {"camera": Camera()}
    controller._apply_point = lambda _point, _config: None
    controller._raise_if_cancelled = lambda: None
    waits = []
    controller._interruptible_sleep = waits.append
    config = {
        "samples": 1,
        "invalid_frame_retries": 1,
        "camera_frame_wait_s": 0.25,
        "sample_interval_s": 0.2,
    }

    assert DS_LaserPointing._measure_point(
        controller, "point6", config
    ) == pytest.approx((34.0, 42.0), abs=0.25)
    assert controller._read_beam_shape()["contour_count"] >= 3
    assert waits == [0.25, 0.25]

def test_aperture_cycle_sweeps_repeats_and_finishes_closed():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point1": {"CrimpingDiaphragm1": 10.0},
        "point3": {"CrimpingDiaphragm1": 5.0},
    }
    controller._active_point = "point3"
    controller._search_stop = Event()
    controller._search_progress = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    aperture_position = [5.0]
    moves = []

    def move(_device, target, _config):
        aperture_position[0] = float(target)
        moves.append(float(target))

    def measure(_point, _config):
        displacement = 0.2 * (aperture_position[0] - 5.0)
        return 40.0 + displacement, 40.0

    def shape():
        return {
            "roundness_error_pct": 4.0,
            "roundness_pct": 96.0,
            "shape_centroid": [40.0, 40.0],
            "sigma_major_px": 10.0,
        }

    controller._move_single_axis = move
    controller._measure_point = measure
    controller._read_beam_shape = shape
    config = DS_LaserPointing._normalise_search_config({
        "aperture_sweep_positions": 3,
        "aperture_cycle_count": 2,
        "aperture_samples": 1,
    })

    centroid = DS_LaserPointing._measure_aperture_cycle(
        controller, ("point1", "point3"), config
    )

    assert moves == [7.5, 10.0, 5.0, 10.0, 5.0, 10.0, 5.0]
    assert aperture_position == [5.0]
    assert centroid[0] == pytest.approx(40.25)
    assert controller._last_beam_shape["aperture_measurement_count"] == 8
    assert controller._last_beam_shape["aperture_centre_drift_px"] > 0
    assert controller._last_beam_shape["roundness_error_pct"] > 4.0
    assert controller._search_progress["phase"] == "aperture_cycle_measured"

def test_failed_aperture_measurement_restores_closed_position():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point4": {"CrimpingDiaphragm2": 15.0},
        "point6": {"CrimpingDiaphragm2": 5.0},
    }
    controller._active_point = "point6"
    controller._search_stop = Event()
    controller._search_progress = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    aperture_position = [5.0]
    moves = []

    def move(_device, target, _config):
        aperture_position[0] = float(target)
        moves.append(float(target))

    def measure(_point, _config):
        if aperture_position[0] > 5.0:
            raise LaserNotVisible("beam disappeared")
        return 40.0, 40.0

    controller._move_single_axis = move
    controller._measure_point = measure
    controller._read_beam_shape = lambda: {
        "roundness_error_pct": 4.0,
        "roundness_pct": 96.0,
        "shape_centroid": [40.0, 40.0],
        "sigma_major_px": 10.0,
    }
    config = DS_LaserPointing._normalise_search_config({
        "aperture_sweep_positions": 3,
    })

    with pytest.raises(LaserNotVisible, match="beam disappeared"):
        DS_LaserPointing._measure_aperture_cycle(
            controller, ("point4", "point6"), config
        )

    assert moves == [10.0, 5.0]
    assert aperture_position == [5.0]
    assert controller._active_point == "point6"

def test_measurement_discards_a_beamless_pulsed_laser_frame():
    import numpy as np

    class Camera:
        def __init__(self):
            self.frame_reads = 0
            self.isgrabbing = True
            self.width = 81
            self.height = 81
            self.center_gravity_threshold = 10

        @property
        def image(self):
            self.frame_reads += 1
            if self.frame_reads == 1:
                return np.zeros((81, 81), dtype=float)
            yy, xx = np.indices((81, 81), dtype=float)
            return 220 * np.exp(
                -0.5 * (((xx - 34) / 7) ** 2 + ((yy - 42) / 7) ** 2)
            )

    camera = Camera()
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "camera"}
    controller.devices = {"camera": camera}
    controller._active_point = "point6"
    controller._raise_if_cancelled = lambda: None
    waits = []
    controller._interruptible_sleep = waits.append
    config = {
        "samples": 1,
        "invalid_frame_retries": 1,
        "camera_frame_wait_s": 0.25,
        "sample_interval_s": 0.2,
    }

    assert DS_LaserPointing._measure_point(
        controller, "point6", config
    ) == pytest.approx((34.0, 42.0), abs=0.25)
    assert camera.frame_reads == 2
    assert waits == [0.25, 0.25]

def test_camera_profile_settings_bypass_stale_taurus_cache():
    class Source(Enum):
        DEV = "direct"
        CACHE_DEV = "cached"

    class Proxy:
        def __init__(self):
            self.source = Source.CACHE_DEV
            self.sources = []

        def get_source(self):
            return self.source

        def set_source(self, source):
            self.source = source
            self.sources.append(source)

        def read_attribute(self, name):
            assert self.source is Source.DEV
            values = {
                "center_gravity_threshold": 50,
                "width": 400,
                "height": 400,
                "isgrabbing": True,
            }
            return SimpleNamespace(value=values[name])

    class Camera:
        center_gravity_threshold = 120
        width = 300
        height = 300
        isgrabbing = False

        def __init__(self):
            self.proxy = Proxy()

        def getDeviceProxy(self):
            return self.proxy

    camera = Camera()

    values = DS_LaserPointing._fresh_camera_values(
        camera,
        "center_gravity_threshold",
        "width",
        "height",
        "isgrabbing",
    )

    assert values == {
        "center_gravity_threshold": 50,
        "width": 400,
        "height": 400,
        "isgrabbing": True,
    }
    assert camera.proxy.sources == [Source.DEV, Source.CACHE_DEV]
