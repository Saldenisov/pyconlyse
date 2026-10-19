"""Existing Python 3.4 agent/listener + shared emulator + web Supervision."""
import json
import os
import socket
import subprocess
import time
import uuid

import pytest

import test_elyse_acq_process_integration as integration
from legacy.xp_acq_agent.elyse_agent.protocol import recv_message, send_message

domain, transport = integration.domain, integration.transport
app = integration.app


@pytest.fixture(scope="module")
def remote(tmp_path_factory):
    instance = integration.RemoteProcess(tmp_path_factory.mktemp("original-agent-py34"), protocol="tcp")
    try:
        yield instance
    finally:
        instance.stop()


def legacy(remote, command, params=None):
    with socket.create_connection(remote.port.address, timeout=3) as connection:
        send_message(connection, dict(id="legacy-" + uuid.uuid4().hex, command=command, params=params or {}))
        return recv_message(connection, 1048576)


@pytest.mark.parametrize("entry", integration.ROUTABLE, ids=lambda entry: entry["procedure"])
def test_all_23_web_procedures_use_original_agent_and_shared_outputs(app, remote, entry):
    integration.test_all_23_web_procedures_execute_through_actual_py34_agent(app, remote, entry)
    snapshot = legacy(remote, "get_snapshot")["result"]
    state = remote.port.read_state()
    image = remote.port.outputs()
    assert snapshot["supervision"]["session_id"] == state["session_id"]
    assert snapshot["supervision"]["run"] == state["run"]
    assert snapshot["procedure_outputs"] == image
    assert snapshot["procedure_output_units"] == "LEGACY_LOGICAL_SIMULATION"
    business = app.extensions["elyse_supervision_business"].snapshot()
    assert business["acq"]["trace_intent_id"] == state["run"]["intent_id"]
    assert any(phase["outcome"] == "SUCCEEDED" for phase in business["acq"]["phases"])
    for target, value in image["digital"].items():
        group, index = target.rsplit(".", 1)
        assert snapshot["digital_outputs"][group.replace("_OUT_DIO96", "_DIO96_DO")][int(index)] is value
    assert legacy(remote, "get_status")["result"]["supervision"]["run"] == state["run"]
    assert legacy(remote, "ping")["result"]["reply"] == "pong"


def test_original_agent_fault_emulation_and_recovery(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    try:
        assert legacy(remote, "set_simulation_scenario", dict(name="fault"))["ok"] is True
        for intent_id, expected in (("equipment-fault", "FAILED"), ("equipment-recovered", "SUCCEEDED")):
            service.stage(dict(intent_id=intent_id, page="Page Fluides", control="Marche régulation"))
            service.submit(intent_id, remote.port.read_state()["revision"])
            item, snapshot = integration.wait_terminal(service, intent_id)
            assert item["state"] == expected
            if expected == "FAILED":
                assert "Simulated equipment fault" in item["error"]
                started = [step for step in remote.port.trace(intent_id) if step["outcome"] == "STARTED"]
                assert len(started) == 1  # No later equipment command after failed precondition.
                assert legacy(remote, "set_simulation_scenario", dict(name="idle"))["ok"] is True
            assert snapshot["active_intent_id"] is None
    finally:
        legacy(remote, "set_simulation_scenario", dict(name="idle"))


def test_unsigned_legacy_raw_writes_cannot_bypass_procedure_owner(remote):
    for command, params in (("set_simulated_digital_output", dict(task="C3_DIO96_DO", index=0, value=True)),
                            ("reset_simulated_outputs", {})):
        response = legacy(remote, command, params)
        assert response["ok"] is False
        assert "Named procedures own outputs" in response["error"]["message"]
    assert legacy(remote, "get_capabilities")["result"]["supervision_protocol"] == "signed_agent_rpc_v1"
    assert legacy(remote, "get_psp_snapshot")["result"]["channel_count"] == 472


def test_wrong_key_is_rejected_by_same_original_listener(remote):
    wrong = transport.TcpAcqPort(remote.endpoint, b"wrong-key-with-32-bytes-at-least!!", allow_loopback=True)
    with pytest.raises(ConnectionError, match="authentication failed"):
        wrong.read_state()


def test_revision_conflict_and_lost_receipt_other_client_use_original_agent(remote, tmp_path):
    integration.test_atomic_revision_rejection_is_not_an_unknown_send(remote, tmp_path)
    integration.test_lost_receipt_resolves_when_another_client_has_advanced_latest_run(remote, tmp_path)


@pytest.mark.parametrize("case", ["lost", "crash", "fault"])
def test_original_agent_restarts_preserve_business_outcome(tmp_path, monkeypatch, case):
    original = integration.RemoteProcess

    def original_agent(directory, scale=0, fault=None):
        return original(directory, scale=scale, fault=fault, protocol="tcp")

    monkeypatch.setattr(integration, "RemoteProcess", original_agent)
    function = dict(lost=integration.test_lost_receipt_resolves_from_history_after_acq_restart,
                    crash=integration.test_acq_crash_retains_unknown_busy_across_both_restarts,
                    fault=integration.test_fault_reaches_supervision_log_and_next_procedure_can_run)[case]
    function(tmp_path)


def test_original_agent_has_one_durable_owner(remote):
    env = dict(os.environ, ELYSE_ACQ_SHARED_KEY=remote.key.decode("ascii"))
    env.pop("ELYSE_ACQ_SHARED_KEY_FILE", None)
    attempted = subprocess.run([str(integration.PY34), str(integration.ROOT / "legacy/xp_acq_agent/main.py"),
                                "--config", str(remote.directory / "agent.json"), "--supervision",
                                "--bind", "127.0.0.1", "--port", "0", "--state-db", str(remote.path)],
                               capture_output=True, text=True, env=env, timeout=10)
    assert attempted.returncode != 0
    assert "database is locked" in attempted.stderr
    assert "listening on" not in attempted.stdout
    assert remote.port.read_state()["quality"] == "SIMULATED"
