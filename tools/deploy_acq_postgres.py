"""Explicit two-phase Everest telemetry archive handover. Never calls XP/NI/PSP.

prepare stops only the exact recorder and exact existing telemetry server, after
validating the staged release and database. launch starts only the same Tango
registration. Source files/Starter launcher are staged between these phases.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import subprocess

import psutil
import requests
import tango

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore, utc

DEVICE = 'elyse/acquisition/telemetry'
RECORDER_ID = 'b5806d3c63ea43aa95c61c0d3e4f7829'


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def guard_jobs():
    session = requests.Session()
    session.trust_env = False
    result = {}
    for experiment in ('v0', 'vd2'):
        response = session.get(f'http://127.0.0.1:5000/api/pump-probe-{experiment}/lifecycle', timeout=(2, 5))
        response.raise_for_status()
        job = response.json()['job']
        if job['status'] == 'running':
            raise RuntimeError('Web lifecycle active; web deployment refused')
        result[experiment] = {k: job.get(k) for k in ('job_id', 'status', 'operation')}
    state = session.get('http://127.0.0.1:5000/api/pump-probe-v0/state', timeout=(2,5)).json()
    if state.get('running') or state.get('real_time'):
        raise RuntimeError('Web experiment active; web deployment refused')
    state2 = session.get('http://127.0.0.1:5000/api/pump-probe-vd2/protocol/state', timeout=(2,5)).json()
    if state2.get('status') in ('acquiring', 'saving'):
        raise RuntimeError('Web acquisition active; web deployment refused')
    treatment = Path('C:/Users/elyse/.pyconlyse/treatment_state.sqlite3')
    if treatment.exists():
        with sqlite3.connect(treatment.as_uri() + '?mode=ro', uri=True) as conn:
            if conn.execute("SELECT name FROM sqlite_master WHERE name='treatment_queue'").fetchone():
                for row in conn.execute('SELECT jobs_json FROM treatment_queue'):
                    if any(job.get('status') == 'running' for job in json.loads(row[0])):
                        raise RuntimeError('Web treatment active; web deployment refused')
    return result


def prepare(args):
    output, release, recording = map(lambda p: Path(p).resolve(), (args.output, args.release, args.recording))
    if output.exists():
        raise ValueError('New handover directory required')
    for item in json.loads((release / 'manifest.json').read_text())['files']:
        path = (release / item['path']).resolve()
        if not path.is_relative_to(release) or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Release manifest mismatch')
    database = PostgresStore(args.config)
    database.initialize()
    admin_config = json.loads(Path(args.config).with_name('admin.json').read_text())
    with database.driver.connect(**admin_config, connect_timeout=2,
                                 options='-c default_transaction_read_only=on') as conn:
        data_path = conn.execute('SHOW data_directory').fetchone()[0]
        if Path(data_path).drive.upper() != 'F:':
            raise ValueError('PostgreSQL data must be on F:')
        if conn.execute('SHOW fsync').fetchone()[0] != 'on':
            raise ValueError('Database fsync is disabled')
    status = json.loads((recording / 'status.json').read_text())
    if status['recorder_id'] != RECORDER_ID or status['state'] != 'RUNNING':
        raise RuntimeError('Recorder identity/state changed')
    recorder = psutil.Process(status['pid'])
    argv = recorder.cmdline()
    if Path(argv[1]).name != 'record_acq_telemetry_hdf5.py' or str(recording) not in argv:
        raise RuntimeError('Unexpected recorder command line')
    db = tango.Database()
    info = db.get_device_info(DEVICE)
    receiver = psutil.Process(info.pid)
    if Path(receiver.cmdline()[1]).name != 'DS_AcqTelemetry.py':
        raise RuntimeError('Unexpected telemetry receiver process')
    parent = receiver.parent()
    parent_name = parent.name().lower() if parent else ''
    properties = {k: list(v) for k, v in db.get_device_property(DEVICE,
        ['producer_kind_filter','commands_enabled','archive_config_file','cooling_journal_file']).items()}
    if properties['commands_enabled'] != ['false']:
        raise RuntimeError('Remote command configuration changed')
    output.mkdir(parents=True)
    save(output / 'before.json', dict(utc=utc(), recorder=status, recorder_command=argv,
         receiver_pid=receiver.pid, receiver_command=receiver.cmdline(), properties=properties,
         release=str(release), recording=str(recording), config=str(Path(args.config)),
         parent_pid=parent.pid if parent else None))
    shutil.copy2('C:/dev/pyconlyse/DeviceServers/DS_AcqTelemetry.bat', output / 'DS_AcqTelemetry.before.bat')
    # The sole recorder's documented stop IPC. No terminate/restart and no HDF5 open.
    (recording / 'stop.request').touch(exist_ok=False)
    recorder.wait(timeout=30)
    final = json.loads((recording / 'status.json').read_text())
    if final['state'] != 'STOPPED' or final['recorder_id'] != RECORDER_ID:
        raise RuntimeError('Recorder did not finish cleanly; receiver left untouched')
    save(output / 'recorder-closed.json', final)
    admin = tango.DeviceProxy('dserver/DS_AcqTelemetry/everest')
    admin.set_timeout_millis(5000)
    try:
        admin.command_inout('Kill')
    except tango.DevFailed:
        pass
    receiver.wait(timeout=20)
    if parent and parent_name == 'cmd.exe':
        try:
            parent.wait(timeout=10)
        except psutil.NoSuchProcess:
            pass
    journal = properties['cooling_journal_file']
    old = Path(journal[0]) if journal else Path('C:/dev/pyconlyse/logs/elyse_cooling_alarms.sqlite3')
    destination = Path('F:/ELYSE_PostgreSQL/alarms/elyse_cooling_alarms.sqlite3')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if old.exists():
        if destination.exists():
            raise RuntimeError('Existing destination alarm journal; do not overwrite')
        with sqlite3.connect(old.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
    db.put_device_property(DEVICE, dict(archive_config_file=[str(Path(args.config).resolve())],
                                       cooling_journal_file=[str(destination)]))
    save(output / 'prepared.json', dict(utc=utc(), recorder_stopped=True, receiver_stopped=True,
         original_hdf5_unmodified=True, hardware_commands_sent=False, alarm_journal=str(destination)))
    print(json.dumps(dict(phase='PREPARED', utc=utc(), output=str(output))), flush=True)


def launch(args):
    output = Path(args.output).resolve()
    before = json.loads((output / 'before.json').read_text())
    if not (output / 'prepared.json').exists():
        raise RuntimeError('Preparation not complete')
    starter = tango.DeviceProxy('tango/admin/everest')
    starter.set_timeout_millis(10000)
    starter.command_inout('DevStart', 'DS_AcqTelemetry/everest')
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            device = tango.DeviceProxy(DEVICE)
            device.set_timeout_millis(3000)
            status = json.loads(device.read_attribute('archive_status_json').value)
            telemetry = json.loads(device.read_attribute('telemetry_json').value)
            if str(device.state()) == 'ON' and status.get('state') == 'RUNNING' and len(telemetry['publications']) == 27:
                current = psutil.Process(tango.Database().get_device_info(DEVICE).pid)
                if not Path(current.cwd()).is_relative_to(Path(before['release'])):
                    raise RuntimeError('Unexpected receiver working directory')
                save(output / 'launched.json', dict(utc=utc(), pid=current.pid,
                     command=current.cmdline(), archive=status, receiver_session=telemetry['receiver_session'],
                     banks=len(telemetry['publications']), hardware_commands_sent=False))
                print(json.dumps(dict(phase='RUNNING', utc=utc(), pid=current.pid, archive=status)), flush=True)
                return
        except tango.DevFailed:
            pass
        time.sleep(0.3)
    raise RuntimeError('New receiver did not become ready; do not auto-restart XP or recorder')


def deploy_web(args):
    output = Path(args.output).resolve()
    revision = output / ('web_revision_' + utc().replace(':','').replace('.','_'))
    revision.mkdir()
    jobs = guard_jobs()
    live = Path('C:/dev/pyconlyse/web/backend')
    target = live / 'acq_telemetry_api.py'
    base = subprocess.check_output(['git', 'show', 'c6ed0502:web/backend/acq_telemetry_api.py'], cwd=ROOT)
    expected = args.expected_web_sha256
    reviewed = (hashlib.sha256(target.read_bytes()).hexdigest() == expected.lower() if expected
                else target.read_bytes().replace(b'\r\n', b'\n') == base.replace(b'\r\n', b'\n'))
    if not reviewed:
        raise RuntimeError('Live telemetry API differs from reviewed base; refusing overwrite')
    listeners = {c.pid for c in psutil.net_connections('tcp')
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == 5000}
    if len(listeners) != 1:
        raise RuntimeError('Web listener identity not unique')
    web = psutil.Process(next(iter(listeners)))
    argv, cwd, environment = web.cmdline(), web.cwd(), web.environ()
    if args.config:
        config = Path(args.config).resolve()
        if config.drive.upper() != 'F:':
            raise ValueError('Web archive configuration must remain on F:')
        PostgresStore(config).summary()
        environment['ELYSE_TELEMETRY_ARCHIVE_CONFIG'] = str(config)
    if Path(cwd).resolve() != Path('C:/dev/pyconlyse/web') or argv[-1] != 'start_local.py':
        raise RuntimeError('Unexpected web process')
    shutil.copy2(target, revision / 'acq_telemetry_api.before.py')
    if (live / 'telemetry_history.html').exists():
        if not expected:
            raise RuntimeError('History page already exists; refusing overwrite')
        shutil.copy2(live / 'telemetry_history.html', revision / 'telemetry_history.before.html')
    if guard_jobs() != jobs:
        raise RuntimeError('Web work changed during preparation')
    for name in ('acq_telemetry_api.py', 'telemetry_history.html'):
        shutil.copy2(ROOT / 'web/backend' / name, live / name)
    if args.config:
        archive_module = Path('C:/dev/pyconlyse/DeviceServers/control/elyse_acq/telemetry_archive.py')
        if archive_module.exists():
            shutil.copy2(archive_module, revision / 'telemetry_archive.before.py')
        shutil.copy2(ROOT / 'DeviceServers/control/elyse_acq/telemetry_archive.py', archive_module)
    web.terminate()
    web.wait(timeout=15)
    with (revision / 'web-stdout.log').open('xb') as stdout, (revision / 'web-stderr.log').open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=stdout, stderr=stderr,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    session = requests.Session()
    session.trust_env = False
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('Web replacement exited')
        try:
            response = session.get('http://127.0.0.1:5000/api/elyse/acquisition/telemetry/history-view', timeout=(2,3))
            if response.ok and 'Historique de télémétrie' in response.text:
                if guard_jobs() != jobs:
                    raise RuntimeError('Web job identity changed')
                save(output / 'web.json', dict(utc=utc(), pid=child.pid, old_pid=web.pid,
                     frontend_assets_unchanged=True, jobs_preserved=True, hardware_commands_sent=False))
                print(json.dumps(dict(phase='WEB_READY', utc=utc(), pid=child.pid)), flush=True)
                return
        except requests.RequestException:
            pass
        time.sleep(.3)
    raise RuntimeError('Web history readiness failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare','launch','web'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--release')
    parser.add_argument('--recording')
    parser.add_argument('--config')
    parser.add_argument('--expected-web-sha256')
    args = parser.parse_args()
    {'prepare': prepare, 'launch': launch, 'web': deploy_web}[args.phase](args)
