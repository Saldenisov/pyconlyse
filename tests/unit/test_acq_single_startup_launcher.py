"""Actual Python3.4 cold launcher checks, temporary files and fake Popen only."""
import os
import tempfile
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_startup import install_startup, MARKER


class SingleStartupLauncherTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = self.folder.name
        self.entry = os.path.join(self.root, 'acquisition_control_server.pyw')
        self.alias = os.path.join(self.root, 'acquisition_server.pyw')
        self.config = os.path.join(self.root, 'config.acquisition.control.json')
        self.python = os.path.join(self.root, 'pythonw.exe')
        for name in (self.entry, self.alias, self.config, self.python):
            with open(name, 'wb') as stream:
                stream.write(b'fixture')
        self.startup = os.path.join(self.root, 'Startup')
        os.mkdir(self.startup)

    def tearDown(self):
        self.folder.cleanup()

    def test_canonical_launcher_spawns_only_unified_gui_then_returns(self):
        with mock.patch('subprocess.Popen') as spawn:
            path = install_startup(self.alias, self.config, self.startup, self.python)
            self.assertFalse(spawn.called)  # Installing a launcher never runs it.
            with open(path, 'r', encoding='utf-8') as stream:
                source = stream.read()
            self.assertIn('ONE_UNIFIED_SERVER_V3', source)
            self.assertNotIn('acquisition_supervisor', source)
            self.assertNotIn('shared_state_receiver', source)
            exec(compile(source, path, 'exec'), {})
            spawn.assert_called_once_with([self.python, self.entry, '--config', self.config],
                cwd=self.root, shell=False, close_fds=True)

    def test_unrelated_startup_file_is_preserved(self):
        path = os.path.join(self.startup, 'ELYSE_Acquisition_Server.pyw')
        with open(path, 'wb') as stream:
            stream.write(b'Unrelated application')
        with self.assertRaises(ValueError):
            install_startup(self.entry, self.config, self.startup, self.python)
        with open(path, 'rb') as stream:
            self.assertEqual(stream.read(), b'Unrelated application')

    def test_old_marked_supervisor_launcher_is_replaced_but_never_executed(self):
        path = os.path.join(self.startup, 'ELYSE_Acquisition_Server.pyw')
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(MARKER + '\n# COLD_SUPERVISOR_V2\n')
        with mock.patch('subprocess.Popen') as spawn:
            self.assertEqual(install_startup(self.entry, self.config, self.startup, self.python), path)
            self.assertFalse(spawn.called)
        with open(path, 'r', encoding='utf-8') as stream:
            self.assertNotIn('COLD_SUPERVISOR_V2', stream.read())
        backups = [name for name in os.listdir(self.startup) if '.backup_' in name]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.startup, backups[0]), 'r', encoding='utf-8') as stream:
            self.assertIn('COLD_SUPERVISOR_V2', stream.read())

    def test_standalone_telemetry_entrypoint_cannot_be_added_to_startup(self):
        with self.assertRaises(ValueError):
            install_startup(os.path.join(self.root, 'shared_state_receiver.pyw'),
                self.config, self.startup, self.python)
        self.assertEqual(os.listdir(self.startup), [])


if __name__ == '__main__':
    unittest.main()
