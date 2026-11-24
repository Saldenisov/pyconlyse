"""Explicit endpoint-counter calibration with fake motors; no Tango/network."""

import json
from enum import IntEnum
from types import SimpleNamespace

import pytest

from DeviceServers.control.laser_pointing.DS_LaserPointing import DS_LaserPointing


class Axis:
    def __init__(self, name, position=97.5, endpoint='RIGHT', *, stopped_position=97.5,
                 stopped_endpoint='RIGHT', definition='ok'):
        self.name, self.position, self.endpoint = name, position, endpoint
        self.state = 'ON'
        self.stopped_position, self.stopped_endpoint = stopped_position, stopped_endpoint
        self.definition = definition
        self.moves, self.definitions = [], []

    def getFullName(self):
        return self.name

    def move_axis_abs(self, target):
        self.moves.append(float(target))
        self.position, self.endpoint = self.stopped_position, self.stopped_endpoint
        return 0

    def define_position(self, target):
        self.definitions.append(float(target))
        if self.definition == 'command_error':
            return -1
        if self.definition != 'no_effect':
            self.position = float(target)
        if self.definition == 'endpoint_changed':
            self.endpoint = 'BETWEEN'
        return 0


@pytest.fixture
def endpoint_controller():
    def build(**axis_settings):
        controller = object.__new__(DS_LaserPointing)
        iris = Axis('fake-iris', **axis_settings)
        mirror = Axis('fake-mirror')
        controller.ds_dict = {'CrimpingDiaphragm1': 'fake-iris', 'ActuatorX1': 'fake-mirror'}
        controller.devices = {'fake-iris': iris, 'fake-mirror': mirror}
        controller.full_open_endpoint_calibrations = json.dumps({
            'CrimpingDiaphragm1': {'endpoint': 'RIGHT', 'position': 100., 'max_counter_error': 5.},
        })
        controller._search_progress, controller._search_history = {}, []
        controller._raise_if_cancelled = lambda: None
        controller._interruptible_sleep = lambda _: None
        controller._fresh_position_and_state = lambda axis: (axis.position, axis.state)
        controller._fresh_endpoint_state = lambda axis: axis.endpoint
        events = []
        controller._record_alignment_event = lambda kind, **details: events.append((kind, details))
        config = {'motion_timeout_s': .05, 'motion_poll_s': 0., 'position_tolerance': .05}
        controller._search_config = config
        controller._search_is_running = lambda: False
        controller._point_application_is_running = lambda: False
        return SimpleNamespace(controller=controller, iris=iris, mirror=mirror, events=events, config=config)
    return build


def test_existing_confirmed_right_endpoint_redefines_counter_without_motion(endpoint_controller):
    sim = endpoint_controller()
    sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.moves == []
    assert sim.iris.definitions == [100.]
    assert sim.iris.position == 100. and sim.iris.endpoint == 'RIGHT'
    calibrated = [details for kind, details in sim.events if kind == 'full_open_endpoint_calibrated']
    assert len(calibrated) == 1
    assert calibrated[0]['role'] == 'CrimpingDiaphragm1'
    assert calibrated[0]['endpoint'] == 'RIGHT'
    assert calibrated[0]['raw_position_before'] == 97.5
    assert calibrated[0]['position_after'] == 100.
    assert calibrated[0]['physical_motion_commanded'] is False


def test_endpoint_reached_after_motion_is_normalized_before_success(endpoint_controller):
    sim = endpoint_controller(position=80., endpoint='BETWEEN')
    sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.moves == [100.]
    assert sim.iris.definitions == [100.]
    assert sim.iris.position == 100. and sim.iris.endpoint == 'RIGHT'


@pytest.mark.parametrize("role, name", [
    ("MainLaserDiaphragm1", "elyse/motorized_devices/de1"),
    ("MainLaserDiaphragm2", "manip/V0/dv01"),
    ("CrimpingDiaphragm1", "manip/V0/dv02"),
    ("CrimpingDiaphragm2", "manip/V0/dv03"),
])
def test_working_normalizes_registered_full_open_irises_without_motion(endpoint_controller, role, name):
    sim = endpoint_controller(position=99.992)
    sim.controller.ds_dict = {role: name}
    sim.controller.devices = {name: sim.iris}
    sim.controller.full_open_endpoint_calibrations = "{}"

    sim.controller._move_single_axis(sim.iris, 100., {**sim.config, "_working_point": True})

    assert sim.iris.moves == []
    assert sim.iris.definitions == [100.]
    assert sim.iris.position == 100.


@pytest.mark.parametrize('endpoint', ['LEFT', 'UNKNOWN', 'BOTH', 'BETWEEN'])
def test_wrong_or_unknown_endpoint_never_rebases_a_short_readback(endpoint_controller, endpoint):
    sim = endpoint_controller(endpoint=endpoint, stopped_endpoint=endpoint)
    with pytest.raises(RuntimeError):
        sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.definitions == []
    assert sim.iris.position == 97.5


def test_partial_aperture_target_keeps_strict_native_tolerance(endpoint_controller):
    sim = endpoint_controller(position=49.5, stopped_position=49.5)
    with pytest.raises(RuntimeError, match='motor stopped'):
        sim.controller._move_single_axis(sim.iris, 50., sim.config)
    assert sim.iris.definitions == []
    assert sim.iris.moves == [50.]


def test_reached_partial_target_never_redefines_counter(endpoint_controller):
    sim = endpoint_controller(position=40., stopped_position=50.)
    sim.controller._move_single_axis(sim.iris, 50., sim.config)
    assert sim.iris.definitions == [] and sim.iris.position == 50.


def test_unconfigured_mirror_cannot_use_iris_endpoint_override(endpoint_controller):
    sim = endpoint_controller()
    with pytest.raises(RuntimeError, match='motor stopped'):
        sim.controller._move_single_axis(sim.mirror, 100., sim.config)
    assert sim.mirror.definitions == [] and sim.mirror.position == 97.5


@pytest.mark.parametrize('definition', ['command_error', 'no_effect', 'endpoint_changed'])
def test_failed_or_unverified_counter_definition_cannot_pass(endpoint_controller, definition):
    sim = endpoint_controller(definition=definition)
    with pytest.raises(RuntimeError):
        sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.definitions == [100.]
    assert sim.iris.moves == []  # Never retry a failed definition with a physical move.


def test_numeric_100_without_the_configured_endpoint_is_not_full_open(endpoint_controller):
    sim = endpoint_controller(position=100., endpoint='BETWEEN', stopped_position=100., stopped_endpoint='BETWEEN')
    with pytest.raises(RuntimeError):
        sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.definitions == []


def test_far_outside_counter_error_window_cannot_be_rebased(endpoint_controller):
    sim = endpoint_controller(position=30., stopped_position=30.)
    with pytest.raises(RuntimeError):
        sim.controller._move_single_axis(sim.iris, 100., sim.config)
    assert sim.iris.definitions == [] and sim.iris.position == 30.


def test_endpoint_counter_definition_requires_fresh_on_state(endpoint_controller):
    sim = endpoint_controller()
    sim.iris.state = 'MOVING'
    assert not sim.controller._calibrate_full_open_endpoint(sim.iris, 100., sim.config)
    assert sim.iris.definitions == [] and sim.iris.moves == []


def test_public_endpoint_command_returns_verified_counter_state_without_motion(endpoint_controller):
    sim = endpoint_controller()
    result = json.loads(sim.controller.calibrate_full_open_endpoint('CrimpingDiaphragm1'))
    assert result == {'role': 'CrimpingDiaphragm1', 'position': 100., 'state': 'ON',
                      'endpoint': 'RIGHT', 'physical_motion_commanded': False}
    assert sim.iris.position == 100. and sim.iris.definitions == [100.]
    assert sim.iris.moves == []


def test_public_endpoint_command_rejects_between_position_without_motion(endpoint_controller):
    sim = endpoint_controller(position=50., endpoint='BETWEEN')
    with pytest.raises(RuntimeError, match='not confirmed'):
        sim.controller.calibrate_full_open_endpoint('CrimpingDiaphragm1')
    assert sim.iris.position == 50.
    assert sim.iris.moves == [] and sim.iris.definitions == []


@pytest.mark.parametrize('search_busy, point_busy', [(True, False), (False, True)])
def test_public_endpoint_command_rejects_active_optical_operations(endpoint_controller, search_busy, point_busy):
    sim = endpoint_controller()
    sim.controller._search_is_running = lambda: search_busy
    sim.controller._point_application_is_running = lambda: point_busy
    with pytest.raises(RuntimeError, match='active optical operation'):
        sim.controller.calibrate_full_open_endpoint('CrimpingDiaphragm1')
    assert sim.iris.position == 97.5
    assert sim.iris.moves == [] and sim.iris.definitions == [] and sim.events == []


def test_endpoint_read_refreshes_native_status_and_uses_device_source():
    class Source(IntEnum):
        CACHE = 1
        DEV = 2
    calls = []
    def native_status():
        calls.append(('native_status',))
        return 0
    proxy = SimpleNamespace(get_source=lambda: Source.CACHE,
                            set_source=lambda source: calls.append(('source', source)),
                            read_attribute=lambda name: calls.append(('read', name)) or SimpleNamespace(value='RIGHT'),
                            command_inout=lambda name: native_status() if name == 'get_controller_status' else None)
    axis = SimpleNamespace(getDeviceProxy=lambda: proxy,
                           get_controller_status=native_status)
    controller = object.__new__(DS_LaserPointing)
    assert controller._fresh_endpoint_state(axis) == 'RIGHT'
    assert calls.count(('native_status',)) == 1
    assert calls.index(('native_status',)) < calls.index(('read', 'endpoint_state'))
    assert calls.index(('source', Source.DEV)) < calls.index(('read', 'endpoint_state'))
    assert calls[-1] == ('source', Source.CACHE)
