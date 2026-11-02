"""File-only SuperVision launch/mode update, then cold GUI. Python3.4 x86."""
import ctypes
import datetime
import hashlib
import importlib.machinery
import json
import os
import shutil
import socket
import subprocess
import sys
import traceback

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = r'C:\SV_READY_20261030'
MANIFEST_SHA256 = 'b6f8fdb0c7c54d4fd797e8392a3057d7339b7e786f2fd2cc1cb83dfea7d1f4ed'


def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def save(path, value):
    with open(path, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)


def main():
    if sys.version_info[:2] != (3, 4) or ctypes.sizeof(ctypes.c_void_p) != 4:
        raise RuntimeError('Installed Python3.4 x86 required')
    probe = socket.socket()
    try:
        probe.bind(('10.20.30.2', 0))
    finally:
        probe.close()
    manifest_path = os.path.join(BASE, 'manifest.json')
    if sha(manifest_path) != MANIFEST_SHA256:
        raise RuntimeError('Manifest checksum differs')
    with open(manifest_path, 'r', encoding='utf-8') as stream:
        manifest = json.load(stream)
    for row in manifest['files']:
        if os.path.basename(row['name']) != row['name'] or sha(os.path.join(BASE, row['name'])) != row['sha256']:
            raise RuntimeError('Payload checksum differs')
    launcher = importlib.machinery.SourceFileLoader('supervision_launch_fix', os.path.join(BASE, 'launch_supervision.pyw')).load_module()
    if any(launcher.listening(port) for port in (8772, 8766, 8768)):
        raise RuntimeError('Existing SuperVision listener: close only the cold server normally first')
    runtime = os.path.join(TARGET, 'runtime')
    config = os.path.join(runtime, 'config.supervision.active.json')
    with open(config, 'r', encoding='utf-8') as stream:
        previous = json.load(stream)
    updated = launcher.unified_configuration(previous)
    # Existing runtime validates keys/schema only; no NI factory is constructed.
    sys.path.insert(0, runtime)
    from elyse_agent.acquisition_supervisor import FileInstanceGuard
    from elyse_agent.supervision_gui import validate_supervision_configuration
    validate_supervision_configuration(updated)
    guard = FileInstanceGuard(config + '.application.lock')
    guard.acquire()
    backup = os.path.join(TARGET, 'launcher_backup_' + datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'))
    report = dict(host='10.20.30.2', state='PREPARING', backup=backup,
        initialize_invoked=False, hardware_commands_sent=False, vi_started=False,
        protections_changed=False, source_files_changed=False,
        configuration_fields_changed=['vi_passive_shadow'] if previous != updated else [])
    try:
        if os.path.exists(backup):
            raise RuntimeError('Backup destination exists; preserved')
        os.mkdir(backup)
        desktop = next((os.path.join(os.environ['USERPROFILE'], name) for name in ('Bureau', 'Desktop')
                        if os.path.isfile(os.path.join(os.environ['USERPROFILE'], name, 'Supervision Telemetry.lnk'))), None)
        if desktop is None:
            raise RuntimeError('Existing Supervision Telemetry desktop shortcut not found')
        shutil.copy2(config, os.path.join(backup, 'config.supervision.active.json'))
        destination = os.path.join(TARGET, 'launch_supervision.pyw')
        if os.path.exists(destination):
            shutil.copy2(destination, os.path.join(backup, 'launch_supervision.pyw'))
        shutil.copy2(os.path.join(BASE, 'launch_supervision.pyw'), destination)
        for name in ('Supervision Telemetry.lnk', 'Supervision Server.lnk'):
            dest = os.path.join(desktop, name)
            if os.path.exists(dest):
                shutil.copy2(dest, os.path.join(backup, name))
            shutil.copy2(os.path.join(BASE, name), dest)
        temp = config + '.startup_fix.tmp'
        if os.path.exists(temp):
            raise RuntimeError('Existing configuration staging file preserved')
        with open(temp, 'x', encoding='utf-8') as stream:
            json.dump(updated, stream, indent=2, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, config)
        with open(config, 'r', encoding='utf-8') as stream:
            installed = json.load(stream)
        if installed != updated or dict(installed, vi_passive_shadow=previous['vi_passive_shadow']) != previous:
            raise RuntimeError('Unexpected configuration difference')
        report.update(state='FILES_INSTALLED', vi_passive_shadow=installed['vi_passive_shadow'],
            launcher_sha256=sha(destination), desktop=desktop, original_VI_unchanged=True)
    finally:
        guard.release()
        save(os.path.join(BASE, 'xp_install_receipt.json'), report)
        save(os.path.join(TARGET, 'startup_fix_receipt.json'), report)
    child = subprocess.Popen([sys.executable, '-B', os.path.join(TARGET, 'launch_supervision.pyw')], cwd=TARGET)
    report.update(state='UNIFIED_COLD_LAUNCH_REQUESTED', launcher_pid=child.pid)
    save(os.path.join(BASE, 'xp_install_receipt.json'), report)
    save(os.path.join(TARGET, 'startup_fix_receipt.json'), report)
    return report


if __name__ == '__main__':
    try:
        result = main()
        message = 'Unified server opened in IDLE. Initialize was NOT invoked.\n\nDesktop:\nSupervision Server = server only\nSupervision Telemetry = server then existing VI\n\nBackup: ' + result['backup']
    except Exception:
        message = traceback.format_exc()[-1600:]
        save(os.path.join(BASE, 'xp_install_error.json'), dict(error=message, hardware_commands_sent=False))
    import tkinter as tk
    from tkinter import messagebox
    window = tk.Tk(); window.withdraw()
    messagebox.showinfo('SuperVision startup update - no Initialize', message, parent=window)
    window.destroy()
