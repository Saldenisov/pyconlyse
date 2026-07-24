import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

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


def test_protocol_routes_start_one_brew_his(monkeypatch):
    protocol = Vd2MeasurementProtocol(FakeProxy)
    monkeypatch.setattr(vd2_api_module, "_measurement_protocol", protocol)
    app = Flask(__name__)
    app.register_blueprint(vd2_api_module.pump_probe_vd2_api)

    with app.test_client() as client:
        initial = client.get("/api/pump-probe-vd2/protocol/state")
        assert initial.get_json()["status"] == "idle"

        started = client.post("/api/pump-probe-vd2/protocol/start", json={
            "phase": "BREW",
            "frames_per_his": 4,
            "output_root": r"E:\\DATA_VD2",
            "run_name": "test_run",
        })
        assert started.status_code == 200
        assert started.get_json()["his_path"].endswith(r"test_run\NOISE.his")

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
