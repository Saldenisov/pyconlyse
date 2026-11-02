import importlib.machinery
import json
import os
import tempfile
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
m = importlib.machinery.SourceFileLoader('launch_test_target', os.path.join(HERE, 'launch_supervision.pyw')).load_module()


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = self.temp.name
        os.mkdir(os.path.join(self.root, 'runtime'))
        self.config = dict(bind_host=m.HOST, port=8772, vi_passive_shadow=False,
                           remote_control_enabled=False, read_key_file='unchanged.key')
        with open(os.path.join(self.root, 'runtime', 'config.supervision.active.json'), 'w') as f:
            json.dump(self.config, f)
        open(os.path.join(self.root, 'runtime', 'supervision_control_server.pyw'), 'w').close()

    def tearDown(self):
        self.temp.cleanup()

    def test_configuration_changes_only_shadow_flag(self):
        old = dict(self.config, vi_passive_shadow=True)
        self.assertEqual(m.unified_configuration(old), self.config)
        self.assertTrue(old['vi_passive_shadow'])

    def test_wrong_host_rejected(self):
        with self.assertRaises(ValueError):
            m.unified_configuration(dict(self.config, bind_host='127.0.0.1'))

    def test_existing_listener_never_spawns_duplicate(self):
        def forbidden(*args, **kwargs): self.fail('duplicate process')
        result = m.ensure_server(self.root, probe=lambda p: p == 8772, spawn=forbidden)
        self.assertFalse(result['started'])

    def test_orphan_listener_blocks_second_server(self):
        def forbidden(*args, **kwargs): self.fail('duplicate process')
        with self.assertRaises(RuntimeError):
            m.ensure_server(self.root, probe=lambda p: p == 8766, spawn=forbidden)

    def test_cold_start_has_only_entrypoint_and_config(self):
        calls = []; probes = []
        class Child:
            pid = 123
            def poll(self): return None
        def spawn(args, **kwargs): calls.append(args); return Child()
        def probe(port):
            probes.append(port)
            return port == 8772 and len(probes) > 3
        result = m.ensure_server(self.root, probe=probe, spawn=spawn, interpreter='pythonw.exe')
        self.assertTrue(result['started'])
        self.assertEqual(calls[0][0:2], ['pythonw.exe', '-B'])
        self.assertEqual(calls[0][3], '--config')
        self.assertEqual(len(calls[0]), 5)
        self.assertNotIn('initialize', ' '.join(calls[0]).lower())

    def test_failed_child_is_not_restarted(self):
        calls = []
        class Child:
            pid = 123
            def poll(self): return 1
        def spawn(*args, **kwargs): calls.append(args); return Child()
        with self.assertRaises(RuntimeError):
            m.ensure_server(self.root, probe=lambda p: False, spawn=spawn)
        self.assertEqual(len(calls), 1)

    def test_server_only_does_not_open_vi(self):
        def forbidden(): self.fail('VI opened')
        result = m.launch(self.root, ensure=lambda root: dict(state='IDLE'), open_vi=forbidden)
        self.assertFalse(result['vi_open_requested'])
        self.assertFalse(result['initialize_invoked'])

    def test_owned_native_boards_block_vi(self):
        marker = os.path.join(self.root, 'runtime', 'config.supervision.active.json.ownership')
        with open(marker, 'w') as f: f.write('preserve')
        with self.assertRaises(RuntimeError): m.launch(self.root, with_vi=True)
        with open(marker) as f: self.assertEqual(f.read(), 'preserve')

    def test_vi_opens_only_after_server(self):
        calls = []
        def ensure(root): calls.append('server'); return dict(state='IDLE')
        with patch.object(m.os.path, 'isfile', return_value=True):
            result = m.launch(self.root, with_vi=True, ensure=ensure, open_vi=lambda: calls.append('vi'))
        self.assertEqual(calls, ['server', 'vi'])
        self.assertTrue(result['vi_open_requested'])


if __name__ == '__main__':
    unittest.main()
