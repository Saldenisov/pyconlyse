"""Explicit local operator approval path; fake Tango, no equipment commands."""
import pytest

from tests.web.test_acq_control_api import setup_api, request_command, ROOT, writes, api


@pytest.fixture
def local_setup(setup_api, tmp_path):
    key = tmp_path / "local.key"
    key.write_bytes(b"test-only-local-key-" * 3)
    setup_api[0].config.update(ACQ_LOCAL_CONSOLE_ENABLED=True,
        ACQ_LOCAL_CONSOLE_ORIGIN="http://127.0.0.1:5000", ACQ_LOCAL_CONSOLE_KEY_FILE=str(key),
        ACQ_LOCAL_CONSOLE_DB_FILE=str(tmp_path / "approvals.sqlite3"))
    return setup_api


def local_post(setup, path, command, nonce=None, origin="http://127.0.0.1:5000"):
    headers = {"Origin": origin}
    if nonce:
        headers["X-PYCONLYSE-HARDWARE-APPROVAL"] = nonce
    return setup[1].post(ROOT + path, json=command, headers=headers,
                         base_url="http://127.0.0.1:5000")


def test_local_confirmation_reads_only_and_next_post_dispatches_exactly_once(local_setup):
    command = request_command()
    approved = local_post(local_setup, "/approvals", command)
    assert approved.status_code == 200, approved.json
    assert approved.json["dispatch_attempted"] is False
    assert writes(local_setup) == []
    nonce = approved.json["nonce"]
    first = local_post(local_setup, "/commands", command, nonce)
    assert first.status_code == 200, first.json
    assert first.json["receipt"]["outcome"] == "QUEUED"
    second = local_post(local_setup, "/commands", command, nonce)
    assert second.status_code == 409, second.json
    assert second.json["receipt"]["dispatch_attempted"] is False
    assert len(writes(local_setup)) == 1


def test_local_origin_and_nonce_are_both_mandatory(local_setup):
    command = request_command()
    assert local_post(local_setup, "/commands", command, origin="http://elsewhere.test").status_code == 403
    assert local_post(local_setup, "/commands", command).status_code == 428
    assert writes(local_setup) == []


def test_approval_does_not_authorize_a_changed_boot_or_value(local_setup):
    command = request_command()
    approved = local_post(local_setup, "/approvals", command)
    changed = dict(command, expected_revision=command["expected_revision"] + 1)
    response = local_post(local_setup, "/commands", changed, approved.json["nonce"])
    assert response.status_code == 409
    assert writes(local_setup) == []


def test_production_never_uses_console_mode(local_setup, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    assert local_post(local_setup, "/commands", request_command()).status_code == 401
    assert writes(local_setup) == []


def test_metadata_exposes_only_mode_and_updated_exact_contract(local_setup):
    response = local_setup[1].get(ROOT, base_url="http://127.0.0.1:5000")
    assert response.status_code == 200
    assert response.json["approval_mode"] == "LOCAL_CONSOLE"
    assert set(response.json["capabilities"]) == set(api.OPERATIONS)
    assert len(api.OPERATIONS) == 25
    assert "local.key" not in response.text
    assert "nonce" not in response.text
    assert writes(local_setup) == []
