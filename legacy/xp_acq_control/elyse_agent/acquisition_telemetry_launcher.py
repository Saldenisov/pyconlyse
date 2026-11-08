"""Operator launch shortcuts; Python 3.4, no NI imports or card commands.

Start the existing unified server cold. An explicit --vi additionally opens
the existing operator START VI, which retains its original NI initialization.
Installation and the server-only shortcut never open that VI. This launcher
exits after startup; it is not a second telemetry server or resident supervisor.
"""
import argparse
import datetime
import errno
import json
import os
import socket
import subprocess
import sys
import time


class LaunchError(RuntimeError):
    pass


def launch(environment, vi=None, timeout=20, clock=None, sleep=None):
    """Bound startup and reuse the existing config-scoped application owner."""
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    child = None
    started = False
    result = dict(server_started=False, vi_opened=False, python_initialize_invoked=False)
    if not environment.acquire_launch_guard():
        result['state'] = 'ANOTHER_LAUNCH_IN_PROGRESS'
        return result
    try:
        environment.validate_files(vi)
        if not environment.server_held():
            if environment.ingress_bound() or environment.api_bound():
                raise LaunchError('A port is occupied without this installation server lock; no second server was started.')
            child = environment.spawn_server()
            started = True
        deadline = clock() + timeout
        while True:
            if child is not None and child.poll() is not None:
                raise LaunchError('Unified server exited during startup (exit {0}); inspect its error window.'.format(child.returncode))
            if environment.server_held() and environment.ingress_bound() and environment.api_bound():
                break
            if clock() >= deadline:
                raise LaunchError('Unified server did not open 8766 and 8772 within {0}s. The VI was not opened.'.format(timeout))
            sleep(min(.1, max(0, deadline - clock())))
        result.update(server_started=started, state='SERVER_READY',
                      server_pid=None if child is None else child.pid)
        if vi is not None:
            if environment.acquisition_window_open():
                result['state'] = 'SERVER_READY_EXISTING_ACQUISITION_WINDOW'
            elif environment.native_ownership_marker_exists():
                raise LaunchError('Python NI ownership marker exists; server is available, but LabVIEW was not opened. No ownership state was cleared.')
            else:
                environment.open_vi(vi)
                result.update(vi_opened=True, state='SERVER_READY_VI_OPEN_REQUESTED')
        return result
    finally:
        environment.release_launch_guard()


def _try_lock(stream):
    import msvcrt
    stream.seek(0)
    try:
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return False
        raise


def _unlock(stream):
    import msvcrt
    stream.seek(0)
    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


class WindowsEnvironment(object):
    def __init__(self, config):
        if sys.platform != 'win32':
            raise LaunchError('Windows XP launcher required')
        self.config = os.path.abspath(config)
        self.folder = os.path.dirname(self.config)
        self.entry = os.path.join(self.folder, 'acquisition_control_server.pyw')
        self.pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        self.guard = None

    def validate_files(self, vi):
        for path in (self.pythonw, self.entry, self.config):
            if not os.path.isfile(path):
                raise LaunchError('Required installed file missing: ' + path)
        if vi is not None and not os.path.isfile(vi):
            raise LaunchError('Existing operator START VI missing: ' + vi)
        if os.path.basename(self.config) != 'config.acquisition.active.json':
            raise LaunchError('The installed active Acquisition configuration is required')

    def acquire_launch_guard(self):
        path = self.config + '.shortcut.lock'
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        stream = os.fdopen(descriptor, 'r+b')
        try:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'0')
                stream.flush()
            if not _try_lock(stream):
                stream.close()
                return False
            self.guard = stream
            return True
        except Exception:
            stream.close()
            raise

    def release_launch_guard(self):
        if self.guard is not None:
            stream, self.guard = self.guard, None
            try:
                _unlock(stream)
            finally:
                stream.close()

    def server_held(self):
        path = self.config + '.application.lock'
        if not os.path.isfile(path):
            return False
        with open(path, 'r+b') as stream:
            if not _try_lock(stream):
                return True
            _unlock(stream)
            return False

    @staticmethod
    def _bound(host, port):
        # Probe by exclusive bind, not connection: never submit a fake frame
        # or increment VI read-error counters during ordinary launcher use.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                sock.bind((host, port))
            except OSError as error:
                if getattr(error, 'winerror', None) in (10048, 10013) or error.errno in (10048, 10013):
                    return True
                raise
            return False
        finally:
            sock.close()

    def ingress_bound(self):
        return self._bound('127.0.0.1', 8766)

    def api_bound(self):
        return self._bound('10.20.30.10', 8772)

    def spawn_server(self):
        return subprocess.Popen([self.pythonw, '-B', self.entry, '--config', self.config],
                                cwd=self.folder, shell=False, close_fds=True)

    def native_ownership_marker_exists(self):
        return os.path.exists(self.config + '.ownership')

    @staticmethod
    def acquisition_window_open():
        import ctypes
        from ctypes import wintypes
        found = [False]
        user = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        @callback_type
        def visit(hwnd, unused):
            text = ctypes.create_unicode_buffer(1024)
            user.GetWindowTextW(hwnd, text, len(text))
            if '0_ACQ_ELYSE.vi' in text.value or 'START_Acquisition_Telemetry.vi' in text.value:
                found[0] = True
            return True
        user.EnumWindows(visit, 0)
        return found[0]

    @staticmethod
    def open_vi(vi):
        # Explicit operator click only. The original START VI runs on open.
        os.startfile(vi)


def main(entrypoint):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--vi', default=None)
    args = parser.parse_args()
    result = None
    try:
        result = launch(WindowsEnvironment(args.config), vi=args.vi)
        return 0
    except Exception as error:
        result = dict(state='FAILED', error=str(error), python_initialize_invoked=False)
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        messagebox.showerror('ELYSE Acquisition startup', str(error), parent=root)
        root.destroy()
        return 1
    finally:
        # Diagnostic receipt is best effort; no alarm journal or launch gate.
        if result is not None:
            result['observed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(entrypoint)),
                                       'last_shortcut_launch.json'), 'w') as stream:
                    json.dump(result, stream, indent=2)
            except (OSError, ValueError):
                pass
