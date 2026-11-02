"""Cold XP update; no VI, NI command, configuration or alarm-journal change."""
from __future__ import print_function
import datetime
import hashlib
import json
import os
import shutil
import socket
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r'C:\ACQ_READY_20261030\runtime'
CONFIG = os.path.join(ROOT, 'config.acquisition.active.json')
EXPECTED = {'acquisition_control_gui.py', 'acquisition_control_runtime.py',
            'dual_mode_telemetry.py', 'shared_state_receiver.py',
            'telemetry_diagnostics.py', 'acquisition_telemetry_launcher.py'}


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def main():
    with open(os.path.join(HERE, 'manifest.json')) as stream:
        manifest = json.load(stream)
    if set(manifest.get('files', {})) != EXPECTED:
        raise ValueError('Exact six-module Acquisition update required; no paths were changed')
    for name, row in manifest['files'].items():
        if digest(os.path.join(HERE, name)) != row['new_sha256']:
            raise ValueError('Package checksum mismatch: ' + name)
    if '--verify-only' in sys.argv:
        return dict(state='PACKAGE_VERIFIED_NOT_INSTALLED', files=len(manifest['files']))
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 4):
        raise ValueError('Use the installed Acquisition XP Python 3.4')
    probe = socket.socket()
    try:
        probe.bind(('10.20.30.10', 0))
    finally:
        probe.close()
    if not os.path.isfile(CONFIG):
        raise ValueError('Existing active configuration missing; no configuration is created')
    # Use the prepared standard-library-only helper for cold checks. The old
    # shortcut helper can confuse TIME_WAIT with a still-listening server.
    from acquisition_telemetry_launcher import WindowsEnvironment, launch
    environment = WindowsEnvironment(CONFIG)
    if environment.server_held() or environment.ingress_bound() or environment.api_bound():
        raise ValueError('Stop only the Python server after IDLE / NI resources: 0, then repeat. No process was stopped automatically.')
    if os.path.exists(CONFIG + '.ownership'):
        raise ValueError('NI ownership marker retained; no marker, recovery state or journal was changed')
    # Verify every installed input before changing any file. Idempotent retry
    # allows a previous partial copy, never an unrelated code version.
    for name, row in manifest['files'].items():
        path = os.path.join(ROOT, 'elyse_agent', name)
        present = digest(path) if os.path.isfile(path) else None
        if present not in (row['old_sha256'], row['new_sha256']):
            raise ValueError('Unexpected installed source; preserved: ' + name)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = os.path.join(ROOT, 'reliability_backup_' + stamp)
    os.makedirs(backup)
    for name in manifest['files']:
        current = os.path.join(ROOT, 'elyse_agent', name)
        if os.path.isfile(current):
            shutil.copy2(current, os.path.join(backup, name))
    for name, row in manifest['files'].items():
        path = os.path.join(ROOT, 'elyse_agent', name)
        temporary = path + '.reliability-new'
        shutil.copy2(os.path.join(HERE, name), temporary)
        if digest(temporary) != row['new_sha256']:
            raise ValueError('Copied checksum mismatch: ' + name)
        os.replace(temporary, path)
    server = launch(WindowsEnvironment(CONFIG), vi=None)
    return dict(state='UPDATED_COLD_SERVER', backup=backup, server=server,
                source_commit=manifest.get('source_commit'),
                observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                VI_opened=False, VI_stopped=False, NI_initialize_invoked=False,
                hardware_commands_sent=False, configuration_or_journal_changed=False)


if __name__ == '__main__':
    try:
        report = main()
    except Exception:
        report = dict(state='FAILED', error=traceback.format_exc(),
                      NI_initialize_invoked=False, hardware_commands_sent=False)
    filename = 'local_package_check.json' if '--verify-only' in sys.argv else 'xp_update_receipt.json'
    with open(os.path.join(HERE, filename), 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, ensure_ascii=True, indent=2))
