"""Actual Python model invocation through Flask; no accelerator adapter."""

import base64
import importlib
import json
import sys
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("elyse_supervision_api")
service = importlib.import_module("elyse_supervision_service")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    instance = Flask(__name__)
    instance.config.update(TESTING=True, JWT_SECRET_KEY="test-only-elyse-replay-secret")
    JWTManager(instance)
    instance.register_blueprint(api.elyse_supervision_api)
    return instance


def request(client, operation, inputs):
    return client.post(
        "/api/elyse/supervision/replay",
        json={
            "operation": operation,
            "inputs": inputs,
        },
    )


def dps():
    return dict.fromkeys(service.model("page_command_events").DPS_FIELDS, False)


def camera_error(status=False):
    return {"status": status, "code": 44 if status else 0, "source": "supplied source"}


@pytest.mark.parametrize("mask", range(64))
def test_video_tools_cover_all_native_masks_without_dispatch(app, mask):
    body = request(
        app.test_client(),
        "video_tools",
        {
            "values": [bool(mask & (1 << i)) for i in range(6)],
            "final_property_error": camera_error(),
        },
    ).json
    result = body["result"]
    assert result["mask"] == mask
    assert result["selected_case"] == (mask if mask in (1, 2, 4, 8, 16, 32) else 0)
    assert result["reset_tools"] == [False] * 6
    assert [patch["value"] for patch in result["center_properties"]] == [250, 250]
    assert result["delay_ms"] is None
    assert result["external_effects_blocked"] is True
    assert body["physical_status"] == "NOT_EXECUTED"
    if mask in (1, 2, 4, 8):
        assert [patch["value"] for patch in result["branch_properties"]] == [
            {1: 0.5, 2: 1, 4: 2, 8: 4}[mask]
        ] * 4
    elif mask in (16, 32):
        assert result["branch_properties"][0]["value"]["global_rectangle"] == (
            [200, 200, 300, 300] if mask == 16 else [0, 0, 0, 0]
        )
    else:
        assert result["branch_properties"] == []


@pytest.mark.parametrize(
    "operation,index,waits",
    [
        ("camera_thresholds", 24, [300, 50]),
        ("camera_channel", 25, [500, 500]),
    ],
)
@pytest.mark.parametrize("status", [False, True])
def test_camera_sequences_preserve_error_and_wait_semantics(
    app, operation, index, waits, status
):
    result = request(
        app.test_client(),
        operation,
        {
            "final_error": camera_error(status),
            "formatted_text": None,
        },
    ).json["result"]
    assert result["event_index"] == index
    assert [
        dict(effect["arguments"])["ms"]
        for frame in result["frames"]
        for effect in frame["effects"]
        if effect["operation"] == "Wait (ms)"
    ] == waits
    wait_resets = [
        p["value"] for p in result["final_patches"] if p["control"] == "Wait"
    ]
    assert wait_resets == ([] if operation == "camera_channel" and status else [False])
    assert not any(p["control"] == "TME" for p in result["final_patches"])
    assert (result["ter_text"] is not None) == status
    assert result["external_effects_blocked"] is True
    if operation == "camera_channel":
        assert result["pre_sequence_patches"][0]["value"] is True
        assert result["frames"][2]["effects"][0]["operation"] == "Clear Errors.vi"
        assert (
            "NOT Event NewVal"
            in dict(result["frames"][3]["effects"][1]["arguments"])["channel"]
        )


@pytest.mark.parametrize("status", [False, True])
def test_camera_formatter_is_supplied_not_synthesized(app, status):
    result = request(
        app.test_client(),
        "camera_channel",
        {
            "final_error": camera_error(status),
            "formatted_text": "externally supplied text",
        },
    ).json["result"]
    tme = [p["value"] for p in result["final_patches"] if p["control"] == "TME"]
    assert tme == ([] if status else ["externally supplied text"])


@pytest.mark.parametrize(
    "error",
    [
        None,
        {},
        {"status": False, "code": 0},
        {"status": 0, "code": 0, "source": ""},
        {"status": False, "code": True, "source": ""},
        {"status": False, "code": 2**31, "source": ""},
        {"status": False, "code": -(2**31) - 1, "source": ""},
        {"status": False, "code": 0.0, "source": ""},
        {"status": False, "code": 0, "source": None},
        {"status": False, "code": 0, "source": "", "driver_success": True},
    ],
)
def test_camera_rejects_untyped_or_implicit_driver_result(app, error):
    assert (
        request(
            app.test_client(),
            "video_tools",
            {
                "values": [False] * 6,
                "final_property_error": error,
            },
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "values", [None, "000000", {}, [False] * 5, [False] * 7, [0] * 6]
)
def test_video_tools_reject_invalid_arrays(app, values):
    assert (
        request(
            app.test_client(),
            "video_tools",
            {
                "values": values,
                "final_property_error": camera_error(),
            },
        ).status_code
        == 400
    )


def test_camera_rejects_browser_threshold_and_channel_overrides(app):
    for operation in ("camera_thresholds", "camera_channel"):
        assert (
            request(
                app.test_client(),
                operation,
                {
                    "final_error": camera_error(),
                    "formatted_text": None,
                    "new_value": 3,
                },
            ).status_code
            == 400
        )
        assert (
            request(
                app.test_client(),
                operation,
                {
                    "final_error": camera_error(True),
                    "formatted_text": 123,
                },
            ).status_code
            == 400
        )


def test_density_stays_literal_false_even_in_web(app):
    result = request(app.test_client(), "video_density", {}).json["result"]
    assert result["selector"] is False
    assert result["reachable_effects"] == []
    assert (
        request(app.test_client(), "video_density", {"new_value": True}).status_code
        == 400
    )


@pytest.mark.parametrize("cancelled", [None, True, False])
def test_save_image_dialog_and_tiff_are_intents_not_file_access(
    app, monkeypatch, tmp_path, cancelled
):
    import builtins
    import socket
    import time

    selected = tmp_path / "must-not-be-created.tif"
    client = app.test_client()
    # Eagerly import the pure model before blocking all file/network/sleep access.
    service.model("video_events")

    def prohibited(*args, **kwargs):
        raise AssertionError("Replay attempted an external effect")

    with monkeypatch.context() as blocked:
        blocked.setattr(builtins, "open", prohibited)
        blocked.setattr(Path, "open", prohibited)
        blocked.setattr(socket, "create_connection", prohibited)
        blocked.setattr(time, "sleep", prohibited)
        body = request(
            client,
            "save_image",
            {
                "new_value": True,
                "resolved_year": 2026,
                "dialog_cancelled": cancelled,
                "selected_path": str(selected) if cancelled is False else None,
            },
        ).json
    result = body["result"]
    assert result["start_path"] == "Z:\\Manips\\Mesures\\2026"
    assert result["dialog_pending"] == (cancelled is None)
    assert len(result["prepare_effects"]) == 3
    assert len(result["write_effects"]) == (2 if cancelled is False else 0)
    if cancelled is False:
        assert result["write_effects"][1]["operation"] == "IMAQ Write TIFF File"
        args = dict(result["write_effects"][1]["arguments"])
        assert [
            args[k] for k in ("Rows Per Strip", "Photometric", "Compression Type")
        ] == [0, 1, 0]
    assert body["execution_allowed"] is False
    assert not selected.exists()


def test_save_image_false_is_noop_and_active_requires_explicit_year(app):
    inputs = {
        "new_value": False,
        "resolved_year": None,
        "dialog_cancelled": None,
        "selected_path": None,
    }
    result = request(app.test_client(), "save_image", inputs).json["result"]
    assert result["active"] is False
    assert result["prepare_effects"] == result["write_effects"] == []
    inputs["new_value"] = True
    assert request(app.test_client(), "save_image", inputs).status_code == 400


@pytest.mark.parametrize(
    "key,value",
    [
        ("new_value", 1),
        ("resolved_year", True),
        ("resolved_year", 2026.0),
        ("resolved_year", 2**31),
        ("dialog_cancelled", "false"),
        ("selected_path", 123),
    ],
)
def test_save_image_rejects_coercion(app, key, value):
    inputs = {
        "new_value": True,
        "resolved_year": 2026,
        "dialog_cancelled": False,
        "selected_path": "opaque.tif",
    }
    inputs[key] = value
    assert request(app.test_client(), "save_image", inputs).status_code == 400


def test_snapshot_exposes_actual_models_and_unavailable_telemetry(app):
    response = app.test_client().get("/api/elyse/supervision")
    assert response.status_code == 200
    body = response.json
    assert body["execution_allowed"] is False
    assert body["telemetry"] == {"quality": "UNAVAILABLE", "timestamp": None}
    assert len(body["registry"]["entries"]) == 21
    assert len(body["dps_fields"]) == 29
    assert len(body["coverage"]["events"]) == 34
    assert len(body["pages"]["hf"]["arrows"]) == 8
    assert sum(e["owner"] == "DEVICE_SERVER" for e in body["registry"]["entries"]) == 8
    assert all(
        e["telemetry"]["measured_a"] is None for e in body["registry"]["entries"]
    )
    assert response.headers["Cache-Control"] == "no-store"
    assert body["video_controls"]["tool_fields"] == [
        "zoom 0,5",
        "zoom x1",
        "zoom x2",
        "zoom x3",
        "250",
        "Clear 250",
    ]
    assert body["video_controls"]["image_quality"] == "UNAVAILABLE"
    assert len(body["replay_operations"]) == 86
    assert {"saved_acq_event_33620", "saved_sup_frequency"} <= set(body["replay_operations"])
    assert {"saved_acq_event_22879", "saved_sup_gain"} <= set(body["replay_operations"])
    assert {"saved_acq_event_26012", "saved_sup_position_t2"} <= set(body["replay_operations"])
    assert {"saved_acq_event_23449", "saved_sup_position_t3"} <= set(body["replay_operations"])
    assert {"saved_acq_event_34531", "saved_sup_event_30817"} <= set(body["replay_operations"])
    assert {"saved_acq_event_42457", "saved_sup_event_47072"} <= set(body["replay_operations"])
    assert {"saved_acq_event_40079", "saved_sup_event_53656"} <= set(body["replay_operations"])
    assert {"saved_acq_event_35942", "saved_sup_event_56943"} <= set(body["replay_operations"])
    assert {"saved_acq_event_23143", "saved_sup_event_23770"} <= set(body["replay_operations"])
    assert {"saved_acq_event_17899", "saved_sup_event_53772"} <= set(body["replay_operations"])
    assert {"saved_acq_event_37991", "saved_sup_event_23880"} <= set(body["replay_operations"])
    assert {"saved_acq_event_38732", "saved_sup_event_26490"} <= set(body["replay_operations"])
    assert {"saved_acq_event_23113", "saved_sup_event_5847"} <= set(body["replay_operations"])
    assert {"saved_acq_event_8896", "saved_sup_event_38707"} <= set(body["replay_operations"])
    assert {"saved_acq_event_48846", "saved_sup_event_33463"} <= set(body["replay_operations"])
    assert {"saved_acq_event_31552", "saved_sup_event_18780"} <= set(body["replay_operations"])
    assert {"saved_acq_event_43634", "saved_sup_event_53716"} <= set(body["replay_operations"])
    assert {"saved_acq_event_34191", "saved_sup_event_38030"} <= set(body["replay_operations"])
    assert {"saved_acq_event_45123", "saved_sup_event_65050"} <= set(body["replay_operations"])
    assert {"saved_card_init", "saved_sup_helper"} <= set(body["replay_operations"])
    assert "saved_numeric" in body["replay_operations"]
    assert "saved_psp_reads" in body["replay_operations"]
    assert "saved_sup_reads" in body["replay_operations"]
    assert "saved_stop" in body["replay_operations"]
    assert "saved_dispatch" in body["replay_operations"]
    assert "saved_requests" in body["replay_operations"]
    assert "saved_cleanup" in body["replay_operations"]
    assert "saved_initializer" in body["replay_operations"]
    assert "saved_ni6220" in body["replay_operations"]
    assert "saved_timing" in body["replay_operations"]
    assert "saved_xnode" in body["replay_operations"]
    assert body["beamline_controls"]["diagnostic_stations"] == ["T1", "T2", "T3"]
    assert body["beamline_controls"]["engineering_units_qualified"] is False
    assert body["translator_controls"]["stop_implementation_allowed"] is False
    assert body["file_controls"]["save_tir_model_status"] == "EXCLUDED_BY_USER"
    assert "STOP" in body["excluded_ui_features"]
    assert body["motion_controls"]["physical_motion_performed"] is False


def test_frequency_invokes_cluster_replacement_not_dispatch(app):
    body = request(app.test_client(), "machine_frequency", {"new_value": 5}).json
    assert body["physical_status"] == "NOT_EXECUTED"
    assert body["result"]["updated_cluster"]["replacements"] == [
        ["Fréquence ELYSE", 5],
        ["N° de la sélection (1 à 32): ", 4.0],
    ]
    assert len(body["result"]["sinks"]) == 3
    assert body["result"]["external_effects_blocked"] is True


@pytest.mark.parametrize("value", [True, 1.5, "5", None])
def test_frequency_rejects_coercion(app, value):
    assert (
        request(
            app.test_client(), "machine_frequency", {"new_value": value}
        ).status_code
        == 400
    )


def test_busy_dps_discards_modulator_command(app):
    module = service.model("page_command_events")
    inputs = {
        "page": module.CommandPage.MODULATOR.value,
        "current_dps": dps(),
        "newval": dict.fromkeys((s for s, _ in module.MODULATOR_FIELD_MAP), False),
    }
    inputs["newval"]["Marche MOD"] = True
    idle = request(app.test_client(), "page_command", inputs).json["result"]
    assert idle["projected_dps"] is not None
    assert idle["acquisition_preview"]["legacy_event_case"] == 5
    assert idle["acquisition_preview"]["acceptance_observed"] is False
    inputs["current_dps"][module.DPS_FIELDS[0]] = True
    busy = request(app.test_client(), "page_command", inputs).json["result"]
    assert busy["projected_dps"] is None
    assert busy["wait_ms"] == 0
    assert busy["acquisition_preview"]["state"] == "NO_NEW_DPS_WRITE"


@pytest.mark.parametrize(
    "rule",
    service.model("parameter_page_events").PARAMETER_RULES,
    ids=lambda rule: f"{rule.page.name}/{rule.mask}",
)
def test_parameter_arrow_reuses_original_rule_even_when_dps_busy(app, rule):
    module = service.model("parameter_page_events")
    selected = rule.page
    rules = [r for r in module.PARAMETER_RULES if r.page is selected]
    current = dps()
    current[next(iter(current))] = True
    inputs = {
        "page": selected.value,
        "current_dps": current,
        "arrows": {r.arrow: r is rule for r in rules},
        "procedures": dict.fromkeys(
            (s for s, _ in module.PROCEDURE_FIELD_MAPS[selected]), False
        ),
        "numeric_newval": {rule.numeric_field: 1.0},
    }
    response = request(app.test_client(), "parameter_page", inputs)
    assert response.status_code == 200
    result = response.json["result"]
    expected = 1.0 + rule.delta
    if rule.limits:
        expected = max(rule.limits[0], min(rule.limits[1], expected))
    assert result["projected_numeric"] == expected
    assert result["projected_dps"] is None
    assert result["external_effects_blocked"] is True


def test_magnet_plan_does_not_fall_back_to_retired_daqmx(app):
    registry = service.model("magnet_registry").candidate_registry()
    entry = next(e for e in registry.entries if e.retired_legacy)
    result = request(
        app.test_client(),
        "magnet_currents",
        {
            "idempotency_key": "test",
            "expected_revision": registry.revision,
            "requests": [{"equipment_id": entry.equipment_id, "current_a": 0.25}],
        },
    ).json["result"]
    assert result["physical_status"] == "NOT_EXECUTED"
    assert result["execution_allowed"] is False
    assert (
        result["plans"][0]["route"] is None
        or result["plans"][0]["route"]["owner"] != "LEGACY_ACQ"
    )


def test_synchronisation_identifies_native_changed_slot(app):
    old = [0.0] * 33
    new = old.copy()
    new[3] = 2.0
    response = request(
        app.test_client(),
        "synchronisation",
        {
            "current_dps": dps(),
            "oldval": old,
            "newval": new,
            "stored_flash_index": None,
        },
    )
    assert response.status_code == 200
    assert response.json["result"]["external_effects_blocked"] is True


def test_monitoring_retains_raw_deltas_and_literal_video_guard(app):
    current = dict(
        acq_auxiliary=9,
        acq_variables=9,
        acq_events=-9,
        sup_video=-99,
        sup_variables=9,
        sup_events=5,
    )
    result = request(
        app.test_client(),
        "monitoring",
        {
            "current": current,
            "previous": dict.fromkeys(current, 0),
            "finished_late_previous": False,
        },
    ).json["result"]
    assert result["deltas"]["sup_video"] == -99
    assert result["status"]["somme_monitoring"] is True
    assert result["is_physical_interlock"] is False
    assert len(result["mean_requests"]) == 7
    assert result["unit"] == "RAW_COUNTER_DELTA_NOT_HZ"


def test_display_flags_copy_raw_bits_not_safety_permission(app):
    c4 = [False] * 64
    c4[53] = True
    result = request(
        app.test_client(),
        "display_flags",
        {
            "c3": [False] * 56,
            "c4": c4,
            "eps": [False] * 77,
        },
    ).json["result"]
    assert result["radioprotection"]["Porte lourde"] is True
    assert result["is_physical_interlock"] is False
    assert result["electrical_polarity_qualified"] is False


def test_profiles_keep_threshold_and_independent_buffers(app):
    result = request(
        app.test_client(),
        "profiles",
        {
            "iteration": 0,
            "average_count": 2,
            "buffers": {"x": [[0, 0], [0, 0]], "y": [[0, 0], [0, 0]]},
            "x_samples": [1001, 1001],
            "y_samples": [1000, 1000],
        },
    ).json["result"]
    assert result["x_accepted"] is True
    assert result["y_accepted"] is False
    assert result["profile_x"] == [500.5, 500.5]


def test_journal_preserves_bytes_without_file_write(app):
    def encoded(value):
        return base64.b64encode(value).decode("ascii")

    result = request(
        app.test_client(),
        "journal",
        {
            "message_input": encoded(b"hello\x00"),
            "journal_in": encoded(b"old"),
            "display_timestamp": encoded(b"display   "),
            "file_timestamp": encoded(b"file   "),
            "file_path_token": "C:/must-not-be-created.txt",
        },
    ).json["result"]
    assert (
        base64.b64decode(result["projection"]["journal_out"]["base64"])
        == b"display   hello\x00\r\nold"
    )
    assert result["file_written"] is False


@pytest.mark.parametrize(
    "raw",
    [
        '{"operation":"machine_frequency","operation":"journal","inputs":{}}',
        '{"operation":"machine_frequency","inputs":{"new_value":NaN}}',
        '{"operation":"machine_frequency","inputs":{"new_value":1e1000}}',
        '{"operation":"dispatch","inputs":{}}',
        "[]",
        "{",
    ],
)
def test_strict_json_and_closed_operation_allowlist(app, raw):
    response = app.test_client().post(
        "/api/elyse/supervision/replay", data=raw, content_type="application/json"
    )
    assert response.status_code == 400
    assert response.json["execution_allowed"] is False


def test_body_bound_and_content_type(app):
    client = app.test_client()
    assert client.post("/api/elyse/supervision/replay", data="x").status_code == 415
    assert (
        client.post(
            "/api/elyse/supervision/replay",
            data=" " * 65537,
            content_type="application/json",
        ).status_code
        == 413
    )
    assert client.post("/api/elyse/supervision/dispatch", json={}).status_code == 404


def test_existing_production_auth_guards_snapshot_and_replay(app, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    client = app.test_client()
    assert client.get("/api/elyse/supervision").status_code == 401
    assert request(client, "machine_frequency", {"new_value": 5}).status_code == 401
    with app.app_context():
        token = create_access_token(identity="operator")
    response = client.get(
        "/api/elyse/supervision", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_evidence_missing_fails_closed_without_mock_fallback(
    app, monkeypatch, tmp_path
):
    monkeypatch.setattr(service, "SUPERVISION_ROOT", tmp_path)
    response = app.test_client().get("/api/elyse/supervision")
    assert response.status_code == 503
    assert response.json["execution_allowed"] is False


def test_snapshot_does_not_open_network_or_construct_hardware(monkeypatch):
    import socket

    def deny(*args, **kwargs):
        raise AssertionError("Reconstruction must not connect to hardware")

    monkeypatch.setattr(socket.socket, "connect", deny)
    snapshot = service.snapshot()
    assert snapshot["physical_status"] == "NOT_CONNECTED"
    assert "tango" not in json.dumps(snapshot["replay_operations"])
