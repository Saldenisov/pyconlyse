"""Cold transport source swap preserves configuration and rolls back failures."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.install_telemetry_reconnect import install_files


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


if __name__ == '__main__':
    unittest.main()
