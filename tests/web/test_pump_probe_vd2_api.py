import sys
from pathlib import Path

from flask import Flask
import pytest

from tests._tango_stub import install_tango_stub


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class _CollectionMonkeyPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(_CollectionMonkeyPatch())

import pump_probe_vd2_api as vd2_api_module
from vd2_measurement_protocol import Vd2MeasurementProtocol


class FakeProxy:
    def __init__(self):
        self.commands = []

    def set_timeout_millis(self, value):
        return None

    def state(self):
        return "ON"

    def read_attribute(self, name):
        class Attribute:
            value = True
        return Attribute()

    def write_attribute(self, name, value):
        return None

    def command_inout(self, name, value=None):
        self.commands.append((name, value))
        return None


class RecoverableDG645Proxy:
    def __init__(self):
        self.commands = []
        self.current_state = "FAULT"

    def set_timeout_millis(self, value):
        return None

    def state(self):
        return self.current_state

    def command_inout(self, name, value=None):
        self.commands.append((name, value))
        if name == "recover":
            self.current_state = "ON"
            return "Recovered"
        if name == "scpi_query" and value == "*IDN?":
            return "Stanford Research Systems,DG645,123,1.0"
        return None


def test_protocol_routes_start_one_bruit_his(monkeypatch):
    protocol = Vd2MeasurementProtocol(FakeProxy)
    monkeypatch.setattr(vd2_api_module, "_measurement_protocol", protocol)
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)

    with app.test_client() as client:
        initial = client.get("/api/pump-probe-vd2/protocol/state")
        assert initial.get_json()["status"] == "idle"

        started = client.post("/api/pump-probe-vd2/protocol/start", json={
            "phase": "BRUIT",
            "frames_per_his": 4,
            "output_root": r"E:\\DATA_VD2",
            "run_name": "test_run",
        })
        assert started.status_code == 200
        assert started.get_json()["his_path"].endswith(r"test_run\BRUIT.his")

    protocol.wait(1)
    assert protocol.status()["status"] == "completed"


def test_remoteex_routes_use_tango_commands(monkeypatch):
    proxy = FakeProxy()
    monkeypatch.setattr(vd2_api_module, "_proxy", lambda: proxy)
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)

    with app.test_client() as client:
        state = client.get("/api/pump-probe-vd2/runtime/state")
        assert state.status_code == 200
        assert state.get_json()["remoteex_running"] is True

        started = client.post("/api/pump-probe-vd2/runtime/remoteex/start")
        assert started.status_code == 200
        assert started.get_json()["remoteex_running"] is True

        stopped = client.post("/api/pump-probe-vd2/runtime/remoteex/stop")
        assert stopped.status_code == 200
        assert stopped.get_json()["remoteex_running"] is False

    assert proxy.commands == [("StartRemoteEx", None), ("StopRemoteEx", None)]


def test_initialize_route_returns_preflight_result(monkeypatch):
    monkeypatch.setattr(
        vd2_api_module,
        "_initialize_experiment",
        lambda: {"steps": [{"step": "DG645 Recall 9", "status": "applied; burst mode off"}]},
    )
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)

    with app.test_client() as client:
        response = client.post("/api/pump-probe-vd2/initialize")

    assert response.status_code == 200
    assert response.get_json()["steps"][0]["step"] == "DG645 Recall 9"


def test_deinitialize_route_returns_shutdown_result(monkeypatch):
    monkeypatch.setattr(
        vd2_api_module,
        "_deinitialize_experiment",
        lambda: {"steps": [{"step": "VD2 power", "status": "disabled"}]},
    )
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)

    with app.test_client() as client:
        response = client.post("/api/pump-probe-vd2/deinitialize")

    assert response.status_code == 200
    assert response.get_json()["steps"][0]["status"] == "disabled"


def test_ensure_server_recovers_exported_dg645_before_astor_restart(monkeypatch):
    proxy = RecoverableDG645Proxy()
    steps = []
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *args, **kwargs: proxy)
    monkeypatch.setattr(
        vd2_api_module,
        "_restart_server",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("restart not expected")),
    )

    result = vd2_api_module._ensure_server(vd2_api_module.DG645_DEVICE, steps)

    assert result is proxy
    assert proxy.commands == [
        ("recover", None),
        ("scpi_query", "*IDN?"),
    ]
    assert steps == [{"step": f"Tango {vd2_api_module.DG645_DEVICE}", "status": "recovered"}]


def test_exported_off_kymera_opens_once_with_native_initialization_timeout(monkeypatch):
    events = []

    class Kymera:
        opened = False

        def set_timeout_millis(self, timeout):
            events.append(("timeout", timeout))

        def state(self):
            return "ON" if self.opened else "OFF"

        def read_attribute(self, name):
            assert name == "grating"
            return type("Attribute", (), {"value": 2})()

        def get_command_list(self):
            return ["Init", "turn_on"]

        def command_inout(self, name):
            events.append((name, None))
            assert name == "turn_on"
            assert events[-2] == ("timeout", 60000)
            self.opened = True

    proxy = Kymera()
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *args, **kwargs: proxy)
    monkeypatch.setattr(vd2_api_module, "_restart_server", lambda *args: pytest.fail("no restart expected"))
    assert vd2_api_module._ensure_server(vd2_api_module.KYMERA_DEVICE, []) is proxy
    assert events == [("timeout", 60000), ("turn_on", None)]


def test_initialize_requires_confirmed_power_before_instrument_servers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        vd2_api_module, "_ensure_server",
        lambda device, steps: calls.append(device) or FakeProxy(),
    )
    monkeypatch.setattr(
        vd2_api_module, "_enable_vd2_power",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("DG645 output 2 is OFF")),
    )

    with pytest.raises(RuntimeError, match="DG645 output 2 is OFF"):
        vd2_api_module._initialize_experiment()
    assert calls == [
        vd2_api_module.VD2_PDU_DEVICE,
        vd2_api_module.ZABER_PDU_DEVICE,
        vd2_api_module.OWIS_PDU_DEVICE,
    ]


def test_enable_power_confirms_id_based_readback_and_preserves_other_outputs(monkeypatch):
    class Pdu:
        values = {"ids": [2, 1, 3, 4], "states": [0, 1, 0, 0]}
        commands = []

        def read_attribute(self, name):
            return type("Attribute", (), {"value": self.values[name]})()

        def command_inout(self, name, states):
            self.commands.append((name, states))
            self.values["states"] = states

    proxy = Pdu()
    sleeps = []
    monkeypatch.setattr(vd2_api_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    steps = []
    vd2_api_module._enable_required_power(proxy, steps, vd2_api_module.SD2_REQUIRED_PDU_OUTPUTS, "SD2")
    assert proxy.commands == [("set_channels_states", [1, 1, 1, 0])]
    assert sleeps == [5.0]
    assert steps[-1] == {"step": "SD2 power", "status": "enabled"}


def test_initialize_error_retains_completed_and_failed_device_checks(monkeypatch):
    steps = [
        {"step": "SD2 power", "status": "enabled"},
        {"step": "DG645", "status": "failed", "detail": "instrument not responding"},
    ]
    monkeypatch.setattr(
        vd2_api_module, "_initialize_experiment",
        lambda: (_ for _ in ()).throw(vd2_api_module.PreparationFailure("instrument not responding", steps)),
    )
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)
    with app.test_client() as client:
        result = client.post("/api/pump-probe-vd2/initialize")
    assert result.status_code == 503
    assert result.get_json()["steps"] == steps


@pytest.mark.parametrize("already_running", [False, True])
def test_initialize_applies_profile_and_waits_for_verified_optics(monkeypatch, already_running):
    monkeypatch.setattr(vd2_api_module, "_assert_preparation_idle", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_prepare_kymera_for_vd2", lambda *args: None)
    class PreparingProxy(FakeProxy):
        def __init__(self):
            super().__init__()
            self.preparing = False

        def state(self):
            return "RUNNING" if self.preparing else "ON"

        def read_attribute(self, name):
            values = {
                "connected": True,
                "application_running": already_running or self.preparing,
                "remoteex_status": "preparing" if self.preparing else "idle",
            }
            return type("Attribute", (), {"value": values[name]})()

        def command_inout(self, name, value=None):
            super().command_inout(name, value)
            if name in {"StartApplication", "PrepareVD2Startup"}:
                self.preparing = True

    proxy = PreparingProxy()
    sleeps = []
    monkeypatch.setattr(vd2_api_module, "_ensure_server", lambda *args: proxy)
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *args, **kwargs: proxy)
    monkeypatch.setattr(vd2_api_module, "_enable_vd2_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_enable_required_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_snapshot", lambda _: {"profile": "verified"})
    monkeypatch.setattr(vd2_api_module, "_prepare_dg645_for_vd2", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_verify_owis_sample_axis", lambda *args: None)

    def finish_preparation(delay):
        nonlocal already_running
        sleeps.append(delay)
        already_running = True
        proxy.preparing = False

    monkeypatch.setattr(vd2_api_module.time, "sleep", finish_preparation)
    expected = "StartApplication"

    result = vd2_api_module._initialize_experiment()

    assert proxy.commands == [("StartRemoteEx", None), (expected, None)]
    assert sleeps == [1.0]
    assert result["steps"][-1]["step"] == "VD2 optical profile"
    assert "Blaze 800" in result["steps"][-1]["status"]


def test_initialize_does_not_report_success_after_optical_profile_failure(monkeypatch):
    monkeypatch.setattr(vd2_api_module, "_assert_preparation_idle", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_prepare_kymera_for_vd2", lambda *args: None)
    class FailedProxy(FakeProxy):
        def state(self):
            return "FAULT"

        def status(self):
            return "VD2 startup readback mismatch"

    proxy = FailedProxy()
    monkeypatch.setattr(vd2_api_module, "_ensure_server", lambda *args: proxy)
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *args, **kwargs: proxy)
    monkeypatch.setattr(vd2_api_module, "_enable_vd2_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_enable_required_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_prepare_dg645_for_vd2", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_verify_owis_sample_axis", lambda *args: None)

    with pytest.raises(RuntimeError, match="VD2 startup readback mismatch"):
        vd2_api_module._initialize_experiment()


@pytest.mark.parametrize("readback", ["0", "+0.0", "0.0"])
def test_dg645_preset_is_recalled_then_burst_is_disabled_and_verified(monkeypatch, readback):
    proxy = FakeProxy()

    def command(name, value=None):
        proxy.commands.append((name, value))
        return readback if value == "BURM?" else "1"

    proxy.command_inout = command
    sleeps = []
    monkeypatch.setattr(vd2_api_module.time, "sleep", sleeps.append)
    steps = []
    vd2_api_module._prepare_dg645_for_vd2(proxy, steps)
    assert proxy.commands == [
        ("scpi_write", "*RCL 9"),
        ("scpi_write", "BURM 0"),
        ("scpi_query", "*OPC?"),
        ("scpi_query", "BURM?"),
    ]
    assert sleeps == [1.0]
    assert steps == [{"step": "DG645 Recall 9", "status": "applied; verified BURM=0"}]


@pytest.mark.parametrize("readback", ["1", "", "nan"])
def test_dg645_invalid_burst_readback_fails_preparation(monkeypatch, readback):
    proxy = FakeProxy()
    proxy.command_inout = lambda name, value=None: readback
    monkeypatch.setattr(vd2_api_module.time, "sleep", lambda *_: None)
    steps = []
    with pytest.raises(RuntimeError, match="burst-off verification failed"):
        vd2_api_module._prepare_dg645_for_vd2(proxy, steps)
    assert steps[-1]["status"] == "failed"


def test_owis_verifies_only_vd2_sample_axis_and_enables_an_off_motor():
    proxy = FakeProxy()
    state = vd2_api_module.DevState.OFF

    def command(name, value=None):
        nonlocal state
        proxy.commands.append((name, value))
        if name == "turn_on_axis":
            state = vd2_api_module.DevState.ON
            return "0"
        if name == "get_status_axis":
            return state
        if name == "read_position_axis":
            return 12.5
        raise AssertionError(f"unexpected motion/setup command {name}")

    proxy.command_inout = command
    steps = []
    vd2_api_module._verify_owis_sample_axis(proxy, steps)
    assert proxy.commands == [
        ("get_status_axis", 2), ("turn_on_axis", 2),
        ("get_status_axis", 2), ("read_position_axis", 2),
    ]
    assert steps == [{"step": "OWIS sample axis 2", "status": "verified ON; 12.5000 mm"}]


@pytest.mark.parametrize("state,position", [
    (vd2_api_module.DevState.FAULT, 0),
    (vd2_api_module.DevState.MOVING, 0),
    (vd2_api_module.DevState.ON, float("nan")),
])
def test_owis_not_ready_or_invalid_position_does_not_pass(state, position):
    proxy = FakeProxy()
    proxy.command_inout = lambda name, value=None: state if name == "get_status_axis" else position
    steps = []
    with pytest.raises(RuntimeError, match="OWIS sample axis 2"):
        vd2_api_module._verify_owis_sample_axis(proxy, steps)
    assert steps[-1]["status"] == "failed"


def test_initialization_powers_owis_and_applies_recall_before_other_instruments(monkeypatch):
    monkeypatch.setattr(vd2_api_module, "_assert_preparation_idle", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_prepare_kymera_for_vd2", lambda *args: None)
    events = []

    class Streak(FakeProxy):
        def read_attribute(self, name):
            return type("Attribute", (), {"value": "idle" if name == "remoteex_status" else True})()

    streak = Streak()
    monkeypatch.setattr(vd2_api_module, "_ensure_server", lambda device, steps: events.append(device) or streak)
    monkeypatch.setattr(vd2_api_module, "_enable_vd2_power", lambda *args: events.append("SD2 power"))
    monkeypatch.setattr(vd2_api_module, "_enable_required_power", lambda pdu, steps, outputs, label: events.append((label, outputs)))
    monkeypatch.setattr(vd2_api_module, "_prepare_dg645_for_vd2", lambda *args: events.append("Recall 9 / BURM=0"))
    monkeypatch.setattr(vd2_api_module, "_verify_owis_sample_axis", lambda *args: events.append("OWIS axis 2 verified"))
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *_args, **_kwargs: streak)
    monkeypatch.setattr(vd2_api_module, "_snapshot", lambda *_: {})

    vd2_api_module._initialize_experiment()
    assert events == [
        vd2_api_module.VD2_PDU_DEVICE, vd2_api_module.ZABER_PDU_DEVICE, vd2_api_module.OWIS_PDU_DEVICE,
        "SD2 power", ("VD2", vd2_api_module.VD2_REQUIRED_PDU_OUTPUTS), ("OWIS", {2: "OWIS controller (VD2 sample axis 2)"}),
        vd2_api_module.DG645_DEVICE, "Recall 9 / BURM=0",
        vd2_api_module.OWIS_CONTROLLER_DEVICE, vd2_api_module.OWIS_LEGACY_DEVICE, vd2_api_module.OWIS_SAMPLE_DEVICE,
        "OWIS axis 2 verified", vd2_api_module.ZABER_STAGE_DEVICE, vd2_api_module.STREAK_DEVICE,
    ]


def test_initialization_stops_before_other_instruments_when_burst_check_fails(monkeypatch):
    monkeypatch.setattr(vd2_api_module, "_assert_preparation_idle", lambda *args: None)
    calls = []
    monkeypatch.setattr(vd2_api_module, "_ensure_server", lambda device, steps: calls.append(device) or FakeProxy())
    monkeypatch.setattr(vd2_api_module, "_enable_vd2_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_enable_required_power", lambda *args: None)
    monkeypatch.setattr(vd2_api_module, "_prepare_dg645_for_vd2", lambda *args: (_ for _ in ()).throw(RuntimeError("BURM?=1")))
    with pytest.raises(RuntimeError, match="BURM\\?=1"):
        vd2_api_module._initialize_experiment()
    assert calls == [
        vd2_api_module.VD2_PDU_DEVICE, vd2_api_module.ZABER_PDU_DEVICE,
        vd2_api_module.OWIS_PDU_DEVICE, vd2_api_module.DG645_DEVICE,
    ]


def test_stopped_owis_server_is_activated_after_transport_discovery(monkeypatch):
    class Owis(FakeProxy):
        current_state = "STANDBY"

        def state(self):
            return self.current_state

        def command_inout(self, name, value=None):
            super().command_inout(name, value)
            assert name == "turn_on"
            self.current_state = "ON"

        def read_attribute(self, name):
            assert name == "pos2"
            return type("Attribute", (), {"value": 12.5})()

    proxy = Owis()
    monkeypatch.setattr(vd2_api_module, "_astor", lambda *_: object())
    monkeypatch.setattr(vd2_api_module, "_wait_for_device", lambda *_args, **_kwargs: proxy)
    monkeypatch.setattr(vd2_api_module, "start_managed_server", lambda starter, server, ready: ready())

    def final_health(device):
        assert device == vd2_api_module.OWIS_CONTROLLER_DEVICE
        assert vd2_api_module._is_healthy_device(proxy, device)
        return proxy

    monkeypatch.setattr(vd2_api_module, "_wait_for_healthy_device", final_health)
    assert vd2_api_module._restart_server(vd2_api_module.OWIS_CONTROLLER_DEVICE, "DS_OWIS_PS90/2_IP") is proxy
    assert proxy.commands == [("turn_on", None)]
