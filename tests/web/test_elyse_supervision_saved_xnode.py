"""Flask replay and modern projection consume the Python 3.4 arithmetic core."""

import importlib
import sys
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("elyse_supervision_api")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="software-only-xnode-replay-key")
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, uid="36467", inputs=None, status=False, code=-17):
    return client.post(
        "/api/elyse/supervision/replay",
        json=dict(
            operation="saved_xnode",
            inputs=dict(
                source_id="APP-17",
                uid=uid,
                inputs=[2, 5, 11, 17] if inputs is None else inputs,
                error_in=dict(status=status, code=code, source="supplied source"),
            ),
        ),
    )


def test_modern_projection_reuses_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import saved_xnode as modern
    from legacy.xp_acq_agent.elyse_agent import saved_xnode as portable

    assert modern.evaluate_saved_xnode is portable.evaluate_saved_xnode
    assert modern.replay_saved_xnode is portable.replay_saved_xnode


@pytest.mark.parametrize(
    "uid,expected", [("36467", 120 / 35), ("37034", 240 / 35), ("47576", 120 / 35)]
)
def test_http_replay_preserves_warning_and_input_order(client, uid, expected):
    response = post(client, uid)
    assert response.status_code == 200
    body = response.json
    assert body["result"]["result"] == expected
    assert body["result"]["error_out"] == dict(
        status=False, code=-17, source="supplied source"
    )
    assert body["execution_allowed"] is False
    assert body["result"]["acquired_data_bound"] is False
    assert body["physical_status"] == "NOT_EXECUTED"


def test_http_true_status_skips_invalid_formula_domain(client):
    response = post(client, inputs=[0, 0, 0, 0], status=True, code=0)
    assert response.status_code == 200
    assert response.json["result"]["result"] == 0.0


@pytest.mark.parametrize(
    "uid,inputs",
    [
        ("36467", [0, 0, 0, 0]),
        ("36467", [1]),
        ("50983", [9]),
        ("45051", [1]),
        ("36467", [True] * 4),
    ],
)
def test_http_unqualified_domain_is_explicit_rejection(client, uid, inputs):
    assert post(client, uid, inputs).status_code == 400


def test_disabled_source_body_is_explicitly_isolated(client):
    response = post(client, uid="50983", inputs=[0])
    assert response.status_code == 200
    assert response.json["result"]["inactive_saved_body"] is True
    assert response.json["result"]["native_runtime_equivalence_qualified"] is False
