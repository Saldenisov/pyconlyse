"""Everest-only pinned rollout; review by default, --apply restarts Tango DS.

Does not restart either XP computer, stop a VI, initialize NI or issue hardware
commands. Existing sender protocols remain supported. Archive configuration is
unchanged. The receiver's normal shutdown drains its existing archive worker.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]
LIVE = Path(r'F:\ELYSE_Telemetry_Server\postgres_v3')
MODULES = {
    'telemetry_sink.py': 'a611c1872086112a0113123ae8bb1b30ee0dc5fdb1bcedab61eb89bc26e897fd',
    'DS_AcqTelemetry.py': '3bd3248f117f5526f7bdfb5548f2bb6a92baa962852fb06511e4b246f278a286',
}
RELATIVE = Path('DeviceServers/control/elyse_acq')
PYTHON = r'C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe'
COMMAND = [PYTHON, 'DS_AcqTelemetry.py', 'everest']
DEVICE = 'tango://10.20.30.202:10000/elyse/acquisition/telemetry'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import psutil
    import tango
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    destination = LIVE/RELATIVE
    for name, expected in MODULES.items():
        if sha(destination/name) != expected:
            raise RuntimeError('Installed source changed; review before rollout: ' + name)
        compile((ROOT/RELATIVE/name).read_bytes(), name, 'exec')
    processes = [p for p in psutil.process_iter(['cmdline'])
                 if p.info['cmdline'] == COMMAND and Path(p.cwd()).resolve() == destination.resolve()]
    if len(processes) != 1:
        raise RuntimeError('One exact existing receiver process required')
    previous = processes[0]
    proxy = tango.DeviceProxy(DEVICE)
    proxy.set_timeout_millis(4000)

    def snapshot():
        return {name: json.loads(proxy.read_attribute(name).value)
                for name in ('telemetry_json', 'archive_status_json', 'camera_stream_json')}

    before = snapshot()
    banks = before['telemetry_json']['publications']
    if len(banks) != 27 or any(row['stale'] for row in banks.values()):
        raise RuntimeError('Establish healthy 27-bank baseline before rollout')
    if before['archive_status_json']['state'] != 'RUNNING':
        raise RuntimeError('Archive must be running before rollout')
    report = dict(mode='APPLY' if args.apply else 'REVIEW_ONLY', old_pid=previous.pid,
        checked_utc=datetime.now(timezone.utc).isoformat(),
        files={name: dict(before=expected, after=sha(ROOT/RELATIVE/name)) for name, expected in MODULES.items()},
        initialize_invoked=False, hardware_commands_sent=False, xp_files_changed=False, vi_files_changed=False)

    def save():
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    save()
    if not args.apply:
        print(json.dumps(report, indent=2))
        return
    backup = LIVE/'rollbacks'/('persistent_tcp_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir()
    for name in MODULES:
        shutil.copy2(destination/name, backup/name)
    (backup/'before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    report.update(state='GRACEFUL_STOP_REQUESTED', backup=str(backup))
    save()
    admin = tango.DeviceProxy('tango://10.20.30.202:10000/dserver/DS_AcqTelemetry/everest')
    admin.set_timeout_millis(5000)
    try:
        admin.command_inout('Kill')
    except tango.DevFailed:
        pass
    previous.wait(timeout=35)  # No forced termination or competing receiver.
    for name, expected in MODULES.items():
        if sha(destination/name) != expected:
            raise RuntimeError('Source changed during receiver shutdown')
        shutil.copy2(ROOT/RELATIVE/name, destination/name)
        if sha(destination/name) != report['files'][name]['after']:
            raise RuntimeError('Installed checksum mismatch')
    # A directly spawned child bypasses DS_AcqTelemetry.bat's failure retry
    # loop and may inherit the deployment tool's Windows process lifetime.
    # Starter must own every production receiver, including after upgrades.
    starter = tango.DeviceProxy('tango://10.20.30.202:10000/tango/admin/everest')
    starter.set_timeout_millis(10000)
    starter.command_inout('DevStart', 'DS_AcqTelemetry/everest')
    report.update(state='VERIFYING', launch_method='Starter.DevStart')
    save()
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        try:
            after = snapshot()
            banks = after['telemetry_json']['publications']
            transport = after['telemetry_json']['telemetry_transport']
            if (len(banks) == 27 and all(not row['stale'] for row in banks.values())
                    and after['archive_status_json']['state'] == 'RUNNING'
                    and after['archive_status_json']['committed_this_process'] > 0
                    and transport['listening']):
                receiver_info = tango.Database().get_device_info('elyse/acquisition/telemetry')
                current = psutil.Process(receiver_info.pid)
                if current.cmdline() != COMMAND or Path(current.cwd()).resolve() != destination.resolve():
                    raise RuntimeError('Unexpected replacement receiver identity')
                report.update(state='VERIFIED', new_pid=current.pid,
                    verified_utc=datetime.now(timezone.utc).isoformat(),
                    bank_count=27, transport=transport, archive_commits=after['archive_status_json']['committed_this_process'],
                    camera_active_connections=after['camera_stream_json']['active_connections'])
                (backup/'after.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
                break
        except (tango.DevFailed, KeyError):
            pass
        time.sleep(.25)
    else:
        report['state'] = 'VERIFICATION_PENDING'
    save()
    print(json.dumps(report, indent=2))
    if report['state'] != 'VERIFIED':
        raise RuntimeError('Receiver live verification incomplete')


if __name__ == '__main__':
    main()
