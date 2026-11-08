import json
from enum import Enum
from math import hypot
from threading import Event, Lock, Thread
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


def test_working_point_sets_waveplate_then_forces_every_diaphragm_open():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "MainLaserDiaphragm1": "main",
        "CrimpingDiaphragm1": "iris-1",
        "CrimpingDiaphragm2": "iris-2",
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
        ("HalfWavePlate1", 20.5),
        ("MainLaserDiaphragm1", 100.0),
        ("CrimpingDiaphragm1", 100.0),
        ("CrimpingDiaphragm2", 100.0),
    ]
    assert controller._active_point == "working"


def test_effective_working_rule_exposes_open_diaphragms_and_down_shutters():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "MainLaserDiaphragm1": "main",
        "CrimpingDiaphragm1": "iris",
        "HalfWavePlate1": "wave-plate",
        "Shutter1": "shutter-1",
        "Shutter2": "shutter-2",
    }
    controller.controller_rules = {
        "working": {
            "MainLaserDiaphragm1": 75.0,
            "HalfWavePlate1": 20.5,
            "Shutter1": -1.0,
        }
    }

    DS_LaserPointing._normalise_working_rule(controller)

    assert controller.controller_rules["working"] == {
        "MainLaserDiaphragm1": 100.0,
        "CrimpingDiaphragm1": 100.0,
        "HalfWavePlate1": 20.5,
        "Shutter1": 1.0,
        "Shutter2": 1.0,
    }


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


def test_working_point_refuses_to_lower_shutters_without_waveplate_target():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {
        "HalfWavePlate1": "wave-plate",
        "CrimpingDiaphragm1": "iris",
        "Shutter1": "shutter-1",
    }
    controller.controller_rules = {
        "working": {"CrimpingDiaphragm1": 100.0, "Shutter1": 1.0}
    }
    controller._active_point = "point3"
    controller._raise_if_cancelled = lambda: None
    moves = []
    controller._move_single_axis = (
        lambda device, target, _config: moves.append((device, target))
    )

    with pytest.raises(RuntimeError, match="no registered working target"):
        DS_LaserPointing._apply_point(controller, "working", {})

    assert moves == []
    assert controller._active_point == "point3"


def test_working_point_lowers_every_configured_shutter_even_with_stale_rule():
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

    assert flippers["Shutter1"].commands == [1.0]
    assert flippers["Shutter2"].commands == [1.0]
    assert flippers["Shutter1"].commanded_flipper_state == "DOWN_CLEAR"
    assert flippers["Shutter2"].commanded_flipper_state == "DOWN_CLEAR"
    assert controller._active_point == "working"


@pytest.mark.parametrize(
    "camera_number, route",
    [
        (1, {"Shutter1": -1.0}),
        (2, {"Shutter1": 1.0, "Shutter2": -1.0}),
    ],
)
def test_numbered_points_preserve_route_and_working_lowers_all_shutters(
    camera_number, route
):
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

    for role, flipper in flippers.items():
        expected = []
        if role in route:
            expected.append(route[role])
        if not expected or expected[-1] != 1.0:
            expected.append(1.0)
        assert flipper.commands == expected
        assert flipper.position == 0.0
        assert flipper.commanded_flipper_state == "DOWN_CLEAR"


def test_cam2_applies_waveplate_then_working_optics_then_lowers_shutters():
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
        ("HalfWavePlate1", 20.5),
        ("MainLaserDiaphragm1", 100.0),
        ("MainLaserDiaphragm2", 100.0),
        ("CrimpingDiaphragm1", 100.0),
        ("CrimpingDiaphragm2", 100.0),
        ("TranslationStage1", (3, 0.0)),
        ("Shutter1", 1.0),
        ("Shutter2", 1.0),
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


def test_multi_axis_point_move_retries_transient_owis_read_timeout():
    class Owis:
        def __init__(self):
            self.status_calls = 0

        @staticmethod
        def move_axis(_command):
            return 0

        def get_status_axis(self, _axis):
            self.status_calls += 1
            if self.status_calls == 1:
                raise RuntimeError("API_DeviceTimedOut")
            return 0

        @staticmethod
        def read_position_axis(_axis):
            return 0.0

    controller = object.__new__(DS_LaserPointing)
    controller._raise_if_cancelled = lambda: None
    controller._interruptible_sleep = lambda _delay: None
    owis = Owis()

    DS_LaserPointing._move_multi_axis(
        controller,
        owis,
        (3, 0.0),
        {
            "motion_timeout_s": 1.0,
            "motion_poll_s": 0.01,
            "position_tolerance": 0.05,
            "position_stable_reads": 1,
        },
    )

    assert owis.status_calls == 2


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


# Keep the original pytest entry point and assertion diagnostics.
pytest.register_assert_rewrite(
    f"{__package__}._automatic_search_failed_optical_probe_restores_cases" if __package__ else "_automatic_search_failed_optical_probe_restores_cases",
    f"{__package__}._automatic_search_automatic_worker_revisits_both_cases" if __package__ else "_automatic_search_automatic_worker_revisits_both_cases",
    f"{__package__}._automatic_search_pattern_search_stops_one_cases" if __package__ else "_automatic_search_pattern_search_stops_one_cases",
)

if __package__:
    from ._automatic_search_failed_optical_probe_restores_cases import (
        test_failed_optical_probe_restores_last_visible_mount_position,
        test_invisible_directional_probe_is_rejected_without_aborting_search,
        test_worse_probe_returns_to_last_good_actuator_position,
        test_noisier_fine_pass_retains_better_position_from_coarse_pass,
        test_cancelled_search_does_not_issue_a_rollback_move,
        test_plain_cancel_retains_last_measured_good_position,
        test_parallel_pair_move_preserves_cancellation_signal,
        test_measurement_retries_a_transient_invalid_camera_frame,
        test_aperture_cycle_sweeps_repeats_and_finishes_closed,
        test_failed_aperture_measurement_restores_closed_position,
        test_measurement_discards_a_beamless_pulsed_laser_frame,
        test_camera_profile_settings_bypass_stale_taurus_cache,
    )
else:
    from _automatic_search_failed_optical_probe_restores_cases import (
        test_failed_optical_probe_restores_last_visible_mount_position,
        test_invisible_directional_probe_is_rejected_without_aborting_search,
        test_worse_probe_returns_to_last_good_actuator_position,
        test_noisier_fine_pass_retains_better_position_from_coarse_pass,
        test_cancelled_search_does_not_issue_a_rollback_move,
        test_plain_cancel_retains_last_measured_good_position,
        test_parallel_pair_move_preserves_cancellation_signal,
        test_measurement_retries_a_transient_invalid_camera_frame,
        test_aperture_cycle_sweeps_repeats_and_finishes_closed,
        test_failed_aperture_measurement_restores_closed_position,
        test_measurement_discards_a_beamless_pulsed_laser_frame,
        test_camera_profile_settings_bypass_stale_taurus_cache,
    )

if __package__:
    from ._automatic_search_automatic_worker_revisits_both_cases import (
        test_automatic_worker_revisits_both_points_before_declaring_convergence,
        test_automatic_worker_stops_after_five_complete_stagnant_passes,
        test_pause_and_continue_keep_the_same_search_worker,
        test_plain_cancel_requests_stop_without_restoring_current_alignment,
        test_plain_cancel_discards_pending_decision_without_hardware_restore,
        test_pause_checkpoint_restores_in_progress_search_phase_on_continue,
        test_cancel_restore_replays_all_captured_readbacks,
        test_accept_reference_appends_revision_without_erasing_history,
        test_manual_alignment_can_be_saved_as_next_day_reference_without_search,
        test_reference_acceptance_detects_post_search_hardware_movement,
        test_stopped_axis_readback_mismatch_fails_without_long_polling,
        test_timed_out_blocking_move_is_accepted_after_direct_target_readback,
        test_non_timeout_move_exception_is_not_hidden,
        test_move_verification_bypasses_stale_taurus_position_cache,
        test_working_point_accepts_mechanical_fully_open_diaphragm_stop,
        test_manual_point_selection_unlocks_pair_without_moving_optical_hardware,
        test_pattern_search_converges_without_assuming_linear_response,
        test_pattern_search_never_proposes_outside_bounds,
        test_pattern_search_applies_a_smaller_learned_limit_during_same_run,
    )
else:
    from _automatic_search_automatic_worker_revisits_both_cases import (
        test_automatic_worker_revisits_both_points_before_declaring_convergence,
        test_automatic_worker_stops_after_five_complete_stagnant_passes,
        test_pause_and_continue_keep_the_same_search_worker,
        test_plain_cancel_requests_stop_without_restoring_current_alignment,
        test_plain_cancel_discards_pending_decision_without_hardware_restore,
        test_pause_checkpoint_restores_in_progress_search_phase_on_continue,
        test_cancel_restore_replays_all_captured_readbacks,
        test_accept_reference_appends_revision_without_erasing_history,
        test_manual_alignment_can_be_saved_as_next_day_reference_without_search,
        test_reference_acceptance_detects_post_search_hardware_movement,
        test_stopped_axis_readback_mismatch_fails_without_long_polling,
        test_timed_out_blocking_move_is_accepted_after_direct_target_readback,
        test_non_timeout_move_exception_is_not_hidden,
        test_move_verification_bypasses_stale_taurus_position_cache,
        test_working_point_accepts_mechanical_fully_open_diaphragm_stop,
        test_manual_point_selection_unlocks_pair_without_moving_optical_hardware,
        test_pattern_search_converges_without_assuming_linear_response,
        test_pattern_search_never_proposes_outside_bounds,
        test_pattern_search_applies_a_smaller_learned_limit_during_same_run,
    )

if __package__:
    from ._automatic_search_pattern_search_stops_one_cases import (
        test_pattern_search_stops_one_actuator_group_after_five_plateau_probes,
        test_five_percent_cumulative_improvement_resets_local_plateau_counter,
        test_cam2_point6_uses_persistent_adaptive_half_step_safety_limit,
        test_visible_worse_probe_does_not_collapse_persistent_safety_step,
        test_visible_worse_probe_preserves_an_existing_visibility_backoff,
        test_adaptive_model_remembers_effect_and_prioritises_good_direction,
        test_pattern_search_honours_cancellation_before_moving,
        test_repeated_directional_probe_crosses_mount_stiction,
        test_optical_signature_prevents_false_stiction_from_equal_scores,
        test_invalid_search_parameters_are_rejected,
    )
else:
    from _automatic_search_pattern_search_stops_one_cases import (
        test_pattern_search_stops_one_actuator_group_after_five_plateau_probes,
        test_five_percent_cumulative_improvement_resets_local_plateau_counter,
        test_cam2_point6_uses_persistent_adaptive_half_step_safety_limit,
        test_visible_worse_probe_does_not_collapse_persistent_safety_step,
        test_visible_worse_probe_preserves_an_existing_visibility_backoff,
        test_adaptive_model_remembers_effect_and_prioritises_good_direction,
        test_pattern_search_honours_cancellation_before_moving,
        test_repeated_directional_probe_crosses_mount_stiction,
        test_optical_signature_prevents_false_stiction_from_equal_scores,
        test_invalid_search_parameters_are_rejected,
    )
