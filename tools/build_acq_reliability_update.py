"""Build a cold, checksum-pinned XP patch; no machine, process or VI access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('acquisition_control_gui.py', 'acquisition_control_runtime.py',
           'dual_mode_telemetry.py', 'shared_state_receiver.py', 'telemetry_diagnostics.py',
           'acquisition_telemetry_launcher.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-modules', type=Path, required=True)
    parser.add_argument('--base-launcher', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'legacy/xp_acq_control/elyse_agent'
    files = {}
    for name in MODULES:
        old = args.base_launcher if name == 'acquisition_telemetry_launcher.py' else args.base_modules / name
        shutil.copy2(source / name, args.output / name)
        files[name] = dict(old_sha256=sha(old) if old.exists() else None,
                           new_sha256=sha(args.output / name))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(ROOT), text=True).strip()
    manifest = dict(schema=1, source_commit=commit, files=files, python='3.4',
                    status='PREPARED_NOT_DEPLOYED', restart_earliest='2026-11-03 Europe/Paris',
                    install_starts_only_cold_python_server=True,
                    automatic_NI_initialize=False, VI_changes=False)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    shutil.copy2(ROOT / 'tools/templates/acq_reliability_install.py', args.output / 'INSTALL_RELIABILITY.py')
    shutil.copy2(ROOT / 'tools/templates/acq_crash_evidence.vbs', args.output / 'READ_XP_CRASH_EVENTS.vbs')
    (args.output / 'APPLY_RELIABILITY.cmd').write_text(
        '@echo off\nC:\\Python34_ELYSE\\python.exe -B "%~dp0INSTALL_RELIABILITY.py"\npause\n', encoding='ascii')
    (args.output / 'COLLECT_CRASH_EVENTS.cmd').write_text(
        '@echo off\ncscript.exe //nologo "%~dp0READ_XP_CRASH_EVENTS.vbs" > "%~dp0xp_crash_events.txt" 2>&1\n'
        'type "%~dp0xp_crash_events.txt"\npause\n', encoding='ascii')
    shutil.copy2(ROOT / 'docs/ELYSE_ACQ_RELIABILITY_2026-11-02.rst', args.output / 'READ_FIRST.rst')
    print(json.dumps(dict(output=str(args.output), modules=len(files), deployed=False)))


if __name__ == '__main__':
    main()
