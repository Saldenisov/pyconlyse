"""Everest-only process recovery. Never kills a process or contacts XP.

Task Scheduler calls --once every minute. DS_AcqTelemetry.bat already retries
nonzero child exits after five seconds. This independent check also covers the
loss of that wrapper and of the existing PostgreSQL cluster. Healthy/stale/live
processes are never restarted. Normal recorded stops and a pause file prevail.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

BASE = Path(r'F:\ELYSE_PostgreSQL')
HOME = BASE / 'recovery'
SERVER = 'DS_AcqTelemetry/everest'
DEVICE_DIR = Path(r'F:\ELYSE_Telemetry_Server\postgres_v3\DeviceServers\control\elyse_acq')
LOG = BASE / 'logs/device_server/DS_AcqTelemetry_everest.log'


def utc():
    return datetime.now(timezone.utc).isoformat()


def tail(path, limit=16384):
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - limit))
            return stream.read().decode('utf-8', errors='replace')
    except FileNotFoundError:
        return ''


def normal_receiver_stop(log):
    """Only the last completed wrapper lifecycle can disarm recovery."""
    lines = [line for line in log.splitlines()
             if re.search(r' (?:runner entered|starting|exited with) ', line)]
    return bool(lines and re.search(r' exited with 0\s+====\s*$', lines[-1]))


def normal_database_stop(log):
    lines = [line for line in log.splitlines()
             if any(x in line for x in ('starting PostgreSQL ', 'database system is shut down',
                                       'ready to accept connections', 'database system was interrupted'))]
    return bool(lines and 'database system is shut down' in lines[-1])


def plan(state, observed, now):
    """Pure recovery policy: no stale-data restart, no duplicate, no stop replay."""
    actions = []
    if not state.get('enabled') or observed.get('paused'):
        return actions
    for role in ('receiver', 'postgres'):
        item = state.setdefault(role, {})
        view = observed[role]
        if view['alive'] or view.get('occupied'):
            item.pop('absent_since', None)
            if view['alive']:
                item.pop('normal_stop_seen', None)
            continue
        if view.get('normal_stop'):
            item.update(normal_stop_seen=True)
            continue
        if item.get('normal_stop_seen'):
            continue
        since = item.setdefault('absent_since', now)
        if now - since >= 10 and now >= item.get('next_attempt', 0):
            actions.append(role)
            item['next_attempt'] = now + 60
    return actions


def observations():
    import psutil
    receiver, wrappers, postgres, other_receivers, postgres_children = [], [], [], [], []
    for process in psutil.process_iter(['name', 'cmdline', 'exe']):
        try:
            argv = process.info['cmdline'] or []
            name = (process.info['name'] or '').lower()
            if any(Path(x).name.lower() == 'ds_acqtelemetry.py' for x in argv):
                if (len(argv) == 3 and argv[-1] == 'everest'
                        and Path(process.cwd()).resolve() == DEVICE_DIR.resolve()):
                    receiver.append(process.pid)
                else:
                    other_receivers.append(process.pid)
            if name == 'cmd.exe' and 'ds_acqtelemetry.bat' in ' '.join(argv).lower():
                wrappers.append(process.pid)
            if name == 'postgres.exe' and process.info['exe']:
                expected = BASE / '17.11/pgsql/bin/postgres.exe'
                if Path(process.info['exe']).resolve() == expected.resolve():
                    if '-D' in argv and Path(argv[argv.index('-D') + 1]).resolve() == (BASE/'data').resolve():
                        postgres.append(process.pid)
                    else:
                        postgres_children.append(process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            continue
    occupied = any(c.status == psutil.CONN_LISTEN and c.laddr.port == 8767
                   for c in psutil.net_connections(kind='tcp'))
    current = tail(BASE/'data/current_logfiles').strip().split(' ', 1)
    pg_log = ''
    if len(current) == 2:
        path = Path(current[1]).resolve()
        if path.is_relative_to((BASE/'logs').resolve()):
            pg_log = tail(path)
    return dict(paused=(HOME/'PAUSE').exists(),
        receiver=dict(alive=bool(receiver), pids=receiver, wrappers=wrappers,
                      occupied=bool(wrappers or occupied or other_receivers),
                      normal_stop=normal_receiver_stop(tail(LOG))),
        postgres=dict(alive=bool(postgres), pids=postgres,
                      occupied=bool(postgres_children and not postgres),
                      normal_stop=normal_database_stop(pg_log)))


def recover(role):
    if role == 'receiver':
        import tango
        starter = tango.DeviceProxy('tango://10.20.30.202:10000/tango/admin/everest')
        starter.set_timeout_millis(10000)
        starter.command_inout('DevStart', SERVER)
        return 'Starter.DevStart requested'
    if role != 'postgres':
        raise ValueError('Unknown recovery target')
    # Existing cluster only. pg_ctl itself refuses a second postmaster.
    if (BASE/'data/PG_VERSION').read_text().strip() != '17':
        raise RuntimeError('Existing PostgreSQL 17 cluster required')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    binary = str(BASE/'17.11/pgsql/bin/pg_ctl.exe')
    check = subprocess.run([binary, 'status', '-D', str(BASE/'data')],
                           capture_output=True, timeout=10, creationflags=flags)
    if check.returncode == 0:
        return 'Already running; recovery left untouched'
    if check.returncode != 3:
        raise RuntimeError('PostgreSQL status uncertain: ' + str(check.returncode))
    with (BASE/'logs/autostart.log').open('a', encoding='utf-8') as log:
        # Do not wait for WAL replay. A running postmaster must be allowed to
        # recover for longer than the former 30-second launcher deadline.
        result = subprocess.run([binary, 'start', '-D', str(BASE/'data'), '-W',
                '-l', str(BASE/'logs/startup.log')], stdout=log, stderr=log,
                timeout=15, creationflags=flags)
    if result.returncode:
        raise RuntimeError('PostgreSQL startup request failed: ' + str(result.returncode))
    return 'Existing cluster startup requested; WAL recovery may continue'


def save(path, value):
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def event(value):
    path = HOME/'events.jsonl'
    if path.exists() and path.stat().st_size > 2*1024*1024:
        os.replace(path, HOME/'events.previous.jsonl')
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(utc=utc(), **value)) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', required=True)
    parser.add_argument('--arm', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' or socket.gethostname().lower().split('.')[0] != 'everest':
        raise RuntimeError('Everest Windows host only')
    HOME.mkdir(parents=True, exist_ok=True)
    # Task Scheduler IgnoreNew is reinforced with an OS byte lock. It is
    # released by the kernel after a crash; stale files do not claim ownership.
    import msvcrt
    with (HOME/'watchdog.lock').open('a+b') as guard:
        if guard.tell() == 0:
            guard.write(b'0'); guard.flush()
        guard.seek(0)
        try:
            msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        state_path = HOME/'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        observed = observations()
        if args.arm:
            if not all(observed[x]['alive'] for x in ('receiver', 'postgres')):
                raise RuntimeError('Arming requires both current processes running')
            state = dict(enabled=True, armed_utc=utc())
            event(dict(event='armed'))
        actions = plan(state, observed, time.time())
        outcomes = {}
        for role in actions:
            # Re-read immediately before mutation, including operator PAUSE.
            latest = observations()
            if latest['paused'] or latest[role]['alive'] or latest[role].get('occupied') or latest[role]['normal_stop']:
                continue
            try:
                outcomes[role] = recover(role)
            except Exception as error:
                outcomes[role] = type(error).__name__ + ': ' + str(error)[:300]
            event(dict(event='recovery', role=role, result=outcomes[role]))
        state.update(checked_utc=utc(), observed=observed, outcomes=outcomes,
                     hardware_commands_sent=False, xp_contacted=False)
        save(state_path, state)
        print(json.dumps(state))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        try:
            event(dict(event='watchdog_error', error=type(error).__name__ + ': ' + str(error)[:300]))
        finally:
            raise
