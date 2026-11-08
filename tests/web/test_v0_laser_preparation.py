"""Power-first V0 laser setup: fake equipment only; no real Tango I/O."""

import copy
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from flask import Flask

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
sys.path.insert(0, str(BACKEND)) if str(BACKEND) not in sys.path else None
import pump_probe_v0_api as api
from experiment_lifecycle import ExperimentLifecycle
from pump_probe_v0_config import V0_CAMERA_DEVICES, V0_LASER_POINTING_DEVICES, V0_STANDA_DEVICES


class Equipment:
    def __init__(self):
        self.calls = []
        self.states = {}
        self.outputs = {"manip/V0/PDU_VO": [1, 0, 0, 1], "manip/SD2/PDU_SD2": [0, 0, 0, 0]}
        self.streaming = dict.fromkeys(V0_CAMERA_DEVICES, False)
        self.timings = {"BURM?": "1", "DLAY?1": "0,+0.0004"}
        self.counter = 0
        self.broken = set()
        self.servers = {}
        self.running = {api.V0_STARTER_DEVICE: set(), api.V0_STANDA_STARTER_DEVICE: set()}
        self.dependencies = {}
        for index, name in enumerate(V0_LASER_POINTING_DEVICES):
            self.dependencies[name] = {"Camera": V0_CAMERA_DEVICES[index],
                **{f"Actuator{role}": f"elyse/motorized_devices/mm{index}_{role}" for role in ("X1", "Y1", "X2", "Y2")},
                "Shutter1": "manip/V0/S1"}
        devices = [*self.outputs, *V0_CAMERA_DEVICES, *V0_LASER_POINTING_DEVICES,
                   *V0_STANDA_DEVICES, *api.DEFAULT_HARDWARE_CONFIG.values()]
        devices += [child for deps in self.dependencies.values() for child in deps.values()]
        for name in devices:
            if not isinstance(name, str) or "/" not in name:
                continue
            motor = name in V0_STANDA_DEVICES or name.startswith("elyse/motorized_devices/")
            self.servers[name] = ("DS_Standa_Motor/" if motor else "DS_Test/") + name.replace("/", "_")
            self.running[api.V0_STANDA_STARTER_DEVICE if motor else api.V0_STARTER_DEVICE].add(self.servers[name])
            self.states[name] = "OFF" if name in V0_CAMERA_DEVICES else "ON"

    def proxy(self, name, **_kwargs):
        world = self

        class Proxy:
            def state(self):
                return world.states[name]

            def get_property(self, _names):
                return {"ds_dict": [repr(world.dependencies[name])]}

            def get_command_list(self):
                return ["recover", "turn_on", "Init"]

            def read_attribute(self, attr):
                if attr == "ids": value = [1, 2, 3, 4]
                elif attr == "names": value = ["kept", "DG645", "control", "current"]
                elif attr == "states": value = list(world.outputs[name])
                elif attr == "isgrabbing": value = world.streaming[name]
                elif attr == "image": value = np.ones((4, 4))
                else: raise RuntimeError(f"Unexpected attribute {name}/{attr}")
                return SimpleNamespace(value=value)

            def command_inout(self, cmd, arg=None):
                world.calls.append((name, cmd, arg))
                if cmd == "DevGetRunningServers": return list(world.running[name])
                if world.servers.get(name, "").startswith("DS_Standa_Motor/"):
                    pytest.fail(f"No STANDA command is allowed: {name}/{cmd}")
                if cmd == "set_channels_states":
                    world.outputs[name] = [old if action == 5 else action for old, action in zip(world.outputs[name], arg)]
                elif cmd in ("recover", "turn_on", "Init"):
                    if name in world.broken: raise RuntimeError("deliberately unavailable")
                    world.states[name] = "ON"
                elif cmd == "start_grabbing": world.streaming[name] = True
                elif cmd == "get_status_axis": return "ON"
                elif cmd == "read_position_axis": return 1.25
                elif cmd == "scpi_query": return "DG645 test" if arg == "*IDN?" else world.timings[arg]
                elif cmd == "read_counter":
                    world.counter += 5
                    return world.counter
                else: pytest.fail(f"Unexpected hardware command: {name}/{cmd} {arg}")
        return Proxy()


@pytest.fixture
def rig(monkeypatch):
    world = Equipment()
    controller = api.PumpProbeV0Controller()
    monkeypatch.setattr(api, "_tango_proxy", world.proxy)
    monkeypatch.setattr(api, "_server_name_for_device", lambda name: world.servers[name])
    monkeypatch.setattr(api, "_load_dg645_recall_config", lambda _: {"snapshot": {"raw_queries": copy.deepcopy(world.timings)}})
    monkeypatch.setattr(api.time, "sleep", lambda _: None)
    monkeypatch.setattr(controller, "_starter_server_snapshot", lambda starter: (
        {"label": starter, "ok": True}, set(world.running[starter])))
    return world, controller


def test_preparation_powers_only_explicit_outputs_and_verifies_laser_dependencies(rig):
    world, controller = rig
    timings = dict(world.timings)
    result = controller.hardware_preflight(fix=True)
    assert result["success"]
    assert world.outputs == {"manip/V0/PDU_VO": [1, 1, 1, 1], "manip/SD2/PDU_SD2": [0, 1, 1, 1]}
    assert all(world.streaming.values())
    assert world.timings == timings
    assert all(cmd != "scpi_write" for _, cmd, _ in world.calls)
    power = [arg for _, cmd, arg in world.calls if cmd == "set_channels_states"]
    assert power == [[5, 1, 5, 5], [5, 5, 1, 5], [5, 1, 5, 5], [5, 5, 1, 5], [5, 5, 5, 1]]
    assert sum(check["label"].endswith("functional readiness") and check["ok"] for check in result["checks"]) == 2
    # A repeated Prepare performs queries only; it does not reset ready equipment.
    world.calls.clear()
    assert controller.hardware_preflight(fix=True)["success"]
    assert {cmd for _, cmd, _ in world.calls} <= {"scpi_query", "get_status_axis", "read_position_axis", "read_counter"}


def test_passive_preflight_remains_nonmutating(rig):
    world, controller = rig
    before = copy.deepcopy(world.outputs)
    result = controller.hardware_preflight(fix=False)
    assert result["read_only"] is True
    assert world.outputs == before
    assert not any(cmd in {"DevStart", "Init", "turn_on", "recover", "start_grabbing", "set_channels_states", "scpi_write"}
                   for _, cmd, _ in world.calls)


def test_standby_standa_and_mirror_aliases_are_never_initialised(rig):
    world, controller = rig
    mirror = next(child for child in world.dependencies[V0_LASER_POINTING_DEVICES[0]].values() if child.startswith("elyse/"))
    world.states[V0_STANDA_DEVICES[0]] = "STANDBY"
    world.states[mirror] = "STANDBY"
    result = controller.hardware_preflight(fix=True)
    assert not result["success"]
    assert world.states[mirror] == "STANDBY"
    assert any(check["label"] == "Laser Pointing 1 functional readiness" and not check["ok"] for check in result["checks"])
    # A caller misclassifying a motor as a local instrument is also fail-closed.
    controller._check_device("miswired local device", mirror, fix=True, starter_name=api.V0_STARTER_DEVICE)
    assert world.states[mirror] == "STANDBY"
    assert not any(name == mirror for name, _, _ in world.calls)


def test_failed_branch_does_not_block_independent_power_and_pointing_checks(rig):
    world, controller = rig
    pdu = "manip/V0/PDU_VO"
    world.broken.add(pdu)
    world.states[pdu] = "FAULT"
    result = controller.hardware_preflight(fix=True)
    assert not result["success"]
    assert world.outputs["manip/SD2/PDU_SD2"] == [0, 1, 1, 1]
    assert any(check["label"] == "Laser Pointing 2 functional readiness" for check in result["checks"])
    assert not any(cmd in {"DevStop", "HardKillServer"} for _, cmd, _ in world.calls)


def test_timing_mismatch_is_reported_without_recall_or_write(rig, monkeypatch):
    world, controller = rig
    monkeypatch.setattr(api, "_load_dg645_recall_config", lambda _: {"snapshot": {"raw_queries": {"DLAY?1": "0,+0.0022"}}})
    result = controller.hardware_preflight(fix=True)
    assert not result["success"]
    assert any(check["label"] == "DG645 recall 8" and not check["ok"] for check in result["checks"])
    assert not any(cmd == "scpi_write" for _, cmd, _ in world.calls)


def test_standa_server_start_is_rejected_before_starter_access(monkeypatch):
    monkeypatch.setattr(api, "_server_name_for_device", lambda _: "DS_Standa_Motor/7_DV01")
    monkeypatch.setattr(api, "_starter_for_server", lambda *a, **kw: pytest.fail("No STANDA start anywhere"))
    with pytest.raises(RuntimeError, match="never starts"):
        api._restart_server_for_device("manip/V0/DV01", preferred_starter=api.V0_STARTER_DEVICE)


@pytest.fixture
def lifecycle_client(monkeypatch, tmp_path):
    lifecycle = ExperimentLifecycle(tmp_path / "lifecycle.sqlite3", experiment="V0")
    monkeypatch.setattr(api, "_v0_lifecycle_instance", lifecycle)
    monkeypatch.setattr(api, "EXPERIMENT_MUTATION_LOCK", threading.Lock())
    monkeypatch.setattr(api, "authorization_required", lambda: False)
    monkeypatch.setattr(api, "_guard_v0_hardware", lambda *a: None)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    return app.test_client(), lifecycle


def test_background_prepare_attaches_persists_failure_and_get_never_replays(lifecycle_client, monkeypatch):
    client, lifecycle = lifecycle_client
    entered, release = threading.Event(), threading.Event()
    calls = []

    def prepare(steps):
        calls.append("prepare")
        steps.append({"step": "PDU SD2/2", "status": "verified", "detail": "ON"})
        entered.set()
        assert release.wait(3)
        raise api.V0PreparationFailure({"checks": [{"label": "STANDA Elysium2", "ok": False, "detail": "STANDBY"}]})

    monkeypatch.setattr(api, "_prepare_v0_experiment", prepare)
    first = client.post("/api/pump-probe-v0/hardware/initialize?background=1").get_json()["job"]
    assert entered.wait(1)
    second = client.post("/api/pump-probe-v0/hardware/initialize?background=1")
    assert second.status_code == 202
    assert second.get_json()["attached"]
    assert second.get_json()["job"]["job_id"] == first["job_id"]
    assert client.get("/api/pump-probe-v0/lifecycle").get_json()["job"]["steps"][0]["detail"] == "ON"
    release.set()
    for _ in range(100):
        if lifecycle.snapshot()["status"] != "running": break
        time.sleep(0.01)
    assert lifecycle.snapshot()["status"] == "failed"
    assert lifecycle.snapshot()["steps"][0]["detail"] == "STANDBY"
    assert len(lifecycle.events()) >= 3
    restored = ExperimentLifecycle(lifecycle.path, experiment="V0")
    assert restored.snapshot()["job_id"] == first["job_id"]
    assert calls == ["prepare"]


@pytest.mark.parametrize("payload", [{"fix": True}, {"hardware_config": {"dg645_device": "other"}}, [], {"args": [1, 1, 1, 1]}])
def test_initialize_rejects_scope_rewiring(lifecycle_client, monkeypatch, payload):
    client, _ = lifecycle_client
    monkeypatch.setattr(api, "_prepare_v0_experiment", lambda *a: pytest.fail("No hardware access"))
    assert client.post("/api/pump-probe-v0/hardware/initialize", json=payload).status_code == 400


def test_initialize_permissions_exclude_standa_and_dg645_writes():
    targets = api._v0_targets(api.DEFAULT_HARDWARE_CONFIG, "v0.initialize")
    assert not any(target["command"] in {"scpi_write", "DevStop"} for target in targets)
    assert not any(target["device"] in V0_STANDA_DEVICES for target in targets)
    assert {target["device"] for target in targets if target["command"] == "set_channels_states"} == {
        "manip/V0/PDU_VO", "manip/SD2/PDU_SD2"}


@pytest.mark.parametrize("state,position,ready", [
    (0, 1.0, True), ("ON", 1.0, True), (6, 1.0, True),
    (1, 0.0, False), (8, 0.0, False), (8.0, 0.0, False), (9, 0.0, False),
    ("FAULT", 0.0, False), (0, float("nan"), False),
])
def test_owis_numeric_fault_off_and_stale_positions_are_not_ready(state, position, ready):
    assert api._axis_is_ready(state, position) is ready
