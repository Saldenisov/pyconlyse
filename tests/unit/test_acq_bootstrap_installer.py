"""Cold updater acceptance, temporary files only; actual Python 3.4 compatible."""
import hashlib
import importlib.machinery
import json
import os
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
installer = importlib.machinery.SourceFileLoader('bootstrap_installer_fixture',
    os.path.join(ROOT, 'tools', 'install_acq_bootstrap_update.pyw')).load_module()


class BootstrapInstallerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.target = os.path.join(self.folder.name, 'installed')
        self.incoming = os.path.join(self.folder.name, 'incoming')
        self.plan = dict(files={})
        for relative in installer.FILES:
            self.write(self.target, relative, b'VALUE = "old"\n')
            self.write(self.incoming, relative, b'VALUE = "new"\n')
            self.plan['files'][relative] = dict(old=self.sha(self.target, relative),
                                               new=self.sha(self.incoming, relative))
        self.write(self.target, 'manifest.json', b'{"release":"old"}')
        self.write(self.incoming, 'manifest.json', b'{"release":"new"}')
        self.plan.update(old_manifest_sha256=self.sha(self.target, 'manifest.json'),
                         new_manifest_sha256=self.sha(self.incoming, 'manifest.json'))
        self.write(self.target, 'config.acquisition.control.json.ownership', b'prior marker MUST stay')
        self.write(self.target, 'config.acquisition.json', b'unchanged configuration')
        self.write(self.target, 'runtime/cooling-alarms.sqlite3', b'unchanged journal')
        self.save_plan()
        self.closed = mock.patch.object(installer, 'require_server_closed')
        self.closed.start()

    def tearDown(self):
        self.closed.stop()
        self.folder.cleanup()

    @staticmethod
    def write(root, relative, data):
        path = os.path.join(root, *relative.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as stream:
            stream.write(data)

    @staticmethod
    def sha(root, relative):
        with open(os.path.join(root, *relative.split('/')), 'rb') as stream:
            return hashlib.sha256(stream.read()).hexdigest()

    def save_plan(self):
        with open(os.path.join(self.incoming, 'bootstrap_plan.json'), 'w') as stream:
            json.dump(self.plan, stream)

    def test_exact_five_file_update_backs_up_sources_and_preserves_marker_config_journal(self):
        protected = {name: self.sha(self.target, name) for name in (
            'config.acquisition.control.json.ownership', 'config.acquisition.json', 'runtime/cooling-alarms.sqlite3')}
        backup = installer.install(self.incoming, self.target)
        for relative in installer.FILES:
            self.assertEqual(self.sha(self.target, relative), self.plan['files'][relative]['new'])
            self.assertEqual(self.sha(backup, relative), self.plan['files'][relative]['old'])
        for name, digest in protected.items():
            self.assertEqual(self.sha(self.target, name), digest)

    def test_changed_installed_source_is_not_overwritten(self):
        relative = installer.FILES[0]
        self.write(self.target, relative, b'VALUE = "local change"\n')
        before = self.sha(self.target, relative)
        with self.assertRaises(RuntimeError):
            installer.install(self.incoming, self.target)
        self.assertEqual(self.sha(self.target, relative), before)

    def test_extra_file_scope_cannot_mutate_configuration(self):
        self.plan['files']['config.acquisition.json'] = dict(old='a', new='b')
        self.save_plan()
        with self.assertRaises(RuntimeError):
            installer.install(self.incoming, self.target)

    def test_changed_manifest_refuses_before_any_replacement(self):
        self.write(self.target, 'manifest.json', b'changed')
        with self.assertRaises(RuntimeError):
            installer.install(self.incoming, self.target)
        for relative in installer.FILES:
            self.assertEqual(self.sha(self.target, relative), self.plan['files'][relative]['old'])

    def test_marker_changed_between_preflight_and_install_is_preserved_and_refused(self):
        with mock.patch.object(installer, 'marker_image', side_effect=(b'before', b'after')):
            with self.assertRaises(RuntimeError):
                installer.install(self.incoming, self.target)
        for relative in installer.FILES:
            self.assertEqual(self.sha(self.target, relative), self.plan['files'][relative]['old'])


if __name__ == '__main__':
    unittest.main()
