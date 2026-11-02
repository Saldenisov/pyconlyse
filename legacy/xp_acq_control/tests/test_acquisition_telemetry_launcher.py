"""Fake lifecycle plus disposable Windows socket/lock tests; no NI or VI calls."""
import unittest
import os
import socket
import subprocess
import sys
import tempfile
import struct
from legacy.xp_acq_control.elyse_agent.acquisition_telemetry_launcher import launch, LaunchError
from legacy.xp_acq_control.elyse_agent.acquisition_telemetry_launcher import WindowsEnvironment
from legacy.xp_acq_control.elyse_agent.acquisition_telemetry_launcher import _decode_tcp_listeners


class Child:
    pid = 123
    returncode = None
    def poll(self):
        return self.returncode


class Environment:
    def __init__(self, running=False):
        self.running = running
        self.events = []
        self.guard_available = True
        self.current_vi = False
        self.ownership = False
        self.ready_after_spawn = True
        self.orphan_port = False
        self.child = Child()
    def acquire_launch_guard(self):
        self.events.append('lock')
        return self.guard_available
    def release_launch_guard(self): self.events.append('unlock')
    def validate_files(self, vi): self.events.append('validate')
    def server_held(self): return self.running
    def ingress_bound(self): return self.running or self.orphan_port
    def api_bound(self): return self.running or self.orphan_port
    def spawn_server(self):
        self.events.append('spawn_cold_server')
        self.running = self.ready_after_spawn
        return self.child
    def acquisition_window_open(self): return self.current_vi
    def native_ownership_marker_exists(self): return self.ownership
    def open_vi(self, vi): self.events.append('open_operator_vi')


class LauncherTests(unittest.TestCase):
    def test_tcp_table_distinguishes_listen_from_time_wait_and_masks_port(self):
        address = struct.unpack('=I', socket.inet_aton('127.0.0.1'))[0]
        raw = struct.pack('=I', 2)
        raw += struct.pack('=IIIII', 11, address, socket.htons(8766), 0, 0)
        raw += struct.pack('=IIIII', 2, address, socket.htons(8772) | 0xffff0000, 0, 0)
        self.assertEqual(_decode_tcp_listeners(raw), {('127.0.0.1', 8772)})

    def test_tcp_inventory_rejects_truncated_rows(self):
        with self.assertRaises(LaunchError): _decode_tcp_listeners(struct.pack('=I', 1))

    def test_cold_server_starts_before_operator_vi(self):
        e = Environment()
        r = launch(e, vi='operator.vi')
        self.assertEqual(e.events, ['lock', 'validate', 'spawn_cold_server', 'open_operator_vi', 'unlock'])
        self.assertTrue(r['server_started'])
        self.assertTrue(r['vi_opened'])
        self.assertFalse(r['python_initialize_invoked'])

    def test_standalone_shortcut_never_opens_vi(self):
        e = Environment()
        r = launch(e)
        self.assertTrue(r['server_started'])
        self.assertFalse(r['vi_opened'])
        self.assertNotIn('open_operator_vi', e.events)

    def test_existing_server_is_reused(self):
        e = Environment(running=True)
        r = launch(e, vi='operator.vi')
        self.assertFalse(r['server_started'])
        self.assertNotIn('spawn_cold_server', e.events)
        self.assertIn('open_operator_vi', e.events)

    def test_running_acquisition_is_not_opened_again(self):
        e = Environment(running=True)
        e.current_vi = True
        r = launch(e, vi='operator.vi')
        self.assertFalse(r['vi_opened'])
        self.assertNotIn('open_operator_vi', e.events)

    def test_retained_native_owner_prevents_labview_launch(self):
        e = Environment(running=True)
        e.ownership = True
        with self.assertRaises(LaunchError): launch(e, vi='operator.vi')
        self.assertEqual(e.events[-1], 'unlock')
        self.assertNotIn('open_operator_vi', e.events)

    def test_child_failure_does_not_launch_vi(self):
        e = Environment()
        e.child.returncode = 2
        with self.assertRaises(LaunchError): launch(e, vi='operator.vi')
        self.assertNotIn('open_operator_vi', e.events)

    def test_timeout_does_not_launch_vi_or_kill_child(self):
        e = Environment()
        e.ready_after_spawn = False
        t = [0.0]
        def sleep(dt): t[0] += dt
        with self.assertRaises(LaunchError):
            launch(e, vi='operator.vi', timeout=1, clock=lambda: t[0], sleep=sleep)
        self.assertNotIn('open_operator_vi', e.events)
        self.assertEqual(e.events[-1], 'unlock')

    def test_occupied_unknown_port_never_starts_second_server(self):
        e = Environment()
        e.orphan_port = True
        with self.assertRaises(LaunchError): launch(e, vi='operator.vi')
        self.assertNotIn('spawn_cold_server', e.events)

    def test_concurrent_click_is_quiet_and_does_not_launch(self):
        e = Environment()
        e.guard_available = False
        r = launch(e, vi='operator.vi')
        self.assertEqual(r['state'], 'ANOTHER_LAUNCH_IN_PROGRESS')
        self.assertEqual(e.events, ['lock'])


@unittest.skipUnless(sys.platform == 'win32', 'Windows socket/file-lock contract')
class WindowsContractTests(unittest.TestCase):
    def test_closed_server_time_wait_is_not_a_live_listener(self):
        server = socket.socket()
        client = connection = None
        try:
            server.bind(('127.0.0.1', 0)); server.listen(1)
            port = server.getsockname()[1]
            client = socket.create_connection(('127.0.0.1', port), timeout=2)
            connection, unused = server.accept()
            connection.shutdown(socket.SHUT_WR)  # Server closes first, leaving TIME_WAIT.
            self.assertEqual(client.recv(1), b'')
            connection.close(); connection = None
            client.close(); client = None
            server.close()
            self.assertFalse(WindowsEnvironment._bound('127.0.0.1', port))
        finally:
            for item in (connection, client, server):
                if item is not None: item.close()

    def test_bound_probe_detects_reusable_listener_without_connecting(self):
        server = socket.socket()
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            port = server.getsockname()[1]
            self.assertTrue(WindowsEnvironment._bound('127.0.0.1', port))
        finally:
            server.close()
        self.assertFalse(WindowsEnvironment._bound('127.0.0.1', port))

    def test_server_lock_probe_reuses_held_owner_and_ignores_old_file(self):
        with tempfile.TemporaryDirectory() as folder:
            config = os.path.join(folder, 'config.acquisition.active.json')
            path = config + '.application.lock'
            with open(path, 'wb') as stream:
                stream.write(b'EXISTING LOCK MARKER')
            code = ('import msvcrt,sys; f=open(sys.argv[1],"r+b"); '
                    'msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1); '
                    'print("held",flush=True); sys.stdin.read(1)')
            child = subprocess.Popen([sys.executable, '-c', code, path],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            try:
                self.assertEqual(child.stdout.readline().strip(), b'held')
                self.assertTrue(WindowsEnvironment(config).server_held())
            finally:
                child.communicate(b'x', timeout=5)
            self.assertFalse(WindowsEnvironment(config).server_held())
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), b'EXISTING LOCK MARKER')


if __name__ == '__main__':
    unittest.main()
