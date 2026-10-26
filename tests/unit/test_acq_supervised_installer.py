"""Operator test permission remains distinct from site qualification facts."""
import json
import os
import tempfile
import unittest

from tools.configure_acq_command_transport import read, atomic_write
from tools.configure_acq_supervised_test import configure
from legacy.xp_acq_control.elyse_agent.acquisition_gui import load_configuration


class SupervisedInstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.target = self.directory.name
        self.config = dict(bind_host="127.0.0.1", port=8772, key_file="read.key", period_seconds=.2,
            read_timeout_seconds=.5, control_profile="extended_ht_stop", stage_controls_verified=False,
            ht_controls_verified=False, focal_controls_verified=False,
            ht_shutdown=dict(feedback_verified=False, zero_tolerance_kv=0., timeout_seconds=10),
            focal_stop=dict(resources_verified=False))
        atomic_write(os.path.join(self.target, "config.acquisition.json"), json.dumps(self.config).encode())
        atomic_write(os.path.join(self.target, "manifest.json"), json.dumps(dict(files=[
            dict(path="config.acquisition.json", sha256="old")])).encode())
        atomic_write(os.path.join(self.target, "read.key"), b"r" * 64)

    def tearDown(self):
        self.directory.cleanup()

    def test_permission_enabled_without_changing_any_qualification_fact(self):
        result = configure(self.target, closed_check=lambda: None)
        current, unused = load_configuration(os.path.join(self.target, "config.acquisition.json"))
        self.assertTrue(current.pop("operator_supervised_test"))
        self.assertEqual(current, self.config)
        self.assertFalse(result["physical_qualification_changed"])
        self.assertFalse(result["hardware_commands_sent"])

    def test_failed_manifest_write_restores_previous_configuration(self):
        paths = [os.path.join(self.target, name) for name in ("config.acquisition.json", "manifest.json")]
        before = [read(path) for path in paths]
        def failed(path, data):
            if path.endswith("manifest.json"):
                raise OSError("fixture manifest write failure")
            atomic_write(path, data)
        with self.assertRaises(OSError):
            configure(self.target, closed_check=lambda: None, write=failed)
        self.assertEqual([read(path) for path in paths], before)

    def test_live_listener_is_refused(self):
        def live():
            raise RuntimeError("listener active")
        with self.assertRaises(RuntimeError):
            configure(self.target, closed_check=live)
        current = json.loads(read(os.path.join(self.target, "config.acquisition.json")).decode())
        self.assertNotIn("operator_supervised_test", current)

    def test_non_boolean_mode_configuration_is_refused(self):
        self.config["operator_supervised_test"] = "true"
        atomic_write(os.path.join(self.target, "config.acquisition.json"), json.dumps(self.config).encode())
        with self.assertRaises(ValueError):
            load_configuration(os.path.join(self.target, "config.acquisition.json"))
