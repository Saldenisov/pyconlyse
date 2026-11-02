"""Cold update of existing live-camera buffers; Python 3.4 x86, no NI calls.

Run only after normal VI stop/LabVIEW exit and cold Python server stop. Preserve
all configuration except camera_stream.delivery_policy, and retain local backups.
"""
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import traceback

TARGET = r'C:\SV_READY_20261030'
BASE = os.path.dirname(os.path.abspath(__file__))
EXPORT = r'\\tsclient\C\dev\SuperVision_Telemetry\latest_20261102'
MANIFEST_SHA256 = 'PAYLOAD_MANIFEST_SHA256'
HELPER = r'C:\SUP_Telemetry_Helpers_88fd4200\camera\observer_v3\SUP_Camera_Queue_Latest.vi'
ENTRY = r'C:\SUPERVISION_TELEMETRY_20261028\Supervision Telemetry.vi'


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def latest_configuration(previous):
    # Copy JSON data so the caller's original remains available for rollback.
    updated = json.loads(json.dumps(previous))
    camera = updated.get('camera_stream')
    if (type(camera) is not dict or camera.get('enabled') is not True
            or camera.get('host') != '10.20.30.202' or camera.get('port') != 8769
            or camera.get('source_mode') not in ('LABVIEW_BRIDGE', 'VI_OR_NATIVE')):
        raise RuntimeError('Expected existing independent SuperVision camera stream')
    camera['delivery_policy'] = 'latest'
    return updated


def listening(port):
    connection = socket.socket()
    connection.settimeout(.4)
    try:
        return connection.connect_ex(('127.0.0.1', port)) == 0
    finally:
        connection.close()


def save(report):
    for root in (BASE, EXPORT):
        try:
            with open(os.path.join(root, 'xp_latest_receipt.json'), 'w', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2, sort_keys=True)
        except OSError:
            if root == BASE:
                raise


def main():
    if sys.version_info[:2] != (3, 4) or ctypes.sizeof(ctypes.c_void_p) != 4:
        raise RuntimeError('Installed Python 3.4 x86 required')
    probe = socket.socket()
    try:
        probe.bind(('10.20.30.2', 0))
    finally:
        probe.close()
    if any(listening(port) for port in (8772, 8766, 8768)):
        raise RuntimeError('Close only cold SuperVision Python server normally first')
    runtime = os.path.join(TARGET, 'runtime')
    sys.path.insert(0, runtime)
    from elyse_agent.handover_recovery import windows_process_inventory
    from elyse_agent.acquisition_supervisor import FileInstanceGuard
    if any(row['name'].lower() == 'labview.exe' for row in windows_process_inventory()['processes']):
        raise RuntimeError('Stop telemetry VI normally and exit LabVIEW before replacing its helper')
    manifest_path = os.path.join(BASE, 'manifest.json')
    if digest(manifest_path) != MANIFEST_SHA256:
        raise RuntimeError('Manifest checksum differs')
    with open(manifest_path, encoding='utf-8') as stream:
        manifest = json.load(stream)
    for name, expected in manifest['files'].items():
        if os.path.basename(name) != name or digest(os.path.join(BASE, name)) != expected:
            raise RuntimeError('Payload checksum differs: ' + name)
    agent = os.path.join(runtime, 'elyse_agent')
    publisher = os.path.join(agent, 'camera_stream_publisher.py')
    latest = os.path.join(agent, 'camera_latest.py')
    if digest(publisher) not in manifest['expected_publisher_sha256']:
        raise RuntimeError('Installed publisher differs; no overwrite')
    if os.path.exists(latest) or os.path.exists(latest + '.not_activated'):
        raise RuntimeError('Existing latest module preserved; no repeated installation')
    if (digest(HELPER) != manifest['expected_helper_sha256']
            or digest(ENTRY) != manifest['expected_entry_sha256']):
        raise RuntimeError('Installed VI helper/wrapper differs; no overwrite')
    config_path = os.path.join(runtime, 'config.supervision.active.json')
    config_hash = digest(config_path)
    with open(config_path, encoding='utf-8') as stream:
        previous = json.load(stream)
    updated = latest_configuration(previous)
    guard = FileInstanceGuard(config_path + '.application.lock')
    guard.acquire()
    backup = os.path.join(TARGET, 'latest_camera_backup_' + datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))
    report = dict(state='PREPARING', backup=backup, initialize_invoked=False,
                  hardware_commands_sent=False, original_vi_changed=False,
                  synchronization_changed=False, protections_changed=False,
                  configuration_fields_changed=['camera_stream.delivery_policy'])
    destinations = {'camera_latest.py': latest, 'camera_stream_publisher.py': publisher,
                    'SUP_Camera_Queue_Latest.vi': HELPER}
    installed = []
    try:
        os.mkdir(backup)
        shutil.copy2(config_path, os.path.join(backup, 'config.supervision.active.json'))
        for name, destination in destinations.items():
            if os.path.isfile(destination):
                shutil.copy2(destination, os.path.join(backup, name))
        for name, destination in destinations.items():
            staged = destination + '.latest.tmp'
            if os.path.exists(staged):
                raise RuntimeError('Existing staging file preserved')
            shutil.copy2(os.path.join(BASE, name), staged)
            os.replace(staged, destination)
            installed.append(name)
            if digest(destination) != manifest['files'][name]:
                raise RuntimeError('Installed checksum differs')
        from elyse_agent.supervision_gui import validate_supervision_configuration
        validate_supervision_configuration(updated)
        if digest(config_path) != config_hash:
            raise RuntimeError('Configuration changed concurrently')
        staged = config_path + '.latest.tmp'
        if os.path.exists(staged):
            raise RuntimeError('Existing configuration staging file preserved')
        with open(staged, 'w', encoding='utf-8') as stream:
            json.dump(updated, stream, indent=2, sort_keys=True)
        os.replace(staged, config_path)
        installed.append('config.supervision.active.json')
        if digest(ENTRY) != manifest['expected_entry_sha256']:
            raise RuntimeError('Wrapper changed concurrently')
        report.update(state='INSTALLED', installed_sha256=manifest['files'],
                      wrapper_unchanged=True, python_delivery_policy='latest',
                      vi_delivery_policy='lossy_enqueue_latest_queue_capacity_1')
    except Exception:
        for name in reversed(installed):
            old = os.path.join(backup, name)
            destination = config_path if name == 'config.supervision.active.json' else destinations[name]
            if os.path.isfile(old):
                shutil.copy2(old, destination)
            elif name == 'camera_latest.py':
                # Preserve the newly created module rather than deleting user data.
                os.replace(destination, destination + '.not_activated')
        report['state'] = 'ROLLED_BACK'
        raise
    finally:
        guard.release()
        save(report)
    child = subprocess.Popen([sys.executable, '-B', os.path.join(TARGET, 'launch_supervision.pyw')], cwd=TARGET)
    report.update(state='COLD_SERVER_LAUNCH_REQUESTED', launcher_pid=child.pid)
    save(report)
    return report


if __name__ == '__main__':
    try:
        result = main()
        message = 'Latest-frame mode installed. Python server opens in IDLE.\nOpen Supervision Telemetry to resume VI camera/sync.\nBackup: ' + result['backup']
    except Exception:
        message = traceback.format_exc()[-2200:]
        save(dict(state='FAILED', error=message))
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk(); root.withdraw()
    messagebox.showinfo('SuperVision latest frames', message, parent=root)
    root.destroy()
