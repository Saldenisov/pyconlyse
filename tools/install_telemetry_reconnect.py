"""Cold Python-only transport update, Python 3.4; never stops/starts NI or VI.

Use built apply_xp.py, not this manifest-unpinned template. The existing Python
server must be stopped normally. Its VI may continue running. Restart through
the existing site launcher afterward, without Initialize.
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import socket
import sys

MANIFEST_SHA256 = 'PAYLOAD_MANIFEST_SHA256'
HOSTS = dict(acquisition='10.20.30.10', supervision='10.20.30.2')


def digest(path, normalize=False):
    with open(path, 'rb') as stream:
        raw = stream.read()
    return hashlib.sha256(raw.replace(b'\r\n', b'\n') if normalize else raw).hexdigest()


def install_files(folder, runtime, role, manifest, replace=os.replace):
    """Copy exactly the pinned modules; keep configuration and backups intact."""
    names = manifest['roles'][role]
    allowed = {'telemetry_relay.py', 'shared_state_receiver.py', 'camera_stream.py', 'camera_stream_publisher.py'}
    if (not names or len(names) != len(set(names)) or set(names) - allowed
            or any(name not in manifest['files'] for name in names)):
        raise ValueError('Unexpected transport payload')
    agent = os.path.join(runtime, 'elyse_agent')
    for name in names:
        item = manifest['files'][name]
        source, target = os.path.join(folder, name), os.path.join(agent, name)
        if digest(source) != item['after_sha256']:
            raise ValueError('Payload differs: ' + name)
        with open(source, 'rb') as stream:
            compile(stream.read(), name, 'exec')
        if digest(target, normalize=True) != item['before_sha256']:
            raise ValueError('Installed source differs; no overwrite: ' + name)
        if os.path.exists(target + '.reconnect.tmp'):
            raise ValueError('Existing staging file preserved: ' + name)
    backup = os.path.join(runtime, 'transport_backup_' + datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ'))
    os.mkdir(backup)
    for name in names:
        shutil.copy2(os.path.join(agent, name), os.path.join(backup, name))
    installed = []
    try:
        for name in names:
            target = os.path.join(agent, name)
            staged = target + '.reconnect.tmp'
            shutil.copy2(os.path.join(folder, name), staged)
            replace(staged, target)
            installed.append(name)
            if digest(target) != manifest['files'][name]['after_sha256']:
                raise ValueError('Installed checksum differs: ' + name)
    except Exception:
        for name in reversed(installed):
            shutil.copy2(os.path.join(backup, name), os.path.join(agent, name))
        raise
    report = dict(state='INSTALLED_SERVER_NOT_STARTED', role=role, backup=backup, files=names,
                  initialize_invoked=False, vi_files_changed=False, configuration_changed=False)
    with open(os.path.join(backup, 'receipt.json'), 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--role', choices=sorted(HOSTS), required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 4) or ctypes.sizeof(ctypes.c_void_p) != 4:
        raise RuntimeError('Installed XP Python 3.4 x86 required')
    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, 'manifest.json')
    if digest(path) != MANIFEST_SHA256:
        raise RuntimeError('Build the hash-pinned payload first')
    with open(path, encoding='utf-8') as stream:
        manifest = json.load(stream)
    config_path = os.path.abspath(args.config)
    with open(config_path, encoding='utf-8') as stream:
        config = json.load(stream)
    if config.get('bind_host') != HOSTS[args.role] or config.get('port') != 8772:
        raise RuntimeError('Role/configuration host mismatch')
    probe = socket.socket()
    try:
        probe.bind((HOSTS[args.role], 0))
    finally:
        probe.close()
    for host, port in ((HOSTS[args.role], 8772), ('127.0.0.1', 8766), ('127.0.0.1', 8768)):
        probe = socket.socket()
        try:
            probe.settimeout(.4)
            if probe.connect_ex((host, port)) == 0:
                raise RuntimeError('Stop only the cold Python server normally before installation')
        finally:
            probe.close()
    runtime = os.path.abspath(args.runtime)
    sys.path.insert(0, runtime)
    from elyse_agent.acquisition_supervisor import FileInstanceGuard
    guard = FileInstanceGuard(config_path + '.application.lock')
    guard.acquire()
    try:
        print(json.dumps(install_files(folder, runtime, args.role, manifest), indent=2))
    finally:
        guard.release()


if __name__ == '__main__':
    main()
