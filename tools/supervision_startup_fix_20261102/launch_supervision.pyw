"""Single installed SuperVision orchestrator, optional existing VI. Python3.4.

Never initializes, deinitializes, resets or commands NI. Never restarts a failed
worker. Existing ownership markers and server locks are preserved.
"""
import argparse
import datetime
import glob
import json
import os
import socket
import subprocess
import sys
import time

HOST = '10.20.30.2'
LABVIEW = r'C:\Program Files\National Instruments\LabVIEW 2012\LabVIEW.exe'
VI = r'C:\SUPERVISION_TELEMETRY_20261028\Supervision Telemetry.vi'


def listening(port):
    try:
        connection = socket.create_connection((HOST, port), timeout=.3)
    except OSError:
        return False
    connection.close()
    return True


def unified_configuration(value):
    if (value.get('bind_host') != HOST or value.get('port') != 8772
            or type(value.get('vi_passive_shadow')) is not bool):
        raise ValueError('Expected installed SuperVision configuration')
    updated = dict(value)
    updated['vi_passive_shadow'] = False
    return updated


def ensure_server(root, probe=listening, spawn=subprocess.Popen, pause=time.sleep,
                  clock=time.monotonic, interpreter=None):
    runtime = os.path.join(root, 'runtime')
    config_path = os.path.join(runtime, 'config.supervision.active.json')
    entry = os.path.join(runtime, 'supervision_control_server.pyw')
    with open(config_path, 'r', encoding='utf-8') as stream:
        config = json.load(stream)
    if config != unified_configuration(config):
        raise RuntimeError('VI_PASSIVE_SHADOW configuration still installed; use the prepared update')
    if not os.path.isfile(entry):
        raise RuntimeError('Installed SuperVision entrypoint missing')
    if probe(8772):
        return dict(state='EXISTING_LISTENER_REUSED', started=False)
    if any(probe(port) for port in (8766, 8768)):
        raise RuntimeError('Existing VI listener without API; no second server was started')
    interpreter = interpreter or sys.executable
    with open(os.path.join(root, 'server.stdout.log'), 'ab') as stdout:
        with open(os.path.join(root, 'server.stderr.log'), 'ab') as stderr:
            child = spawn([interpreter, '-B', entry, '--config', config_path],
                          cwd=runtime, stdout=stdout, stderr=stderr)
    deadline = clock() + 20.
    while clock() < deadline:
        if child.poll() is not None:
            raise RuntimeError('SuperVision server exited during cold startup; see server.stderr.log')
        if probe(8772):
            return dict(state='COLD_SERVER_LISTENING', started=True, pid=child.pid)
        pause(.2)
    raise RuntimeError('Server startup still pending; no duplicate or automatic restart was attempted')


def launch(root, with_vi=False, ensure=ensure_server, open_vi=None):
    if with_vi:
        markers = glob.glob(os.path.join(root, 'runtime', 'config.supervision*.json.ownership'))
        if markers:
            raise RuntimeError('Native ownership marker present; release native boards before opening VI')
        if not os.path.isfile(VI) or not os.path.isfile(LABVIEW):
            raise RuntimeError('Existing LabVIEW2012/telemetry VI not found; original files preserved')
    result = ensure(root)
    if with_vi:
        if glob.glob(os.path.join(root, 'runtime', 'config.supervision*.json.ownership')):
            raise RuntimeError('Native ownership appeared; VI was not opened')
        if open_vi is None:
            open_vi = lambda: subprocess.Popen([LABVIEW, VI], cwd=os.path.dirname(VI))
        open_vi()
        result['vi_open_requested'] = True
    else:
        result['vi_open_requested'] = False
    result.update(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  initialize_invoked=False, hardware_commands_sent=False)
    return result


class LaunchLock(object):
    def __init__(self, path):
        self.path, self.stream = path, None

    def __enter__(self):
        import msvcrt
        self.stream = open(self.path, 'a+b')
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b'1'); self.stream.flush()
        self.stream.seek(0)
        try:
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.stream.close(); self.stream = None
            raise RuntimeError('SuperVision launch already in progress')
        return self

    def __exit__(self, *unused):
        import msvcrt
        self.stream.seek(0)
        msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-vi', action='store_true')
    args = parser.parse_args()
    root = os.path.dirname(os.path.abspath(__file__))
    try:
        with LaunchLock(os.path.join(root, 'supervision.launch.lock')):
            result = launch(root, with_vi=args.with_vi)
        with open(os.path.join(root, 'launcher_events.jsonl'), 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, sort_keys=True) + '\n')
    except Exception as error:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk(); window.withdraw()
        messagebox.showerror('SuperVision launch', str(error), parent=window)
        window.destroy()


if __name__ == '__main__':
    main()
