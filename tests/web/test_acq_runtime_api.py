"""Fixed Tango proxy fake only; no XP, NI, fallback values or commands."""
import importlib
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from tests.unit.test_acq_runtime_contract import runtime_snapshot


URL = "/api/elyse/acquisition/runtime"


@pytest.fixture
def setup_api(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "web/backend"))
    api = importlib.import_module("acq_runtime_api")
    monkeypatch.setattr(api.tango_gateway.tango, "DevSource", SimpleNamespace(DEV="DEV"), raising=False)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="synthetic-runtime-read-test-secret")
    JWTManager(app)
    app.register_blueprint(api.acq_runtime_api)
    calls, mode = [], {}
    content = dict(source="xp_python_acquisition_runtime", storage_mode="ram_latest",
                   execution_allowed=False, hardware_writes=False, runtime=runtime_snapshot(),
                   bridge_age_seconds=0.1, bridge_stale=False, bridge_error="",
                   read_duration_seconds=0.1, session_changed=False,
                   source_age_seconds=0.0, source_stale=False, source_current=True)
    class Proxy:
        direct = False
        def set_timeout_millis(self, timeout):
            calls.append(("timeout", timeout))
        def set_source(self, source):
            calls.append(("source", source))
            self.direct = source == "DEV"
        def read_attributes(self, names):
            calls.append(("read", names))
            if mode.get("frozen_cache") and not self.direct:
                raise AssertionError("Frozen Tango polling cache must never be used")
            return [SimpleNamespace(has_failed=mode.get("failed", False), value=mode.get("state", "RUNNING")),
                    SimpleNamespace(has_failed=False, value=mode.get("raw", json.dumps(content)))]
    def factory(device):
        calls.append(("proxy", device))
        if mode.get("offline"):
            raise OSError("synthetic unavailable")
        return Proxy()
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    service = api.RuntimeAttributeReader(factory, lambda: api.tango_gateway.tango.DevSource.DEV,
                                         timeout=0.05)
    app.extensions["acq_runtime_read_service"] = service
    yield app, content, calls, mode, api
    assert service.close(1.0), "Fake runtime API reader leaked a worker"


def test_only_fixed_tango_attributes_read_and_no_device_selection(setup_api):
    app, content, calls, mode, api = setup_api
    response = app.test_client().get(URL + "?device=other/device&host=other&command=Start")
    assert response.status_code == 200
    assert calls == [("proxy", "tango://10.20.30.202:10000/elyse/acquisition/runtime"),
                     ("timeout", 1500), ("source", "DEV"), ("read", ["State", "runtime_json"])]
    body = response.json
    assert body["schema_version"] == 1
    assert body["source"] == "xp_python_acquisition_runtime"
    assert body["quality"] == "FRESH"
    assert body["session_id"] == content["runtime"]["session_id"]
    assert body["build_id"] == content["runtime"]["build_id"]
    assert body["execution_allowed"] is False and body["hardware_writes"] is False
    assert len(body["snapshot"]["runtime"]["latest"]["banks"]) == 6
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_all_mutation_methods_are_405_without_tango_access(setup_api, method):
    app, _, calls, _, _ = setup_api
    assert getattr(app.test_client(), method)(URL, json={"command": "GeneralMarche"}).status_code == 405
    assert calls == []


@pytest.mark.parametrize("change", [dict(age_seconds=10), dict(stale=True),
                                    dict(latest=dict(source="python_acquisition_demo", simulated=True, banks={}))])
def test_tango_on_and_fresh_wrapper_flags_do_not_override_source_validation(setup_api, change):
    app, content, _, mode, _ = setup_api
    mode["state"] = "ON"
    content["runtime"].update(change)
    body = app.test_client().get(URL).json
    assert body["quality"] == "STALE"
    assert body["source_stale"] is True
    assert body["snapshot"]["runtime"]["latest"] is None
    assert body["snapshot"]["measurements_hidden"] is True


def test_bridge_age_read_duration_and_tango_duration_independently_expire_values(setup_api):
    app, content, _, _, api = setup_api
    content["runtime"]["age_seconds"] = 1.6
    content["bridge_age_seconds"] = 0.2
    content["read_duration_seconds"] = 0.1
    body = api.present_snapshot(json.dumps(content), "RUNNING", read_duration_seconds=0.2)
    assert body["quality"] == "STALE"
    assert body["source_age_seconds"] == pytest.approx(2.1)
    assert body["bridge_stale"] is False
    content["bridge_age_seconds"] = 3.1
    body = api.present_snapshot(json.dumps(content), "ON")
    assert body["bridge_stale"] is True
    assert body["snapshot"]["runtime"]["latest"] is None


@pytest.mark.parametrize("change", [dict(runtime_protocol_version=1), dict(session_id="old-session"),
                                    dict(build_id=""), dict(state_revision=True), dict(recovery=None)])
def test_missing_or_invalid_runtime_identity_is_incompatible_not_fresh(setup_api, change):
    app, content, _, _, _ = setup_api
    content["runtime"].update(change)
    response = app.test_client().get(URL)
    assert response.status_code == 200
    body = response.json
    assert body["quality"] == "INCOMPATIBLE"
    assert body["session_id"] is None and body["build_id"] is None
    assert body["snapshot"]["runtime"]["latest"] is None
    assert body["execution_allowed"] is False


@pytest.mark.parametrize("state,quality", [("IDLE", "IDLE"), ("INITIALIZING", "EXECUTING"),
                                           ("DEINITIALIZING", "EXECUTING"), ("EXECUTING", "EXECUTING"),
                                           ("FAULT", "FAULT"), ("RECOVERY_REQUIRED", "RECOVERY_REQUIRED")])
def test_lifecycle_and_recovery_observations_never_expose_cached_ni_values(setup_api, state, quality):
    app, content, _, _, _ = setup_api
    content["runtime"]["state"] = state
    if state == "RECOVERY_REQUIRED":
        content["runtime"]["recovery"].update(required=True, reason="retained ownership marker")
    body = app.test_client().get(URL).json
    assert body["quality"] == quality
    assert body["runtime_state"] == state
    assert body["snapshot"]["runtime"]["latest"] is None
    assert body["source_stale"] is True


def test_guard_inactive_keeps_observation_fresh_without_enabling_commands(setup_api):
    app, content, _, _, _ = setup_api
    content["runtime"]["recovery"]["protection_active"] = False
    body = app.test_client().get(URL).json
    assert body["quality"] == "FRESH"
    assert body["execution_allowed"] is False
    assert body["snapshot"]["runtime"]["recovery"]["protection_active"] is False


def test_session_switch_hides_old_values_until_bridge_requalifies(setup_api):
    app, content, _, _, _ = setup_api
    client = app.test_client()
    assert client.get(URL).json["quality"] == "FRESH"
    content["runtime"]["session_id"] = "2" * 32
    content["runtime"]["latest"]["banks"]["C1_NI6071E_AI"]["values"][0] = 9.0
    content["session_changed"] = True
    body = client.get(URL).json
    assert body["quality"] == "STALE"
    assert body["session_id"] == "2" * 32
    assert body["snapshot"]["runtime"]["latest"] is None
    content["session_changed"] = False
    body = client.get(URL).json
    assert body["quality"] == "FRESH"
    assert body["snapshot"]["runtime"]["latest"]["banks"]["C1_NI6071E_AI"]["values"][0] == 9.0


def test_bridge_revision_rollback_diagnostic_prevents_fresh(setup_api):
    app, content, _, _, _ = setup_api
    content["bridge_protocol_error"] = "Runtime state revision moved backwards within one session"
    body = app.test_client().get(URL).json
    assert body["quality"] == "INCOMPATIBLE"
    assert body["snapshot"]["runtime"]["latest"] is None


def test_error_clears_previous_values_without_fallback_or_previous_session_cache(setup_api):
    app, _, calls, mode, _ = setup_api
    client = app.test_client()
    assert client.get(URL).json["quality"] == "FRESH"
    mode["offline"] = True
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json["quality"] == "UNAVAILABLE"
    assert response.json["snapshot"] is None
    assert len([item for item in calls if item[0] == "proxy"]) == 2


def test_direct_source_avoids_frozen_tango_polling_cache(setup_api):
    app, content, calls, mode, _ = setup_api
    mode["frozen_cache"] = True
    content["runtime"]["age_seconds"] = 99
    response = app.test_client().get(URL)
    assert response.status_code == 200
    assert response.json["quality"] == "STALE"
    assert ("source", "DEV") in calls
    assert response.json["snapshot"]["runtime"]["latest"] is None


def test_missing_direct_source_support_fails_closed_without_cached_read(setup_api, monkeypatch):
    app, _, calls, _, api = setup_api
    monkeypatch.delattr(api.tango_gateway.tango, "DevSource")
    response = app.test_client().get(URL)
    assert response.status_code == 503
    assert response.json["snapshot"] is None
    assert not any(item[0] == "read" for item in calls)


@pytest.mark.parametrize("defect", ["source", "hardware", "nan", "duplicate", "oversize", "attribute"])
def test_wrong_or_corrupt_bridge_is_unavailable_without_values(setup_api, defect):
    app, content, _, mode, api = setup_api
    if defect == "source":
        content["source"] = "copied_labview_telemetry"
    elif defect == "hardware":
        content["hardware_writes"] = True
    elif defect == "nan":
        content["runtime"]["age_seconds"] = float("nan")
    elif defect == "duplicate":
        mode["raw"] = '{"source":"one","source":"two"}'
    elif defect == "oversize":
        mode["raw"] = " " * (api.MAX_JSON_BYTES + 1)
    else:
        mode["failed"] = True
    response = app.test_client().get(URL)
    assert response.status_code == 503
    assert response.json["quality"] == "UNAVAILABLE"
    assert response.json["snapshot"] is None


def test_explicit_bridge_error_precedes_wrong_identity(setup_api):
    app, content, _, _, _ = setup_api
    content["runtime"].pop("session_id")
    content["bridge_error"] = "read failed"
    body = app.test_client().get(URL).json
    assert body["quality"] == "UNAVAILABLE"
    assert body["snapshot"]["runtime"]["latest"] is None


def test_large_integer_preserved_and_response_is_strict_json(setup_api):
    app, content, _, _, api = setup_api
    content["runtime"]["diagnostic_counter"] = 2**63 - 1
    body = app.test_client().get(URL).json
    assert body["snapshot"]["runtime"]["diagnostic_counter"] == {"integer_decimal": "9223372036854775807"}
    invalid_duration = api.present_snapshot(json.dumps(content), "RUNNING", float("inf"))
    assert invalid_duration["quality"] == "STALE"
    json.dumps(invalid_duration, allow_nan=False)


def test_production_get_requires_existing_jwt_before_tango_access(setup_api, monkeypatch):
    app, _, calls, _, _ = setup_api
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    client = app.test_client()
    assert client.get(URL).status_code == 401
    assert calls == []
    assert app.extensions["acq_runtime_read_service"]._flight is None
    with app.app_context():
        token = create_access_token(identity="operator")
    assert client.get(URL, headers={"Authorization": "Bearer " + token}).status_code == 200


@pytest.mark.parametrize("blocked_phase", ["factory", "read"])
def test_hung_complete_tango_read_is_single_flight_caller_bounded_and_recovers(setup_api, blocked_phase):
    app, content, _, _, api = setup_api
    # Explicit replacement is safe only because the fixture service is idle.
    assert app.extensions["acq_runtime_read_service"].close(1.0)
    entered, release = threading.Event(), threading.Event()
    calls = []
    blocking = [True]
    class Proxy:
        def set_timeout_millis(self, value):
            calls.append(("timeout", value))
        def set_source(self, value):
            calls.append(("source", value))
        def read_attributes(self, names):
            calls.append(("read", names))
            if blocking[0] and blocked_phase == "read":
                entered.set()
                assert release.wait(2)
            return [SimpleNamespace(has_failed=False, value="RUNNING"),
                    SimpleNamespace(has_failed=False, value=json.dumps(content))]
    def factory(device):
        calls.append(("factory", device))
        if blocking[0] and blocked_phase == "factory":
            entered.set()
            assert release.wait(2)
        return Proxy()
    service = api.RuntimeAttributeReader(factory, lambda: "DEV", timeout=0.02)
    app.extensions["acq_runtime_read_service"] = service
    try:
        first = app.test_client().get(URL)
        assert entered.is_set()
        assert first.status_code == 503 and first.json["snapshot"] is None
        assert service._flight.thread.is_alive()
        # Repeated browser retries must not create more blocked workers.
        for _ in range(4):
            retry = app.test_client().get(URL)
            assert retry.status_code == 503 and retry.json["quality"] == "UNAVAILABLE"
        assert len([item for item in calls if item[0] == "factory"]) == 1
        blocked_flight = service._flight
        blocking[0] = False
        release.set()
        blocked_flight.thread.join(1)
        assert not blocked_flight.thread.is_alive()
        assert blocked_flight.result is None  # Late old reply never becomes a cache.
        recovered = app.test_client().get(URL)
        assert recovered.status_code == 200 and recovered.json["quality"] == "FRESH"
        assert service._flight is not blocked_flight
        assert len([item for item in calls if item[0] == "factory"]) == 2
    finally:
        release.set()
        assert service.close(1.0)


def test_concurrent_callers_share_one_active_flight_and_never_overlap_proxy_factories(setup_api):
    app, content, _, _, api = setup_api
    entered, release, calls = threading.Event(), threading.Event(), []
    class Proxy:
        def set_timeout_millis(self, value):
            pass
        def set_source(self, value):
            assert value == "DEV"
        def read_attributes(self, names):
            entered.set()
            assert release.wait(2)
            return [SimpleNamespace(has_failed=False, value="RUNNING"),
                    SimpleNamespace(has_failed=False, value=json.dumps(content))]
    def factory(device):
        calls.append(device)
        return Proxy()
    admitted, caller_names = threading.Event(), set()
    def clock():
        name = threading.current_thread().name
        if name.startswith("runtime-api-test-caller-"):
            caller_names.add(name)
            if len(caller_names) == 3:
                admitted.set()
        return time.monotonic()
    service = api.RuntimeAttributeReader(factory, lambda: "DEV", timeout=1.0, clock=clock)
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.read()),
                                name="runtime-api-test-caller-" + str(index)) for index in range(3)]
    try:
        for thread in threads:
            thread.start()
        assert entered.wait(1)
        assert admitted.wait(1)
        # A single retained flight admits every concurrent caller.
        assert calls == [api.DEVICE]
        release.set()
        for thread in threads:
            thread.join(2)
            assert not thread.is_alive()
        assert len(results) == 3
        assert calls == [api.DEVICE]
    finally:
        release.set()
        assert service.close(1.0)


def test_process_inherited_service_is_rejected_without_creating_a_worker(setup_api):
    _, _, _, _, api = setup_api
    service = api.RuntimeAttributeReader(lambda *_: pytest.fail("factory called"), lambda: "DEV")
    service._pid = -1
    with pytest.raises(RuntimeError, match="inherited across processes"):
        service.read()
    assert service._flight is None


def test_reader_elapsed_includes_caller_resume_delay_after_worker_completion(setup_api):
    _, content, _, _, api = setup_api
    class Proxy:
        def set_timeout_millis(self, _):
            pass
        def set_source(self, _):
            pass
        def read_attributes(self, _):
            return [SimpleNamespace(has_failed=False, value="RUNNING"),
                    SimpleNamespace(has_failed=False, value=json.dumps(content))]
    caller_times = iter((100.0, 100.0, 100.2, 100.3))
    def clock():
        if threading.current_thread().name == "ACQ-runtime-web-read":
            return 100.1
        return next(caller_times)
    service = api.RuntimeAttributeReader(lambda _: Proxy(), lambda: "DEV", clock=clock)
    try:
        _, _, elapsed = service.read()
        assert elapsed == pytest.approx(0.3)
        assert elapsed > 0.1  # Worker I/O alone would undercount source age.
    finally:
        assert service.close(1)


@pytest.mark.parametrize("bad_clock", [float("nan"), float("inf"), -1.0])
def test_reader_invalid_or_backwards_completion_clock_hides_reply(setup_api, bad_clock):
    _, content, _, _, api = setup_api
    class Proxy:
        def set_timeout_millis(self, _):
            pass
        def set_source(self, _):
            pass
        def read_attributes(self, _):
            return [SimpleNamespace(has_failed=False, value="RUNNING"),
                    SimpleNamespace(has_failed=False, value=json.dumps(content))]
    caller_times = iter((100.0, 100.0, 100.2, bad_clock))
    def clock():
        if threading.current_thread().name == "ACQ-runtime-web-read":
            return 100.1
        return next(caller_times)
    service = api.RuntimeAttributeReader(lambda _: Proxy(), lambda: "DEV", clock=clock)
    try:
        with pytest.raises(RuntimeError):
            service.read()
        assert service._flight.result is None
    finally:
        assert service.close(1)
