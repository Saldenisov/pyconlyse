"""Software-only V0 supply plan; no physical power commands."""

import json
from types import SimpleNamespace

from flask import Flask, jsonify
import pytest

from tests.web.test_pump_probe_v0_api import v0_api_module as api
import v0_experiment_shutdown as shutdown
from experiment_lifecycle import ExperimentLifecycle


@pytest.fixture
def rig(monkeypatch):
    events = []
    power = {shutdown.SD1: {1: 1, 2: 1, 3: 1, 4: 1},
             shutdown.SD2: {1: 0, 2: 1, 3: 1, 4: 1},
             shutdown.STAGE_POWER: {1: 0, 2: 1, 3: 1, 4: 1}}
    faults = {}
    temperatures = [-50, -10, 1]
    camera_state = {"sdk": True}
    stage_state = {"position": -700.0, "status": "0", "last_error": ""}
    clock = [0.0]
    camera_connections = [0]
    vd2 = dict(application_running=False, connected=False, protocol_active=False, lifecycle_active=False)

    class Proxy:
        def __init__(self, device):
            self.device = device

        def set_timeout_millis(self, _timeout):
            pass

        def lock(self, _seconds):
            events.append((self.device, "lock", None))

        def unlock(self):
            events.append((self.device, "unlock", None))
            if faults.get("unlock_stage") and self.device == shutdown.STAGE:
                raise RuntimeError("Stage unlock failed")

        def state(self):
            return "ON" if camera_state["sdk"] else "OFF"

        def get_command_list(self):
            camera_connections[0] += 1
            if faults.get("camera_connection_down") or camera_connections[0] <= faults.get("camera_connection_failures", 0):
                raise ConnectionError("Andor is unreachable")
            return [] if faults.get("legacy_server") else ["BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup"]

        def read_attribute(self, name):
            if name == "last_error":
                return SimpleNamespace(value=stage_state["last_error"])
            if name == "automatic_search_status":
                return SimpleNamespace(value="running" if faults.get("alignment_active") else "idle")
            if name == "automatic_search_progress":
                return SimpleNamespace(value=json.dumps({"phase": "manual_point" if faults.get("manual_point_active") else "idle"}))
            if name == "alignment_pending_reference_json":
                return SimpleNamespace(value='{"pending": true}' if faults.get("pending_alignment") else '{}')
            ids = [3, 1, 4, 2]
            return SimpleNamespace(value=ids if name == "ids" else [power[self.device][i] for i in ids])

        def command_inout(self, command, argument=None):
            events.append((self.device, command, argument))
            if faults.get(command):
                raise TimeoutError(f"{command} failed; outcome may be unknown")
            if command == "set_channels_states":
                power[self.device].update(zip([3, 1, 4, 2], argument))
                if faults.get("accepted_power_timeout"):
                    raise TimeoutError("Accepted write timed out")
                return
            if command == "get_status_axis":
                assert self.device == shutdown.STAGE_BACKEND and argument == 3
                return stage_state["status"]
            if command == "read_position_axis":
                assert self.device == shutdown.STAGE_BACKEND and argument == 3
                return stage_state["position"]
            if command == "move_axis":
                assert self.device == shutdown.STAGE and argument == [3.0, 0.0]
                stage_state.update(position=-10.0 if faults.get("stage_stuck") else 0.0,
                                   status="6" if faults.get("stage_stuck") else "0")
                if faults.get("move_accepted_timeout"):
                    raise TimeoutError("Move may already be running")
                if faults.get("move_rejected"):
                    return "target rejected"
                return "0"
            if command == "stop_axis":
                assert self.device == shutdown.STAGE and argument == 3
                stage_state["status"] = "0"
                return "0"
            if command in {"BeginSafePowerOff", "GetPowerOffSafety"}:
                temperature = temperatures.pop(0) if len(temperatures) > 1 else temperatures[0]
                return json.dumps({"temperature_c": temperature, "cooler_on": faults.get("cooler_on", False),
                                   "acquisition_active": faults.get("still_acquiring", False),
                                   "fresh_sdk_readback": not faults.get("cached_readback", False)})
            if command == "ReleaseAfterWarmup":
                camera_state["sdk"] = False
                if faults.get("stage_drift_after_warmup"):
                    stage_state["position"] = 2.0
                return "SDK released"
            pytest.fail(f"Unexpected mutation: {command}")

    def proxy(device, **_kwargs):
        if faults.get(device):
            raise RuntimeError(f"{device} unavailable")
        assert device in {shutdown.SD1, shutdown.SD2, shutdown.CAMERA, shutdown.STAGE,
                          shutdown.STAGE_BACKEND, shutdown.STAGE_POWER,
                          "manip/V0/LaserPointing-Cam1", "manip/V0/LaserPointing-Cam2"}
        return Proxy(device)

    monkeypatch.setattr(shutdown.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(shutdown.time, "monotonic", lambda: clock[0])
    return SimpleNamespace(events=events, power=power, faults=faults, temperatures=temperatures,
                           camera_state=camera_state, vd2=vd2, proxy=proxy, stage_state=stage_state,
                           camera_connections=camera_connections,
                           stop=lambda: events.append(("web", "stop_sequence", None)))


def run(rig, steps=None):
    return shutdown.execute_shutdown(rig.proxy, [] if steps is None else steps, rig.stop, lambda: rig.vd2)


def test_verified_shutdown_disables_exact_operator_scope_after_warmup(rig):
    result = run(rig)
    writes = [(device, states) for device, command, states in rig.events if command == "set_channels_states"]
    assert writes == [(shutdown.SD2, [1, 0, 1, 0]), (shutdown.SD1, [1, 0, 1, 1]),
                      (shutdown.SD2, [1, 0, 0, 0]), (shutdown.SD2, [0, 0, 0, 0])]
    assert rig.power[shutdown.SD1] == {1: 0, 2: 1, 3: 1, 4: 1}
    assert rig.power[shutdown.SD2] == {1: 0, 2: 0, 3: 0, 4: 0}
    release = next(i for i, event in enumerate(rig.events) if event[1] == "ReleaseAfterWarmup")
    camera_power = next(i for i, event in enumerate(rig.events) if event[:2] == (shutdown.SD1, "set_channels_states"))
    assert release < camera_power
    trigger = next(i for i, event in enumerate(rig.events) if event[:2] == (shutdown.SD2, "set_channels_states"))
    move = next(i for i, event in enumerate(rig.events) if event[1] == "move_axis")
    begin_warmup = next(i for i, event in enumerate(rig.events) if event[1] == "BeginSafePowerOff")
    assert trigger < move < begin_warmup < release < camera_power
    assert rig.stage_state["position"] == 0.0
    assert rig.power[shutdown.STAGE_POWER] == {1: 0, 2: 1, 3: 1, 4: 1}
    assert "axis 3 verified at 0 mm" in result["message"]
    assert "supplies verified OFF" in result["message"]
    assert sum(command == "move_axis" for _, command, _ in rig.events) == 1
    assert not any(command in {"DevStart", "DevStop", "Init", "turn_on", "Home", "define_position_axis"} for _, command, _ in rig.events)


def test_repeat_shutdown_is_no_power_or_camera_replay(rig):
    run(rig)
    rig.events.clear()
    run(rig)
    assert ("web", "stop_sequence", None) in rig.events
    assert not any(command in {"move_axis", "stop_axis", "set_channels_states", "BeginSafePowerOff", "ReleaseAfterWarmup"}
                   for _, command, _ in rig.events)


@pytest.mark.parametrize("condition", ["application_running", "connected", "protocol_active", "lifecycle_active", "streak_power"])
def test_active_vd2_blocks_every_v0_shutdown_mutation(rig, condition):
    if condition == "streak_power":
        rig.power[shutdown.SD2][1] = 1
    else:
        rig.vd2[condition] = True
    with pytest.raises(shutdown.ShutdownFailure, match="VD2"):
        run(rig)
    assert not rig.events


@pytest.mark.parametrize("fault", ["BeginSafePowerOff", "GetPowerOffSafety", "ReleaseAfterWarmup",
                                   "cooler_on", "still_acquiring", "cached_readback", "legacy_server", shutdown.CAMERA, shutdown.SD1])
def test_unverified_camera_preserves_its_power_but_completes_independent_supplies(rig, fault):
    rig.faults[fault] = True
    with pytest.raises(shutdown.ShutdownFailure, match="Andor power retained"):
        run(rig)
    assert rig.power[shutdown.SD1][1] == 1
    assert rig.power[shutdown.SD2] == {1: 0, 2: 0, 3: 0, 4: 0}
    assert sum(command == "BeginSafePowerOff" for _, command, _ in rig.events) <= 1


def test_cold_camera_timeout_keeps_camera_power_and_releases_ownership_lock(rig, monkeypatch):
    rig.temperatures[:] = [-50]
    monkeypatch.setattr(shutdown, "WARMUP_TIMEOUT_S", 0.5)
    with pytest.raises(shutdown.ShutdownFailure, match="15 minutes"):
        run(rig)
    assert rig.power[shutdown.SD1][1] == 1
    assert (shutdown.CAMERA, "unlock", None) in rig.events


def test_unknown_trigger_power_write_outcome_is_not_replayed_or_followed_by_camera_cut(rig):
    rig.faults["accepted_power_timeout"] = True
    with pytest.raises(shutdown.ShutdownFailure, match="DG645 power-off unverified"):
        run(rig)
    assert sum(command == "set_channels_states" for _, command, _ in rig.events) == 1
    assert rig.power[shutdown.SD1][1] == 1
    assert not any(device == shutdown.CAMERA for device, _, _ in rig.events)


def test_denied_route_has_no_proxy_or_lifecycle_access(monkeypatch):
    monkeypatch.setattr(api, "require_http_hardware", lambda *_args, **_kwargs: (jsonify({"success": False}), 428))
    monkeypatch.setattr(api, "_v0_lifecycle", lambda: pytest.fail("No lifecycle or hardware on denial"))
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    assert app.test_client().post("/api/pump-probe-v0/deinitialize").status_code == 428


def test_authorization_plan_returns_only_v0_axis_3_and_preserves_unrelated_power():
    targets, args = api._v0_shutdown_authorization()
    assert {(item["device"], item["output_id"]) for item in args["pdu_output_states"]} == {
        (shutdown.SD1, 1), (shutdown.SD2, 2), (shutdown.SD2, 3), (shutdown.SD2, 4)}
    assert {(target["device"], target["command"]) for target in targets if "OWIS" in target["device"]} == {
        (shutdown.STAGE, "move_axis"), (shutdown.STAGE, "stop_axis")}
    assert args["translation_stage_return"] == {
        "device": shutdown.STAGE, "backend": shutdown.STAGE_BACKEND,
        "axis": 3, "position_mm": 0.0, "tolerance_mm": 0.01,
        "timeout_s": 900.0, "home_or_redefine": False}
    assert not any("STANDA" in target["device"] or "VD2/PDU" in target["device"] for target in targets)


@pytest.mark.parametrize("position", [0.0, 0.005, -0.005])
def test_already_zero_requires_stationary_readbacks_but_no_move(rig, position):
    rig.stage_state["position"] = position
    result = run(rig)
    assert not any(command == "move_axis" for _, command, _ in rig.events)
    parked = next(step for step in result["steps"] if step["step"] == "V0 translation stage")
    assert parked["final_mm"] == position
    assert parked["status"] == "verified 0 mm (3 stationary readbacks)"


@pytest.mark.parametrize("fault", [shutdown.STAGE, shutdown.STAGE_BACKEND, "alignment_active",
                                   "manual_point_active", "pending_alignment", "get_status_axis", "read_position_axis"])
def test_unavailable_or_busy_stage_does_not_block_independent_camera_poweroff(rig, fault):
    rig.faults[fault] = True
    with pytest.raises(shutdown.ShutdownFailure, match="translation stage not parked"):
        run(rig)
    assert not any(command in {"move_axis", "stop_axis"} for _, command, _ in rig.events)
    assert rig.power[shutdown.SD1][1] == 0
    assert rig.power[shutdown.STAGE_POWER][2] == 1


@pytest.mark.parametrize("state", ["1", "8", "OFF", "FAULT", "6", "10", "MOVING"])
def test_stage_unknown_or_existing_motion_never_receives_return_or_stop(rig, state):
    rig.stage_state["status"] = state
    with pytest.raises(shutdown.ShutdownFailure, match="translation stage not parked"):
        run(rig)
    assert not any(command in {"move_axis", "stop_axis"} for _, command, _ in rig.events)


@pytest.mark.parametrize("position", [float("nan"), float("inf"), True, "invalid"])
def test_invalid_stage_position_fails_closed(rig, position):
    rig.stage_state["position"] = position
    with pytest.raises(shutdown.ShutdownFailure, match="translation stage not parked"):
        run(rig)
    assert not any(command == "move_axis" for _, command, _ in rig.events)


def test_cached_zero_with_backend_error_is_not_accepted(rig):
    rig.stage_state.update(position=0.0, last_error="native position read failed")
    with pytest.raises(shutdown.ShutdownFailure, match="native position read failed"):
        run(rig)
    assert not any(command == "move_axis" for _, command, _ in rig.events)


@pytest.mark.parametrize("position", [-1000.0, 1000.0])
def test_out_of_range_initial_position_cannot_start_automatic_return(rig, position):
    rig.stage_state["position"] = position
    with pytest.raises(shutdown.ShutdownFailure, match="outside the approved travel range"):
        run(rig)
    assert not any(command == "move_axis" for _, command, _ in rig.events)


def test_stage_unlock_failure_does_not_leave_laser_controller_locks_unreleased(rig):
    rig.faults["unlock_stage"] = True
    with pytest.raises(shutdown.ShutdownFailure, match="ownership-lock release unverified"):
        run(rig)
    for name in ["manip/V0/LaserPointing-Cam1", "manip/V0/LaserPointing-Cam2"]:
        assert (name, "unlock", None) in rig.events


def test_stage_drift_during_camera_warmup_cannot_report_completed_shutdown(rig):
    rig.faults["stage_drift_after_warmup"] = True
    with pytest.raises(shutdown.ShutdownFailure, match="Final V0 translation-stage zero unverified"):
        run(rig)
    assert sum(command == "move_axis" for _, command, _ in rig.events) == 1


def test_stage_power_off_is_not_implicitly_switched_on(rig):
    rig.power[shutdown.STAGE_POWER][2] = 0
    with pytest.raises(shutdown.ShutdownFailure, match="Unprepare does not switch it on"):
        run(rig)
    assert not any(device == shutdown.STAGE_POWER for device, _, _ in rig.events)


@pytest.mark.parametrize("fault", ["move_accepted_timeout", "move_rejected", "stage_stuck"])
def test_failed_return_stops_once_never_replays_move_and_finishes_independent_shutdown(rig, monkeypatch, fault):
    rig.faults[fault] = True
    monkeypatch.setattr(shutdown, "STAGE_TIMEOUT_S", 1.0)
    with pytest.raises(shutdown.ShutdownFailure, match="translation stage not parked"):
        run(rig)
    assert sum(command == "move_axis" for _, command, _ in rig.events) == 1
    assert sum(command == "stop_axis" for _, command, _ in rig.events) == 1
    assert rig.power[shutdown.SD1][1] == 0
    assert rig.power[shutdown.STAGE_POWER][2] == 1
    assert (shutdown.STAGE, "unlock", None) in rig.events


def test_temporary_camera_disconnect_is_retried_readonly_without_write_replay(rig):
    rig.faults["camera_connection_failures"] = 2
    run(rig)
    assert rig.camera_connections[0] == 3
    assert sum(command == "BeginSafePowerOff" for _, command, _ in rig.events) == 1
    assert rig.power[shutdown.SD1][1] == 0


def test_unreachable_camera_keeps_supply_on_and_reports_actionable_failure(rig):
    rig.faults["camera_connection_down"] = True
    with pytest.raises(shutdown.ShutdownFailure, match="restore its connection on Elysium2"):
        run(rig)
    assert rig.camera_connections[0] == 3
    assert not any(command == "BeginSafePowerOff" for _, command, _ in rig.events)
    assert rig.power[shutdown.SD1][1] == 1
    assert rig.stage_state["position"] == 0.0


def test_v0_restores_progress_on_restart_without_touching_hardware(tmp_path):
    path = tmp_path / "v0.sqlite3"
    lifecycle = ExperimentLifecycle(path, experiment="V0")
    lifecycle.put("job", {"status": "running", "experiment": "V0", "operation": "shutdown", "steps": [
        {"step": "SD2/2 DG645", "status": "verified OFF"}], "job_id": "warmup", "phase": "CCD warm-up"})
    restored = ExperimentLifecycle(path, experiment="V0").snapshot()
    assert restored["status"] == "interrupted"
    assert restored["steps"] == [{"step": "SD2/2 DG645", "status": "verified OFF"}]
    assert restored["experiment"] == "V0"


@pytest.mark.parametrize("path", ["run", "realtime", "stage/move", "stage/stop", "sample-stage/move", "sample-stage/stop"])
def test_new_v0_commands_cannot_race_shared_supply_shutdown(path):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    assert api.EXPERIMENT_MUTATION_LOCK.acquire(blocking=False)
    try:
        response = app.test_client().post("/api/pump-probe-v0/" + path, json={})
        assert response.status_code == 409
    finally:
        api.EXPERIMENT_MUTATION_LOCK.release()
