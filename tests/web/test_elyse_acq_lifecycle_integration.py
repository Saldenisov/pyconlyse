"""Full simulated lifecycle across Flask -> existing TCP agent on actual 3.4."""
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_elyse_acq_process_integration as integration
from test_elyse_acq_tcp_integration import legacy
from tools.build_elyse_acq_supervision import check_lifecycle_parity

domain = integration.domain
ROOT = integration.BUSINESS_ROOT
app = integration.app


@pytest.fixture
def remote(tmp_path):
    process = integration.RemoteProcess(tmp_path)
    try:
        yield process
    finally:
        process.stop()


def stage(service, identity, control):
    return service.stage(dict(intent_id=identity, page="Cycle ACQ", control=control))


def run(service, process, identity, control):
    stage(service, identity, control)
    service.submit(identity, process.port.read_state()["revision"])
    item, snapshot = integration.wait_terminal(service, identity)
    assert item["state"] == "SUCCEEDED", item
    return snapshot


def test_start_stop_start_start_again_stop_through_flask(app, remote):
    client = app.test_client()
    service = None
    for identity, control, cycle in (("start", "Initialiser ACQ", "RUNNING"),
                                     ("stop", "Arrêt général ACQ", "STOPPED"),
                                     ("start-again", "Initialiser ACQ", "RUNNING"),
                                     ("duplicate-start", "Initialiser ACQ", "RUNNING"),
                                     ("stop-again", "Arrêt général ACQ", "STOPPED")):
        response = client.post(ROOT + "/intents", json=dict(intent_id=identity, page="Cycle ACQ", control=control))
        assert response.status_code == 200
        observed = client.get(ROOT).json
        before = remote.port.outputs()
        response = client.post(ROOT + "/intents/" + identity + "/submit", json=dict(expected_revision=observed["acq"]["revision"]))
        service = app.extensions["elyse_supervision_business"]
        if identity == "duplicate-start":
            assert response.status_code == 409
            assert "already initialized" in response.json["error"]
            assert service.intent(identity)["state"] == "BLOCKED"
            assert remote.port.outputs() == before
            continue
        assert response.status_code == 200
        item, observed = integration.wait_terminal(service, identity)
        assert item["state"] == "SUCCEEDED"
        assert observed["acq"]["lifecycle"]["state"] == cycle
        assert observed["physical_status"] == "NOT_EXECUTED"
        assert observed["setpoint_submission_allowed"] is (cycle == "RUNNING")
        trace = client.get(ROOT + "/intents/" + identity + "/trace")
        assert trace.status_code == 200
        assert trace.json["phases"][-1]["outcome"] == "SUCCEEDED"
        assert len(trace.json["phases"]) > 50  # All phases cross the bounded signed frame.
    restored = domain.SupervisionBusiness(service.path, remote.port)
    assert restored.snapshot()["acq"]["lifecycle"]["state"] == "STOPPED"
    assert remote.port.read_state()["run"]["procedure"] == "acq.stop"
    assert legacy(remote, "ping")["result"]["reply"] == "pong"


def test_startup_defaults_and_native_stop_match_independent_source_projectors(remote, tmp_path):
    from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import project_ht_ramp_iteration
    plans = check_lifecycle_parity()
    assert set(plans) == {"acq.initialize", "acq.stop"}
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    run(service, remote, "start", "Initialiser ACQ")
    assert service.snapshot()["acq"]["setpoints"]["C8NI6703.01"] == 21
    assert service.snapshot()["acq"]["setpoints"]["C9NI6703.00"] == 6.5
    state = remote.port.read_state()
    remote.port.submit_setpoint(intent_id="ht", page="Page HT", control=">> HT", base_value=6.5,
                                expected_revision=state["revision"], session_id=state["session_id"])
    run(service, remote, "stop", "Arrêt général ACQ")
    image = remote.port.outputs()
    command = 7.5
    iterations = 0
    while True:
        bank = (command,) + (0.0,) * 9
        projected = project_ht_ramp_iteration(bank, bank)
        if projected.should_stop:
            break
        command = dict(projected.local_writes)[12][0]
        iterations += 1
    ramp = next(row for row in remote.port.trace("stop") if row["operation"] == "lifecycle_ht_ramp" and row["outcome"] == "SUCCEEDED")
    assert ramp["detail"]["iterations"] == iterations
    assert image["analog"]["C9NI6703.00"] == command
    assert image["counters"]["ctr0"] == "RUNNING"  # Native cleanup is not global task-clear.
    assert image["resources"]["tpg.COM1"] == "CLOSED"


def test_lost_startup_receipt_and_both_restarts_restore_without_output_replay(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    original = remote.port.submit_procedure
    def lost(**request):
        original(**request)
        raise ConnectionError("Injected lost lifecycle ACK")
    remote.port.submit_procedure = lost
    stage(service, "lost", "Initialiser ACQ")
    assert service.submit("lost", remote.port.read_state()["revision"])["state"] == "UNKNOWN"
    integration.wait_terminal(service, "lost")
    image = remote.port.outputs()
    trace = remote.port.trace("lost")
    remote.stop()
    remote.start()
    restored = domain.SupervisionBusiness(service.path, remote.port)
    assert restored.snapshot()["acq"]["lifecycle"]["state"] == "RUNNING"
    assert restored.intent("lost")["state"] == "SUCCEEDED"
    assert remote.port.outputs() == image
    assert remote.port.trace("lost") == trace
    assert restored.submit("lost", "obsolete")["state"] == "SUCCEEDED"


def test_initializer_failure_can_be_retried_after_stub_recovery(tmp_path):
    process = integration.RemoteProcess(tmp_path, fault=2)
    try:
        service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", process.port)
        stage(service, "failed", "Initialiser ACQ")
        service.submit("failed", process.port.read_state()["revision"])
        item, observed = integration.wait_terminal(service, "failed")
        assert item["state"] == "FAILED"
        assert observed["acq"]["lifecycle"]["state"] == "FAULT"
        assert "Injected simulation failure" in item["error"]
        process.stop()
        process.fault = None
        process.start()
        restored = domain.SupervisionBusiness(service.path, process.port)
        assert restored.snapshot()["acq"]["lifecycle"]["state"] == "FAULT"
        assert run(restored, process, "retry", "Initialiser ACQ")["acq"]["lifecycle"]["state"] == "RUNNING"
    finally:
        process.stop()


def test_process_loss_during_lifecycle_remains_unknown_in_both_ledgers(tmp_path):
    process = integration.RemoteProcess(tmp_path, scale=1)
    try:
        service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", process.port)
        run(service, process, "start", "Initialiser ACQ")
        stage(service, "stopping", "Arrêt général ACQ")
        service.submit("stopping", process.port.read_state()["revision"])
        assert process.port.read_lifecycle()["state"] == "STOPPING"
        process.stop()  # Actual owned child loss, not a fabricated marker.
        process.start()
        restored = domain.SupervisionBusiness(service.path, process.port)
        observed = restored.snapshot()
        assert observed["acq"]["lifecycle"]["state"] == "UNKNOWN"
        assert restored.intent("stopping")["state"] == "UNKNOWN"
        assert observed["busy"] is True
        assert observed["setpoint_submission_allowed"] is False
        before = process.port.outputs()
        stage(restored, "no-replay", "Initialiser ACQ")
        with pytest.raises(domain.BusinessBlocked):
            restored.submit("no-replay", observed["acq"]["revision"])
        assert process.port.outputs() == before
    finally:
        process.stop()


def test_closed_cycle_blocks_normal_procedures_and_arrows(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    run(service, remote, "start", "Initialiser ACQ")
    run(service, remote, "stop", "Arrêt général ACQ")
    for request in (dict(intent_id="procedure", page="Page Fluides", control="Marche régulation"),
                    dict(intent_id="arrow", page="Page Fluides", control="> Canon", base_value=21)):
        service.stage(request)
        with pytest.raises(domain.BusinessBlocked, match="not RUNNING"):
            service.submit(request["intent_id"], remote.port.read_state()["revision"])
        assert service.intent(request["intent_id"])["state"] == "BLOCKED"


def test_atomic_web_observation_retains_cycle_and_values_during_transition(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    stage(service, "start", "Initialiser ACQ")
    service.submit("start", remote.port.read_state()["revision"])
    def poll(unused):
        for unused in range(25):
            sample = service.snapshot()
            assert sample["acq"]["quality"] == "SIMULATED"
            assert sample["acq"]["lifecycle"] is not None
            assert sample["acq"]["lifecycle_error"] == ""
            assert sample["acq"]["setpoint_error"] == ""
            assert sample["acq"]["lifecycle"]["revision"] == sample["acq"]["revision"]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(poll, range(3)):
            assert result is None
    assert integration.wait_terminal(service, "start")[0]["state"] == "SUCCEEDED"


def test_failed_stop_close_reaches_web_and_other_closes_still_run(remote, tmp_path):
    from legacy.xp_acq_agent.elyse_agent.supervision_lifecycle import plans
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    run(service, remote, "start", "Initialiser ACQ")
    remote.stop()
    remote.fault = next(i for i, step in enumerate(plans()["acq.stop"]["steps"])
                        if step["operation"] == "lifecycle_close")
    remote.start()
    restored = domain.SupervisionBusiness(service.path, remote.port)
    stage(restored, "failed-stop", "Arrêt général ACQ")
    restored.submit("failed-stop", remote.port.read_state()["revision"])
    item, observed = integration.wait_terminal(restored, "failed-stop")
    assert item["state"] == "FAILED"
    assert observed["acq"]["lifecycle"]["state"] == "FAULT"
    image = remote.port.outputs()
    assert image["resources"]["psp.C1NI6071E"] == "OPEN"
    assert image["resources"]["psp.VTS"] == "CLOSED"
    assert image["resources"]["tpg.COM1"] == "CLOSED"
    assert image["resources"]["tpg.COM2"] == "CLOSED"
    assert any(row["outcome"] == "FAILED" and row["operation"] == "lifecycle_close"
               for row in remote.port.trace("failed-stop"))
    remote.stop()
    remote.fault = None
    remote.start()
    restored = domain.SupervisionBusiness(service.path, remote.port)
    assert run(restored, remote, "explicit-retry", "Arrêt général ACQ")["acq"]["lifecycle"]["state"] == "STOPPED"
