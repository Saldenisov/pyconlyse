"""Owner-selected web intents: fake Tango, real local nonce/SQLite boundaries."""
import copy
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.web.test_acq_control_api import setup_api, request_command, ROOT, api
from tests.web.test_acq_hardware_approval import approval_setup


@pytest.fixture
def owner_setup(setup_api, monkeypatch):
    app, client, headers, acquisition, calls, proxy = setup_api
    supervision = copy.deepcopy(acquisition)
    supervision.update(source="xp_python_supervision_control", owner="supervision", quality="READY",
        owner_state_current=True, telemetry_source_current=True, source_current=False)
    supervision["runtime"].update(server_variant="supervision_control_vnext", session_id="f" * 32,
        card_health=dict(all_required_ready=True),
        latest=dict(source="python_supervision_card_processes", simulated=False))
    supervision["runtime"]["control"]["capabilities"] = {
        name: dict(enabled=name == "counter_timing.set", reason="" if name == "counter_timing.set" else "NOT_OWNED")
        for name in api.OPERATIONS}
    owner_document = dict(federated=True, owners=dict(acquisition=acquisition, supervision=supervision))
    original_read = proxy.read_attribute
    def read_attribute(name):
        if name == "orchestrators_json":
            calls.append(("read", name))
            return SimpleNamespace(has_failed=False, value=json.dumps(owner_document))
        return original_read(name)
    def command_inout(name, raw):
        value = json.loads(raw)
        calls.append(("command", name, value))
        if proxy.fail:
            raise TimeoutError("fixture lost owner command reply")
        command = value["request"] if name == "ExecuteOwnerCommand" else value
        return json.dumps(dict(command_id=command["command_id"], session_id=command["session_id"],
            operation=command["operation"], outcome="QUEUED", hardware_acknowledged=False))
    monkeypatch.setattr(proxy, "read_attribute", read_attribute)
    monkeypatch.setattr(proxy, "command_inout", command_inout)
    return setup_api, supervision, owner_document


def sup_command(**changes):
    value = dict(command_id="c" * 32, session_id="f" * 32, operation="counter_timing.set",
                 value=dict(counter=2, delay_us=1.25, width_us=3.5))
    value.update(changes)
    return request_command(**value)


def send(owner_setup, command=None, owner="supervision"):
    setup, supervision, document = owner_setup
    suffix = "" if owner is None else "?owner=" + owner
    return setup[1].post(ROOT + "/commands" + suffix, json=command or sup_command(), headers=setup[2])


def writes(owner_setup):
    return [item for item in owner_setup[0][4] if item[0] == "command"]


def test_supervision_get_reads_only_bound_owner_metadata_and_redacts_both_leases(owner_setup):
    setup, supervision, document = owner_setup
    response = setup[1].get(ROOT + "?owner=supervision")
    assert response.status_code == 200, response.json
    assert response.json["owner"] == "supervision" and response.json["source_host"] == "10.20.30.2"
    assert response.json["topology"]["xp_host"] == "10.20.30.2"
    assert response.json["execution_allowed"]
    assert response.json["capabilities"]["counter_timing.set"]["enabled"]
    assert not any(v["enabled"] for k, v in response.json["capabilities"].items() if k != "counter_timing.set")
    assert "lease" not in response.text and "banks" not in supervision["runtime"]["latest"]
    assert setup[4] == [("read", "orchestrators_json")] and writes(owner_setup) == []


def test_supervision_dispatch_uses_exact_owner_envelope_and_named_facade(owner_setup):
    response = send(owner_setup)
    assert response.status_code == 200, response.json
    assert writes(owner_setup) == [("command", "ExecuteOwnerCommand", dict(owner="supervision", request=sup_command()))]
    assert response.json["receipt"]["owner"] == "supervision"
    assert response.json["receipt"]["hardware_acknowledged"] is False


def real_supervision_view(owner_setup, phase=None):
    from DeviceServers.control.elyse_acq.control_client import ControlBridge
    from tests.unit.test_two_orchestrator_end_to_end import supervision_runtime_with_ram_owners
    runtime = supervision_runtime_with_ram_owners()
    if phase == "pending":
        runtime._pending = ("timing", dict(counter=2, delay_us=1., width_us=2.))
    elif phase == "executing":
        runtime.dispatch_remote("counter_timing.set", dict(counter=2, delay_us=1., width_us=2.))
    bridge = ControlBridge(SimpleNamespace(owner="supervision", enabled=True,
                                           read=runtime.snapshot), clock=lambda: 0.)
    bridge.poll_once()
    view = bridge.snapshot()
    view.update(owner="supervision", telemetry_source_current=True)
    target = owner_setup[1]
    target.clear()
    target.update(view)
    return runtime


def test_real_supervision_snapshot_bridge_and_web_accept_top_level_card_health(owner_setup):
    runtime = real_supervision_view(owner_setup)
    actual = runtime.snapshot()
    assert actual["card_health"]["all_required_ready"] is True
    assert "card_health" not in actual["latest"] and actual["latest"]["banks"] == {}
    response = owner_setup[0][1].get(ROOT + "?owner=supervision")
    assert response.status_code == 200, response.json
    assert response.json["execution_allowed"]
    assert response.json["capabilities"]["counter_timing.set"]["enabled"]
    assert send(owner_setup).status_code == 200
    assert writes(owner_setup)[0][1] == "ExecuteOwnerCommand"
    assert runtime._thread is None


@pytest.mark.parametrize("phase", ["pending", "executing"])
def test_real_supervision_pending_and_executing_timing_are_disabled_in_web(owner_setup, phase):
    runtime = real_supervision_view(owner_setup, phase)
    response = owner_setup[0][1].get(ROOT + "?owner=supervision")
    assert response.status_code == 200, response.json
    assert not response.json["capabilities"]["counter_timing.set"]["enabled"]
    assert send(owner_setup).status_code == 409
    assert not writes(owner_setup)
    assert runtime._thread is None


def test_default_and_explicit_acquisition_keep_old_wire_and_ledger_encoding(owner_setup):
    setup, supervision, document = owner_setup
    command = request_command()
    assert send(owner_setup, command, owner=None).status_code == 200
    assert send(owner_setup, command, owner="acquisition").json["duplicate"]
    assert writes(owner_setup) == [("command", "ExecuteCommand", command)]
    with sqlite3.connect(setup[0].config["ELYSE_CONTROL_STATE_DB"]) as db:
        row = db.execute("SELECT id,request FROM commands").fetchone()
    assert row[0] == command["command_id"]
    assert json.loads(row[1]) == command


@pytest.mark.parametrize("query", ["owner=unknown", "owner=", "owner=Supervision", "owner=supervision&owner=acquisition"])
def test_invalid_owner_never_reaches_tango_or_dispatch_journal(owner_setup, query):
    setup, supervision, document = owner_setup
    assert setup[1].get(ROOT + "?" + query).status_code == 400
    response = setup[1].post(ROOT + "/commands?" + query, json=sup_command(), headers=setup[2])
    assert response.status_code == 400
    assert setup[4] == []
    assert not Path(setup[0].config["ELYSE_CONTROL_STATE_DB"]).exists()


def test_supervision_machine_stage_request_rejected_before_tango_or_journal(owner_setup):
    command = sup_command(operation="modulator.general.start", value=None)
    response = send(owner_setup, command)
    assert response.status_code == 400
    assert owner_setup[0][4] == [] and not writes(owner_setup)


def test_command_id_namespaces_and_histories_do_not_alias_between_owners(owner_setup):
    setup, supervision, document = owner_setup
    # Deliberately identical boot/revision/ID/value proves owner namespace,
    # rather than relying on UUIDs normally differing between computers.
    supervision["runtime"]["session_id"] = "a" * 32
    command = request_command(operation="counter_timing.set", value=dict(counter=2, delay_us=1.25, width_us=3.5))
    assert send(owner_setup, command, owner="acquisition").status_code == 200
    assert send(owner_setup, command).status_code == 200
    assert len(writes(owner_setup)) == 2
    with sqlite3.connect(setup[0].config["ELYSE_CONTROL_STATE_DB"]) as db:
        assert {r[0] for r in db.execute("SELECT id FROM commands")} == {command["command_id"], "supervision:" + command["command_id"]}
    supervision["runtime"]["control"]["results"] = [dict(command_id=command["command_id"], session_id="a" * 32,
        operation="counter_timing.set", hardware_acknowledged=False, outcome="COMPLETED")]
    sup = setup[1].get(ROOT + "?owner=supervision").json
    acq = setup[1].get(ROOT).json
    assert len(sup["commands"]) == len(acq["commands"]) == 1
    assert sup["commands"][0]["outcome"] == "COMPLETED"
    assert acq["commands"][0]["outcome"] == "QUEUED"


def test_unknown_dispatch_blocks_only_its_owner_even_with_same_session(owner_setup):
    setup, supervision, document = owner_setup
    supervision["runtime"]["session_id"] = "a" * 32
    command = request_command(operation="counter_timing.set", value=dict(counter=0, delay_us=1., width_us=2.))
    setup[5].fail = True
    first = send(owner_setup, command)
    assert first.json["receipt"]["outcome"] == "INDETERMINATE"
    setup[5].fail = False
    duplicate = send(owner_setup, command)
    assert duplicate.json["duplicate"] and len(writes(owner_setup)) == 1
    assert send(owner_setup, dict(command, command_id="d" * 32)).status_code == 409
    assert send(owner_setup, command, owner="acquisition").status_code == 200
    assert len(writes(owner_setup)) == 2


def test_local_approval_nonce_cannot_cross_owner_with_identical_command(owner_setup, tmp_path):
    setup, supervision, document = owner_setup
    supervision["runtime"]["session_id"] = "a" * 32
    key = tmp_path / "local.key"
    key.write_bytes(b"test-only-owner-local-console-key-" * 2)
    setup[0].config.update(ACQ_LOCAL_CONSOLE_ENABLED=True,
        ACQ_LOCAL_CONSOLE_ORIGIN="http://127.0.0.1:5000", ACQ_LOCAL_CONSOLE_KEY_FILE=str(key),
        ACQ_LOCAL_CONSOLE_DB_FILE=str(tmp_path / "owner-approvals.sqlite3"))
    command = request_command(operation="counter_timing.set", value=dict(counter=0, delay_us=1., width_us=2.))
    headers = dict(Origin="http://127.0.0.1:5000")
    approved = setup[1].post(ROOT + "/approvals?owner=supervision", json=command,
        headers=headers, base_url="http://127.0.0.1:5000")
    assert approved.status_code == 200, approved.json
    setup[4][:] = []
    headers["X-PYCONLYSE-HARDWARE-APPROVAL"] = approved.json["nonce"]
    cross_owner = setup[1].post(ROOT + "/commands", json=command, headers=headers,
        base_url="http://127.0.0.1:5000")
    assert cross_owner.status_code == 409 and not setup[4]
    assert not Path(setup[0].config["ELYSE_CONTROL_STATE_DB"]).exists()
    correct = setup[1].post(ROOT + "/commands?owner=supervision", json=command,
        headers=headers, base_url="http://127.0.0.1:5000")
    assert correct.status_code == 200, correct.json
    assert len(writes(owner_setup)) == 1 and writes(owner_setup)[0][1] == "ExecuteOwnerCommand"


def test_hardware_authorization_intent_is_owner_bound_without_changing_default():
    command = request_command(operation="counter_timing.set", value=dict(counter=0, delay_us=1., width_us=2.))
    acquisition = api.hardware_intent(command)
    supervision = api.hardware_intent(command, "supervision")
    assert acquisition.route_id == "acquisition.command.counter_timing.set"
    assert acquisition.targets == ({"device": api.DEVICE, "command": "ExecuteCommand"},)
    assert "owner" not in acquisition.args
    assert supervision.route_id == "supervision.command.counter_timing.set"
    assert supervision.targets == ({"device": api.DEVICE, "command": "ExecuteOwnerCommand"},)
    assert supervision.args["owner"] == "supervision"


@pytest.mark.parametrize("approval_setup", ["sync"], indirect=True)
def test_real_external_acquisition_approval_cannot_authorize_supervision(owner_setup, approval_setup):
    setup, supervision, document = owner_setup
    approved_setup, command, intent, consumed, approve, submit = approval_setup
    assert approved_setup is setup
    supervision["runtime"]["session_id"] = command["session_id"]
    approve()
    headers = dict(setup[2], **{"X-PYCONLYSE-HARDWARE-APPROVAL": "a" * 64})
    response = setup[1].post(ROOT + "/commands?owner=supervision", json=command, headers=headers)
    assert response.status_code == 403, response.json
    assert setup[4] == [] and not Path(setup[0].config["ELYSE_CONTROL_STATE_DB"]).exists()
    assert not list(consumed.iterdir())
    # The failed cross-owner attempt neither dispatches nor consumes the real
    # Acquisition approval. Its original, authorized destination still works.
    assert submit().status_code == 200
    assert writes(owner_setup)[0][1] == "ExecuteCommand"


@pytest.mark.parametrize("change", ["binding", "variant", "federated", "stale", "source"])
def test_wrong_or_stale_supervision_metadata_has_no_acquisition_fallback(owner_setup, change):
    setup, supervision, document = owner_setup
    if change == "binding": supervision["owner"] = "acquisition"
    elif change == "variant": supervision["runtime"]["server_variant"] = "acquisition_control_vnext"
    elif change == "federated": document["federated"] = False
    elif change == "stale": supervision["bridge_age_seconds"] = 2.
    else: supervision["runtime"]["latest"]["source"] = "python_daqmx_acquisition"
    assert setup[1].get(ROOT + "?owner=supervision").status_code == 503
    assert send(owner_setup).status_code == 409
    assert not writes(owner_setup)
    assert all(item == ("read", "orchestrators_json") for item in setup[4])


def test_supervision_readiness_false_cannot_be_overridden_by_enabled_capability(owner_setup):
    setup, supervision, document = owner_setup
    supervision["owner_state_current"] = False
    get = setup[1].get(ROOT + "?owner=supervision")
    assert get.status_code == 200 and not get.json["execution_allowed"]
    assert send(owner_setup).status_code == 409
    assert not writes(owner_setup)
