import sys
import time
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pump_probe_v0_api as v0_api_module


def test_emulator_run_publishes_h5_dat_and_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(v0_api_module, "_emulator", v0_api_module.PumpProbeV0Controller())
    app = Flask(__name__)
    app.register_blueprint(v0_api_module.pump_probe_v0_api)

    with app.test_client() as client:
        configured = client.post("/api/pump-probe-v0/config", json={
            "control_mode": "emulator",
            "point_count": 2,
            "scan_start_ps": -1,
            "delay_step_ps": 1,
            "pulses_per_point": 1,
            "real_zero_ps": 0,
        })
        assert configured.status_code == 200

        started = client.post("/api/pump-probe-v0/run", json={
            "running": True,
            "save_path": str(tmp_path),
            "sample_name": "emulator-test",
        })
        assert started.status_code == 200

        time.sleep(1.0)
        state = client.get("/api/pump-probe-v0/state").get_json()

        assert state["run"]["status"] == "completed"
        artifacts = state["run"]["artifacts"]
        assert all(Path(artifacts[key]).is_file() for key in ("h5", "dat", "manifest"))

        loaded = client.post("/api/pump-probe-v0/data/load", json={"path": artifacts["h5"]})
        assert loaded.status_code == 200
        payload = loaded.get_json()
        assert payload["kind"] == "h5"
        assert len(payload["channels"]) == 6
        assert payload["raw_trace_count"] == 1
