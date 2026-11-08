"""Main-web camera bridge reads only fake fixed Tango attributes."""
import json
from types import SimpleNamespace

import pytest

from tests.web.test_acq_telemetry_api import setup_api, api, URL


@pytest.fixture
def observer(setup_api, monkeypatch):
    app, unused_snapshot, calls = setup_api
    payload = dict(owner="supervision", available=False, stale=True, frame=None)
    class Proxy:
        def set_timeout_millis(self, timeout):
            calls.append(("timeout", timeout))
        def read_attribute(self, name):
            calls.append(("read_attribute", name))
            return SimpleNamespace(has_failed=False, value=json.dumps(payload))
    def factory(name):
        calls.append(("proxy", name))
        return Proxy()
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    return app.test_client(), payload, calls


def test_video_reads_only_existing_ds_attribute_without_commands_or_xp_access(observer):
    client, payload, calls = observer
    result = client.get(URL + "/video")
    assert result.status_code == 200 and result.json["frame"] is None
    assert result.json["owner"] == "supervision" and result.json["schema_version"] == 1
    assert calls == [("proxy", api.DEVICE), ("timeout", 1500), ("read_attribute", "video_json")]
    assert result.headers["Cache-Control"] == "no-store"


def test_orchestrators_metadata_is_read_only_and_lease_tokens_are_not_exposed(observer):
    client, payload, calls = observer
    payload.clear()
    payload.update(federated=False, migration_mode="acquisition_legacy_supervision_read_only",
        owners=dict(supervision=dict(runtime=dict(control=dict(lease="must-not-expose")))))
    result = client.get(URL + "/owners")
    assert result.status_code == 200 and result.json["federated"] is False
    assert "lease" not in result.text
    assert calls[-1] == ("read_attribute", "orchestrators_json")


@pytest.mark.parametrize("change", [dict(owner="acquisition"), dict(available="true")])
def test_unexpected_video_contract_fails_closed(observer, change):
    client, payload, calls = observer
    payload.update(change)
    result = client.get(URL + "/video")
    assert result.status_code == 503 and result.json["frame"] is None
