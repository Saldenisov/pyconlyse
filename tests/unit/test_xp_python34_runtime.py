"""Portable runtime selection/install tests in temporary directories only.

Python 3.4 compatible. Synthetic bytes are copied but never executed. No real
Python target, NI driver, network endpoint, registry or PATH is modified.
"""
import hashlib
import importlib.machinery
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile

from tools import stage_xp_python34_runtime as staging


INSTALLER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "tools", "install_xp_python34_runtime.pyw")
installer = importlib.machinery.SourceFileLoader("_portable_runtime_test_installer", INSTALLER).load_module()


def write(path, value):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "wb") as stream:
        stream.write(value)


def write_manifest(folder, value):
    value["manifest_id"] = installer.manifest_identity(value)
    with io.open(os.path.join(folder, "runtime_manifest.json"), "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def fixture(folder, archive=False):
    os.mkdir(folder)
    runtime = os.path.join(folder, "runtime")
    os.mkdir(runtime)
    rows = []
    for name in sorted(installer.CORE_FILES):
        content = ("private synthetic fixture " + name).encode("ascii")
        write(os.path.join(runtime, *name.split("/")), content)
        rows.append(dict(path=name, sha256=hashlib.sha256(content).hexdigest(), bytes=len(content)))
    value = dict(schema_version=1, role=installer.ROLE,
        python=dict(version="3.4.4", bits=32, implementation="CPython"),
        packages=dict(staging.PINS), files=rows, auto_initialize=False,
        changes_system_configuration=False)
    if archive:
        path = os.path.join(folder, "runtime.zip")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as stream:
            for row in rows:
                stream.write(os.path.join(runtime, *row["path"].split("/")), row["path"])
        value["archive"] = dict(path="runtime.zip", sha256=installer.digest(path))
    write_manifest(folder, value)
    return value


class PortableRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="elyse-portable-runtime-test-")
        self.package = os.path.join(self.folder, "package")
        self.target = os.path.join(self.folder, "installed")

    def tearDown(self):
        # This test's own random temporary root only, never the real C target.
        shutil.rmtree(self.folder)

    def test_install_new_runtime_and_verify_exact_idempotence(self):
        manifest = fixture(self.package)
        first = installer.install(self.package, self.target)
        self.assertEqual(first["result"], "INSTALLED")
        self.assertFalse(first["hardware_commands_sent"])
        self.assertFalse(first["system_configuration_changed"])
        self.assertTrue(installer.verify_files(self.target, manifest, installed=True))
        second = installer.install(self.package, self.target)
        self.assertEqual(second["result"], "ALREADY_INSTALLED")
        self.assertEqual(first["manifest_id"], second["manifest_id"])
        self.assertFalse(any(".installing-" in name for name in os.listdir(self.folder)))

    def test_existing_unrelated_target_is_never_overwritten(self):
        fixture(self.package)
        os.mkdir(self.target)
        sentinel = os.path.join(self.target, "colleague_runtime.txt")
        write(sentinel, b"preserve unrelated bytes")
        self.assertRaises(RuntimeError, installer.install, self.package, self.target)
        with open(sentinel, "rb") as stream:
            self.assertEqual(stream.read(), b"preserve unrelated bytes")

    def test_existing_matched_target_with_tampering_is_not_repaired_implicitly(self):
        fixture(self.package)
        installer.install(self.package, self.target)
        changed = os.path.join(self.target, "python.exe")
        write(changed, b"changed by another process")
        self.assertRaises(ValueError, installer.install, self.package, self.target)
        with open(changed, "rb") as stream:
            self.assertEqual(stream.read(), b"changed by another process")

    def test_copy_failure_removes_only_own_temporary_tree(self):
        fixture(self.package)
        sibling = os.path.join(self.folder, "other_work")
        os.mkdir(sibling)
        sentinel = os.path.join(sibling, "keep.bin")
        write(sentinel, b"unchanged")
        count = [0]
        def fail_copy(source, destination):
            count[0] += 1
            if count[0] == 3:
                raise IOError("injected copy failure")
            return shutil.copy2(source, destination)
        self.assertRaises(IOError, installer.install, self.package, self.target, fail_copy)
        self.assertFalse(os.path.exists(self.target))
        self.assertEqual(sorted(os.listdir(self.folder)), ["other_work", "package"])
        with open(sentinel, "rb") as stream:
            self.assertEqual(stream.read(), b"unchanged")

    def test_traversal_and_windows_device_paths_rejected_before_copy(self):
        manifest = fixture(self.package)
        for path in ("../escape.txt", "/absolute", "C:/Windows/x", "Lib/CON.txt", "Lib/aux", "Lib/x. ", "Lib\\x"):
            candidate = dict(manifest)
            candidate["files"] = list(manifest["files"]) + [dict(path=path, sha256="0" * 64, bytes=0)]
            write_manifest(self.package, candidate)
            self.assertRaises(ValueError, installer.install, self.package, self.target)
            self.assertFalse(os.path.exists(self.target))

    def test_archive_install_and_unexpected_member_refusal(self):
        manifest = fixture(self.package, archive=True)
        installer.install(self.package, self.target)
        self.assertTrue(installer.verify_files(self.target, manifest, installed=True))
        other_target = os.path.join(self.folder, "other_target")
        archive = os.path.join(self.package, "runtime.zip")
        with zipfile.ZipFile(archive, "a") as stream:
            stream.writestr("unexpected.bin", b"not in manifest")
        manifest["archive"]["sha256"] = installer.digest(archive)
        write_manifest(self.package, manifest)
        self.assertRaises(ValueError, installer.install, self.package, other_target)
        self.assertFalse(os.path.exists(other_target))

    def test_result_is_written_back_without_starting_any_program(self):
        fixture(self.package)
        result = installer.install_and_record(self.package, self.target)
        self.assertEqual(result["result"], "INSTALLED")
        with io.open(os.path.join(self.package, "python34_installation_result.json"), encoding="utf-8") as stream:
            record = json.load(stream)
        self.assertEqual(record["role"], installer.RESULT_ROLE)
        self.assertFalse(record["hardware_commands_sent"])
        self.assertFalse(record["system_configuration_changed"])

    def test_selection_excludes_caches_tests_packagers_and_private_material(self):
        source = os.path.join(self.folder, "reviewed_source")
        for name in ("os.py", "typing.py", "tests/test_x.py", "__pycache__/os.pyc",
                     "secret.key", "certificate.pem", "install.msi", "lib.pdb", "wininst-amd64.exe",
                     "site-packages/pip/__init__.py", "nested/keep.py"):
            write(os.path.join(source, *name.split("/")), b"fixture")
        selected = staging.selected_tree(source, "Lib", skip_roots=("site-packages",))
        self.assertEqual([target for source, target in selected], ["Lib/os.py", "Lib/typing.py", "Lib/nested/keep.py"])

    def test_pe_architecture_is_read_without_loading_binary(self):
        path = os.path.join(self.folder, "synthetic.dll")
        raw = bytearray(70)
        raw[0:2], raw[0x3c:0x40], raw[0x40:0x44] = b"MZ", struct.pack("<I", 64), b"PE\0\0"
        raw[0x44:0x46] = struct.pack("<H", 0x14c)
        write(path, bytes(raw))
        self.assertEqual(staging.pe_machine(path), 0x14c)
        raw[0x44:0x46] = struct.pack("<H", 0x8664)
        write(path, bytes(raw))
        self.assertEqual(staging.pe_machine(path), 0x8664)

    def test_timeout_terminates_only_the_owned_probe_object(self):
        class PrivateProbe(object):
            pid, returncode = 123, None
            def __init__(self):
                self.calls = self.kills = 0
            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired("private probe", timeout)
                return b"", b""
            def kill(self):
                self.kills += 1
        probe = PrivateProbe()
        calls = []
        def create(arguments, **keywords):
            calls.append((arguments, keywords))
            return probe
        self.assertRaises(RuntimeError, staging.probe_runtime, self.folder, .05, create)
        self.assertEqual(probe.kills, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][0], os.path.join(self.folder, "python.exe"))
        self.assertEqual(calls[0][0][1:4], ["-E", "-s", "-B"])


if __name__ == "__main__":
    unittest.main()
