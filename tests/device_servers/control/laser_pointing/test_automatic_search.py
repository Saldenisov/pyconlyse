from math import hypot
from threading import Lock

import pytest

from DeviceServers.control.laser_pointing.automatic_search import (
    SearchParameters,
    bounded_pattern_search,
    optical_point_group,
)
from DeviceServers.control.laser_pointing.DS_LaserPointing import DS_LaserPointing


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
