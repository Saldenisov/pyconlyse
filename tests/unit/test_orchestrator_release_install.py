"""Cold source installation tests: temporary synthetic bytes, no execution."""
import hashlib
import importlib.machinery
import json
import os
import shutil
import sys
import tempfile
import types
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
installer = importlib.machinery.SourceFileLoader("_orchestrator_release_installer",
    os.path.join(ROOT, "tools", "install_orchestrator_release.pyw")).load_module()


def write(path, data):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "wb") as stream:
        stream.write(data)


def json_file(path, value):
    write(path, json.dumps(value, sort_keys=True, indent=2).encode("utf-8"))
    return installer.digest(path)


def rows(folder, names):
    return [dict(path=name, sha256=installer.digest(os.path.join(folder, *name.split("/"))))
            for name in sorted(names)]


def source_fixture(folder):
    os.mkdir(folder)
    names = set(installer.ENTRYPOINTS.values()) | installer.DEFAULT_CONFIGS | {"elyse_agent/__init__.py"}
    for name in names:
        write(os.path.join(folder, *name.split("/")), ("synthetic source " + name).encode("ascii"))
    manifest = dict(schema_version=1, role="xp_python34", release=installer.RELEASE,
        named_operation_count=25, standard_bank_count=27, auto_initialize=False,
        hardware_activated=False, commands_default_enabled=False, federation_default_enabled=False,
        files=rows(folder, names))
    return json_file(os.path.join(folder, "manifest.json"), manifest)


def runtime_fixture(folder):
    os.mkdir(folder)
    write(os.path.join(folder, "pythonw.exe"), b"synthetic executable is never executed")
    value = dict(role="elyse_python34_x86_portable",
        python=dict(version="3.4.4", bits=32, implementation="CPython"),
        packages=dict(numpy="1.15.4", nidaqmx="0.5.7", six="1.16.0"),
        files=[dict(path="pythonw.exe", sha256=installer.digest(os.path.join(folder, "pythonw.exe")), bytes=37)])
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    value["manifest_id"] = hashlib.sha256(raw).hexdigest()
    json_file(os.path.join(folder, "portable_runtime_manifest.json"), value)


def site_fixture(folder, role, shortcut=False):
    os.mkdir(folder)
    read_key, command_key = "read.key", "command.key"
    if role == "acquisition":
        base = dict(bind_host="10.20.30.10", port=8772, key_file=read_key,
                    period_seconds=.2, read_timeout_seconds=.5, native_isolation_mode="per_card")
        control = dict(remote_control_enabled=False, command_key_file=command_key,
            cooling_safety=dict(polarity_verified=False, journal_file="runtime/cooling.sqlite3"),
            telemetry=dict(enabled=True, wire_mode="legacy_27", host="10.20.30.202", port=8767, period_seconds=.2))
        config = {"config.acquisition.json": base, "config.acquisition.control.json": control}
    else:
        config = {"config.supervision.control.json": dict(schema_version=1, bind_host="10.20.30.2", port=8772,
            read_key_file=read_key, command_key_file=command_key, remote_control_enabled=False,
            counter_timing_controls_verified=False, period_seconds=.2, read_timeout_seconds=.5,
            video=dict(channel=2, white_ref_volt=.9, black_ref_volt=.1),
            telemetry=dict(enabled=False, wire="federated_owner", host="10.20.30.202", port=8767, period_seconds=.2))}
    names = set(config) | {read_key, command_key}
    for name, value in config.items():
        json_file(os.path.join(folder, name), value)
    write(os.path.join(folder, read_key), b"r" * 32)
    write(os.path.join(folder, command_key), b"c" * 32)
    if shortcut:
        names.add("START.lnk")
        write(os.path.join(folder, "START.lnk"), b"opaque pinned shortcut fixture; never opened")
    return refresh_site(folder, role, names)


def refresh_site(folder, role, names=None):
    if names is None:
        names = installer._closure(folder, ignored=("site_manifest.json",))
    value = dict(schema_version=1, role=role, release=installer.RELEASE, files=rows(folder, names))
    return json_file(os.path.join(folder, "site_manifest.json"), value)


class OrchestratorReleaseInstallTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="elyse-cold-release-test-")
        self.package, self.site, self.runtime, self.target = [os.path.join(self.root, name)
            for name in ("package", "site", "portable runtime", "new source target")]
        self.source_pin = source_fixture(self.package)
        runtime_fixture(self.runtime)
        self.role = "acquisition"
        self.site_pin = site_fixture(self.site, self.role)
        self.old = os.path.join(self.root, "ACQ_Python_Control_20261022_v8", "preserve.txt")
        write(self.old, b"old working installation stays intact")

    def tearDown(self):
        # Only the random temporary root created by this test. No actual XP path.
        shutil.rmtree(self.root)

    def install(self, **overrides):
        options = dict(target=self.target, runtime=self.runtime)
        options.update(overrides)
        return installer.install(self.package, self.site, self.role,
            self.source_pin, self.site_pin, **options)

    def assert_old(self):
        with open(self.old, "rb") as stream:
            self.assertEqual(stream.read(), b"old working installation stays intact")

    def test_new_transaction_and_exact_idempotence_preserve_old_tree(self):
        self.assertEqual(self.install()["result"], "INSTALLED")
        self.assertEqual(self.install()["result"], "ALREADY_INSTALLED")
        for name in installer.DEFAULT_CONFIGS:
            self.assertTrue(os.path.isfile(os.path.join(self.target, "package_defaults", name)))
        with open(os.path.join(self.target, "START.cmd"), "rb") as stream:
            launcher = stream.read().decode("utf-8")
        self.assertIn('"' + os.path.join(self.runtime, "pythonw.exe") + '" -B ', launcher)
        self.assertIn("--config", launcher)
        self.assertNotIn("initialize", launcher.lower())
        self.assertEqual(installer.digest(os.path.join(self.target, installer.SOURCE_MANIFEST)), self.source_pin)
        self.assertEqual(installer.digest(os.path.join(self.target, "site_manifest.json")), self.site_pin)
        self.assert_old()

    def test_supervision_cold_role_and_pinned_shortcut(self):
        shutil.rmtree(self.site)
        self.role = "supervision"
        self.site_pin = site_fixture(self.site, self.role, shortcut=True)
        result = self.install()
        self.assertEqual(result["role"], "supervision")
        self.assertFalse(result["processes_started"])
        self.assertTrue(os.path.isfile(os.path.join(self.target, "START.lnk")))
        config = installer._read_json(os.path.join(self.target, "config.supervision.control.json"))
        self.assertFalse(config["telemetry"]["enabled"])
        self.assertFalse(config["remote_control_enabled"])
        self.assert_old()

    def test_source_or_site_pins_and_changed_payload_refuse_before_target(self):
        pin = self.source_pin
        self.source_pin = "0" * 64
        self.assertRaises(ValueError, self.install)
        self.source_pin = pin
        site_pin = self.site_pin
        self.site_pin = "1" * 64
        self.assertRaises(ValueError, self.install)
        self.site_pin = site_pin
        write(os.path.join(self.package, installer.ENTRYPOINTS["acquisition"]), b"changed source")
        self.assertRaises(ValueError, self.install)
        self.assertFalse(os.path.exists(self.target))
        self.assert_old()

    def test_unknown_target_or_modified_matched_target_never_repaired(self):
        os.mkdir(self.target)
        sentinel = os.path.join(self.target, "unknown.bin")
        write(sentinel, b"preserved")
        self.assertRaises(RuntimeError, self.install)
        with open(sentinel, "rb") as stream:
            self.assertEqual(stream.read(), b"preserved")
        shutil.rmtree(self.target)
        self.install()
        write(os.path.join(self.target, "read.key"), b"changed after installation")
        self.assertRaises(ValueError, self.install)
        with open(os.path.join(self.target, "read.key"), "rb") as stream:
            self.assertEqual(stream.read(), b"changed after installation")
        self.assert_old()

    def test_copy_failure_cleans_only_own_temporary_tree(self):
        count = [0]
        def fail(source, destination):
            count[0] += 1
            if count[0] == 3:
                raise IOError("injected file copy failure")
            return shutil.copy2(source, destination)
        self.assertRaises(IOError, self.install, copy_file=fail)
        self.assertFalse(os.path.exists(self.target))
        self.assertFalse(any(".installing-" in name for name in os.listdir(self.root)))
        self.assert_old()

    def test_copy_race_hash_mismatch_and_rename_race_preserve_competitor(self):
        def corrupt(source, destination):
            write(destination, b"changed while copying")
        self.assertRaises(ValueError, self.install, copy_file=corrupt)
        def competitor(source, target):
            os.mkdir(target)
            write(os.path.join(target, "another_installer.txt"), b"do not remove")
            raise OSError("target appeared at final rename")
        self.assertRaises(OSError, self.install, rename_directory=competitor)
        with open(os.path.join(self.target, "another_installer.txt"), "rb") as stream:
            self.assertEqual(stream.read(), b"do not remove")
        self.assertFalse(any(".installing-" in name for name in os.listdir(self.root)))
        self.assert_old()

    def test_unsafe_paths_and_duplicate_windows_case_refuse(self):
        for name in ("../escape", "C:/Windows/escape", "x/CON.txt", "x\\bad", "x/../bad", "x/ends."):
            self.assertRaises(ValueError, installer._name, name)
        manifest = installer._read_json(os.path.join(self.package, "manifest.json"))
        manifest["files"].append(dict(path="ELyse_agent/__init__.py", sha256="0" * 64))
        self.source_pin = json_file(os.path.join(self.package, "manifest.json"), manifest)
        self.assertRaises(ValueError, self.install)
        self.assertFalse(os.path.exists(self.target))

    def test_role_configuration_does_not_activate_federation_or_remote_sup(self):
        path = os.path.join(self.site, "config.acquisition.control.json")
        config = installer._read_json(path)
        config["telemetry"]["wire_mode"] = "federated_owner"
        json_file(path, config)
        self.site_pin = refresh_site(self.site, self.role)
        self.assertRaises(ValueError, self.install)
        shutil.rmtree(self.site)
        self.role = "supervision"
        self.site_pin = site_fixture(self.site, self.role)
        path = os.path.join(self.site, "config.supervision.control.json")
        config = installer._read_json(path)
        config["remote_control_enabled"] = True
        json_file(path, config)
        self.site_pin = refresh_site(self.site, self.role)
        self.assertRaises(ValueError, self.install)
        self.assertFalse(os.path.exists(self.target))

    def test_same_key_unlisted_file_and_changed_runtime_refuse(self):
        write(os.path.join(self.site, "command.key"), b"r" * 32)
        self.site_pin = refresh_site(self.site, self.role)
        self.assertRaises(ValueError, self.install)
        write(os.path.join(self.site, "command.key"), b"c" * 32)
        self.site_pin = refresh_site(self.site, self.role)
        write(os.path.join(self.site, "unlisted.key"), b"other data")
        self.assertRaises(ValueError, self.install)
        os.remove(os.path.join(self.site, "unlisted.key"))
        write(os.path.join(self.runtime, "pythonw.exe"), b"changed runtime executable")
        self.assertRaises(ValueError, self.install)
        self.assertFalse(os.path.exists(self.target))
        self.assert_old()

    def test_separate_role_result_is_idempotent_and_unrelated_result_is_preserved(self):
        result = self.install()
        path = installer._record_result(self.site, self.role, result)
        self.assertEqual(installer._read_json(path)["kind"], installer.RESULT_KIND)
        self.assertEqual(self.install()["result"], "ALREADY_INSTALLED")
        write(path, b'{"role":"another_application","must_keep":true}')
        self.assertRaises(RuntimeError, installer._record_result, self.site, self.role, result)
        self.assertRaises(ValueError, self.install)
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(), b'{"role":"another_application","must_keep":true}')

    def test_gui_mode_records_visible_success_and_failure_without_real_tk_or_process(self):
        notices, destroyed = [], []
        class Root(object):
            def withdraw(self):
                pass
            def destroy(self):
                destroyed.append(True)
        tk = types.ModuleType("tkinter")
        tk.Tk = Root
        messagebox = types.ModuleType("tkinter.messagebox")
        messagebox.showinfo = lambda title, value, **kw: notices.append(("info", title, value))
        messagebox.showerror = lambda title, value, **kw: notices.append(("error", title, value))
        tk.messagebox = messagebox
        modules = {name: sys.modules.get(name) for name in ("tkinter", "tkinter.messagebox")}
        original_install = installer.install
        def private_install(package, site, role, source_pin, site_pin):
            return original_install(package, site, role, source_pin, site_pin,
                                    target=self.target, runtime=self.runtime)
        try:
            sys.modules.update({"tkinter": tk, "tkinter.messagebox": messagebox})
            installer.install = private_install
            arguments = ["--package", self.package, "--site", self.site, "--role", self.role,
                "--manifest-sha256", self.source_pin, "--site-manifest-sha256", self.site_pin, "--gui"]
            self.assertEqual(installer.main(arguments), 0)
            self.assertEqual(notices[-1][0], "info")
            arguments[arguments.index(self.source_pin)] = "0" * 64
            self.assertEqual(installer.main(arguments), 1)
            self.assertEqual(notices[-1][0], "error")
            value = installer._read_json(os.path.join(self.site, "installation_result.acquisition.json"))
            self.assertEqual(value["result"], "FAILED")
            self.assertFalse(value["hardware_commands_sent"])
            self.assertNotIn("read_key", value)
            self.assertEqual(len(destroyed), 2)
        finally:
            installer.install = original_install
            for name, old in modules.items():
                if old is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old
        self.assert_old()


if __name__ == "__main__":
    unittest.main()
