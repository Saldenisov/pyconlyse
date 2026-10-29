"""Verify the stopped native FIFO patch inventory. Python 3.4 compatible.

Read-only. Does not load LabVIEW, deploy files, start a server, or touch NI.
Preparation success is deliberately distinct from runtime qualification.
"""

import argparse
import hashlib
import json
from pathlib import Path

try:
    from tools.verify_labview_sync_native12_package import vi_header
except ImportError:
    from verify_labview_sync_native12_package import vi_header


PACKAGE = Path('legacy/labview/supervision_telemetry/realtime_fifo_20261029')


def read_bytes(path):
    with path.open('rb') as stream:
        return stream.read()


def load_json(path):
    with path.open('r', encoding='utf-8') as stream:
        return json.load(stream)


def checked_path(root, relative):
    relative_path = Path(relative)
    if relative_path.is_absolute() or relative_path.drive or '..' in relative_path.parts:
        raise ValueError('Inventory path leaves its root: ' + relative)
    path = root / relative
    root_parts = tuple(x.lower() for x in root.resolve().parts)
    path_parts = tuple(x.lower() for x in path.resolve().parts)
    if path_parts[:len(root_parts)] != root_parts or len(path_parts) <= len(root_parts):
        raise ValueError('Inventory path leaves its root: ' + relative)
    return path


def check_digest(root, record):
    path = checked_path(root, record['path'])
    data = read_bytes(path)
    if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('Artifact bytes changed: ' + record['path'])
    return data


def verify(repo, package=None, header_reader=vi_header):
    repo = Path(repo)
    package = Path(package) if package else repo / PACKAGE
    manifest = load_json(package / 'manifest.json')
    if manifest['kind'] != 'NATIVE_CAMERA_FIFO_PREPARATION':
        raise ValueError('Unexpected package kind')
    if (manifest['xp_deployed'] or manifest['runtime_25Hz_qualified'] or
            not manifest['native12_complete_dependency_load_pending']):
        raise ValueError('Prepared patch must not claim deployment/runtime qualification')
    if manifest['queue_capacity'] != 128 or manifest['enqueue_timeout_ms'] != 0 or manifest['copy_gate_ms'] != 0:
        raise ValueError('Unexpected FIFO preparation policy')
    if len(manifest['artifacts']) != 4:
        raise ValueError('Expected exactly four changed native files')
    for record in manifest['artifacts']:
        header = header_reader(check_digest(package, record))
        if header['major'] != 12 or header['RunOnOpen'] or not header['source_diagram']:
            raise ValueError('Artifact must be stopped native12 source: ' + record['path'])
    for record in manifest['preserved_repo_files']:
        check_digest(repo, record)
    audit_record = manifest['source_audit']
    audit = json.loads(check_digest(package, audit_record).decode('utf-8'))
    if not audit['passed'] or audit['Run'] or audit['RSRC_writer'] or audit['runtime_25Hz_qualified']:
        raise ValueError('Missing read-only source qualification')
    if set(audit['files']) != {'tap', 'producer', 'consumer', 'entry'}:
        raise ValueError('Incomplete native graph coverage')
    for name, findings in audit['files'].items():
        if not all(findings[k] for k in ('source_graph_checked', 'callee_links_unchanged',
                                         'fp_connector_contract_unchanged', 'structure_unchanged')):
            raise ValueError('Source graph contract failed: ' + name)
        expected = '1' if name == 'entry' else '0'
        if findings['saved_execution_flags']['BadNode'] != expected:
            raise ValueError('Unreviewed native compilation state: ' + name)
        if findings['native12_complete_dependency_load_pending'] != (name == 'entry'):
            raise ValueError('Missing entry dependency-load gate')
    artifact_hashes = {x['sha256'] for x in manifest['artifacts']}
    if artifact_hashes != {x['after_sha256'] for x in audit['files'].values()}:
        raise ValueError('Native audit does not bind delivered artifacts')
    return {'preparation_verified': True, 'native_files': 4, 'xp_deployed': False,
            'native12_complete_dependency_load_pending': True,
            'runtime_25Hz_qualified': False, 'hardware_commands_sent': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, args.package), indent=2))


if __name__ == '__main__':
    main()
