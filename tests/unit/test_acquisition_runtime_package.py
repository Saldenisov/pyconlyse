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
        assert config["focal_controls_verified"] is False
        assert config["counter_controls_verified"] is False
        assert config["counter_timing_controls_verified"] is False
        assert config["ht_voltage_controls_verified"] is False
        assert config["outer_stop_verified"] is False
        assert config["focal_stop"]["resources_verified"] is False
        assert config["ht_shutdown"]["feedback_verified"] is False
        assert manifest["auto_initialize"] is False
        assert manifest["source_stage_controls_default_enabled"] is False
        assert manifest["ht_stage_controls_default_enabled"] is False
        assert manifest["focal_stage_controls_default_enabled"] is False
        assert manifest["impulsion_paths_implemented"] == 2
        assert manifest["impulsion_controls_default_enabled"] is False
        assert manifest["counter_timing_transfer_implemented"] is True
        assert manifest["counter_timing_controls_default_enabled"] is False
        assert manifest["ht_voltage_transfer_implemented"] is True
        assert manifest["ht_voltage_transfer_default_enabled"] is False
        assert manifest["outer_controlled_stop_frames"] == 40
        assert manifest["outer_controlled_stop_default_enabled"] is False
        assert manifest["source_stage_paths_implemented"] == 14
        assert manifest["runtime_protocol_version"] == 2
        assert manifest["cold_process_supervisor_included"] is True
        assert manifest["automatic_ni_recovery"] is False
        assert manifest["command_admission_installed_on_network"] is False
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


def test_source_fingerprint_covers_exact_packaged_source_closure():
    from legacy.xp_acq_agent.elyse_agent.runtime_identity import SOURCE_MODULES, SOURCE_PATHS
    assert set(SOURCE_MODULES) == set(MODULES)
    assert set(SOURCE_PATHS) == {"acquisition_server.pyw"} | {
        "elyse_agent/" + name for name in MODULES
    } | {"data/" + name for name in DATA}
    assert {"acquisition_source_controls.py", "acquisition_impulsion.py",
            "acquisition_ht_voltage.py", "acquisition_outer_stop.py",
            "acquisition_counter_timing.py"} <= set(MODULES)
    assert len(SOURCE_MODULES) == 27
    assert len(SOURCE_MODULES) == len(set(SOURCE_MODULES))
    assert len(SOURCE_PATHS) == len(set(SOURCE_PATHS))


def test_package_forces_new_source_permissions_off_even_if_template_changes(tmp_path, monkeypatch):
    template = ROOT / "legacy/xp_acq_agent/config.acquisition.example.json"
    original_read = Path.read_text
    modified = json.loads(original_read(template, encoding="utf-8"))
    flags = ("counter_controls_verified", "counter_timing_controls_verified",
             "ht_voltage_controls_verified", "outer_stop_verified")
    for key in flags:
        modified[key] = True

    def altered_template(path, *args, **kwargs):
        return json.dumps(modified) if path == template else original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", altered_template)
    output = tmp_path / "cold"
    build(output, ROOT)
    packaged = json.loads((output / "config.acquisition.json").read_text(encoding="utf-8"))
    assert all(packaged[key] is False for key in flags)


@pytest.mark.parametrize("module", ["acquisition_source_controls.py", "acquisition_impulsion.py",
                                   "acquisition_ht_voltage.py", "acquisition_outer_stop.py",
                                   "acquisition_counter_timing.py"])
def test_each_new_module_byte_change_changes_packaged_source_identity(tmp_path, module):
    from legacy.xp_acq_agent.elyse_agent.runtime_identity import source_fingerprint
    output = tmp_path / "cold"
    build(output, ROOT)
    original = source_fingerprint(str(output))
    path = output / "elyse_agent" / module
    raw = path.read_bytes()
    path.write_bytes(raw + b"\n# Synthetic fingerprint test only.\n")
    assert source_fingerprint(str(output)) != original
    path.write_bytes(raw)
    assert source_fingerprint(str(output)) == original


def test_gui_entrypoint_propagates_error_exit_instead_of_hiding_it_from_supervisor(monkeypatch):
    import runpy
    import sys
    import types
    module = types.ModuleType("elyse_agent.acquisition_gui")
    calls = []
    module.main = lambda path: calls.append(path) or 7
    monkeypatch.setitem(sys.modules, "elyse_agent", types.ModuleType("elyse_agent"))
    monkeypatch.setitem(sys.modules, "elyse_agent.acquisition_gui", module)
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / "legacy/xp_acq_agent/acquisition_server.pyw"), run_name="__main__")
    assert exited.value.code == 7
    assert calls == [str(ROOT / "legacy/xp_acq_agent/acquisition_server.pyw")]


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
from elyse_agent.acquisition_impulsion import SUPPORTED_OPERATIONS as IMPULSION_OPERATIONS
from elyse_agent.acquisition_ht_voltage import execute_ht_voltage
from elyse_agent.acquisition_outer_stop import CONTROLLED_STOP
from elyse_agent.acquisition_source_controls import SourceControls
from elyse_agent.acquisition_counter_timing import execute_counter_timing
load_model()
runtime = AcquisitionRuntime(denied)
runtime.start()
snapshot = runtime.snapshot()
runtime.request_shutdown()
assert runtime.join(2)
assert snapshot['state'] == 'IDLE'
assert snapshot['resource_count'] == 0
assert snapshot['runtime_protocol_version'] == 2
assert len(snapshot['session_id']) == 32 and len(snapshot['build_id']) == 64
assert type(snapshot['state_revision']) is int
assert snapshot['recovery']['protection_active'] is False
assert snapshot['stage_execution']['counter_commissioned'] is False
assert snapshot['stage_execution']['counter_timing_commissioned'] is False
assert snapshot['counter_timing_stop_required'] == []
assert snapshot['stage_execution']['ht_voltage_commissioned'] is False
assert snapshot['stage_execution']['outer_stop_commissioned'] is False
assert snapshot['stage_execution']['remote_commands_enabled'] is False
assert snapshot['stage_execution']['impulsion_implemented'] == list(IMPULSION_OPERATIONS)
assert len(IMPULSION_OPERATIONS) == 2
assert callable(execute_ht_voltage) and isinstance(SourceControls, type)
assert callable(execute_counter_timing)
assert callable(runtime.configure_counter_timing)
assert len(CONTROLLED_STOP) == 7
from elyse_agent.acquisition_command_admission import CommandAdmission
from elyse_agent.acquisition_supervisor import ColdAcquisitionSupervisor
from elyse_agent.runtime_identity import source_fingerprint
assert snapshot['build_id'] == source_fingerprint()
assert not set(sys.modules).intersection(('nidaqmx', 'PyDAQmx', 'visa', 'pyvisa'))
print(json.dumps(dict(version=list(sys.version_info[:2]), paths=len(SUPPORTED_OPERATIONS))))
"""
        env = dict(os.environ, PYTHONPATH=str(output))
        result = subprocess.run([interpreter, "-c", code], cwd=output, env=env,
                                capture_output=True, text=True, timeout=10, check=True)
        assert json.loads(result.stdout) == {"version": [3, 4], "paths": 14}
