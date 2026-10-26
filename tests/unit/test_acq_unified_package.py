"""Modern-host packager tests; payload itself is cold-checked on Python3.4."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from tools import package_acq_web_control as packager


def test_release_uses_explicit_source_closure_not_runtime_or_repair_scripts(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    for name in packager.xp_release_paths():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packager.XP / name, target)
    for name in ('recover_after_reboot.pyw', 'shared_state_receiver.pyw',
                 'elyse_agent/reboot_recovery.py', 'runtime/old.json', 'runtime/cooling-alarms.sqlite3'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('UNREVIEWED RUNTIME FILE', encoding='utf-8')
    monkeypatch.setattr(packager, 'XP', source)
    release = tmp_path / 'release'
    result = packager.package(release)
    included = {item['path'] for item in result['files']}
    assert included == set(packager.xp_release_paths())
    assert 'handover_recovery.py' not in included  # Correct module-relative path only.
    assert 'elyse_agent/handover_recovery.py' in included
    assert not any(name.startswith('runtime/') or name.endswith('recover_after_reboot.pyw') for name in included)
    assert not (release / 'shared_state_receiver.pyw').exists()
    assert result['standalone_telemetry_application_included'] is False
    assert result['canonical_entrypoint'] == 'acquisition_control_server.pyw'
    assert result['release'] == 'elyse-card-process-orchestrators-20261026-r16'
    assert result['native_isolation_default'] == 'per_card'
    assert result['local_orchestrator_roles'] == ['acquisition', 'supervision']
    assert 'supervision_control_server.pyw' in included
    assert 'elyse_agent/orchestrator_backend.py' in included
    assert json.loads((release / 'config.acquisition.json').read_text())['native_isolation_mode'] == 'per_card'
    from legacy.xp_acq_control.elyse_agent.supervision_gui import validate_supervision_configuration
    assert validate_supervision_configuration(json.loads((release / 'config.supervision.control.json').read_text()))['telemetry']['enabled'] is False
    assert result['operator_supervised_test_supported'] is True
    assert result['operator_test_is_physical_qualification'] is False
    assert 'TaskHandle metadata before stdin reader' in result['native_bootstrap']
    assert '11 concurrent card' in result['native_initialization']
    assert 'PeekNamedPipe' in result['native_child_input']
    assert result['native_analog_processing'] == 'last_raw_sample_of_finite_block'
    assert result['native_software_averaging'] is False
    assert result['native_finite_samples_per_channel'] == 10
    assert result['native_selected_sample_index'] == 9
    assert result['vi_forwarded_processing_unchanged'] is True
    assert result['native_software_status_banks'] == ['EPS', 'DPS']
    assert result['execution_sampling_default'] is None
    assert 'not hardware readback' in result['native_software_status_semantics']
    assert result['named_operation_count'] == 25
    assert result['matched_control_capability_set_required'] is True
    assert result['beamline_pulses_default_enabled'] is False
    assert result['faraday_hors_commands_qualified'] is False
    assert result['faraday_3_position_feedback_qualified'] is False
    assert result['ht_increase_requires_software_supply_and_modulator'] is True
    assert result['autonomous_ht_ramp'] is False
    assert 'elyse_agent/acquisition_beamline.py' in included
    assert all(hashlib.sha256((release / row['path']).read_bytes()).hexdigest() == row['sha256']
               for row in result['files'])
    assert json.loads((release / 'manifest.json').read_text())['auto_initialize'] is False


def test_both_compatibility_entrypoints_launch_same_unified_main():
    sources = [(packager.XP / name).read_text(encoding='utf-8')
               for name in ('acquisition_control_server.pyw', 'acquisition_server.pyw')]
    assert sources[0] == sources[1]
    assert 'from elyse_agent.acquisition_control_gui import main' in sources[0]
    assert 'shared_state_receiver' not in sources[0]


def test_everest_release_imports_from_its_own_complete_closure(tmp_path):
    target = tmp_path / 'everest'
    packager.package(target, everest=True)
    code = '''
import sys
sys.path.insert(0, sys.argv[1])
from DeviceServers.control.elyse_acq import DS_AcqTelemetry, federated_telemetry, telemetry_archive
from legacy.xp_acq_control.elyse_agent import federation_wire
for module in (DS_AcqTelemetry, federated_telemetry, telemetry_archive, federation_wire):
    assert module.__file__.startswith(sys.argv[1]), module.__file__
assert 'nidaqmx' not in sys.modules
print('COLD_CLOSURE_OK')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(target)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'COLD_CLOSURE_OK' in result.stdout
