"""Cold transport provisioning must not qualify or manipulate hardware."""
import hashlib
import json
import os
import tempfile
import unittest

from tools.configure_acq_command_transport import configure, read, atomic_write


class CommandTransportSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.target = self.directory.name
        self.base = dict(key_file="read.key", stage_controls_verified=False,
                         ht_controls_verified=False, control_profile="extended_ht_stop")
        self.control = dict(remote_control_enabled=False, command_key_file="old.key",
                            cooling_safety=dict(polarity_verified=False, journal_file="alarms.sqlite3"))
        for name, value in (("config.acquisition.json", self.base),
                            ("config.acquisition.control.json", self.control),
                            ("manifest.json", dict(files=[dict(path="config.acquisition.control.json", sha256="old")]))):
            atomic_write(os.path.join(self.target, name), json.dumps(value).encode("utf-8"))
        atomic_write(os.path.join(self.target, "read.key"), b"r" * 64)
        atomic_write(os.path.join(self.target, "config.acquisition.control.json.ownership"), b"evidence")

    def tearDown(self):
        self.directory.cleanup()

    def test_enables_only_transport_and_preserves_ownership_and_commissioning(self):
        base = read(os.path.join(self.target, "config.acquisition.json"))
        result = configure(self.target, b"c" * 64, closed_check=lambda: None)
        self.assertTrue(result["remote_control_enabled"])
        self.assertFalse(result["hardware_commands_sent"])
        self.assertEqual(read(os.path.join(self.target, "config.acquisition.json")), base)
        self.assertEqual(read(os.path.join(self.target, "config.acquisition.control.json.ownership")), b"evidence")
        current = json.loads(read(os.path.join(self.target, "config.acquisition.control.json")).decode())
        self.assertEqual(current["cooling_safety"], self.control["cooling_safety"])
        self.assertEqual(read(os.path.join(self.target, current["command_key_file"])), b"c" * 64)
        manifest = json.loads(read(os.path.join(self.target, "manifest.json")).decode())
        self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(read(os.path.join(
            self.target, "config.acquisition.control.json"))).hexdigest())

    def test_refuses_same_read_and_command_key_before_configuration_change(self):
        with self.assertRaises(ValueError):
            configure(self.target, b"r" * 64, closed_check=lambda: None)
        self.assertFalse(json.loads(read(os.path.join(self.target, "config.acquisition.control.json")).decode())["remote_control_enabled"])

    def test_failed_manifest_write_restores_control_and_manifest(self):
        paths = [os.path.join(self.target, name) for name in ("config.acquisition.control.json", "manifest.json")]
        before = [read(path) for path in paths]
        def fail_manifest(path, value):
            if path.endswith("manifest.json"):
                raise IOError("fixture manifest failure")
            atomic_write(path, value)
        with self.assertRaises(IOError):
            configure(self.target, b"c" * 64, closed_check=lambda: None, write=fail_manifest)
        self.assertEqual([read(path) for path in paths], before)

    def test_live_listener_refusal_changes_nothing(self):
        def blocked():
            raise RuntimeError("listener active")
        with self.assertRaises(RuntimeError):
            configure(self.target, b"c" * 64, closed_check=blocked)
        self.assertFalse(os.path.exists(os.path.join(self.target, "runtime")))

    def test_preflight_change_is_not_overwritten_by_rollback(self):
        calls = []
        path = os.path.join(self.target, "config.acquisition.control.json")
        def changed():
            calls.append(1)
            if len(calls) == 2:
                atomic_write(path, b'{"changed_by_operator": true}')
        with self.assertRaises(RuntimeError):
            configure(self.target, b"c" * 64, closed_check=changed)
        self.assertEqual(read(path), b'{"changed_by_operator": true}')

    def test_existing_temporary_file_is_preserved(self):
        path = os.path.join(self.target, "existing")
        temporary = path + ".command-transport-new"
        with open(temporary, "wb") as stream:
            stream.write(b"other transaction")
        with self.assertRaises(FileExistsError):
            atomic_write(path, b"new data")
        self.assertEqual(read(temporary), b"other transaction")
