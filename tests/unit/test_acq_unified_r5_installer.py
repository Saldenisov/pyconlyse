"""Cold r5 installer tests: temp files, mocked socket/startup, no live OS probes."""
import hashlib
import importlib.machinery
import json
import os
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
installer = importlib.machinery.SourceFileLoader("unified_r5_installer_fixture",
    os.path.join(ROOT, "tools", "install_acq_unified_r5.pyw")).load_module()


class UnifiedR5InstallerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.target = os.path.join(self.folder.name, "installed")
        self.incoming = os.path.join(self.folder.name, "incoming")
        self.legacy = os.path.join(self.folder.name, "old_bridge", "shared_state_receiver.pyw")
        self.startup = os.path.join(self.folder.name, "startup")
        os.makedirs(self.startup)
        self.plan = dict(files={})
        for relative in installer.FILES:
            old = None
            if relative != "elyse_agent/handover_recovery.py":
                self.write(self.target, relative, b'VALUE = "old"\n')
                old = self.sha(self.target, relative)
            self.write(self.incoming, relative, b'VALUE = "new"\n')
            self.plan["files"][relative] = dict(old=old, new=self.sha(self.incoming, relative))
        self.write(self.target, "manifest.json", b'{"release":"old"}')
        self.write(self.incoming, "manifest.json", b'{"release":"new"}')
        self.plan.update(old_manifest_sha256=self.sha(self.target, "manifest.json"),
                         new_manifest_sha256=self.sha(self.incoming, "manifest.json"))
        self.protected = ("config.acquisition.control.json.ownership", "config.acquisition.control.json",
                          "secret.key", "runtime/cooling-alarms.sqlite3")
        for relative in self.protected:
            self.write(self.target, relative, b"PROTECTED BYTES MUST STAY")
        self.save_plan()
        self.closed = mock.patch.object(installer, "require_server_closed")
        self.closed_mock = self.closed.start()
        self.legacy_patch = mock.patch.object(installer, "LEGACY_ENTRYPOINT", self.legacy)
        self.legacy_patch.start()
        self.startup_patch = mock.patch.object(installer, "_load_startup_module",
            side_effect=AssertionError("Unmocked Startup use forbidden in cold test"))
        self.startup_mock = self.startup_patch.start()

    def tearDown(self):
        self.startup_patch.stop()
        self.legacy_patch.stop()
        self.closed.stop()
        self.folder.cleanup()

    @staticmethod
    def write(root, relative, data):
        path = os.path.join(root, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as stream:
            stream.write(data)

    @staticmethod
    def sha(root, relative):
        with open(os.path.join(root, *relative.split("/")), "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()

    def save_plan(self):
        with open(os.path.join(self.incoming, installer.PLAN), "w") as stream:
            json.dump(self.plan, stream)

    def install(self, **kwargs):
        kwargs.setdefault("migrate_startup", False)
        return installer.install(self.incoming, self.target, **kwargs)

    def assert_unchanged(self):
        for relative in installer.FILES:
            expected = self.plan["files"][relative]["old"]
            path = os.path.join(self.target, *relative.split("/"))
            if expected is None:
                self.assertFalse(os.path.exists(path))
            else:
                self.assertEqual(installer.sha(path), expected)

    def fake_startup(self):
        fake = mock.Mock()
        fake.FILENAME = installer.STARTUP_FILENAME
        fake.MARKER = installer.STARTUP_MARKER.decode("utf-8")
        fake.startup_directory.side_effect = AssertionError("Real Startup metadata forbidden")
        self.startup_mock.side_effect = None
        self.startup_mock.return_value = fake
        return fake

    def test_nine_modules_and_manifest_backed_up_protected_bytes_unchanged(self):
        protected = {name: self.sha(self.target, name) for name in self.protected}
        report = self.install()
        for relative in installer.FILES:
            self.assertEqual(self.sha(self.target, relative), self.plan["files"][relative]["new"])
            old = self.plan["files"][relative]["old"]
            if old is not None:
                self.assertEqual(self.sha(report["backup"], relative), old)
            else:
                self.assertFalse(os.path.exists(os.path.join(report["backup"], *relative.split("/"))))
        self.assertEqual(self.sha(report["backup"], "manifest.json"), self.plan["old_manifest_sha256"])
        for relative, digest in protected.items():
            self.assertEqual(self.sha(self.target, relative), digest)
        self.assertEqual(report["legacy_retirement"]["status"], "absent")
        self.assertEqual(report["startup_migration"]["status"], "not_requested")
        self.assertEqual(self.closed_mock.call_count, 2)
        self.assertFalse(self.startup_mock.called)

    def test_new_source_must_not_already_exist(self):
        relative = "elyse_agent/handover_recovery.py"
        self.write(self.target, relative, b"USER_SOURCE = True\n")
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(installer._read_bytes(os.path.join(self.target, *relative.split("/"))),
                         b"USER_SOURCE = True\n")
        self.assertEqual(self.sha(self.target, installer.FILES[0]),
                         self.plan["files"][installer.FILES[0]]["old"])

    def test_unexpected_scope_and_hash_mismatch_refuse_before_mutation(self):
        self.plan["files"]["config.acquisition.control.json"] = dict(old=None, new="a" * 64)
        self.save_plan()
        with self.assertRaises(RuntimeError):
            self.install()
        del self.plan["files"]["config.acquisition.control.json"]
        self.plan["files"][installer.FILES[0]]["new"] = "a" * 64
        self.save_plan()
        with self.assertRaises(RuntimeError):
            self.install()
        self.assert_unchanged()

    def test_invalid_syntax_or_manifest_refuses_before_mutation(self):
        relative = installer.FILES[0]
        self.write(self.incoming, relative, b"if bad syntax\n")
        self.plan["files"][relative]["new"] = self.sha(self.incoming, relative)
        self.save_plan()
        with self.assertRaises(SyntaxError):
            self.install()
        self.assert_unchanged()
        self.write(self.incoming, relative, b'VALUE = "new"\n')
        self.plan["files"][relative]["new"] = self.sha(self.incoming, relative)
        self.write(self.incoming, "manifest.json", b"not JSON")
        self.plan["new_manifest_sha256"] = self.sha(self.incoming, "manifest.json")
        self.save_plan()
        with self.assertRaises(ValueError):
            self.install()
        self.assert_unchanged()

    def test_changed_marker_refuses_without_clearing_prior_evidence(self):
        with mock.patch.object(installer, "marker_image", side_effect=(b"old", b"changed")):
            with self.assertRaises(RuntimeError):
                self.install()
        self.assert_unchanged()
        self.assertEqual(installer._read_bytes(os.path.join(self.target, self.protected[0])),
                         b"PROTECTED BYTES MUST STAY")

    def test_busy_port_refuses_before_creating_backup_or_loading_startup(self):
        self.closed_mock.side_effect = RuntimeError("server still listening")
        with self.assertRaises(RuntimeError):
            self.install()
        self.assert_unchanged()
        self.assertFalse(self.startup_mock.called)

    def test_verified_legacy_entrypoint_is_renamed_only_and_key_folder_remains(self):
        self.write(os.path.dirname(self.legacy), os.path.basename(self.legacy), b"old bridge source")
        self.write(os.path.dirname(self.legacy), "read.key", b"DO NOT TOUCH")
        with mock.patch.object(installer, "LEGACY_SHA256", installer.sha(self.legacy)):
            report = self.install()
        retired = report["legacy_retirement"]
        self.assertEqual(retired["status"], "retired")
        self.assertFalse(os.path.exists(self.legacy))
        self.assertEqual(installer._read_bytes(retired["backup"]), b"old bridge source")
        self.assertEqual(installer._read_bytes(os.path.join(os.path.dirname(self.legacy), "read.key")),
                         b"DO NOT TOUCH")

    def test_legacy_hash_mismatch_warns_without_blocking_source_update(self):
        self.write(os.path.dirname(self.legacy), os.path.basename(self.legacy), b"unknown local bridge")
        report = self.install()
        self.assertEqual(report["legacy_retirement"]["status"], "skipped_hash_mismatch")
        self.assertTrue(report["legacy_retirement"]["warning"])
        self.assertEqual(installer._read_bytes(self.legacy), b"unknown local bridge")
        self.assertEqual(self.sha(self.target, installer.FILES[0]),
                         self.plan["files"][installer.FILES[0]]["new"])

    def test_startup_absent_is_not_created(self):
        fake = self.fake_startup()
        report = self.install(migrate_startup=True, startup_folder=self.startup)
        self.assertEqual(report["startup_migration"]["status"], "absent")
        self.assertFalse(fake.install_startup.called)
        self.assertEqual(os.listdir(self.startup), [])

    def test_unmarked_startup_is_never_overwritten(self):
        fake = self.fake_startup()
        self.write(self.startup, installer.STARTUP_FILENAME, b"UNRELATED FILE")
        report = self.install(migrate_startup=True, startup_folder=self.startup)
        self.assertEqual(report["startup_migration"]["status"], "skipped_unmanaged")
        self.assertFalse(fake.install_startup.called)
        self.assertEqual(installer._read_bytes(os.path.join(self.startup, installer.STARTUP_FILENAME)),
                         b"UNRELATED FILE")

    def test_marked_startup_migration_requires_exact_byte_backup(self):
        fake = self.fake_startup()
        original = installer.STARTUP_MARKER + b"\r\n# previous launcher bytes\r\n"
        self.write(self.startup, installer.STARTUP_FILENAME, original)

        def migrate(entrypoint, config_path, folder=None):
            self.assertEqual(entrypoint, os.path.join(self.target, "acquisition_control_server.pyw"))
            self.assertEqual(config_path, os.path.join(self.target, "config.acquisition.control.json"))
            self.write(folder, installer.STARTUP_FILENAME + ".backup_fixture", original)
            self.write(folder, installer.STARTUP_FILENAME, installer.STARTUP_MARKER + b"\n# unified\n")
            return os.path.join(folder, installer.STARTUP_FILENAME)

        fake.install_startup.side_effect = migrate
        report = self.install(migrate_startup=True, startup_folder=self.startup)
        self.assertEqual(report["startup_migration"]["status"], "migrated")
        self.assertEqual(len(report["startup_migration"]["backups"]), 1)
        self.assertEqual(installer._read_bytes(report["startup_migration"]["backups"][0]), original)


if __name__ == "__main__":
    unittest.main()
