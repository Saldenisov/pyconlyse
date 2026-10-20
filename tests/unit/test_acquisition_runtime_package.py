"""Cold package dependency closure; no NI/serial/process deployment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import pytest

from tools.package_acquisition_runtime import build, DATA, MODULES


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", ["legacy_full", "general_only_test", "extended_ht_stop"])
def test_clean_source_package_contains_stage_dependencies_without_live_configuration(profile):
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "cold"
        result = build(output, ROOT, profile)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        config = json.loads((output / "config.acquisition.json").read_text(encoding="utf-8"))
        assert config["control_profile"] == profile
        assert config["stage_controls_verified"] is False
        assert config["cooling_trip_verified"] is False
        assert config["ht_controls_verified"] is False
        assert config["focal_stop"]["resources_verified"] is False
        assert config["ht_shutdown"]["feedback_verified"] is False
        assert manifest["auto_initialize"] is False
        assert manifest["source_stage_controls_default_enabled"] is False
        assert manifest["ht_stage_controls_default_enabled"] is False
        expected = {"acquisition_server.pyw", "config.acquisition.json"}
        expected.update("elyse_agent/" + name for name in MODULES)
        expected.update("data/" + name for name in DATA)
        assert {row["path"] for row in manifest["files"]} == expected
        for row in manifest["files"]:
            assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["sha256"]
        with zipfile.ZipFile(result["archive"]) as archive:
            assert set(archive.namelist()) == {"cold/" + name for name in expected | {"manifest.json"}}
            assert not any(name.endswith((".key", ".sqlite3", ".dll", ".exe", ".jsonl"))
                           for name in archive.namelist())
        original = ROOT / "legacy/xp_acq_agent/data/modulator_stage_catalog.json"
        assert (output / "data/modulator_stage_catalog.json").read_bytes() == original.read_bytes()


def test_packaged_cold_runtime_imports_on_actual_python34_without_loading_a_native_driver():
    interpreter = os.environ.get("ELYSE_PYTHON34")
    if not interpreter or not Path(interpreter).is_file():
        pytest.skip("Provide actual Python 3.4 through ELYSE_PYTHON34; no modern substitute")
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "cold"
        build(output, ROOT)
        code = """
import sys, json, ctypes
def denied(*args, **kwargs):
    raise AssertionError('Native driver/factory access forbidden')
ctypes.CDLL = denied
ctypes.WinDLL = denied
from elyse_agent.acquisition_runtime import AcquisitionRuntime
from elyse_agent.acquisition_stage_execution import SUPPORTED_OPERATIONS
from elyse_agent.acquisition_stage_model import load_model
load_model()
runtime = AcquisitionRuntime(denied)
runtime.start()
snapshot = runtime.snapshot()
runtime.request_shutdown()
assert runtime.join(2)
assert snapshot['state'] == 'IDLE'
assert snapshot['resource_count'] == 0
assert not set(sys.modules).intersection(('nidaqmx', 'PyDAQmx', 'visa', 'pyvisa'))
print(json.dumps(dict(version=list(sys.version_info[:2]), paths=len(SUPPORTED_OPERATIONS))))
"""
        env = dict(os.environ, PYTHONPATH=str(output))
        result = subprocess.run([interpreter, "-c", code], cwd=output, env=env,
                                capture_output=True, text=True, timeout=10, check=True)
        assert json.loads(result.stdout) == {"version": [3, 4], "paths": 12}
