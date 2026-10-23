"""Build the explicit unified XP release and exact rollback-safe r4 delta.

Modern development host only. No XP access, NI imports, configuration changes
on the installed computer, equipment commands or process control.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from tools.package_acq_web_control import package
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import control_identity


MODULES = ('acquisition_control_gui.py', 'acquisition_control_runtime.py',
    'acquisition_recovery.py', 'handover_recovery.py', 'acquisition_startup.py',
    'application_view.py', 'cooling_safety.py', 'journal_worker.py', 'dual_mode_telemetry.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(baseline, destination):
    baseline, destination = Path(baseline).resolve(), Path(destination).resolve()
    previous = json.loads((baseline / 'manifest.json').read_text(encoding='utf-8'))
    before = {item['path']: item['sha256'] for item in previous['files']}
    release = package(destination)
    for name in ('config.acquisition.json', 'config.acquisition.control.json'):
        shutil.copy2(baseline / name, destination / name)
    allowed = {'elyse_agent/' + name for name in MODULES}
    plan = dict(files={}, old_manifest_sha256=sha(baseline / 'manifest.json'))
    for item in release['files']:
        name = item['path']
        new = sha(destination / name)
        if name in allowed:
            old = before.get(name)
            if old is not None and sha(baseline / name) != old:
                raise ValueError('Unqualified old source: ' + name)
            plan['files'][name] = dict(old=old, new=new)
        elif before.get(name) != new:
            raise ValueError('Unexpected source/configuration delta: ' + name)
        item['sha256'] = new
    if set(plan['files']) != allowed:
        raise ValueError('Exact nine-module delta required')
    release['site_configuration_override'] = previous.get('site_configuration_override', '')
    release['control_build_id'] = control_identity(str(destination))['build_id']
    release['rollout_limits'] = ['No auto-initialization or equipment commands',
        'Prior ownership marker retained until separately confirmed local handover',
        'Journal notice clears only after durable local acknowledgment',
        'Login autostart only: no resident supervisor or automatic crash restart']
    (destination / 'manifest.json').write_text(json.dumps(release, indent=2), encoding='utf-8')
    plan['new_manifest_sha256'] = sha(destination / 'manifest.json')
    (destination / 'unified_r5_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    shutil.copy2(Path(__file__).with_name('install_acq_unified_r5.pyw'),
                 destination / 'INSTALL_UNIFIED_R5.pyw')
    with zipfile.ZipFile(destination.with_suffix('.zip'), 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in destination.rglob('*'):
            if path.is_file():
                archive.write(path, path.relative_to(destination).as_posix())
    return dict(release=release['release'], build_id=release['control_build_id'],
        manifest_sha256=plan['new_manifest_sha256'], source_files=len(release['files']),
        changed_modules=len(plan['files']), hardware_commands_sent=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('destination')
    options = parser.parse_args()
    print(json.dumps(build(options.baseline, options.destination)))
