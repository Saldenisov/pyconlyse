"""Finalize an audited five-file delta against a known installed XP baseline.

The prepared full source directory is cold-tested, not deployed by this tool.
No settings, journal behavior, commissioning flags or ownership files change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


FILES = ('elyse_agent/acquisition_control_runtime.py', 'elyse_agent/acquisition_backend.py',
         'elyse_agent/hardware_tasks.py', 'elyse_agent/isolated_backend.py',
         'elyse_agent/isolated_worker.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(baseline, prepared):
    baseline, prepared = Path(baseline).resolve(), Path(prepared).resolve()
    old = json.loads((baseline / 'manifest.json').read_text(encoding='utf-8'))
    plan = dict(files={}, old_manifest_sha256=digest(baseline / 'manifest.json'))
    for entry in old['files']:
        name = entry['path']
        if digest(baseline / name) != entry['sha256']:
            raise ValueError('Unaudited baseline: ' + name)
        new_hash = digest(prepared / name)
        if name not in FILES and new_hash != entry['sha256']:
            raise ValueError('Unrelated source/configuration change: ' + name)
        if name in FILES:
            plan['files'][name] = dict(old=entry['sha256'], new=new_hash)
        entry['sha256'] = new_hash
    if set(plan['files']) != set(FILES):
        raise ValueError('Five exact bootstrap files required')
    old.update(release='acq-v8-unified-bootstrap-r4-20261023',
               bootstrap_order='numpy_nidaqmx_before_stdin_ingress_with_parent_activation',
               cold_prior_recovery='VI_forwarding_only_prior_marker_and_NI_gates_retained')
    (prepared / 'manifest.json').write_text(json.dumps(old, indent=2), encoding='utf-8')
    plan['new_manifest_sha256'] = digest(prepared / 'manifest.json')
    (prepared / 'bootstrap_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    shutil.copy2(Path(__file__).with_name('install_acq_bootstrap_update.pyw'),
                 prepared / 'INSTALL_UNIFIED_BOOTSTRAP.pyw')
    return dict(release=old['release'], files=len(plan['files']),
                manifest_sha256=plan['new_manifest_sha256'], cards_touched=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('prepared')
    args = parser.parse_args()
    print(json.dumps(finalize(args.baseline, args.prepared)))
