"""Cold transport source swap preserves configuration and rolls back failures."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.install_telemetry_reconnect import install_files, site_endpoint


def write(path, raw):
    with path.open('wb') as stream:
        stream.write(raw)


def read(path):
    with path.open('rb') as stream:
        return stream.read()


class TransportInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.payload, self.runtime = self.base/'payload', self.base/'runtime'
        self.payload.mkdir()
        (self.runtime/'elyse_agent').mkdir(parents=True)
        self.names = ['telemetry_relay.py', 'shared_state_receiver.py']
        self.old, self.new = b'VALUE = "old"\r\n', b'VALUE = "new"\n'
        files = {}
        for name in self.names:
            write(self.runtime/'elyse_agent'/name, self.old)
            write(self.payload/name, self.new)
            files[name] = dict(before_sha256=hashlib.sha256(self.old.replace(b'\r\n', b'\n')).hexdigest(),
                               after_sha256=hashlib.sha256(self.new).hexdigest())
        self.manifest = dict(files=files, roles=dict(acquisition=self.names))
        self.preserved = {'config.json': b'unchanged configuration', 'owner.ownership': b'NI evidence',
                          'read.key': b'fixture-only key', 'alarm.journal': b'fixture history'}
        for name, raw in self.preserved.items():
            write(self.runtime/name, raw)

    def tearDown(self):
        for name, raw in self.preserved.items():
            self.assertEqual(read(self.runtime/name), raw)
        self.temp.cleanup()

    def test_atomic_install_preserves_every_site_file_and_original_module_backup(self):
        result = install_files(str(self.payload), str(self.runtime), 'acquisition', self.manifest)
        self.assertFalse(result['initialize_invoked'])
        self.assertFalse(result['configuration_changed'])
        self.assertEqual(result['state'], 'INSTALLED_SERVER_NOT_STARTED')
        for name in self.names:
            self.assertEqual(read(self.runtime/'elyse_agent'/name), self.new)
            self.assertEqual(read(Path(result['backup'])/name), self.old)
        receipt = json.loads(read(Path(result['backup'])/'receipt.json').decode('utf-8'))
        self.assertEqual(receipt['files'], self.names)

    def test_second_swap_failure_rolls_back_first_module_without_touching_site_state(self):
        calls = []
        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError('Fixture swap failure')
            os.replace(source, target)
        with self.assertRaises(OSError):
            install_files(str(self.payload), str(self.runtime), 'acquisition', self.manifest,
                          replace=fail_second)
        for name in self.names:
            self.assertEqual(read(self.runtime/'elyse_agent'/name), self.old)

    def test_unknown_installed_source_is_rejected_before_any_swap_or_backup(self):
        write(self.runtime/'elyse_agent'/self.names[1], b'operator edit')
        with self.assertRaises(ValueError):
            install_files(str(self.payload), str(self.runtime), 'acquisition', self.manifest)
        self.assertEqual(read(self.runtime/'elyse_agent'/self.names[0]), self.old)
        self.assertEqual(list(self.runtime.glob('transport_backup_*')), [])

    def test_deferred_vi_update_swaps_only_acquisition_publisher(self):
        name = 'dual_mode_telemetry.py'
        write(self.runtime/'elyse_agent'/name, self.old)
        write(self.payload/name, self.new)
        self.manifest['files'][name] = dict(
            before_sha256=hashlib.sha256(self.old.replace(b'\r\n', b'\n')).hexdigest(),
            after_sha256=hashlib.sha256(self.new).hexdigest())
        self.manifest['roles']['acquisition'] = [name]
        report = install_files(str(self.payload), str(self.runtime), 'acquisition', self.manifest)
        self.assertEqual(report['files'], [name])
        self.assertEqual(read(self.runtime/'elyse_agent'/name), self.new)
        for untouched in self.names:
            self.assertEqual(read(self.runtime/'elyse_agent'/untouched), self.old)

    def test_acquisition_vi_publisher_cannot_be_installed_on_supervision(self):
        self.manifest['roles']['supervision'] = ['dual_mode_telemetry.py']
        with self.assertRaises(ValueError):
            install_files(str(self.payload), str(self.runtime), 'supervision', self.manifest)
        self.assertEqual(list(self.runtime.glob('transport_backup_*')), [])


class SiteEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.control = self.folder/'config.acquisition.active.json'
        self.base = self.folder/'config.acquisition.json'
        self.write_json(self.control, dict(remote_control_enabled=False,
            command_key_file='fixture-command.key', cooling_safety=dict(polarity_verified=False,
                journal_file='fixture-history.sqlite3')))
        self.write_json(self.base, dict(bind_host='10.20.30.10', port=8772))

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_json(path, value):
        write(path, json.dumps(value).encode('utf-8'))

    def test_acquisition_reads_sibling_endpoint_without_rewriting_either_configuration(self):
        before = read(self.control), read(self.base)
        self.assertEqual(site_endpoint('acquisition', str(self.control)), ('10.20.30.10', 8772))
        self.assertEqual((read(self.control), read(self.base)), before)

    def test_acquisition_rejects_other_host_in_sibling_configuration(self):
        self.write_json(self.base, dict(bind_host='10.20.30.2', port=8772))
        with self.assertRaises(ValueError):
            site_endpoint('acquisition', str(self.control))

    def test_supervision_reads_its_single_configuration(self):
        path = self.folder/'config.supervision.active.json'
        self.write_json(path, dict(bind_host='10.20.30.2', port=8772))
        before = read(path)
        self.assertEqual(site_endpoint('supervision', str(path)), ('10.20.30.2', 8772))
        self.assertEqual(read(path), before)

    def test_flat_supervision_configuration_cannot_select_acquisition_application_lock(self):
        self.write_json(self.control, dict(bind_host='10.20.30.2', port=8772))
        with self.assertRaises(ValueError):
            site_endpoint('acquisition', str(self.control))

    def test_missing_sibling_is_reported_without_falling_back_to_control_file(self):
        absent = self.folder/'other'
        absent.mkdir()
        path = absent/self.control.name
        write(path, read(self.control))
        with self.assertRaises(OSError):
            site_endpoint('acquisition', str(path))


if __name__ == '__main__':
    unittest.main()
