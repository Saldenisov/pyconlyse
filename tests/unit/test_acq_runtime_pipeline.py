"""Actual source-format pipeline with fake NI owner and signed loopback only."""
import json
import importlib
from pathlib import Path
import threading
import time
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_http import RuntimeHTTPServer
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.tests.test_acquisition_stage_backend import fake_owner
from DeviceServers.control.elyse_acq.runtime_client import read_runtime
from DeviceServers.control.elyse_acq.runtime_polling import RuntimePollingWorker
from DeviceServers.control.elyse_acq.runtime_health import INPUT_BANKS


def wait_for(runtime, predicate):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        value = runtime.snapshot()
        if predicate(value):
            return value
        threading.Event().wait(.005)
    raise AssertionError("Fake runtime did not reach expected state")


def test_real_runtime_schema_reaches_web_projection_and_clean_release_hides_old_inputs(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "web/backend"))
    present_snapshot = importlib.import_module("acq_runtime_api").present_snapshot
    owner = fake_owner()  # Mock tasks only; no DAQmx constructor can be reached.
    owner.close.side_effect = owner.tasks.clear
    ni_factory = Mock(return_value=owner)
    runtime = AcquisitionRuntime(lambda: CardBackend(ni_factory), period=.02)
    key = b"offline-runtime-pipeline-key-0000000000000000"
    server = RuntimeHTTPServer(("127.0.0.1", 0), runtime, key)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    reader = RuntimePollingWorker(key, reader=lambda key, **kwargs: read_runtime(
        key, host="127.0.0.1", port=server.server_port, timeout=2))
    runtime.start()
    server_thread.start()
    try:
        reader.poll_once()
        cold = present_snapshot(json.dumps(reader.snapshot()), "STANDBY")
        assert cold["quality"] == "IDLE"
        assert cold["snapshot"]["runtime"]["latest"] is None
        ni_factory.assert_not_called()

        runtime.initialize(startup_confirmed=True)
        wait_for(runtime, lambda value: value["state"] == "RUNNING" and value["latest"] is not None)
        reader.poll_once()
        fresh = present_snapshot(json.dumps(reader.snapshot()), "RUNNING")
        assert fresh["quality"] == "FRESH"
        assert fresh["execution_allowed"] is False and fresh["hardware_writes"] is False
        raw = fresh["snapshot"]["runtime"]
        assert fresh["session_id"] == runtime.snapshot()["session_id"]
        assert raw["recovery"]["protection_active"] is False  # Explicit fake/in-memory test scope.
        assert set(raw["latest"]["banks"]) == set(INPUT_BANKS)
        for name, (kind, device, count) in INPUT_BANKS.items():
            bank = raw["latest"]["banks"][name]
            assert (bank["kind"], bank["device"], len(bank["values"])) == (kind, device, count)
        ni_factory.assert_called_once()

        runtime.deinitialize()
        wait_for(runtime, lambda value: value["state"] == "IDLE")
        reader.poll_once()
        released = present_snapshot(json.dumps(reader.snapshot()), "STANDBY")
        assert released["quality"] == "IDLE"
        assert released["snapshot"]["runtime"]["latest"] is None
        assert released["snapshot"]["runtime"]["resource_count"] == 0
    finally:
        reader.stop()
        runtime.request_shutdown()
        assert runtime.join(2)
        server.shutdown()
        server.server_close()
        server_thread.join(2)
        assert not server_thread.is_alive()
