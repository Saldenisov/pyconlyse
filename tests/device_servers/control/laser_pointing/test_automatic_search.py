from enum import Enum
from math import hypot
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from DeviceServers.control.laser_pointing.automatic_search import (
    SearchParameters,
    bounded_pattern_search,
    optical_point_group,
)
from DeviceServers.control.laser_pointing.DS_LaserPointing import (
    DS_LaserPointing,
    LaserNotVisible,
    SearchCancelled,
)


@pytest.mark.parametrize(
    ("point_name", "expected_group"),
    [
        ("point1", 1),
        ("POINT3", 1),
        ("point4", 2),
        ("point6", 2),
        ("working", 0),
        ("point7", 0),
        ("", 0),
    ],
)
def test_optical_point_group_enforces_diaphragm_mount_pair(point_name, expected_group):
    assert optical_point_group(point_name) == expected_group


class _InitializableAxis:
    def __init__(self, name, events, succeeds=True):
        self.name = name
        self.events = events
        self.succeeds = succeeds
        self.hardware_connection_state = "CONNECTED"
        self.initialization_state = "NOT_REQUESTED"
        self.hardware_lifecycle_status = "passively discovered"
        self.state = "STANDBY"

    def turn_on(self):
        self.events.append(self.name)
        if not self.succeeds:
            self.hardware_connection_state = "DISCONNECTED"
            self.initialization_state = "FAILED"
            self.hardware_lifecycle_status = "USB unavailable"
            self.state = "FAULT"
            return
        self.hardware_connection_state = "READY"
        self.initialization_state = "SUCCEEDED"
        self.hardware_lifecycle_status = "axis ready"
        self.state = "ON"


def _pair_initialization_controller(point="point3", second_succeeds=True):
    controller = object.__new__(DS_LaserPointing)
    controller._search_lock = Lock()
    controller._search_thread = None
    controller._active_point = point
    controller._actuator_initialization_status = {}
    events = []
    axes = {
        "ActuatorX1": _InitializableAxis("ActuatorX1", events),
        "ActuatorY1": _InitializableAxis(
            "ActuatorY1", events, succeeds=second_succeeds
        ),
    }
    controller._actuator_group_entry = lambda group: (
        "Actuators 1", ("ActuatorX1", "ActuatorY1")
    )
    controller._device_for_role = axes.__getitem__
    return controller, events


def test_active_pair_initialization_is_sequential_and_point_interlocked():
    controller, events = _pair_initialization_controller()

    assert DS_LaserPointing.initialize_active_pair(controller) == 0
    assert events == ["ActuatorX1", "ActuatorY1"]
    assert controller._actuator_initialization_status["phase"] == "complete"

    controller._active_point = ""
    with pytest.raises(RuntimeError, match="select optical point"):
        DS_LaserPointing.initialize_active_pair(controller)


def test_active_pair_initialization_stops_after_first_axis_failure():
    controller, events = _pair_initialization_controller(second_succeeds=False)

    with pytest.raises(RuntimeError, match="ActuatorY1 did not initialise"):
        DS_LaserPointing.initialize_active_pair(controller)

    assert events == ["ActuatorX1", "ActuatorY1"]
    assert controller._actuator_initialization_status["phase"] == "failed"
    assert controller._actuator_initialization_status["completed"] == ["ActuatorX1"]


def test_point_application_returns_immediately_and_locks_mounts_until_readback():
    controller = object.__new__(DS_LaserPointing)
    controller._search_lock = Lock()
    controller._search_stop = Event()
    controller._search_thread = None
    controller._point_application_thread = None
    controller._active_point = "point3"
    controller._actuator_initialization_status = {}
    controller._search_progress = {}
    controller._search_config = {}
    controller.controller_rules = {"point1": {"Optic": 1.0}}
    entered = Event()
    release = Event()

    def apply_point(point_name, _config):
        entered.set()
        release.wait(1)
        controller._active_point = point_name

    controller._apply_point = apply_point

    assert DS_LaserPointing.apply_controller_point(controller, "point1") == 0
    assert entered.wait(1)
    assert controller._active_point == ""
    assert controller._search_progress["phase"] == "manual_point"
    assert controller._actuator_initialization_status["group"] == 0

    release.set()
    controller._point_application_thread.join(1)
    assert controller._active_point == "point1"
    assert controller._search_progress["phase"] == "manual_point_complete"


def test_point_preset_devices_are_applied_sequentially():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point1": {"First": 1.0, "Second": 2.0, "Third": 3.0}
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    events = []
    controller._move_single_axis = (
        lambda device, target, _config: events.append((device, target))
    )

    DS_LaserPointing._apply_point(controller, "point1", {})

    assert events == [("First", 1.0), ("Second", 2.0), ("Third", 3.0)]
    assert controller._active_point == "point1"


def test_numbered_point_excludes_flipper_and_moves_dl():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point1": {
            "Shutter1": -1.0,
            "HalfWavePlate1": 20.5,
            "TranslationStage1": (3, -700.0),
            "CrimpingDiaphragm1": 40.0,
            "CrimpingDiaphragm2": 60.0,
        }
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    events = []

    def move(device, target, _config):
        events.append((device, target))
        if device == "Shutter1":
            pytest.fail("flippers must not be part of point application")

    controller._move_single_axis = move
    controller._move_multi_axis = (
        lambda device, target, _config: events.append((device, target))
    )

    DS_LaserPointing._apply_point(controller, "point1", {})

    assert events == [
        ("CrimpingDiaphragm1", 40.0),
        ("CrimpingDiaphragm2", 60.0),
        ("TranslationStage1", (3, -700.0)),
        ("HalfWavePlate1", 20.5),
    ]
    assert controller._active_point == "point1"


def test_numbered_point_attempts_all_diaphragms_before_reporting_failure():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point3": {
            "CrimpingDiaphragm1": 10.0,
            "CrimpingDiaphragm2": 60.0,
        }
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    events = []

    def move(device, target, _config):
        events.append((device, target))
        if device == "CrimpingDiaphragm1":
            raise RuntimeError("jammed")

    controller._move_single_axis = move

    with pytest.raises(RuntimeError, match="after attempting all diaphragms"):
        DS_LaserPointing._apply_point(controller, "point3", {})

    assert events == [
        ("CrimpingDiaphragm1", 10.0),
        ("CrimpingDiaphragm2", 60.0),
    ]


def test_working_point_forces_every_configured_diaphragm_to_100_first():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "MainLaserDiaphragm1": "main",
        "CrimpingDiaphragm1": "iris-1",
        "CrimpingDiaphragm2": "iris-2",
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
        "HalfWavePlate1": "wave-plate",
    }
    controller.controller_rules = {
        "working": {
            "MainLaserDiaphragm1": 75.0,
            "CrimpingDiaphragm1": 90.0,
            "HalfWavePlate1": 20.5,
        }
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    events = []
    controller._move_single_axis = (
        lambda device, target, _config: events.append((device, target))
    )

    DS_LaserPointing._apply_point(controller, "working", {})

    assert events == [
        ("MainLaserDiaphragm1", 100.0),
        ("CrimpingDiaphragm1", 100.0),
        ("CrimpingDiaphragm2", 100.0),
        ("HalfWavePlate1", 20.5),
    ]
    assert controller._active_point == "working"


def test_working_point_attempts_all_diaphragms_when_one_fails():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "CrimpingDiaphragm1": "iris-1",
        "CrimpingDiaphragm2": "iris-2",
    }
    controller.controller_rules = {
        "working": {
            "CrimpingDiaphragm1": 100.0,
            "CrimpingDiaphragm2": 100.0,
        }
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller._device_for_role = lambda role: role
    events = []

    def move(device, target, _config):
        events.append((device, target))
        if device == "CrimpingDiaphragm1":
            raise RuntimeError("jammed")

    controller._move_single_axis = move

    with pytest.raises(RuntimeError, match="after attempting all"):
        DS_LaserPointing._apply_point(controller, "working", {})

    assert events == [
        ("CrimpingDiaphragm1", 100.0),
        ("CrimpingDiaphragm2", 100.0),
    ]
    assert controller._active_point == ""


def test_working_point_commands_only_the_registered_camera_route():
    class Flipper:
        def __init__(self):
            self.commanded_flipper_state = "UNKNOWN"
            self.commands = []

        def move_axis_abs(self, target):
            self.commands.append(target)
            self.commanded_flipper_state = (
                "UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR"
            )

    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
    }
    controller.controller_rules = {"working": {"Shutter1": -1.0}}
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    flippers = {"Shutter1": Flipper(), "Shutter2": Flipper()}
    controller._device_for_role = flippers.__getitem__

    controller._move_single_axis = lambda *_args: None

    DS_LaserPointing._apply_point(controller, "working", {})

    assert flippers["Shutter1"].commands == [-1.0]
    assert flippers["Shutter2"].commands == []
    assert controller._active_point == "working"


@pytest.mark.parametrize(
    "camera_number, route",
    [
        (1, {"Shutter1": -1.0}),
        (2, {"Shutter1": 1.0, "Shutter2": -1.0}),
    ],
)
def test_all_points_preserve_the_registered_camera_route(camera_number, route):
    class Flipper:
        def __init__(self):
            self.commanded_flipper_state = "UNKNOWN"
            self.position = 0.0  # The physical device always reports zero.
            self.commands = []

        def move_axis_abs(self, target):
            self.commands.append(target)
            self.commanded_flipper_state = (
                "UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR"
            )

    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "Camera": f"manip/V0/Cam{camera_number}_V0",
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
    }
    controller.controller_rules = {
        **{f"point{number}": dict(route) for number in range(1, 7)},
        "working": dict(route),
    }
    flippers = {"Shutter1": Flipper(), "Shutter2": Flipper()}
    controller._device_for_role = flippers.__getitem__
    controller._raise_if_cancelled = lambda: None
    controller._active_point = ""
    controller._actuator_initialization_status = {}

    for number in range(1, 7):
        DS_LaserPointing._apply_point(controller, f"point{number}", {})
    DS_LaserPointing._apply_point(controller, "working", {})

    for role, target in route.items():
        assert flippers[role].commands == [target]
        assert flippers[role].position == 0.0
    expected_states = {
        role: ("UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR")
        for role, target in route.items()
    }
    assert {
        role: flippers[role].commanded_flipper_state for role in route
    } == expected_states
    for role in set(flippers) - set(route):
        assert flippers[role].commands == []


def test_cam2_routes_flippers_before_applying_working_optics():
    events = []

    class Flipper:
        def __init__(self, role):
            self.role = role
            self.commanded_flipper_state = "UNKNOWN"

        def move_axis_abs(self, target):
            events.append((self.role, target))
            self.commanded_flipper_state = (
                "UP_BLOCKED" if target == -1.0 else "DOWN_CLEAR"
            )

    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "Camera": "manip/V0/Cam2_V0",
        "MainLaserDiaphragm1": "main-1",
        "MainLaserDiaphragm2": "main-2",
        "CrimpingDiaphragm1": "iris-1",
        "CrimpingDiaphragm2": "iris-2",
        "HalfWavePlate1": "wave-plate",
        "TranslationStage1": ("dl", [3]),
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
    }
    controller.controller_rules = {
        "working": {
            "Shutter1": 1.0,
            "Shutter2": -1.0,
            "MainLaserDiaphragm1": 100.0,
            "MainLaserDiaphragm2": 100.0,
            "CrimpingDiaphragm1": 100.0,
            "CrimpingDiaphragm2": 100.0,
            "HalfWavePlate1": 20.5,
            "TranslationStage1": (3, 0.0),
        }
    }
    flippers = {role: Flipper(role) for role in ("Shutter1", "Shutter2")}
    controller._device_for_role = lambda role: flippers.get(role, role)
    controller._move_single_axis = (
        lambda device, target, _config: events.append((device, target))
    )
    controller._move_multi_axis = (
        lambda device, target, _config: events.append((device, target))
    )
    controller._raise_if_cancelled = lambda: None
    controller._active_point = "point6"
    controller._actuator_initialization_status = {}

    DS_LaserPointing._apply_point(controller, "working", {})

    assert events == [
        ("Shutter1", 1.0),
        ("Shutter2", -1.0),
        ("MainLaserDiaphragm1", 100.0),
        ("MainLaserDiaphragm2", 100.0),
        ("CrimpingDiaphragm1", 100.0),
        ("CrimpingDiaphragm2", 100.0),
        ("TranslationStage1", (3, 0.0)),
        ("HalfWavePlate1", 20.5),
    ]
    assert controller._active_point == "working"


def test_cam2_working_does_not_lower_either_flipper_if_optics_fail():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "Camera": "manip/V0/Cam2_V0",
        "CrimpingDiaphragm1": "iris-1",
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
    }
    controller.controller_rules = {"working": {"CrimpingDiaphragm1": 100.0}}
    controller._device_for_role = lambda role: role
    controller._move_single_axis = (
        lambda _device, _target, _config: (_ for _ in ()).throw(
            RuntimeError("diaphragm jammed")
        )
    )
    controller._raise_if_cancelled = lambda: None
    controller._active_point = "point6"

    with pytest.raises(RuntimeError, match="diaphragm jammed"):
        DS_LaserPointing._apply_point(controller, "working", {})
    assert controller._active_point == "point6"


def test_numbered_point_not_published_if_flipper_command_did_not_complete():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "manip/V0/Cam1_V0", "Shutter1": "shutter-1"}
    controller.controller_rules = {"point3": {"Shutter1": -1.0}}
    controller._raise_if_cancelled = lambda: None
    controller._active_point = "working"
    controller._device_for_role = lambda _role: SimpleNamespace(
        commanded_flipper_state="UNKNOWN", move_axis_abs=lambda _target: None
    )

    with pytest.raises(RuntimeError, match="commanded state is UNKNOWN"):
        DS_LaserPointing._apply_point(controller, "point3", {})
    assert controller._active_point == "working"


def test_multi_axis_point_move_uses_owis_array_command():
    class Owis:
        def __init__(self):
            self.commands = []
            self.position = -700.0

        def move_axis(self, command):
            self.commands.append(command)
            return "0"

        @staticmethod
        def get_status_axis(_axis):
            return 0

        def read_position_axis(self, _axis):
            return self.position

    controller = object.__new__(DS_LaserPointing)
    controller._raise_if_cancelled = lambda: None
    controller._interruptible_sleep = lambda _delay: None
    owis = Owis()

    DS_LaserPointing._move_multi_axis(
        controller,
        owis,
        (3, -700.0),
        {
            "motion_timeout_s": 1.0,
            "motion_poll_s": 0.01,
            "position_tolerance": 0.05,
            "position_stable_reads": 1,
        },
    )

    assert owis.commands == [[3.0, -700.0]]


def test_camera_verified_static_shutter_is_left_untouched_when_laser_is_visible():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "point1": {"Shutter1": -1.0, "Diaphragm1": 40.0}
    }
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller.info = lambda _message: None
    events = []
    controller._device_for_role = lambda role: role
    controller._move_single_axis = (
        lambda device, target, _config: events.append((device, target))
    )

    DS_LaserPointing._apply_point(
        controller,
        "point1",
        {
            "camera_verified_roles": ["Shutter1"],
            "_camera_verified_roles_validated": True,
        },
    )

    assert events == [("Diaphragm1", 40.0)]
    assert controller._active_point == "point1"


def test_manual_point_application_excludes_flipper_without_special_config():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {"point1": {"Shutter1": -1.0}}
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None
    controller.info = lambda _message: None
    events = []
    controller._device_for_role = lambda role: role
    controller._move_single_axis = (
        lambda device, target, _config: events.append((device, target))
    )

    DS_LaserPointing._apply_point(
        controller,
        "point1",
        {"camera_verified_roles": ["Shutter1"]},
    )

    assert events == []


def test_first_pair_staged_run_uses_points_1_2_and_3_only():
    controller = object.__new__(DS_LaserPointing)
    controller.pid_groups = {
        "group1": ("point1", "point3"),
        "group2": ("point4", "point6"),
    }
    controller.controller_rules = {
        f"point{number}": {} for number in range(1, 7)
    }
    config = dict(DS_LaserPointing._normalise_search_config({
        "mode": "staged",
        "groups": ["group1"],
    }))

    assert DS_LaserPointing._point_stages(controller, config) == [
        ("medium", [("group1", ("point1", "point2"))]),
        ("sensitive", [("group1", ("point1", "point3"))]),
    ]


def test_camera_verified_role_must_be_static_across_the_run():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Shutter1": "manip/V0/s1"}
    controller.controller_rules = {
        "point1": {"Shutter1": -1.0},
        "point2": {"Shutter1": 1.0},
    }
    config = {"camera_verified_roles": ["Shutter1"], "restore_point": ""}
    stages = [("medium", [("group1", ("point1", "point2"))])]

    with pytest.raises(ValueError, match="changes target"):
        DS_LaserPointing._validate_camera_verified_roles(
            controller, config, stages
        )


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

    monkeypatch.setitem(
        DS_LaserPointing._optimise_group.__globals__,
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

    monkeypatch.setitem(
        DS_LaserPointing._optimise_group.__globals__,
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
        "Rejected invisible probe"
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
    position = [0.0, 0.0]

    def move(_devices, target, _config):
        position[:] = target
        moves.append(tuple(target))

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

    monkeypatch.setitem(
        DS_LaserPointing._optimise_group.__globals__,
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
    monkeypatch.setitem(
        DS_LaserPointing._optimise_group.__globals__,
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

    monkeypatch.setitem(
        DS_LaserPointing._optimise_group.__globals__,
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


def test_automatic_worker_revisits_both_points_before_declaring_convergence():
    controller = object.__new__(DS_LaserPointing)
    controller.devices = {"camera": type("Camera", (), {"isgrabbing": True})()}
    controller.ds_dict = {"Camera": "camera"}
    controller.pid_groups = {
        "near": ("point1", "point3"),
        "far": ("point4", "point6"),
    }
    controller._search_stop = Event()
    controller._search_progress = {}
    controller._search_history = []
    controller._search_status = "running"
    controller._search_started_at = None
    controller._raise_if_cancelled = lambda: None
    controller._validate_camera_verified_roles = lambda *_args: None
    controller._point_stages = lambda _config: [("sensitive", [
        ("near", ("point1", "point3")),
        ("far", ("point4", "point6")),
    ])]
    calls = []
    current_point = [None]
    pass_number = [0]

    def optimise(group, _pair, _stage, _cycle, step, _config, _origins):
        calls.append(("optimise", group, step))
        if group == "far":
            pass_number[0] += 1
        return {"best_roundness_error_pct": 1.0}

    def measure(point, _config):
        current_point[0] = point
        calls.append(("measure", point))
        return (20.0, 20.0)

    controller._optimise_group = optimise
    controller._measure_point = measure
    controller._read_beam_shape = lambda: {
        "roundness_error_pct": (
            9.0 if pass_number[0] == 1 and current_point[0] == "point3"
            else 2.0
        )
    }
    config = {
        "step_schedule": [2.0, 1.0],
        "max_cycles": 1,
        "roundness_tolerance_pct": 7.0,
        "restore_point": "",
    }

    DS_LaserPointing._automatic_search_worker(controller, config)

    assert controller._search_status == "completed"
    assert [(item["point"], item["roundness_error_pct"])
            for item in controller._search_progress["verification"]] == [
        ("point3", 2.0), ("point6", 2.0)
    ]
    assert calls[:4] == [
        ("optimise", "near", 2.0), ("optimise", "far", 2.0),
        ("measure", "point3"), ("measure", "point6"),
    ]
    assert ("optimise", "near", 1.0) in calls


def test_stopped_axis_readback_mismatch_fails_without_long_polling():
    class Axis:
        position = 0.0
        state = "ON"

        @staticmethod
        def move_axis_abs(_target):
            return None

    controller = object.__new__(DS_LaserPointing)
    controller._raise_if_cancelled = lambda: None
    controller._interruptible_sleep = lambda _delay: pytest.fail(
        "stopped mismatch must not be polled until the long motion timeout"
    )
    config = {
        "motion_timeout_s": 180.0,
        "motion_poll_s": 0.2,
        "position_tolerance": 0.05,
    }

    with pytest.raises(RuntimeError, match="stopped at 0.0, expected -1.0"):
        DS_LaserPointing._move_single_axis(controller, Axis(), -1.0, config)


def test_timed_out_blocking_move_is_accepted_after_direct_target_readback():
    class Axis:
        position = 10.0
        state = "ON"

        @staticmethod
        def move_axis_abs(_target):
            raise RuntimeError("API_DeviceTimedOut: Timeout (3000 mS) exceeded")

    controller = object.__new__(DS_LaserPointing)
    controller._raise_if_cancelled = lambda: None
    controller._interruptible_sleep = lambda _delay: pytest.fail(
        "target readback is already available"
    )

    DS_LaserPointing._move_single_axis(
        controller,
        Axis(),
        10.0,
        {
            "motion_timeout_s": 10.0,
            "motion_poll_s": 0.2,
            "position_tolerance": 0.05,
        },
    )


def test_non_timeout_move_exception_is_not_hidden():
    class Axis:
        @staticmethod
        def move_axis_abs(_target):
            raise RuntimeError("controller rejected target")

    controller = object.__new__(DS_LaserPointing)

    with pytest.raises(RuntimeError, match="controller rejected target"):
        DS_LaserPointing._move_single_axis(
            controller,
            Axis(),
            10.0,
            {
                "motion_timeout_s": 10.0,
                "motion_poll_s": 0.2,
                "position_tolerance": 0.05,
            },
        )


def test_move_verification_bypasses_stale_taurus_position_cache():
    class Source(Enum):
        DEV = "DEV"
        CACHE_DEV = "CACHE_DEV"

    class Attribute:
        value = 40.0

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
            assert name == "position"
            assert self.source == Source.DEV
            return Attribute()

        def state(self):
            assert self.source == Source.DEV
            return "ON"

    class Axis:
        position = 100.0
        state = "ON"

        def __init__(self):
            self.proxy = Proxy()

        @staticmethod
        def move_axis_abs(_target):
            return None

        def getDeviceProxy(self):
            return self.proxy

    controller = object.__new__(DS_LaserPointing)
    controller._raise_if_cancelled = lambda: None
    controller._interruptible_sleep = lambda _delay: pytest.fail(
        "fresh hardware readback already reached the target"
    )
    axis = Axis()

    DS_LaserPointing._move_single_axis(
        controller,
        axis,
        40.0,
        {
            "motion_timeout_s": 180.0,
            "motion_poll_s": 0.2,
            "position_tolerance": 0.05,
        },
    )

    assert axis.proxy.sources == [Source.DEV, Source.CACHE_DEV]


def test_working_point_accepts_mechanical_fully_open_diaphragm_stop():
    controller = object.__new__(DS_LaserPointing)
    controller.controller_rules = {
        "working": {"CrimpingDiaphragm1": 100.0}
    }
    controller.ds_dict = {"CrimpingDiaphragm1": "iris"}
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._raise_if_cancelled = lambda: None

    class Diaphragm:
        position = 99.031
        state = "ON"

        @staticmethod
        def move_axis_abs(_target):
            return None

    controller._device_for_role = lambda _role: Diaphragm()
    controller._interruptible_sleep = lambda _delay: pytest.fail(
        "99-100% is already the mechanical fully-open range"
    )

    DS_LaserPointing._apply_point(
        controller,
        "working",
        {
            "motion_timeout_s": 1.0,
            "motion_poll_s": 0.01,
            "position_tolerance": 0.05,
        },
    )

    assert controller._active_point == "working"


def test_manual_point_selection_unlocks_pair_without_moving_optical_hardware():
    controller = object.__new__(DS_LaserPointing)
    controller._search_lock = Lock()
    controller._search_thread = None
    controller._point_application_thread = None
    controller.controller_rules = {"point1": {"CrimpingDiaphragm1": 40.0}}
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._search_progress = {}
    controller._device_for_role = lambda _role: pytest.fail(
        "manual selection must not access optical hardware"
    )

    result = DS_LaserPointing.select_manual_point(controller, "point1")

    assert result == 0
    assert controller._active_point == "point1"
    assert controller._actuator_initialization_status["group"] == 1
    assert controller._search_progress["phase"] == "manual_point_selected"


def test_pattern_search_converges_without_assuming_linear_response():
    def objective(position):
        x, y = position
        # Cross terms and a small ripple mimic coupled, non-linear optics.
        return hypot(x + 0.2 * y - 2.6, y + 0.1 * x + 1.4) + 0.02 * abs(x * y)

    result = bounded_pattern_search(
        objective,
        start=(0.0, 0.0),
        bounds=((-8.0, 8.0), (-8.0, 8.0)),
        parameters=SearchParameters(
            initial_step=2.0,
            minimum_step=0.125,
            tolerance_px=0.35,
            max_evaluations=80,
        ),
    )

    assert result.converged
    assert result.best_score <= 0.35
    assert result.evaluations <= 80


def test_pattern_search_never_proposes_outside_bounds():
    observed = []

    def objective(position):
        observed.append(position)
        return hypot(position[0] - 100.0, position[1] + 100.0)

    result = bounded_pattern_search(
        objective,
        start=(9.5, -9.5),
        bounds=((8.0, 10.0), (-10.0, -8.0)),
        parameters=SearchParameters(
            initial_step=5.0,
            minimum_step=0.25,
            tolerance_px=0.0,
            max_evaluations=20,
        ),
    )

    assert result.evaluations == len(observed)
    assert all(8.0 <= x <= 10.0 and -10.0 <= y <= -8.0 for x, y in observed)


def test_pattern_search_honours_cancellation_before_moving():
    calls = []

    result = bounded_pattern_search(
        lambda position: calls.append(position) or 1.0,
        start=(4.0, 5.0),
        bounds=((0.0, 10.0), (0.0, 10.0)),
        cancelled=lambda: True,
    )

    assert calls == []
    assert result.reason == "cancelled"
    assert result.evaluations == 0
    assert result.best_position == (4.0, 5.0)


def test_repeated_directional_probe_crosses_mount_stiction():
    observed = []

    def objective(position):
        observed.append(position)
        x, y = position
        # The optical mount does not respond to the first +10 motor movement;
        # the second addition releases it and produces an optical change.
        optical_x = 0.0 if abs(x) < 15.0 else x
        return hypot(optical_x - 20.0, y)

    result = bounded_pattern_search(
        objective,
        start=(0.0, 0.0),
        bounds=((-30.0, 30.0), (-30.0, 30.0)),
        parameters=SearchParameters(
            initial_step=10.0,
            minimum_step=10.0,
            tolerance_px=0.1,
            max_evaluations=12,
            step_schedule=(10.0,),
            probe_repetitions=3,
            unchanged_response_tolerance_px=0.1,
        ),
    )

    assert (10.0, 0.0) in observed
    assert (20.0, 0.0) in observed
    assert result.converged
    assert result.best_position == (20.0, 0.0)


def test_optical_signature_prevents_false_stiction_from_equal_scores():
    observed = []
    signature = [5.0, 0.0]

    def objective(position):
        observed.append(position)
        if position == (0.0, 0.0):
            signature[:] = [5.0, 0.0]
        elif position == (10.0, 0.0):
            # Same scalar error, but a clearly changed optical centroid vector.
            signature[:] = [0.0, 5.0]
        else:
            signature[:] = [position[0], position[1]]
        return hypot(*signature)

    bounded_pattern_search(
        objective,
        start=(0.0, 0.0),
        bounds=((-30.0, 30.0), (-30.0, 30.0)),
        parameters=SearchParameters(
            initial_step=10.0,
            minimum_step=10.0,
            tolerance_px=0.0,
            max_evaluations=8,
            step_schedule=(10.0,),
            probe_repetitions=3,
            unchanged_response_tolerance_px=0.25,
        ),
        response_signature=lambda: tuple(signature),
    )

    assert (10.0, 0.0) in observed
    assert (20.0, 0.0) not in observed


@pytest.mark.parametrize(
    "parameters",
    [
        SearchParameters(initial_step=0.0),
        SearchParameters(initial_step=1.0, minimum_step=2.0),
        SearchParameters(max_evaluations=0),
        SearchParameters(step_schedule=(10.0, 6.0, 6.0)),
        SearchParameters(probe_repetitions=0),
    ],
)
def test_invalid_search_parameters_are_rejected(parameters):
    with pytest.raises(ValueError):
        bounded_pattern_search(
            lambda _position: 0.0,
            start=(0.0, 0.0),
            bounds=((-1.0, 1.0), (-1.0, 1.0)),
            parameters=parameters,
        )
