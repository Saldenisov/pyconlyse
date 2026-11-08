"""Cases collected through test_automatic_search.py."""

if __package__:
    from .test_automatic_search import (
        DS_LaserPointing,
        SearchParameters,
        bounded_pattern_search,
        hypot,
        pytest,
    )
else:
    from test_automatic_search import (
        DS_LaserPointing,
        SearchParameters,
        bounded_pattern_search,
        hypot,
        pytest,
    )


def test_pattern_search_stops_one_actuator_group_after_five_plateau_probes():
    observed = []

    result = bounded_pattern_search(
        lambda position: observed.append(position) or 20.0,
        start=(0.0, 0.0),
        bounds=((-20.0, 20.0), (-20.0, 20.0)),
        parameters=SearchParameters(
            initial_step=2.0,
            minimum_step=0.125,
            tolerance_px=7.0,
            max_evaluations=20,
            plateau_evaluations=5,
            plateau_min_improvement=5.0,
        ),
    )

    assert result.reason == "plateau"
    assert result.evaluations == 6
    assert len(observed) == 6
    assert result.best_score == 20.0

def test_five_percent_cumulative_improvement_resets_local_plateau_counter():
    scores = iter((20.0, 18.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0))

    result = bounded_pattern_search(
        lambda _position: next(scores),
        start=(0.0, 0.0),
        bounds=((-20.0, 20.0), (-20.0, 20.0)),
        parameters=SearchParameters(
            initial_step=2.0,
            minimum_step=0.125,
            tolerance_px=7.0,
            max_evaluations=20,
            plateau_evaluations=5,
            plateau_min_improvement=5.0,
        ),
    )

    assert result.reason == "plateau"
    assert result.evaluations == 8
    assert result.best_score == 15.0

def test_cam2_point6_uses_persistent_adaptive_half_step_safety_limit():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "manip/V0/Cam2_V0"}
    controller._adaptive_search_model = {}
    persisted = []
    controller._persist_alignment_properties = persisted.append
    config = DS_LaserPointing._normalise_search_config({
        "adaptive_min_step": 2.0,
    })

    assert DS_LaserPointing._adaptive_step_limit(
        controller, "group2", "point6", 10.0, config
    ) == 0.5
    assert DS_LaserPointing._adaptive_probe_repetitions(
        controller, "point6", config
    ) == 1

    learning_config = DS_LaserPointing._normalise_search_config({
        "adaptive_min_step": 0.125,
    })

    DS_LaserPointing._learn_from_probe(
        controller,
        "group2",
        "point6",
        ("ActuatorX4", "ActuatorY4"),
        (0.0, 0.0),
        (0.5, 0.0),
        8.0,
        None,
        {"shape_centroid": [40.0, 40.0]},
        None,
        False,
        10.0,
        learning_config,
        error="beam disappeared",
    )

    key = "manip/v0/cam2_v0|point6|group2"
    model = controller._adaptive_search_model[key]
    # A user-configured adaptive floor cannot override the hard 0.5 limit,
    # while loss of visibility halves the next permitted probe.
    assert model["maximum_step"] == 0.5
    assert model["safe_step"] == 0.25
    assert model["last_probe"]["visible"] is False
    assert model["failed_visibility_probes"] == 1
    assert "adaptive_search_model_property" in persisted[-1]

@pytest.mark.parametrize("score_after", [8.05, 9.0, 25.0])
def test_visible_worse_probe_does_not_collapse_persistent_safety_step(score_after):
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "manip/V0/Cam2_V0"}
    controller._adaptive_search_model = {}
    controller._persist_alignment_properties = lambda _properties: None
    config = DS_LaserPointing._normalise_search_config({})

    for index in range(8):
        DS_LaserPointing._learn_from_probe(
            controller, "group2", "point6",
            ("ActuatorX4", "ActuatorY4"),
            (0.0, 0.0), (0.5 if index % 2 else -0.5, 0.0),
            8.0, score_after,
            {"shape_centroid": [40.0, 40.0]},
            {"shape_centroid": [40.2, 40.1]},
            True, 10.0, config,
        )

    model = controller._adaptive_search_model["manip/v0/cam2_v0|point6|group2"]
    assert model["safe_step"] == 0.5
    assert model["successful_probes"] == 8
    assert model["failed_visibility_probes"] == 0
    assert DS_LaserPointing._adaptive_step_limit(
        controller, "group2", "point6", 10.0, config
    ) == 0.5

def test_visible_worse_probe_preserves_an_existing_visibility_backoff():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "manip/V0/Cam2_V0"}
    key = "manip/v0/cam2_v0|point6|group2"
    controller._adaptive_search_model = {key: {
        "safe_step": 0.25, "failed_visibility_probes": 1, "axes": {},
    }}
    controller._persist_alignment_properties = lambda _properties: None
    config = DS_LaserPointing._normalise_search_config({})

    DS_LaserPointing._learn_from_probe(
        controller, "group2", "point6", ("ActuatorX4", "ActuatorY4"),
        (0.0, 0.0), (0.25, 0.0), 8.0, 12.0,
        {"shape_centroid": [40.0, 40.0]},
        {"shape_centroid": [40.2, 40.1]}, True, 10.0, config,
    )

    assert controller._adaptive_search_model[key]["safe_step"] == 0.25
    assert controller._adaptive_search_model[key]["failed_visibility_probes"] == 1

def test_adaptive_model_remembers_effect_and_prioritises_good_direction():
    controller = object.__new__(DS_LaserPointing)
    controller.ds_dict = {"Camera": "manip/V0/Cam2_V0"}
    controller._adaptive_search_model = {}
    controller._persist_alignment_properties = lambda _properties: None
    config = DS_LaserPointing._normalise_search_config({
        "adaptive_min_step": 0.125,
    })

    DS_LaserPointing._learn_from_probe(
        controller,
        "group2",
        "point6",
        ("ActuatorX4", "ActuatorY4"),
        (0.0, 0.0),
        (-0.5, 0.0),
        9.0,
        6.0,
        {"shape_centroid": [40.0, 40.0]},
        {"shape_centroid": [40.2, 39.9]},
        True,
        10.0,
        config,
    )

    order = DS_LaserPointing._adaptive_direction_order(
        controller,
        "group2",
        "point6",
        ("ActuatorX4", "ActuatorY4"),
    )
    key = "manip/v0/cam2_v0|point6|group2"
    statistics = controller._adaptive_search_model[key]["axes"][
        "ActuatorX4"
    ]["negative"]
    assert statistics["mean_improvement_per_step"] == pytest.approx(6.0)
    assert order[0] == (-1.0, 0.0)

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
        SearchParameters(plateau_evaluations=-1),
        SearchParameters(plateau_min_improvement=-1.0),
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
