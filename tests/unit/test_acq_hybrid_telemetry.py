"""Legacy Acq + independent Sup raw image in one RAM router; no sockets/NI."""
import copy
import importlib
import json
from types import SimpleNamespace

import pytest

from DeviceServers.control.elyse_acq.hybrid_telemetry import (
    MIGRATION_MODE, HybridTelemetryStore, load_migration_configuration,
)
from legacy.xp_acq_control.elyse_agent.federation_wire import owner_frame
from legacy.xp_acq_control.elyse_agent.standard_banks import standard_packet
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
from legacy.xp_acq_control.elyse_agent.telemetry_relay import sign
from tests.unit.test_acq_standard_telemetry import state
from tests.unit.test_acq_federated_telemetry import KEYS, part
from tests.unit.test_acq_federated_video import video


def packet(sequence=1):
    value = standard_packet(state(), sequence)
    value.update(producer_kind="copied_acquisition", source_site="xp_unified_labview_bridge_27_banks")
    value["data"].update(capture_kind="sequential_local_controls", timestamp_origin="xp_receipt_not_card_sample")
    for record in value["data"]["banks"]:
        if record["publication"] == "C12NI1409":
            record.update(data="legacy-image-reference", error=dict(status=False, code=0, source=""))
        elif record["publication"] == "C1011NI6602":
            record.update(data=list(range(33)), error=dict(status=False, code=0, source=""))
    return value


def supervision(sequence=1, session="b" * 32, image=True):
    return owner_frame("supervision", session, sequence, source_mode="PYTHON_NATIVE",
                       counter_part=part(500.), video_frame=video() if image else None)


def signed(value, owner, message=1, relay=None, key=None):
    body = dict(schema_version=1, relay_id=relay or ("c" if owner == "acquisition" else "d") * 32,
        message_id=message, received_utc_on_xp="2026-10-26T12:00:00+00:00",
        age_seconds_on_xp=0., packet=value, hardware_writes=False)
    envelope = dict(body=body, nonce="e" * 32)
    return dict(envelope, signature=sign(key or KEYS[owner], "ACQ-TELEMETRY-REQUEST-1", envelope))


@pytest.fixture
def pair():
    now = [0.]
    store = HybridTelemetryStore(KEYS["acquisition"], KEYS["supervision"], clock=lambda: now[0],
                                 permitted_producer_kind="unified_acquisition")
    yield store, now
    store.close()


@pytest.mark.parametrize("order", [("acquisition", "supervision"), ("supervision", "acquisition")])
def test_both_start_orders_keep_all_27_legacy_banks_and_independent_raw_image(pair, order):
    store, now = pair
    values = dict(acquisition=packet(), supervision=supervision())
    for role in order:
        store.accept(signed(values[role], role))
    result = store.snapshot()
    assert set(result["publications"]) == set(BANKS)
    assert result["source"] == "copied_labview_telemetry"
    assert result["active_producer_kind"] == "copied_acquisition"
    assert result["publications"]["C12NI1409"]["data"] == "legacy-image-reference"
    assert result["publications"]["C1011NI6602"]["data"] == list(range(33))
    assert result["migration_mode"] == MIGRATION_MODE and result["sidecar_read_only"]
    assert result["received_this_process"] == 1 and result["migration_received_total"] == 2
    assert store.video_snapshot()["available"] and store.video_snapshot()["frame"]["data"] == video()["data"]
    assert not store.owner_current("acquisition", native=True)


def test_supervision_never_overwrites_or_refreshes_legacy_bank_age(pair):
    store, now = pair
    store.accept(signed(packet(), "acquisition"))
    before = copy.deepcopy(store.snapshot()["publications"])
    store.accept(signed(supervision(), "supervision"))
    assert store.snapshot()["publications"] == before
    now[0] = 3.
    store.accept(signed(supervision(sequence=2), "supervision", message=2))
    value = store.snapshot()
    assert all(row["stale"] and row["age_seconds"] == 3. for row in value["publications"].values())
    assert value["source"] == "copied_labview_telemetry"
    assert value["publications"]["C12NI1409"]["data"] == "legacy-image-reference"
    assert store.owner_current("supervision", native=True)


def test_sup_restart_and_fifo_do_not_retire_acquisition_stream(pair):
    store, now = pair
    store.accept(signed(packet(), "acquisition"))
    old = signed(supervision(), "supervision")
    store.accept(old)
    store.accept(signed(supervision(session="f" * 32), "supervision", relay="1" * 32))
    with pytest.raises(ValueError, match="Retired"):
        store.accept(old)
    store.accept(signed(packet(sequence=2), "acquisition", message=2))
    result = store.snapshot()
    assert result["producer_session"] == "a" * 32
    assert result["supervision_owner"]["session_id"] == "f" * 32
    assert result["received_this_process"] == 2


def test_distinct_credentials_and_wire_authorities_are_enforced(pair):
    store, now = pair
    with pytest.raises(ValueError, match="keys must differ"):
        HybridTelemetryStore(KEYS["acquisition"], KEYS["acquisition"])
    with pytest.raises(ValueError, match="authentication"):
        store.accept(signed(packet(), "acquisition", key=KEYS["supervision"]))
    with pytest.raises(ValueError, match="authentication"):
        store.accept(signed(supervision(), "supervision", key=KEYS["acquisition"]))
    foreign = owner_frame("acquisition", "a" * 32, 1)
    with pytest.raises(ValueError, match="only SuperVision owner"):
        store.accept(signed(foreign, "acquisition"))
    assert store.snapshot()["received_this_process"] == 0
    assert store.snapshot()["migration_received_total"] == 0


def test_sup_data_never_fills_missing_acquisition_or_claims_legacy_source_fresh(pair):
    store, now = pair
    store.accept(signed(supervision(), "supervision"))
    value = store.snapshot()
    assert value["publications"] == {}
    assert value["missing_publications"]
    assert value["received_this_process"] == 0
    assert store.video_snapshot()["available"]
    now[0] = 2.1
    assert store.video_snapshot()["frame"] is None
    assert not store.video_snapshot()["available"]


def test_idempotent_retry_preserves_both_independent_counts(pair):
    store, now = pair
    for value, role in ((packet(), "acquisition"), (supervision(), "supervision")):
        request = signed(value, role)
        store.accept(request)
        now[0] += .1
        assert store.accept(request)["body"]["duplicate"]
    value = store.snapshot()
    assert value["received_this_process"] == 1
    assert value["duplicate_receipts"] == 1
    assert value["migration_received_total"] == 2


def write_config(tmp_path):
    (tmp_path / "supervision.read.key").write_bytes(KEYS["supervision"])
    value = dict(schema_version=1, migration_mode=MIGRATION_MODE,
        supervision=dict(host="10.20.30.2", port=8772, read_key_file="supervision.read.key"))
    path = tmp_path / "supervision_migration.json"
    path.write_text(json.dumps(value))
    return path, value


def test_migration_configuration_is_explicit_fixed_read_only_and_distinct(tmp_path):
    path, value = write_config(tmp_path)
    loaded = load_migration_configuration(path, KEYS["acquisition"])
    assert loaded == dict(host="10.20.30.2", port=8772, read_key=KEYS["supervision"], enabled=False)
    for change in (dict(migration_mode="auto"), dict(extra=True), dict(schema_version=True)):
        path.write_text(json.dumps(dict(value, **change)))
        with pytest.raises(ValueError):
            load_migration_configuration(path, KEYS["acquisition"])
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="keys must differ"):
        load_migration_configuration(path, KEYS["supervision"])
    path.write_text(json.dumps(value).replace('"schema_version": 1', '"schema_version": 1,"schema_version": 1'))
    with pytest.raises(ValueError, match="Duplicate"):
        load_migration_configuration(path, KEYS["acquisition"])


@pytest.mark.parametrize("key_name", ["../outside.key", "..\\outside.key", "/absolute.key",
    "C:\\private\\outside.key", "C:outside.key", "\\\\host\\share\\outside.key", ".", "..", "a\x00.key"])
def test_migration_key_is_a_local_basename_before_any_key_file_read(tmp_path, key_name):
    path, value = write_config(tmp_path)
    value["supervision"]["read_key_file"] = key_name
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Installation-local read-key basename"):
        load_migration_configuration(path, KEYS["acquisition"])


def test_migration_rejects_even_an_existing_absolute_key_path(tmp_path):
    path, value = write_config(tmp_path)
    value["supervision"]["read_key_file"] = str((tmp_path / "supervision.read.key").resolve())
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Installation-local read-key basename"):
        load_migration_configuration(path, KEYS["acquisition"])


def test_actual_tango_facade_delegates_video_and_denies_every_supervision_command(pair, monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    store, now = pair
    store.accept(signed(packet(), "acquisition"))
    store.accept(signed(supervision(), "supervision"))
    device = module.DS_AcqTelemetry()
    device._store, device._migration, device._federated = store, True, False
    device._closing, device._python_source, device.commands_enabled = False, True, True
    from tests.web.test_acq_control_api import view_fixture
    acq, sup = view_fixture(), view_fixture()
    sup.update(owner_state_current=True, source="xp_python_supervision_control", quality="READY")
    sup["runtime"].update(server_variant="supervision_control_vnext", session_id="b" * 32)
    device._bridge = SimpleNamespace(snapshot=lambda: copy.deepcopy(acq))
    device._bridges = {"supervision": SimpleNamespace(snapshot=lambda: copy.deepcopy(sup))}
    device._client = SimpleNamespace(submit=lambda value: pytest.fail("legacy VI must never issue hardware command"))
    device._clients = {"supervision": SimpleNamespace(submit=lambda value: pytest.fail("read-only sidecar dispatched"))}
    assert json.loads(device.video_json())["available"]
    public = json.loads(device.telemetry_json())
    assert len(public["publications"]) == 27 and public["source"] == "copied_labview_telemetry"
    owners = json.loads(device.orchestrators_json())
    assert owners["migration_mode"] == MIGRATION_MODE and owners["federated"] is False
    assert set(owners["owners"]) == {"acquisition", "supervision"}
    side = owners["owners"]["supervision"]
    assert not side["commands_enabled"]
    assert all(not item["enabled"] for item in side["runtime"]["control"]["capabilities"].values())
    intent = dict(command_id="4" * 32, session_id="b" * 32, expected_revision=7,
        operation="counter_timing.set", operator_confirmed=True, value=dict(counter=2, delay_us=1., width_us=2.))
    with pytest.raises(RuntimeError, match="MIGRATION_SUPERVISION_READ_ONLY"):
        device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision", request=intent)))
    with pytest.raises(RuntimeError, match="TANGO_COMMANDS_DISABLED"):
        device.ExecuteCommand(json.dumps(dict(intent, session_id="a" * 32)))


def test_explicit_native_acquisition_legacy27_commands_keep_existing_route_during_migration(pair, monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    store, now = pair
    native = standard_packet(state(), 1)
    native["source_site"] = "xp_unified_python_owner_27_banks"
    store.accept(signed(native, "acquisition"))
    store.accept(signed(supervision(), "supervision"))
    from tests.web.test_acq_control_api import view_fixture
    view, calls = view_fixture(), []
    device = module.DS_AcqTelemetry()
    device._store, device._migration, device._federated = store, True, False
    device._closing, device._python_source, device.commands_enabled = False, True, True
    device._bridge = SimpleNamespace(snapshot=lambda: copy.deepcopy(view))
    device._client = SimpleNamespace(submit=lambda intent: calls.append(intent) or dict(outcome="QUEUED"))
    assert device._control_view()["telemetry_source_current"]
    request = dict(command_id="4" * 32, session_id="a" * 32, expected_revision=7,
        operation="counter_timing.set", operator_confirmed=True, value=dict(counter=2, delay_us=1., width_us=2.))
    assert json.loads(device.ExecuteCommand(json.dumps(request)))["outcome"] == "QUEUED"
    assert calls == [request]
    assert json.loads(device.telemetry_json())["source"] == "python_daqmx_acquisition"


def test_device_initialization_uses_one_listener_two_fixed_peers_and_read_only_sup_client(tmp_path, monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    from DeviceServers.control.elyse_acq.control_client import ControlBridge
    path, value = write_config(tmp_path)
    acq_key = tmp_path / "acquisition.read.key"
    acq_key.write_bytes(KEYS["acquisition"])
    bound = []
    class Listener:
        def __init__(self, address, store, permitted_peers):
            bound.append((address, store, permitted_peers))
        def serve_forever(self, **kwargs):
            return
        def server_close(self):
            pass
    monkeypatch.setattr(module, "TelemetrySinkServer", Listener)
    monkeypatch.setattr(ControlBridge, "start", lambda self: None)
    device = module.DS_AcqTelemetry()
    device.listen_host, device.listen_port = "127.0.0.1", 8767
    device.key_file, device.supervision_migration_config_file = str(acq_key), str(path)
    device.federation_config_file, device.cooling_journal_file, device.archive_config_file = "", "", ""
    device.commands_enabled, device.producer_kind_filter = False, "unified_acquisition"
    device.set_status = lambda value: None
    device.init_device()
    try:
        assert len(bound) == 1
        assert bound[0][0] == ("127.0.0.1", 8767)
        assert bound[0][2] == ("10.20.30.10", "10.20.30.2")
        actual_store_class = importlib.import_module("DeviceServers.control.elyse_acq.hybrid_telemetry").HybridTelemetryStore
        assert isinstance(device._store, actual_store_class)
        assert device._clients["supervision"].enabled is False
        assert device._clients["supervision"].command_key is None
    finally:
        device.delete_device()


@pytest.mark.parametrize("mode", ["legacy", "migration", "federation"])
def test_mode_selection_waits_for_tango_base_to_hydrate_device_properties(tmp_path, monkeypatch, mode):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    from DeviceServers.control.elyse_acq.control_client import ControlBridge
    migration_path, unused_config = write_config(tmp_path)
    acq_key = tmp_path / "acquisition.read.key"
    acq_key.write_bytes(KEYS["acquisition"])
    federation_path = tmp_path / "federation.json"
    federation_path.write_text(json.dumps(dict(schema_version=1, owners={
        role: dict(host="10.20.30.10" if role == "acquisition" else "10.20.30.2", port=8772,
            read_key_file="acquisition.read.key" if role == "acquisition" else "supervision.read.key",
            command_key_file="", commands_enabled=False)
        for role in ("acquisition", "supervision")})))
    hydrated, listeners = [], []
    def base_init(device):
        hydrated.append(True)
        device.listen_host, device.listen_port, device.permitted_xp_host = "127.0.0.1", 8767, "10.20.30.10"
        device.key_file = "" if mode == "federation" else str(acq_key)
        device.federation_config_file = str(federation_path) if mode == "federation" else ""
        device.supervision_migration_config_file = str(migration_path) if mode == "migration" else ""
        device.producer_kind_filter = "unified_acquisition" if mode == "migration" else ""
        device.cooling_journal_file = device.archive_config_file = ""
        device.commands_enabled = False
    class Listener:
        def __init__(self, address, store, permitted_peers):
            listeners.append((address, type(store).__name__, permitted_peers))
        def serve_forever(self, **kwargs):
            return
        def server_close(self):
            pass
    monkeypatch.setattr(module.Device, "init_device", base_init)
    monkeypatch.setattr(module, "TelemetrySinkServer", Listener)
    monkeypatch.setattr(ControlBridge, "start", lambda self: None)
    device = module.DS_AcqTelemetry()
    # Simulate stale/default values before Tango performs its property load.
    device.federation_config_file = device.supervision_migration_config_file = "pre-hydration-placeholder"
    status = []
    device.set_status = status.append
    device.init_device()
    try:
        assert hydrated == [True]
        assert device._federated is (mode == "federation")
        assert device._migration is (mode == "migration")
        assert device._python_source is (mode != "legacy")
        expected_store = {"legacy": "TelemetrySinkStore", "migration": "HybridTelemetryStore",
                          "federation": "FederatedTelemetryStore"}[mode]
        assert len(listeners) == 1, status
        assert listeners[0][1] == expected_store, status
        assert device.get_state() == module.DevState.ON, status
    finally:
        device.delete_device()
