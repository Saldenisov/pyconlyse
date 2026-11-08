"""Cases collected through test_automatic_search.py."""

if __package__:
    from .test_automatic_search import (
        DS_LaserPointing,
        Enum,
        Event,
        Lock,
        SearchParameters,
        Thread,
        bounded_pattern_search,
        hypot,
        json,
        pytest,
    )
else:
    from test_automatic_search import (
        DS_LaserPointing,
        Enum,
        Event,
        Lock,
        SearchParameters,
        Thread,
        bounded_pattern_search,
        hypot,
        json,
        pytest,
    )


def test_automatic_worker_revisits_both_points_before_declaring_convergence():
    controller = object.__new__(DS_LaserPointing)
    controller.devices = {"camera": type("Camera", (), {"isgrabbing": True})()}
    controller.ds_dict = {"Camera": "camera"}
    controller.pid_groups = {
        "near": ("point1", "point3"),
        "far": ("point4", "point6"),
    }
    controller._search_stop = Event()
    controller._search_pause = Event()
    controller._search_progress = {}
    controller._search_history = []
    controller._search_status = "running"
    controller._search_started_at = None
    controller._search_session_id = "session-1"
    controller._pause_active = False
    controller._active_point = "point3"
    controller._capture_alignment_state = lambda: {
        "active_point": controller._active_point,
        "actuators": {},
        "optics": {},
    }
    stored_candidates = []
    controller._store_pending_reference = stored_candidates.append
    accepted_metadata = []
    controller._accept_pending_alignment_reference = lambda metadata: (
        accepted_metadata.append(metadata) or 2
    )
    controller._record_alignment_event = lambda *_args, **_kwargs: None
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

    assert controller._search_status == "finished"
    assert stored_candidates[0]["converged"] is True
    assert accepted_metadata == [{
        "client": "automatic-search",
        "automatic": True,
    }]
    assert controller._search_progress["acceptance_required"] is False
    assert controller._search_progress["accepted_reference_revision"] == 2
    assert [(item["point"], item["roundness_error_pct"])
            for item in controller._search_progress["verification"]] == [
        ("point3", 2.0), ("point6", 2.0)
    ]
    assert calls[:4] == [
        ("optimise", "near", 2.0), ("optimise", "far", 2.0),
        ("measure", "point3"), ("measure", "point6"),
    ]
    assert ("optimise", "near", 1.0) in calls

def test_automatic_worker_stops_after_five_complete_stagnant_passes():
    controller = object.__new__(DS_LaserPointing)
    controller.devices = {"camera": type("Camera", (), {"isgrabbing": True})()}
    controller.ds_dict = {"Camera": "camera"}
    controller.pid_groups = {
        "near": ("point1", "point3"),
        "far": ("point4", "point6"),
    }
    controller._search_stop = Event()
    controller._search_pause = Event()
    controller._search_progress = {}
    controller._search_history = []
    controller._search_status = "running"
    controller._search_started_at = None
    controller._search_session_id = "session-stagnant"
    controller._pause_active = False
    controller.cgc = True
    controller._active_point = "point3"
    controller._capture_alignment_state = lambda: {
        "active_point": controller._active_point,
        "actuators": {},
        "optics": {},
    }
    stored_candidates = []
    controller._store_pending_reference = stored_candidates.append
    controller._accept_pending_alignment_reference = lambda _metadata: (
        pytest.fail("a stagnant result must not be saved automatically")
    )
    events = []
    controller._record_alignment_event = (
        lambda event_type, **details: events.append((event_type, details))
    )
    controller._raise_if_cancelled = lambda: None
    controller._validate_camera_verified_roles = lambda *_args: None
    controller._point_stages = lambda _config: [("sensitive", [
        ("near", ("point1", "point3")),
        ("far", ("point4", "point6")),
    ])]
    optimised_groups = []

    def optimise(group, _pair, _stage, _cycle, _step, _config, _origins):
        optimised_groups.append(group)
        return {"best_roundness_error_pct": 10.0}

    current_point = [""]
    controller._optimise_group = optimise
    controller._measure_aperture_cycle = lambda pair, _config: (
        current_point.__setitem__(0, pair[-1]) or (20.0, 20.0)
    )
    controller._read_beam_shape = lambda: {
        "roundness_error_pct": 10.0,
        "shape_centroid": [20.0, 20.0],
    }
    config = DS_LaserPointing._normalise_search_config({
        "step_schedule": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
        "max_cycles": 2,
        "roundness_tolerance_pct": 7.0,
        "stagnation_pass_limit": 5,
        "stagnation_min_improvement_pct": 5.0,
    })

    DS_LaserPointing._automatic_search_worker(controller, config)

    assert optimised_groups == ["near", "far"] * 5
    assert stored_candidates == []
    assert controller._search_status == "finished; no roundness improvement"
    assert controller._search_progress["phase"] == "stopped_no_improvement"
    assert controller._search_progress["completed_passes"] == 5
    assert controller._search_progress["stagnant_passes"] == 5
    assert controller._search_progress["current_alignment_kept"] is True
    assert controller._search_progress["acceptance_required"] is False
    assert controller.cgc is False
    assert events[-1][0] == "search_stopped_no_improvement"

def test_pause_and_continue_keep_the_same_search_worker():
    class RunningThread:
        @staticmethod
        def is_alive():
            return True

    controller = object.__new__(DS_LaserPointing)
    controller._search_thread = RunningThread()
    controller._search_pause = Event()
    controller._search_status = "running"
    controller._search_session_id = "session-1"
    events = []
    controller._record_alignment_event = (
        lambda event_type, **_details: events.append(event_type)
    )

    assert DS_LaserPointing.pause_automatic_search(controller) == 0
    assert controller._search_pause.is_set()
    assert controller._search_status == "pausing"
    assert controller._search_thread.is_alive()

    assert DS_LaserPointing.resume_automatic_search(controller) == 0
    assert not controller._search_pause.is_set()
    assert controller._search_status == "running"
    assert events == ["pause_requested", "resume_requested"]

def test_plain_cancel_requests_stop_without_restoring_current_alignment():
    class RunningThread:
        @staticmethod
        def is_alive():
            return True

    controller = object.__new__(DS_LaserPointing)
    controller._search_thread = RunningThread()
    controller._search_stop = Event()
    controller._search_pause = Event()
    controller._search_pause.set()
    controller._alignment_pending_reference = {}
    controller._search_status = "paused"
    controller._search_progress = {"phase": "paused"}
    controller._search_session_id = "session-1"
    controller.cgc = True
    events = []
    controller._record_alignment_event = (
        lambda event_type, **_details: events.append(event_type)
    )

    assert DS_LaserPointing.cancel_automatic_search(controller) == 0
    assert controller._search_stop.is_set()
    assert not controller._search_pause.is_set()
    assert controller._restore_on_cancel is False
    assert controller._search_status == "cancelling; keeping current"
    assert controller.cgc is False
    assert events == ["cancel_keep_current_requested"]

def test_plain_cancel_discards_pending_decision_without_hardware_restore():
    controller = object.__new__(DS_LaserPointing)
    controller._search_thread = None
    controller._alignment_pending_reference = {
        "session_id": "session-2", "active_point": "point6"
    }
    controller.controller_rules = {"point6": {}}
    controller._active_point = ""
    controller._actuator_initialization_status = {}
    controller._search_status = "not converged; awaiting operator decision"
    controller._search_progress = {"phase": "not_converged"}
    controller._search_session_id = "session-2"
    cleared = []
    events = []

    def clear_pending():
        cleared.append(True)
        controller._alignment_pending_reference = {}

    controller._clear_pending_reference = clear_pending
    controller._record_alignment_event = (
        lambda event_type, **_details: events.append(event_type)
    )

    assert DS_LaserPointing.cancel_automatic_search(controller) == 0
    assert cleared == [True]
    assert controller._search_status == "cancelled; current alignment kept"
    assert controller._search_progress["phase"] == "cancelled_keep_current"
    assert controller._active_point == "point6"
    assert controller._actuator_initialization_status["group"] == 2
    assert events == ["completed_alignment_kept_without_reference"]

def test_pause_checkpoint_restores_in_progress_search_phase_on_continue():
    controller = object.__new__(DS_LaserPointing)
    controller._search_pause = Event()
    controller._search_pause.set()
    controller._search_stop = Event()
    controller._search_session_id = "session-1"
    controller._search_status = "pausing"
    controller._search_progress = {"phase": "measuring", "group": "near"}
    controller._pause_active = False
    events = []
    paused = Event()

    def record(event_type, **_details):
        events.append(event_type)
        if event_type == "paused":
            paused.set()

    controller._record_alignment_event = record
    worker = Thread(
        target=DS_LaserPointing._wait_if_paused, args=(controller,), daemon=True
    )
    worker.start()
    assert paused.wait(1)
    assert controller._search_status == "paused"
    controller._search_pause.clear()
    worker.join(1)

    assert not worker.is_alive()
    assert controller._search_status == "running"
    assert controller._search_progress["phase"] == "measuring"
    assert events == ["paused", "resumed"]

def test_cancel_restore_replays_all_captured_readbacks():
    controller = object.__new__(DS_LaserPointing)
    controller._search_stop = Event()
    controller._search_stop.set()
    controller._search_pause = Event()
    controller._search_session_id = "session-1"
    controller._search_progress = {}
    controller._active_point = "point6"
    controller._record_alignment_event = lambda *_args, **_kwargs: None
    controller._device_for_role = lambda role: role
    moves = []
    controller._move_single_axis = (
        lambda device, target, _config: moves.append((device, target))
    )
    controller._move_multi_axis = (
        lambda device, target, _config: moves.append((device, list(target)))
    )
    state = {
        "active_point": "point1",
        "actuators": {
            "ActuatorX1": {"position": 12.5},
            "ActuatorY1": {"position": -7.0},
        },
        "optics": {
            "CrimpingDiaphragm1": {
                "kind": "single_axis", "position": 40.0,
            },
            "TranslationStage1": {
                "kind": "multi_axis", "axis": 3, "position": -700.0,
            },
        },
    }

    DS_LaserPointing._restore_alignment_state(controller, state, {})

    assert moves == [
        ("ActuatorX1", 12.5),
        ("ActuatorY1", -7.0),
        ("CrimpingDiaphragm1", 40.0),
        ("TranslationStage1", [3, -700.0]),
    ]
    assert controller._active_point == "point1"
    assert controller._search_status == "cancelled and restored"
    assert controller._search_progress["phase"] == "restored_initial_state"

def test_accept_reference_appends_revision_without_erasing_history():
    controller = object.__new__(DS_LaserPointing)
    controller._search_thread = None
    controller._alignment_pending_reference = {
        "session_id": "session-2",
        "actuators": {"ActuatorX1": {"position": 5.0}},
    }
    old_reference = json.dumps({"session_id": "session-1", "revision": 1})
    controller._alignment_reference_history = [old_reference]
    controller._alignment_reference = json.loads(old_reference)
    controller._search_progress = {"phase": "finished"}
    controller._search_status = "awaiting acceptance"
    controller._search_session_id = "session-2"
    controller._search_config = {"position_tolerance": 0.05}
    controller._capture_alignment_state = lambda: {
        "actuators": {"ActuatorX1": {"position": 5.0}},
        "optics": {},
    }
    persisted = []
    controller._persist_alignment_properties = persisted.append
    controller._record_alignment_event = lambda *_args, **_kwargs: None
    controller._push_alignment_value = lambda *_args, **_kwargs: None

    revision = DS_LaserPointing.accept_alignment_reference(
        controller, json.dumps({"comment": "beam checked"})
    )

    assert revision == 2
    assert controller._alignment_reference["session_id"] == "session-2"
    assert controller._alignment_reference["acceptance"]["comment"] == "beam checked"
    assert controller._alignment_reference_history[0] == old_reference
    assert len(controller._alignment_reference_history) == 2
    assert persisted[0]["alignment_reference_history_property"][0] == old_reference
    assert controller._alignment_pending_reference == {}

def test_manual_alignment_can_be_saved_as_next_day_reference_without_search():
    controller = object.__new__(DS_LaserPointing)
    controller._search_thread = None
    controller._point_application_thread = None
    controller._alignment_pending_reference = {}
    controller._alignment_reference = {}
    controller._alignment_reference_history = []
    controller._search_config = {"position_tolerance": 0.05}
    controller._search_progress = {}
    controller._capture_alignment_state = lambda: {
        "active_point": "point6",
        "actuators": {
            "ActuatorX4": {"position": 12.5},
            "ActuatorY4": {"position": -3.0},
        },
        "optics": {},
    }
    persisted = []
    events = []
    controller._persist_alignment_properties = persisted.append
    controller._record_alignment_event = (
        lambda event_type, **details: events.append((event_type, details))
    )
    controller._push_alignment_value = lambda *_args, **_kwargs: None

    revision = DS_LaserPointing.save_current_alignment_reference(
        controller, json.dumps({"client": "pyqt5"})
    )

    assert revision == 1
    assert controller._alignment_reference["source"] == "manual"
    assert controller._alignment_reference["manual_reference"] is True
    assert controller._alignment_reference["acceptance"] == {
        "client": "pyqt5", "manual": True
    }
    assert controller._alignment_reference["actuators"][
        "ActuatorX4"
    ]["position"] == 12.5
    assert controller._search_status == "reference accepted"
    assert persisted[-1]["alignment_pending_reference_property"] == "{}"
    assert events[-1][0] == "reference_accepted"

def test_reference_acceptance_detects_post_search_hardware_movement():
    controller = object.__new__(DS_LaserPointing)
    controller._search_config = {"position_tolerance": 0.05}

    mismatches = DS_LaserPointing._alignment_state_mismatches(
        controller,
        {
            "actuators": {"ActuatorY2": {"position": 10.0}},
            "optics": {
                "Shutter1": {
                    "kind": "flipper", "commanded_state": "UP_BLOCKED",
                },
            },
        },
        {
            "actuators": {"ActuatorY2": {"position": 10.2}},
            "optics": {
                "Shutter1": {
                    "kind": "flipper", "commanded_state": "DOWN_CLEAR",
                },
            },
        },
    )

    assert any("ActuatorY2 moved by 0.200" in item for item in mismatches)
    assert any("Shutter1 is DOWN_CLEAR" in item for item in mismatches)

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

def test_pattern_search_applies_a_smaller_learned_limit_during_same_run():
    observed = []
    learned_limit = [0.5]

    def objective(position):
        observed.append(position)
        if position == (0.5, 0.0):
            learned_limit[0] = 0.25
        return 10.0

    bounded_pattern_search(
        objective,
        start=(0.0, 0.0),
        bounds=((-20.0, 20.0), (-20.0, 20.0)),
        parameters=SearchParameters(
            initial_step=10.0,
            minimum_step=10.0,
            tolerance_px=0.0,
            max_evaluations=5,
            step_schedule=(10.0,),
            probe_repetitions=1,
        ),
        step_limit=lambda: learned_limit[0],
    )

    assert observed == [
        (0.0, 0.0),
        (0.5, 0.0),
        (-0.25, 0.0),
        (0.0, 0.25),
        (0.0, -0.25),
    ]
