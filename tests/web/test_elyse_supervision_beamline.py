"""Beamline web replay preserves native arithmetic, branching and frame races."""

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
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-beamline-secret")
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def replay(client, operation, inputs):
    return client.post(
        "/api/elyse/supervision/replay", json={"operation": operation, "inputs": inputs}
    )


@pytest.mark.parametrize("axe,gap", [(0, 0), (2, 10), (-5, 3), (1e6, -1e6)])
def test_slits_keep_native_formula_without_invented_units_or_limits(client, axe, gap):
    body = replay(client, "slit_position", {"axe_h": axe, "gap_h": gap}).json
    result = body["result"]
    assert result["position_hg"] == pytest.approx(5 + 0.0979 * axe - 0.049 * gap)
    assert result["position_hd"] == pytest.approx(5 - 0.0979 * axe - 0.049 * gap)
    assert result["preserves_unmentioned_fields"] is True
    assert result["local_and_psp_sink_order_serialized"] is False
    assert result["external_effects_blocked"] is True
    assert result["evidence"]["extracted_copy_matches_evidence_source"] is False
    assert body["execution_allowed"] is False


@pytest.mark.parametrize("value", [None, True, "2", [], {}])
def test_slits_reject_implicit_or_coerced_numbers(client, value):
    assert (
        replay(client, "slit_position", {"axe_h": value, "gap_h": 0}).status_code == 400
    )


@pytest.mark.parametrize("station", ["T1", "T2", "T3"])
@pytest.mark.parametrize("selector,expected", [(0, 2.126), (1, 8.98), (2, 5.553)])
def test_diagnostics_preserve_three_constants_and_display_multiplier(
    client, station, selector, expected
):
    result = replay(
        client, "diagnostic_position", {"station": station, "selector": selector}
    ).json["result"]
    assert result["legacy_command_value"] == expected
    assert result["display_value"] == expected * 10
    assert result["evidence"]["visible_default_label"] == "0, Default"
    assert result["establishes_physical_position"] is False
    assert result["acknowledgement_observed"] is False


@pytest.mark.parametrize("selector", [True, False, None, "0", 1.0, -1, 3, 65535])
def test_unknown_diagnostic_selectors_do_not_emulate_motion_inducing_default(
    client, selector
):
    assert (
        replay(
            client, "diagnostic_position", {"station": "T1", "selector": selector}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("station", [None, 1, True, "T4", "Laser"])
def test_diagnostic_station_is_explicit(client, station):
    assert (
        replay(
            client, "diagnostic_position", {"station": station, "selector": 0}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("station", [1, 2, 3])
@pytest.mark.parametrize("new_value", [False, True])
def test_faraday_position_keeps_boolean_noop_or_dedicated_pulse_frame(
    client, station, new_value
):
    result = replay(
        client,
        "faraday_position",
        {"station": station, "new_value": new_value, "frame_snapshots": None},
    ).json["result"]
    assert result["event_case_index"] == station + 8
    if not new_value:
        assert result["frames"] == []
        assert result["sequence_uid"] is None
    else:
        frames = result["frames"]
        field = service.model("digital_command_events").FARADAY_FIELDS[station - 1]
        assert frames[0]["patches"] == [[field, True]]
        assert frames[1]["waits_ms"] == [500]
        assert frames[2]["patches"] == [[field, False]]
        assert len(frames[2]["ui_assignments"]) == 3
        assert [f["fresh_local_cluster_read_required"] for f in frames] == [
            True,
            False,
            True,
        ]
        assert all(f["projected_cluster"] is None for f in frames)
    assert result["projection_origin"] == "UNRESOLVED_LOCAL_READS"
    assert result["exact_physical_pulse_width_proven"] is False
    assert result["later_frames_conditioned_on_success"] is False


@pytest.mark.parametrize("states", list(product([False, True], repeat=3)))
def test_faraday_arret_inverts_all_three_supplied_en_inputs_not_a_safety_stop(
    client, states
):
    result = replay(
        client,
        "faraday_tab",
        {"new_value": 0, "en_states": list(states), "frame_snapshots": None},
    ).json["result"]
    assert [v for _, v in result["frames"][0]["patches"]] == [not s for s in states]
    assert [v for _, v in result["frames"][1]["patches"]] == [False] * 3
    assert [f["waits_ms"] for f in result["frames"]] == [[500], [], [500]]
    assert result["dedicated_pulse_wait_frame"] is False
    assert result["establishes_physical_state"] is False
    assert all(
        f["operations_within_frame_serialized"] is False for f in result["frames"]
    )


@pytest.mark.parametrize("selector", [1, 2, 3])
def test_faraday_passive_tabs_do_not_release_or_reset_any_output(client, selector):
    result = replay(
        client,
        "faraday_tab",
        {"new_value": selector, "en_states": None, "frame_snapshots": None},
    ).json["result"]
    assert result["frames"] == []


@pytest.mark.parametrize(
    "states", [None, [], [False], [0, 0, 0], [False, None, True], "000"]
)
def test_faraday_arret_requires_explicit_boolean_en_states(client, states):
    assert (
        replay(
            client,
            "faraday_tab",
            {"new_value": 0, "en_states": states, "frame_snapshots": None},
        ).status_code
        == 400
    )


@pytest.mark.parametrize("selector", [0, 1])
def test_mirror_has_distinct_en_hors_fields_and_dedicated_1000ms_frame(
    client, selector
):
    result = replay(
        client, "laser_mirror", {"new_value": selector, "frame_snapshots": None}
    ).json["result"]
    field = service.model("digital_command_events").MIRROR_FIELDS[selector]
    assert result["frames"][0]["patches"] == [[field, True]]
    assert result["frames"][1]["waits_ms"] == [1000]
    assert result["frames"][2]["patches"] == [[field, False]]
    assert result["dedicated_pulse_wait_frame"] is True


@pytest.mark.parametrize("selector", [0, 1])
def test_slit_supply_is_not_misconverted_to_a_pulse(client, selector):
    result = replay(
        client, "slit_supply", {"new_value": selector, "frame_snapshots": None}
    ).json["result"]
    assert result["frames"][0]["patches"][0][1] == bool(selector)
    assert [f["waits_ms"] for f in result["frames"]] == [[500], [500]]
    assert result["frames"][1]["patches"] == []
    assert result["dedicated_pulse_wait_frame"] is False
    assert all(
        f["operations_within_frame_serialized"] is False for f in result["frames"]
    )


def test_later_projection_uses_its_own_snapshot_preserving_intervening_writer(client):
    module = service.model("digital_command_events")
    en, hors = module.MIRROR_FIELDS
    first = {en: False, hors: True, "unrelated": False}
    later = {en: True, hors: True, "unrelated": True}
    result = replay(
        client,
        "laser_mirror",
        {
            "new_value": 0,
            "frame_snapshots": [
                {"frame_index": 0, "cluster": first},
                {"frame_index": 2, "cluster": later},
            ],
        },
    ).json["result"]
    assert result["frames"][0]["projected_cluster"] == {
        en: True,
        hors: True,
        "unrelated": False,
    }
    assert result["frames"][2]["projected_cluster"] == {
        en: False,
        hors: True,
        "unrelated": True,
    }
    assert first["unrelated"] is False and later["unrelated"] is True
    assert result["cluster_freshness_verified"] is False
    assert result["coherent_sampling_verified"] is False
    assert result["live_cluster_read_performed"] is False


@pytest.mark.parametrize(
    "snapshots",
    [
        {},
        [],
        [{"frame_index": 0, "cluster": {}}],
        [{"frame_index": 0, "cluster": {}}, {"frame_index": 0, "cluster": {}}],
        [{"frame_index": 0, "cluster": {}}, {"frame_index": 1, "cluster": {}}],
        [{"frame_index": False, "cluster": {}}, {"frame_index": 2, "cluster": {}}],
        [{"frame_index": 0, "cluster": {"a": 0}}, {"frame_index": 2, "cluster": {}}],
        [
            {"frame_index": 0, "cluster": {f"a{i}": False for i in range(129)}},
            {"frame_index": 2, "cluster": {}},
        ],
        [
            {"frame_index": 0, "cluster": {}, "execute": True},
            {"frame_index": 2, "cluster": {}},
        ],
        [{"frame_index": 0, "cluster": {}}, {"frame_index": 2, "cluster": {}}],
    ],
)
def test_frame_snapshots_reject_missing_fields_duplicates_wait_frames_and_coercion(
    client, snapshots
):
    assert (
        replay(
            client, "laser_mirror", {"new_value": 0, "frame_snapshots": snapshots}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, 0, 4])
def test_faraday_station_cannot_use_intenum_boolean_or_float_coercion(client, value):
    assert (
        replay(
            client,
            "faraday_position",
            {"station": value, "new_value": True, "frame_snapshots": None},
        ).status_code
        == 400
    )


@pytest.mark.parametrize("operation", ["laser_mirror", "slit_supply"])
@pytest.mark.parametrize("value", [True, "0", 1.0, None, -1, 2])
def test_digital_selectors_reject_unknown_native_defaults(client, operation, value):
    assert (
        replay(
            client, operation, {"new_value": value, "frame_snapshots": None}
        ).status_code
        == 400
    )


def test_centroid_reset_preserves_three_ordered_steps_without_claiming_buffer_reset(
    client,
):
    result = replay(client, "centroid_reset", {}).json["result"]
    assert [
        (s["frame_index"], s["value"], s["observed_wait_ms"]) for s in result["steps"]
    ] == [(0, True, None), (1, None, 200), (2, False, None)]
    assert result["establishes_consumer_reset"] is False
    assert result["event_new_value_consumed"] is False
    assert replay(client, "centroid_reset", {"new_value": True}).status_code == 400


def test_all_new_routes_are_pure_no_file_socket_wait_or_hardware_target(
    client, monkeypatch
):
    client.get(
        "/api/elyse/supervision"
    )  # Import domain models before blocking effects.
    operations = {
        "slit_position": {"axe_h": 2, "gap_h": 10},
        "diagnostic_position": {"station": "T2", "selector": 2},
        "faraday_position": {"station": 2, "new_value": True, "frame_snapshots": None},
        "faraday_tab": {
            "new_value": 0,
            "en_states": [False, True, False],
            "frame_snapshots": None,
        },
        "laser_mirror": {"new_value": 1, "frame_snapshots": None},
        "slit_supply": {"new_value": 1, "frame_snapshots": None},
        "centroid_reset": {},
    }

    def prohibited(*args, **kwargs):
        raise AssertionError("Beamline replay attempted an external effect")

    with monkeypatch.context() as blocked:
        blocked.setattr(builtins, "open", prohibited)
        blocked.setattr(Path, "open", prohibited)
        blocked.setattr(socket, "create_connection", prohibited)
        blocked.setattr(time, "sleep", prohibited)
        for name, inputs in operations.items():
            response = replay(client, name, inputs)
            assert response.status_code == 200, response.json
            assert response.json["physical_status"] == "NOT_EXECUTED"
            assert response.json["result"]["external_effects_blocked"] is True
            forged = dict(inputs, execute=True, target="10.20.30.10")
            assert replay(client, name, forged).status_code == 400
