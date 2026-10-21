"""Real signed loopback relay; no NI, PSP, device commands or live Tango DB."""
import copy
import json
import subprocess
import sys
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from legacy.xp_acq_control.elyse_agent.native_telemetry import (
    BANKS, INPUTS, COMMANDS, UNAVAILABLE, standard_packet, validate_standard_packet, StandardTelemetryPublisher,
)
from legacy.xp_acq_control.elyse_agent.telemetry_relay import canonical, sign
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore, TelemetrySinkServer

KEY = b"test-only-standard-telemetry-key-000000000000"


def state():
    banks = {}
    for name, (source, kind, device, count, field, scalar) in INPUTS.items():
        raw = [False] * count if scalar == "Boolean" else [1.] * count
        banks[source] = dict(kind=kind, device=device, values=raw)
        if scalar == "DBL":
            banks[source][field] = [123.] * count
    latest = dict(source="python_daqmx_acquisition", simulated=False, banks=banks,
                  commanded_digital={}, commanded_analog_logical={})
    for name, (section, source, count, kind) in COMMANDS.items():
        latest[section][source] = [False if kind == "Boolean" else 6.5] * count
    return dict(session_id="a" * 32, sequence=1, state_revision=2, state="RUNNING",
                stale=False, age_seconds=.3, error="", latest=latest)


def signed(packet, relay=None, message=1):
    body = dict(schema_version=1, relay_id=relay or uuid4().hex, message_id=message,
                received_utc_on_xp="2026-10-21T14:00:00+00:00", age_seconds_on_xp=.2,
                packet=packet, hardware_writes=False)
    signed_body = dict(body=body, nonce=uuid4().hex)
    return dict(signed_body, signature=sign(KEY, "ACQ-TELEMETRY-REQUEST-1", signed_body))


def test_full_order_calibrated_inputs_and_command_memory_not_invented_statuses():
    packet = standard_packet(state(), 1)
    validate_standard_packet(packet)
    records = {r["publication"]: r for r in packet["data"]["banks"]}
    assert tuple(records) == BANKS and len(records) == 27
    assert records["C1NI6071E"]["data"] == [123.] * 64  # Not raw volts or double-scaled.
    assert records["C9NI6703"]["data"] == [6.5] * 10  # Last successful logical command.
    assert sum(not r["error"]["status"] for r in records.values()) == 12
    for name in set(BANKS) - set(INPUTS) - set(COMMANDS):
        assert records[name]["data"] is None
        assert records[name]["error"]["code"] == UNAVAILABLE
    assert "C11_NI6220_AI" not in records  # No invented mapping to the counter bank.


@pytest.mark.parametrize("change", [dict(state="IDLE"), dict(stale=True), dict(age_seconds=2),
                                    dict(error="native read failed"), dict(latest={})])
def test_inactive_unknown_stale_or_failed_owner_never_replays_valid_data(change):
    value = state(); value.update(change)
    assert all(r["data"] is None and r["error"]["status"] for r in standard_packet(value, 2)["data"]["banks"])


def test_missing_calibration_does_not_publish_raw_volts_as_engineering_units():
    value = state(); del value["latest"]["banks"]["C1_NI6071E_AI"]["legacy_scaled_values"]
    assert standard_packet(value, 2)["data"]["banks"][0]["data"] is None


def test_false_healthy_unknown_bank_and_wrong_scalar_type_are_rejected():
    value = standard_packet(state(), 1)
    value["data"]["banks"][15]["data"] = [False] * 77
    with pytest.raises(ValueError): validate_standard_packet(value)
    value = standard_packet(state(), 1); value["data"]["banks"][2]["data"][0] = 0
    with pytest.raises(ValueError): validate_standard_packet(value)


def test_explicit_exclusive_source_no_labview_python_mix_or_old_boot_revival():
    packet = standard_packet(state(), 1)
    for source in (None, "copied_acquisition", "fixture"):
        store = TelemetrySinkStore(KEY, permitted_producer_kind=source)
        with pytest.raises(ValueError): store.accept(signed(packet))
        assert store.snapshot()["publications"] == {}
    store = TelemetrySinkStore(KEY, permitted_producer_kind="python_acquisition")
    old = signed(packet); store.accept(old)
    native = store.snapshot()
    assert len(native["publications"]) == 27 and native["source"] == "python_daqmx_acquisition"
    newer = state(); newer["session_id"] = "b" * 32
    store.accept(signed(standard_packet(newer, 1)))
    with pytest.raises(ValueError, match="Retired"): store.accept(old)
    with pytest.raises(ValueError, match="sequence"): store.accept(signed(standard_packet(newer, 1)))
    assert all(p["session_id"] == "b" * 32 for p in store.snapshot()["publications"].values())


def test_real_signed_push_ack_and_source_age_are_preserved_without_owner_calls():
    value = state()
    runtime = SimpleNamespace(snapshot=lambda: copy.deepcopy(value))
    store = TelemetrySinkStore(KEY, permitted_producer_kind="python_acquisition")
    server = TelemetrySinkServer(("127.0.0.1", 0), store, permitted_peers=("127.0.0.1",))
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02), daemon=True)
    worker.start()
    publisher = StandardTelemetryPublisher(runtime, server.server_address, KEY)
    try:
        assert publisher.publish_once()
        assert not publisher.publish_once()  # Unchanged source does not get a new timestamp.
        assert publisher.relay.send_once()
        observed = store.snapshot()
        assert len(observed["publications"]) == 27
        assert observed["publications"]["C1NI6071E"]["age_seconds"] >= .3
        assert publisher.status()["everest_acknowledged"] == 1
        assert publisher.outbox.status()["pending"] == 0
        value.update(stale=True)
        assert publisher.publish_once() and publisher.relay.send_once()
        assert store.snapshot()["publications"]["C1NI6071E"]["data"] is None
    finally:
        publisher.close(); server.shutdown(); server.server_close(); worker.join(3); store.close()


def test_everest_package_is_an_isolated_import_closure(tmp_path):
    from tools.package_acq_web_control import package
    target = tmp_path / "everest"
    result = package(target, everest=True)
    assert result["standard_bank_count"] == 27
    code = "import sys; sys.path.insert(0,sys.argv[1]); from DeviceServers.control.elyse_acq.DS_AcqTelemetry import DS_AcqTelemetry; from DeviceServers.control.elyse_acq.control_client import ControlClient; print(DS_AcqTelemetry.__module__)"
    run = subprocess.run([sys.executable, "-I", "-c", code, str(target)], cwd=tmp_path,
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    assert "DS_AcqTelemetry" in run.stdout
