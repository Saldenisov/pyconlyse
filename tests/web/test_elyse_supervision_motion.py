"""Motion/autotune replay retains native quirks without connecting equipment."""

import builtins
import importlib
import socket
import sys
import time
from itertools import product
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("elyse_supervision_api")
service = importlib.import_module("elyse_supervision_service")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-motion-models")
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def replay(client, operation, inputs):
    return client.post(
        "/api/elyse/supervision/replay", json={"operation": operation, "inputs": inputs}
    )


def error(status=False, code=0, source=""):
    return {"status": status, "code": code, "source": source}


@pytest.mark.parametrize(
    "key,zeroes,resolved",
    [(None, [], False), ("", [], True), ("symbolic-key", [1, 2, 3, 4], True)],
)
def test_discovery_unknown_empty_and_supplied_are_distinct(
    client, key, zeroes, resolved
):
    body = replay(client, "motor_initialization", {"discovered_key": key}).json
    p = body["result"]
    assert p["discovery_key_supplied"] is resolved
    assert p["zero_motor_numbers"] == zeroes
    assert [f["index"] for f in p["frames"]] == [0, 1, 2]
    effects = p["frames"][1]["effects"]
    assert dict(effects[0]["arguments"]) == {"timeout": 5000, "flag": True}
    assert [e["operation"] for e in effects].count("SetZeroPosition.vi") == len(zeroes)
    assert (p["no_devices_message"] is not None) is (key == "")
    assert p["external_effects_blocked"] is True
    assert body["execution_allowed"] is False


@pytest.mark.parametrize("key", [True, 1, [], {}])
def test_discovery_key_cannot_be_coerced(client, key):
    assert (
        replay(client, "motor_initialization", {"discovered_key": key}).status_code
        == 400
    )


@pytest.mark.parametrize(
    "label,axis,sign,event",
    [
        ("Move forward X", 0, 1, 28),
        ("Move forward Y", 1, 1, 28),
        ("Move reverse X", 0, -1, 29),
        ("Move reverse Y", 1, -1, 29),
    ],
)
@pytest.mark.parametrize("steps", [-20, 0, 20, 2**31 - 1])
def test_jog_axis_and_signed_i32_steps_preserve_native_semantics(
    client, label, axis, sign, event, steps
):
    p = replay(
        client,
        "motor_jog",
        {"control_label": label, "motor_numbers": [3, 4], "relative_steps": steps},
    ).json["result"]
    assert (p["event_index"], p["motor_number"], p["signed_steps"]) == (
        event,
        [3, 4][axis],
        sign * steps,
    )
    assert dict(p["motion_call"]["arguments"])["relative_steps"] == sign * steps
    assert p["event_newval_guarded"] is False
    assert p["loop_timeout_ms"] is None
    assert [e["operation"] for e in p["polling_calls"]] == [
        "GetErrorMsg.vi",
        "GetMotionDone.vi",
        "GetPosition.vi",
    ]
    assert p["hide_patches"][-1]["value"] == 2
    assert p["restore_patches"][-1]["value"] == 0
    assert all(e["external_effects_blocked"] for e in p["polling_calls"])


@pytest.mark.parametrize(
    "changes",
    [
        {"control_label": "unknown"},
        {"control_label": None},
        {"motor_numbers": [True, 2]},
        {"motor_numbers": [1, -1]},
        {"motor_numbers": [1, 2**32]},
        {"motor_numbers": [1, 2.0]},
        {"motor_numbers": [1]},
        {"motor_numbers": [1, 2, 3]},
        {"motor_numbers": None},
        {"relative_steps": True},
        {"relative_steps": "10"},
        {"relative_steps": 1.0},
        {"relative_steps": 2**31},
        {"control_label": "Move reverse X", "relative_steps": -(2**31)},
    ],
)
def test_jog_rejects_defaults_unsigned_coercion_and_negate_overflow(client, changes):
    data = (
        dict(control_label="Move forward X", motor_numbers=[1, 2], relative_steps=10)
        | changes
    )
    assert replay(client, "motor_jog", data).status_code == 400


@pytest.mark.parametrize(
    "event,done,status,stop",
    product([28, 29], [False, True], [False, True], [False, True]),
)
def test_poll_truth_table_and_unconditional_external_position(
    client, event, done, status, stop
):
    p = replay(
        client,
        "motor_jog_poll",
        dict(
            event_index=event,
            motion_done=done,
            motion_done_error=error(status),
            stop_motor=stop,
            position_result=-123,
        ),
    ).json["result"]
    assert p["terminate"] is (done or status or stop)
    assert p["motor_position"] == -123
    assert (p["abort_intent"] is not None) is stop
    if stop:
        assert p["abort_intent"]["node_uid"] == (95968 if event == 28 else 266362)
        assert dict(p["abort_intent"]["arguments"])["after"] == "GetPosition.vi"
    assert (
        p["termination_error_source"]
        == "GetMotionDone.vi, NOT GetPosition/Abort result"
    )


@pytest.mark.parametrize("event,uid", [(27, 77718), (28, 170563), (29, 266960)])
@pytest.mark.parametrize("status", [False, True])
def test_motor_journal_is_an_intent_only_with_native_event_uid(
    client, event, uid, status
):
    p = replay(
        client,
        "motor_error",
        {"event_index": event, "final_error": error(status, -42, "scenario")},
    ).json["result"]
    assert p["journal_written"] is False
    if status:
        assert p["journal_intent"]["node_uid"] == uid
        assert dict(p["journal_intent"]["arguments"]) == {
            "text": "Erreur N° -42 : scenario",
            "path": "c:\\Erreurs.xls",
            "local_journal": "Journal des erreurs",
        }
    else:
        assert p["journal_intent"] is None


@pytest.mark.parametrize(
    "stage,steps,high,low",
    [
        ("CHANNEL3_X", 10, 2, 10),
        ("CHANNEL3_Y", 10, 9, 1),
        ("CHANNEL2_X", 3, 10, 2),
        ("CHANNEL2_Y", 3, 9, 1),
    ],
)
@pytest.mark.parametrize("coordinate", [248.999, 249, 250, 251, 251.001])
@pytest.mark.parametrize("stop,motor_error", product([False, True], repeat=2))
def test_autotune_matrix_and_stop_not_becoming_a_pre_move_guard(
    client, stage, steps, high, low, coordinate, stop, motor_error
):
    p = replay(
        client,
        "autotune_iteration",
        {
            "stage": stage,
            "coordinate": coordinate,
            "stop_motor": stop,
            "motor_error": motor_error,
        },
    ).json["result"]
    inside = 249 <= coordinate <= 251
    assert p["above"] is (coordinate > 251)
    assert p["below"] is (coordinate < 249)
    assert p["in_band"] is inside
    assert p["terminate_inner_loop"] is (inside or stop or motor_error)
    assert (p["move_intent"] is None) is inside
    assert p["pre_move_stop_guard"] is False
    assert p["wait_ms"] == 3000
    assert p["freshness_after_wait_proven"] is False
    assert p["maximum_iterations"] is None
    if not inside:
        args = dict(p["move_intent"]["arguments"])
        assert args["Relative Steps"] == steps
        assert args["true_connector_index"] == (high if coordinate > 251 else low)
        assert args["stop motor"] is stop
        assert args["other_boolean_defaults"] == "unqualified"


@pytest.mark.parametrize("a,b,stop", product([False, True], repeat=3))
def test_outer_autotune_is_y_only_and_not_a_physical_success(client, a, b, stop):
    p = replay(
        client,
        "autotune_outer",
        dict(channel3_y_in_band=a, channel2_y_in_band=b, stop_motor=stop),
    ).json["result"]
    assert p["terminate_outer_loop"] is ((a and b) or stop)
    assert p["uses_x_convergence"] is False
    assert p["uses_motor_error"] is False
    assert p["physical_alignment_observed"] is False
    assert p["loop_executed"] is False


def test_autotune_plan_is_incomplete_and_completion_journal_is_not_success(client):
    p = replay(client, "autotune_plan", {}).json["result"]
    assert p["stage_order"] == [
        "camera channel 3",
        "channel 3 X",
        "channel 3 Y",
        "camera channel 2",
        "channel 2 X",
        "channel 2 Y",
    ]
    assert p["complete_runtime"] is False
    assert not any(patch["node_uid"] == 89678 for patch in p["entry_patches"])
    assert dict(p["completion_journal"]["arguments"])["success_guard"] is False
    assert p["completion_journal"]["external_effects_blocked"] is True


@pytest.mark.parametrize("channel", [2, 3])
@pytest.mark.parametrize("status", [False, True])
def test_autotune_camera_eight_barriers_error_busy_and_no_skip_guard(
    client, channel, status
):
    p = replay(
        client,
        "autotune_camera",
        {"channel": channel, "final_error": error(status, 4, "camera")},
    ).json["result"]
    assert [f["index"] for f in p["frames"]] == list(range(8))
    assert p["requested_channel"] == channel
    waits = [
        (f["index"], dict(e["arguments"])["ms"])
        for f in p["frames"]
        for e in f["effects"]
        if e["operation"] == "Wait (ms)"
    ]
    assert waits == [(1, 500), (3, 500), (7, 3000)]
    patches = p["frames"][6]["ui_patches"]
    assert [patch["control"] for patch in patches] == (["TER"] if status else ["Wait"])
    assert p["camera_error_skips_following_motion_stages"] is False


@pytest.mark.parametrize(
    "operation,data,field",
    [
        (
            "motor_jog_poll",
            dict(
                event_index=28,
                motion_done=False,
                motion_done_error=error(),
                stop_motor=False,
                position_result=0,
            ),
            "motion_done",
        ),
        (
            "motor_jog_poll",
            dict(
                event_index=28,
                motion_done=False,
                motion_done_error=error(),
                stop_motor=False,
                position_result=0,
            ),
            "stop_motor",
        ),
        (
            "autotune_iteration",
            dict(
                stage="CHANNEL3_X", coordinate=250, stop_motor=False, motor_error=False
            ),
            "stop_motor",
        ),
        (
            "autotune_iteration",
            dict(
                stage="CHANNEL3_X", coordinate=250, stop_motor=False, motor_error=False
            ),
            "motor_error",
        ),
        (
            "autotune_outer",
            dict(channel3_y_in_band=False, channel2_y_in_band=False, stop_motor=False),
            "channel3_y_in_band",
        ),
        (
            "autotune_outer",
            dict(channel3_y_in_band=False, channel2_y_in_band=False, stop_motor=False),
            "channel2_y_in_band",
        ),
        (
            "autotune_outer",
            dict(channel3_y_in_band=False, channel2_y_in_band=False, stop_motor=False),
            "stop_motor",
        ),
    ],
)
@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_motion_boolean_scenarios_cannot_be_coerced(
    client, operation, data, field, value
):
    assert replay(client, operation, data | {field: value}).status_code == 400


@pytest.mark.parametrize("stage", [None, 1, True, "CHANNEL1_X", "channel3_x", [], {}])
def test_autotune_stage_is_explicit_and_no_default_is_executed(client, stage):
    assert (
        replay(
            client,
            "autotune_iteration",
            dict(stage=stage, coordinate=250, stop_motor=False, motor_error=False),
        ).status_code
        == 400
    )


@pytest.mark.parametrize("coordinate", [None, True, "250", [], {}])
def test_centroid_is_not_an_implicit_or_coerced_measurement(client, coordinate):
    assert (
        replay(
            client,
            "autotune_iteration",
            dict(
                stage="CHANNEL2_X",
                coordinate=coordinate,
                stop_motor=False,
                motor_error=False,
            ),
        ).status_code
        == 400
    )


@pytest.mark.parametrize("channel", [True, None, 2.0, "2", 0, 1, 4])
def test_camera_channel_never_takes_unknown_native_default(client, channel):
    assert (
        replay(
            client, "autotune_camera", {"channel": channel, "final_error": error()}
        ).status_code
        == 400
    )


NEW_OPERATIONS = {
    "motor_initialization": {"discovered_key": "symbolic-only"},
    "motor_jog": {
        "control_label": "Move forward X",
        "motor_numbers": [3, 4],
        "relative_steps": 10,
    },
    "motor_jog_poll": dict(
        event_index=28,
        motion_done=False,
        motion_done_error=error(True),
        stop_motor=True,
        position_result=5,
    ),
    "motor_error": {"event_index": 27, "final_error": error(True, -1, "source")},
    "autotune_plan": {},
    "autotune_iteration": dict(
        stage="CHANNEL3_X", coordinate=252, stop_motor=True, motor_error=True
    ),
    "autotune_outer": dict(
        channel3_y_in_band=False, channel2_y_in_band=False, stop_motor=False
    ),
    "autotune_camera": {"channel": 2, "final_error": error(True, 1, "source")},
}


@pytest.mark.parametrize("operation,data", NEW_OPERATIONS.items())
def test_all_new_routes_remain_closed_intent_replays(client, operation, data):
    assert (
        replay(
            client, operation, data | {"execute": True, "target": "10.20.30.10"}
        ).status_code
        == 400
    )
    body = replay(client, operation, data).json
    assert body["execution_allowed"] is False
    assert body["physical_status"] == "NOT_EXECUTED"
    assert body["input_origin"] == "OPERATOR_SUPPLIED_REPLAY"
    assert body["result"]["external_effects_blocked"] is True


def test_motion_planners_do_not_open_network_files_drivers_or_wait(monkeypatch):
    for name in ("motion_events", "autotune_events", "fw102x_errors"):
        service.model(name)

    def prohibited(*args, **kwargs):
        pytest.fail("Motion replay attempted an external effect")

    with monkeypatch.context() as blocked:
        blocked.setattr(builtins, "open", prohibited)
        blocked.setattr(Path, "open", prohibited)
        blocked.setattr(socket, "socket", prohibited)
        blocked.setattr(time, "sleep", prohibited)
        for operation, data in NEW_OPERATIONS.items():
            body = service.replay({"operation": operation, "inputs": data})
            assert body["execution_allowed"] is False


def test_removed_shot_features_are_not_hardware_routes(client):
    snapshot = client.get("/api/elyse/supervision").json
    assert snapshot["excluded_ui_features"] == [
        "TIR",
        "PRE-TIR",
        "VEILLE",
        "ARRÊT",
        "LOAD TIR",
        "SAVE TIR",
        "STOP",
        "LOAD",
        "VALIDER LOAD",
        "Tree",
    ]
    for operation in (
        "tir",
        "pre_tir",
        "veille",
        "arret",
        "load_tir",
        "save_tir",
        "stop",
    ):
        assert replay(client, operation, {}).status_code == 400
