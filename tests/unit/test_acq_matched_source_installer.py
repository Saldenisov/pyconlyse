"""Cold transactional updater; temporary files only, no processes or NI."""
import hashlib
import json
import os
import pathlib
import runpy
import tempfile
import unittest

INSTALLER = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[2] / "tools/install_acq_matched_source.pyw"))

def put(path, data):
    os.makedirs(str(path.parent), exist_ok=True)
    with open(str(path), "wb") as stream:
        stream.write(data)

def get(path):
    with open(str(path), "rb") as stream:
        return stream.read()


class MatchedSourceInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.incoming, self.target = self.root / "incoming", self.root / "target"
        self.incoming.mkdir(); self.target.mkdir()
        files = {"module.py": b"value = 2\n", "new_module.py": b"value = 3\n",
                 "config.acquisition.json": b"{}", "config.acquisition.control.json": b"{}",
                 "data/calibration_map.csv": b"fixture calibration", "data/ni6602_timing.csv": b"fixture timing"}
        records = []
        for name, data in files.items():
            incoming = self.incoming / name
            put(incoming, data)
            records.append(dict(path=name, sha256=hashlib.sha256(data).hexdigest()))
            if name != "new_module.py":
                installed = self.target / name
                put(installed, b"value = 1\n" if name == "module.py" else
                    b'{"site":"preserved"}' if name.startswith("config.") else data)
        put(self.incoming / "manifest.json", json.dumps(dict(role="xp_python34", named_operation_count=24,
            commands_default_enabled=False, auto_initialize=False, files=records)).encode("utf-8"))
        put(self.target / "manifest.json", b'{"old":"manifest"}')
        put(self.target / "config.acquisition.control.json.ownership", b"prior evidence unchanged")

    def tearDown(self):
        self.temporary.cleanup()

    def install(self, **options):
        return INSTALLER["install"](str(self.incoming), str(self.target), closed_check=lambda: None, **options)

    def test_preserves_config_and_ownership_and_backs_up_old_source(self):
        before = INSTALLER["protected_image"](str(self.target))
        result = self.install()
        self.assertEqual(INSTALLER["protected_image"](str(self.target)), before)
        self.assertEqual(get(self.target / "module.py"), b"value = 2\n")
        self.assertEqual(get(pathlib.Path(result["backup"]) / "module.py"), b"value = 1\n")
        self.assertFalse(result["cards_initialized"])

    def test_mid_install_failure_restores_prior_source_and_manifest(self):
        calls = []
        def fail_once(source, destination):
            calls.append(destination)
            if len(calls) == 3:
                raise IOError("injected replace failure")
            os.replace(source, destination)
        with self.assertRaises(IOError):
            self.install(replace=fail_once)
        self.assertEqual(get(self.target / "module.py"), b"value = 1\n")
        self.assertFalse((self.target / "new_module.py").exists())
        self.assertEqual(get(self.target / "manifest.json"), b'{"old":"manifest"}')

    def test_bad_hash_refuses_before_source_changes(self):
        put(self.incoming / "module.py", b"tampered = True\n")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(get(self.target / "module.py"), b"value = 1\n")
        self.assertFalse((self.target / "runtime").exists())

    def test_calibration_change_refuses_even_with_valid_incoming_hashes(self):
        put(self.target / "data/calibration_map.csv", b"different installed calibration")
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(get(self.target / "module.py"), b"value = 1\n")
        self.assertFalse((self.target / "runtime").exists())

    def test_existing_transaction_temporary_file_is_not_deleted(self):
        temporary = self.target / "module.py.matched-source-new"
        put(temporary, b"other transaction")
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertEqual(get(temporary), b"other transaction")
        self.assertEqual(get(self.target / "module.py"), b"value = 1\n")

    def test_escaping_path_is_rejected(self):
        for name in ("../outside.py", "/outside.py", "C:/outside.py", "a/../outside.py"):
            with self.assertRaises(ValueError):
                INSTALLER["safe_path"](str(self.target), name)


if __name__ == "__main__":
    unittest.main()
