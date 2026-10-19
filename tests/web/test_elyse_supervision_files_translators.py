"""Bounded file/translator plans retain native branches without executing I/O."""

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
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-files-translators")
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def replay(client, operation, inputs):
    return client.post(
        "/api/elyse/supervision/replay", json={"operation": operation, "inputs": inputs}
    )


def load_inputs(**changes):
    return (
        dict(
            new_value=True,
            path_state="VALID",
            cached_directory="opaque-nonexistent-directory",
            dialog_directory=None,
        )
        | changes
    )


@pytest.mark.parametrize(
    "selection,field_count,wait_frame", [(1, 2, 0), (2, 4, 1), (3, 4, 1), (4, 4, 1)]
)
def test_translator_selection_keeps_selected_fields_and_wait_races(
    client, selection, field_count, wait_frame
):
    body = replay(client, "translator_selection", {"selection": selection}).json
    result = body["result"]
    assert len(result["assignments"]) == field_count
    assert all(value is True for _, value in result["assignments"])
    assert result["commands_position"] is False
    assert result["switches_other_cameras_off"] is False
    assert result["external_effects_blocked"] is True
    assert body["execution_allowed"] is False
    assert [f["index"] for f in result["frames"]] == [0, 1]
    waits = [
        (f["index"], dict(effect["arguments"])["ms"])
        for f in result["frames"]
        for effect in f["effects"]
        if effect["operation"] == "Wait (ms)"
    ]
    assert waits == [(wait_frame, 2000)]
    assert "does NOT serialize" in result["frames"][1]["note"]
    assert result["frames"][0]["ui_patches"][0]["value"] == [7171459, 7171459]
    assert result["frames"][1]["ui_patches"][0]["value"] == [12171705, 12171705]


@pytest.mark.parametrize("value", [True, False, None, "1", 1.0, 0, 5, -1, [], {}])
def test_translator_selection_never_emulates_an_unknown_default(client, value):
    assert (
        replay(client, "translator_selection", {"selection": value}).status_code == 400
    )


def test_translator_stop_retains_unmapped_visual_and_unknown_numeric_destination(
    client,
):
    result = replay(client, "translator_stop", {}).json["result"]
    assert result["implementation_allowed"] is False
    assert result["visual_frame_mapping_status"] == "UNMAPPED"
    assert result["manual_capture_shows_default"] is True
    assert result["lvkit_reports_default"] is False
    assert result["extracted_copy_matches_evidence_source"] is False
    frames = result["frames"]
    assert [f["index"] for f in frames] == [0, 1, 2, 3]
    start = frames[0]["shared_variable_write"]["assignments"]
    release = frames[3]["shared_variable_write"]["assignments"]
    assert len(start) == len(release) == 11
    assert [p["field"] for p in start] == [p["field"] for p in release]
    assert all(p["value"] is False for p in release)
    positions = frames[1]["shared_variable_write"]
    assert positions["psp_url"] is None
    assert [p["value"] for p in positions["assignments"]] == [2.126] * 3
    for index in (0, 1, 3):
        assert (
            frames[index]["shared_variable_write"]["external_effects_blocked"] is True
        )
    assert frames[2]["polling_selector"]["termination_semantics"] == "NATIVE_UNVERIFIED"


@pytest.mark.parametrize("iteration", [1200, 1201])
@pytest.mark.parametrize("values", list(product([22.6, 22.7, 22.8], repeat=3)))
def test_polling_thresholds_are_strict_and_never_become_a_stop_decision(
    client, iteration, values
):
    inputs = dict(
        iteration=iteration,
        position_miroir_laser=values[0],
        etat_t1=values[1],
        etat_mlaser_en=values[2],
    )
    result = replay(client, "translator_loop_selector", inputs).json["result"]
    assert result["expression_value"] is (
        iteration > 1200 or all(v < 22.7 for v in values)
    )
    assert result["termination_semantics"] == "NATIVE_UNVERIFIED"
    assert result["establishes_safe_state"] is False
    assert result["polling_loop_executed"] is False
    assert result["elapsed_time_guarantee"] is None
    assert "stop_decision" not in result


@pytest.mark.parametrize(
    "name", ["iteration", "position_miroir_laser", "etat_t1", "etat_mlaser_en"]
)
@pytest.mark.parametrize("value", [True, None, "22.7", [], {}])
def test_polling_rejects_implicit_values(client, name, value):
    inputs = dict(
        iteration=1200, position_miroir_laser=22.7, etat_t1=22.7, etat_mlaser_en=22.7
    )
    inputs[name] = value
    assert replay(client, "translator_loop_selector", inputs).status_code == 400


@pytest.mark.parametrize("value", [1.0, 1.5])
def test_polling_iteration_is_an_integer(client, value):
    assert (
        replay(
            client,
            "translator_loop_selector",
            dict(iteration=value, position_miroir_laser=0, etat_t1=0, etat_mlaser_en=0),
        ).status_code
        == 400
    )


def test_load_off_closes_only_the_described_reference(client):
    result = replay(
        client,
        "load_toggle",
        load_inputs(new_value=False, path_state=None, cached_directory=None),
    ).json["result"]
    assert result["active"] is False
    assert [e["operation"] for e in result["effects"]] == [
        "Close Reference",
        "Simple Error Handler.vi",
    ]
    assert [p["value"] for p in result["ui_patches"]] == [2, 0]
    assert result["hardware_commands"] == []


@pytest.mark.parametrize(
    "path", ["not-real", "", "../../opaque", "\\\\10.20.30.10\\never-connect"]
)
def test_valid_load_uses_opaque_cache_without_filesystem_validation(client, path):
    result = replay(
        client,
        "load_toggle",
        load_inputs(cached_directory=path, dialog_directory="unused"),
    ).json["result"]
    assert result["dialog_required"] is False
    assert result["selected_directory"] == path
    assert [e["operation"] for e in result["effects"]] == [
        "Init_Open_Close.vi",
        "Simple Error Handler.vi",
    ]


@pytest.mark.parametrize("state", ["EMPTY", "NOT_A_PATH"])
@pytest.mark.parametrize("path", [None, "", "provided-opaque-directory"])
def test_load_distinguishes_pending_and_empty_dialog_without_cancel_guard(
    client, state, path
):
    result = replay(
        client, "load_toggle", load_inputs(path_state=state, dialog_directory=path)
    ).json["result"]
    assert result["dialog_required"] is True
    assert result["selected_directory"] == path
    operations = [e["operation"] for e in result["effects"]]
    assert operations == (
        ["File Dialog"]
        if path is None
        else ["File Dialog", "Init_Open_Close.vi", "Simple Error Handler.vi"]
    )
    if path is not None:
        assert result["ui_patches"][0]["value"] == path
    assert result["hardware_commands"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"new_value": 1},
        {"new_value": None},
        {"path_state": None},
        {"path_state": "valid"},
        {"path_state": True},
        {"cached_directory": None},
        {"cached_directory": 0},
        {"dialog_directory": []},
    ],
)
def test_load_rejects_unresolved_or_coerced_contract_inputs(client, changes):
    assert replay(client, "load_toggle", load_inputs(**changes)).status_code == 400


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("tag", ["", "opaque-not-existing", "../../no-read"])
def test_validate_load_discards_reads_and_does_not_apply_presets(client, active, tag):
    result = replay(
        client, "validate_load", {"new_value": active, "current_tag": tag}
    ).json["result"]
    assert result["reset_value"] is False
    assert result["read_outputs_consumed"] is False
    assert result["equipment_updates"] == []
    assert result["external_effects_blocked"] is True
    if not active:
        assert result["frames"] == []
    else:
        reads = result["frames"][0]["effects"]
        assert [dict(e["arguments"])["count"] for e in reads] == list(range(10))
        assert all(dict(e["arguments"])["path_string"] == tag for e in reads)
        assert all(dict(e["arguments"])["output_consumed"] is False for e in reads)
        assert (
            result["frames"][1]["ui_patches"][0]["value"] == "Tree Cell String result"
        )


@pytest.mark.parametrize("status", [False, True])
@pytest.mark.parametrize("tag", ["", "external-variant-result"])
def test_tree_tag_is_retained_even_on_error(client, status, tag):
    result = replay(
        client,
        "tree_selection",
        {
            "variant_string_result": tag,
            "final_error": {"status": status, "code": 44, "source": "source"},
        },
    ).json["result"]
    assert result["current_tag"] == tag
    assert result["tag_written_even_on_error"] is True
    expected = service.model("load_events").TREE_ERROR + "source" if status else None
    assert result["ter_text"] == expected


@pytest.mark.parametrize(
    "name,value",
    [
        ("status", 0),
        ("status", None),
        ("code", True),
        ("code", 2**31),
        ("code", 0.0),
        ("source", None),
    ],
)
def test_tree_never_manufactures_external_error_success(client, name, value):
    error = dict(status=False, code=0, source="") | {name: value}
    assert (
        replay(
            client,
            "tree_selection",
            {"variant_string_result": "tag", "final_error": error},
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "operation,inputs",
    [
        ("translator_selection", {"selection": 1}),
        ("translator_stop", {}),
        (
            "translator_loop_selector",
            dict(iteration=0, position_miroir_laser=1, etat_t1=2, etat_mlaser_en=3),
        ),
        ("load_toggle", load_inputs()),
        ("validate_load", {"new_value": True, "current_tag": "tag"}),
        (
            "tree_selection",
            {
                "variant_string_result": "tag",
                "final_error": {"status": False, "code": 0, "source": ""},
            },
        ),
    ],
)
def test_new_operations_have_exact_closed_contracts(client, operation, inputs):
    assert replay(client, operation, inputs | {"execute": True}).status_code == 400
    body = replay(client, operation, inputs).json
    assert body["input_origin"] == "OPERATOR_SUPPLIED_REPLAY"
    assert body["physical_status"] == "NOT_EXECUTED"
    assert body["execution_allowed"] is False


def test_replay_models_never_read_write_sleep_or_open_network(monkeypatch):
    # Load source modules before guarding I/O; import is not equipment access.
    for module in (
        "translator_selection",
        "translator_stop",
        "load_events",
        "fw102x_errors",
    ):
        service.model(module)

    def forbidden(*args, **kwargs):
        pytest.fail("A static replay attempted external I/O or sleep")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(Path, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(time, "sleep", forbidden)
        for operation, inputs in (
            ("translator_selection", {"selection": 1}),
            ("translator_stop", {}),
            (
                "translator_loop_selector",
                dict(
                    iteration=1201,
                    position_miroir_laser=23,
                    etat_t1=23,
                    etat_mlaser_en=23,
                ),
            ),
            ("load_toggle", load_inputs(path_state="EMPTY", dialog_directory="opaque")),
            ("validate_load", {"new_value": True, "current_tag": "no-read"}),
            (
                "tree_selection",
                {
                    "variant_string_result": "tag",
                    "final_error": {"status": True, "code": 1, "source": "scenario"},
                },
            ),
        ):
            assert (
                service.replay({"operation": operation, "inputs": inputs})[
                    "execution_allowed"
                ]
                is False
            )


@pytest.mark.parametrize("value", [None, True, 1, [], {}])
@pytest.mark.parametrize(
    "operation,field,inputs",
    [
        ("validate_load", "current_tag", {"new_value": True, "current_tag": "tag"}),
        (
            "tree_selection",
            "variant_string_result",
            {
                "variant_string_result": "tag",
                "final_error": {"status": False, "code": 0, "source": ""},
            },
        ),
    ],
)
def test_external_tree_strings_are_not_coerced(client, value, operation, field, inputs):
    assert replay(client, operation, inputs | {field: value}).status_code == 400


@pytest.mark.parametrize("value", [None, 0, 1, "true"])
def test_validate_load_newval_is_boolean(client, value):
    assert (
        replay(
            client, "validate_load", {"new_value": value, "current_tag": "tag"}
        ).status_code
        == 400
    )


def test_save_tir_is_not_fabricated(client):
    assert replay(client, "save_tir", {}).status_code == 400
    snapshot = client.get("/api/elyse/supervision").json
    assert snapshot["file_controls"]["load_applies_equipment_preset"] is False
    assert snapshot["file_controls"]["save_tir_model_status"] == "EXCLUDED_BY_USER"
    assert snapshot["file_controls"]["filesystem_access_performed"] is False
