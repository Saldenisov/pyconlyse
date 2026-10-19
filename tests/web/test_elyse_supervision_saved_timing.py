"""Modern web replay consumes the same isolated Python 3.4 adapter core."""
from tests.web import test_elyse_supervision_saved_xnode as replay_helpers

import pytest

client = replay_helpers.client


def post(client, uid="19070", inputs=None):
    return client.post("/api/elyse/supervision/replay", json=dict(operation="saved_timing",
        inputs=dict(source_id="APP-17", uid=uid, inputs={} if inputs is None else inputs)))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import saved_timing as modern
    from legacy.xp_acq_agent.elyse_agent import saved_timing as portable
    assert modern.evaluate_saved_timing is portable.evaluate_saved_timing
    assert modern.replay_saved_timing is portable.replay_saved_timing


@pytest.mark.parametrize("uid,period", [("19070", 1000), ("32991", -1)])
def test_http_constant_snapshot_without_scheduler(client, uid, period):
    response = post(client, uid)
    assert response.status_code == 200
    assert response.json["result"]["outputs"]["timing"]["period"] == period
    assert response.json["result"]["scheduler_execution_qualified"] is False
    assert response.json["execution_allowed"] is False


def test_http_saved_unused_faces_have_no_override(client):
    response = post(client, inputs=dict(period=17, source_name="unused edit"))
    assert response.status_code == 200
    assert response.json["result"]["outputs"]["timing"]["period"] == 1000


def test_http_late_selection_ignores_unselected_error(client):
    raw = post(client).json["result"]["outputs"]["timing"]
    raw.update(finished_late_i_1=True, error=dict(status=True, code=-17, source="fault"))
    response = post(client, "32954", dict(timing=raw))
    assert response.status_code == 200
    assert response.json["result"]["outputs"] == dict(finished_late_i_1=True)
    assert response.json["result"]["acquired_data_bound"] is False


@pytest.mark.parametrize("uid,inputs", [("19142", {}), ("17671", {}), ("32991", {"period": 1}), ("32954", {"timing": {}})])
def test_unqualified_scheduler_and_defaults_explicitly_refuse(client, uid, inputs):
    assert post(client, uid, inputs).status_code == 400
