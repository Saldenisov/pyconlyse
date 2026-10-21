"""Explicit telemetry/web-only handover. No XP lifecycle or equipment calls.

Run after operator approval. Read guards before stopping only named processes.
Never opens the active HDF5 file. Retains web assets and pre-change properties.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

import psutil
import requests
import tango

ROOT = Path('C:/dev/pyconlyse')
DEVICE = 'elyse/acquisition/telemetry'


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def kill_telemetry_server(name, expected_pid):
    info = tango.Database().get_device_info('dserver/' + name)
    if info.pid != expected_pid:
        raise RuntimeError('Telemetry server PID changed: ' + name)
    process = psutil.Process(expected_pid)
    if Path(process.cmdline()[1]).name != name.split('/')[0] + '.py':
        raise RuntimeError('Unexpected telemetry process identity')
    admin = tango.DeviceProxy('dserver/' + name)
    admin.set_timeout_millis(5000)
    try:
        admin.command_inout('Kill')  # Telemetry process only; delete_device owns no hardware.
    except tango.DevFailed:
        pass  # Shutdown can close its own reply socket; process exit is checked below.
    process.wait(timeout=15)


def deploy(output, build):
    output, build = Path(output).resolve(), Path(build).resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = requests.Session()
    session.trust_env = False
    def get(path):
        response = session.get('http://127.0.0.1:5000' + path, timeout=(2, 5))
        response.raise_for_status()
        return response.json()
    def guards():
        v0 = get('/api/pump-probe-v0/state')
        assert not v0.get('running') and not v0.get('real_time'), 'Web experiment active'
        result = {}
        for exp in ('v0', 'vd2'):
            job = get('/api/pump-probe-' + exp + '/lifecycle')['job']
            assert job['status'] != 'running', 'Lifecycle active'
            result[exp] = {key: job.get(key) for key in ('job_id', 'status', 'operation')}
        assert get('/api/pump-probe-vd2/protocol/state')['status'] not in ('acquiring', 'saving')
        database = Path('C:/Users/elyse/.pyconlyse/treatment_state.sqlite3')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
            if connection.execute("SELECT name FROM sqlite_master WHERE name='treatment_queue'").fetchone():
                for row in connection.execute('SELECT jobs_json FROM treatment_queue'):
                    assert not any(job.get('status') == 'running' for job in json.loads(row[0])), 'Treatment active'
        return result
    jobs = guards()
    manifest = json.loads((build / 'asset-manifest.json').read_text())
    assert (build / 'index.html').is_file()
    main = build / manifest['files']['main.js'].lstrip('/')
    assert main.is_file() and 'Acquisition Python' in main.read_text(encoding='utf-8')
    listeners = {entry.pid for entry in psutil.net_connections('tcp')
                 if entry.status == psutil.CONN_LISTEN and entry.laddr.port == 5000}
    assert len(listeners) == 1
    web = psutil.Process(next(iter(listeners)))
    argv, cwd, environment = web.cmdline(), web.cwd(), web.environ()
    assert Path(cwd).resolve() == ROOT / 'web' and argv[-1] == 'start_local.py'
    db = tango.Database()
    props = db.get_device_property(DEVICE, ['producer_kind_filter', 'commands_enabled', 'xp_control_port'])
    save(output / 'properties-before.json', {k: list(v) for k, v in props.items()})
    original_pid = db.get_device_info(DEVICE).pid
    save(output / 'before.json', dict(receiver_pid=original_pid, web_pid=web.pid, jobs=jobs))
    # Stage assets without deleting old hashed assets, which remain usable by
    # already-open browsers. index.html is switched only after the guard recheck.
    live = ROOT / 'web/frontend/build'
    for source in build.rglob('*'):
        if not source.is_file() or source.name == 'index.html':
            continue
        target = live / source.relative_to(build)
        assert target.resolve().is_relative_to(live.resolve())
        if target.exists():
            backup = output / 'previous-assets' / source.relative_to(build)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(live / 'index.html', output / 'previous-index.html')
    assert guards() == jobs, 'Work started during deployment preparation'
    db.put_device_property(DEVICE, dict(producer_kind_filter=['unified_acquisition'],
                                       commands_enabled=['false'], xp_control_port=['8772']))
    kill_telemetry_server('DS_AcqTelemetry/everest', original_pid)
    # Kill exits normally, so the existing .bat supervisor must remain stopped.
    assert not any(p.info['cmdline'] and len(p.info['cmdline']) > 1
        and Path(p.info['cmdline'][1]).name == 'DS_AcqTelemetry.py'
        for p in psutil.process_iter(['cmdline']))
    db_info = db.get_device_info('elyse/acquisition/control')
    old_control_props = db.get_device_property('elyse/acquisition/control', ['commands_enabled'])
    assert list(old_control_props['commands_enabled']) in ([], ['False'], ['false'])
    kill_telemetry_server('DS_AcqTelemetryControl/everest', db_info.pid)
    # Starter retains its registration; this is not a database/device deletion.
    starter = tango.DeviceProxy('tango/admin/everest')
    starter.set_timeout_millis(10000)
    starter.command_inout('DevStart', 'DS_AcqTelemetry/everest')
    deadline = time.monotonic() + 45
    while True:
        try:
            receiver = tango.DeviceProxy(DEVICE)
            receiver.set_timeout_millis(2000)
            if str(receiver.state()) == 'ON' and 'unified_acquisition' in receiver.status():
                break
        except tango.DevFailed:
            pass
        assert time.monotonic() < deadline, 'Unified receiver startup failed'
        time.sleep(.5)
    assert guards() == jobs
    shutil.copy2(build / 'index.html', live / 'index.next.html')
    os.replace(live / 'index.next.html', live / 'index.html')
    web.terminate()
    web.wait(timeout=15)
    with (output / 'web-stdout.log').open('xb') as stdout, (output / 'web-stderr.log').open('xb') as stderr:
        replacement = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 45
    while True:
        assert replacement.poll() is None, 'Web replacement exited'
        try:
            response = session.get('http://127.0.0.1:5000/', timeout=(2, 3))
            if response.ok and response.text == (build / 'index.html').read_text(encoding='utf-8'):
                break
        except requests.RequestException:
            pass
        assert time.monotonic() < deadline, 'Web readiness failed'
        time.sleep(.5)
    served = session.get('http://127.0.0.1:5000' + manifest['files']['main.js'], timeout=(2, 6))
    served.raise_for_status()
    assert hashlib.sha256(served.content).digest() == hashlib.sha256(main.read_bytes()).digest()
    assert guards() == jobs
    report = dict(receiver_pid=db.get_device_info(DEVICE).pid, web_pid=replacement.pid,
                  tango_device=DEVICE, source='unified_acquisition', commands_enabled=False,
                  served_js=manifest['files']['main.js'], assets_hash_verified=True,
                  hardware_commands_sent=False, xp_initialized=False, jobs_preserved=True)
    save(output / 'deployment.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--build', required=True)
    args = parser.parse_args()
    deploy(args.output, args.build)
