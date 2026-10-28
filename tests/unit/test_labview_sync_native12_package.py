"""Native export provenance and path regression; no LabVIEW/NI execution."""

import hashlib
import json
import os
import shutil
import struct
import tempfile
import unittest

from tools.verify_labview_sync_native12_package import (
    rsrc_sections,
    verify_package,
    vi_header,
)

ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "legacy",
        "labview",
        "supervision_telemetry",
        "individual_helpers",
    )
)


class Native12PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.copy = os.path.join(self.temp.name, "packet")
        shutil.copytree(ROOT, self.copy)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        with open(
            os.path.join(self.copy, "package_manifest.json"), encoding="utf-8"
        ) as f:
            return json.load(f)

    def store(self, value):
        with open(
            os.path.join(self.copy, "package_manifest.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(value, f)

    def mutate_header(self, offset, value):
        manifest = self.manifest()
        row = next(r for r in manifest["files"] if r["path"].endswith("SUP_SyncTap.vi"))
        path = os.path.join(self.copy, *row["path"].split("/"))
        with open(path, "rb") as f:
            raw = f.read()
        lvsr = rsrc_sections(raw)[(b"LVSR", 0)]
        updated = lvsr[:offset] + struct.pack(">I", value) + lvsr[offset + 4 :]
        raw = raw.replace(lvsr, updated, 1)
        with open(path, "wb") as f:
            f.write(raw)
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        self.store(manifest)
        return raw

    def test_committed_native12_packet_and_file_based_project_urls(self):
        result = verify_package(self.copy)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["native12_VIs"]), 3)
        self.assertFalse(result["executed"])

    def test_native_header_version_checked_independently_of_hash_pin(self):
        raw = self.mutate_header(0, 0x20008000)
        self.assertEqual(vi_header(raw)["major"], 20)
        with self.assertRaises(ValueError):
            verify_package(self.copy)

    def test_run_on_open_rejected_independently_of_hash_pin(self):
        self.mutate_header(4, 1 << 14)
        with self.assertRaises(ValueError):
            verify_package(self.copy)

    def test_wrong_project_directory_base_regression_is_rejected(self):
        manifest = self.manifest()
        project = os.path.join(self.copy, *manifest["project"].split("/"))
        with open(project, "rb") as f:
            raw = f.read().replace(b"../../sync_lifecycle/", b"../sync_lifecycle/")
        with open(project, "wb") as f:
            f.write(raw)
        row = next(r for r in manifest["files"] if r["path"] == manifest["project"])
        row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.store(manifest)
        with self.assertRaises(ValueError):
            verify_package(self.copy)

    def test_missing_queue_or_extra_unlisted_vi_fails_closed(self):
        manifest = self.manifest()
        queue = next(
            r for r in manifest["files"] if r["path"].endswith("Queue_Latest.vi")
        )
        source = os.path.join(self.copy, *queue["path"].split("/"))
        shutil.copy2(source, os.path.join(self.copy, "unlisted.vi"))
        with self.assertRaises(ValueError):
            verify_package(self.copy)
        os.remove(source)
        with self.assertRaises((ValueError, IOError)):
            verify_package(self.copy)

    def test_truncated_or_bad_resource_offsets_rejected(self):
        row = next(r for r in self.manifest()["files"] if r["path"].endswith(".vi"))
        path = os.path.join(self.copy, *row["path"].split("/"))
        with open(path, "rb") as stream:
            native = stream.read()
        bad_info = bytearray(native)
        bad_info[16:20] = struct.pack(">I", len(native) + 4096)
        bad_data = bytearray(native)
        bad_data[24:28] = struct.pack(">I", len(native) + 4096)
        for raw in (b"RSRC", b"x" * 64, bytes(bad_info), bytes(bad_data)):
            with self.assertRaises(ValueError):
                vi_header(raw)


if __name__ == "__main__":
    unittest.main()
