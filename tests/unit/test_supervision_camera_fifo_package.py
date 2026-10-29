"""Read-only qualification gates for the prepared native VI package (3.4)."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.verify_supervision_camera_fifo import PACKAGE, verify, load_json, checked_path


class CameraFifoPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='supervision_fifo_test_')
        self.package = Path(self.temp.name) / 'patch'
        shutil.copytree(str(ROOT / PACKAGE), str(self.package))

    def tearDown(self):
        self.temp.cleanup()

    def change_manifest(self, change):
        path = self.package / 'manifest.json'
        data = load_json(path)
        change(data)
        with path.open('w', encoding='utf-8') as stream:
            json.dump(data, stream)

    def test_preparation_is_verified_but_not_runtime_qualified(self):
        result = verify(ROOT, self.package)
        self.assertTrue(result['preparation_verified'])
        self.assertTrue(result['native12_complete_dependency_load_pending'])
        self.assertFalse(result['runtime_25Hz_qualified'])
        self.assertFalse(result['xp_deployed'])

    def test_changed_native_bytes_fail(self):
        file = self.package / load_json(self.package / 'manifest.json')['artifacts'][0]['path']
        with file.open('ab') as stream:
            stream.write(b'test-corruption')
        with self.assertRaises(ValueError):
            verify(ROOT, self.package)

    def test_missing_native_file_fails(self):
        file = self.package / load_json(self.package / 'manifest.json')['artifacts'][0]['path']
        file.unlink()
        with self.assertRaises(IOError):
            verify(ROOT, self.package)

    def test_run_on_open_is_refused(self):
        def unsafe_header(data):
            return {'major': 12, 'RunOnOpen': True, 'source_diagram': True}
        with self.assertRaises(ValueError):
            verify(ROOT, self.package, header_reader=unsafe_header)

    def test_false_runtime_claim_is_refused(self):
        self.change_manifest(lambda data: data.update(runtime_25Hz_qualified=True))
        with self.assertRaises(ValueError):
            verify(ROOT, self.package)

    def test_missing_dependency_load_gate_is_refused(self):
        self.change_manifest(lambda data: data.update(native12_complete_dependency_load_pending=False))
        with self.assertRaises(ValueError):
            verify(ROOT, self.package)

    def test_changed_preserved_sync_hash_is_refused(self):
        self.change_manifest(lambda data: data['preserved_repo_files'][0].update(sha256='0' * 64))
        with self.assertRaises(ValueError):
            verify(ROOT, self.package)

    def test_escaping_inventory_path_is_refused(self):
        with self.assertRaises(ValueError):
            checked_path(self.package, '../outside.vi')


if __name__ == '__main__':
    unittest.main(verbosity=2)
