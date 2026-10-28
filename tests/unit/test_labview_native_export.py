"""Native-export boundary checks with a fake COM adapter; no LabVIEW or NI."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import labview_native_export as exporter


def write_bytes(path, data):
    with path.open("wb") as stream:
        return stream.write(data)


class FakeApplication:
    def __init__(self, source):
        self.source = source
        self.calls = []
        self.directory = exporter.APPLICATION_DIRECTORY
        self.version = "20.0f1"
        self.vi_state = {
            "path": str(source), "execution": 1,
            "vi_modifications": 0, "fp_modifications": 0,
            "bd_modifications": 0,
        }
        self.on_open = None
        self.on_export = None

    def identity(self):
        self.calls.append("identity")
        return {"directory": self.directory, "version": self.version,
                "process_id": 42}

    def open_vi(self, source):
        self.calls.append(("open", str(source)))
        if self.on_open:
            self.on_open()
        return object()

    def state(self, vi):
        self.calls.append("state")
        return dict(self.vi_state)

    def export(self, vi, destination):
        self.calls.append(("export", str(destination)))
        write_bytes(destination, b"native12-output")
        if self.on_export:
            self.on_export()
        return ""


class NativeExportBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.vi"
        self.destination = Path(self.temp.name) / "export.vi"
        write_bytes(self.source, b"audited-native20")
        self.sha = hashlib.sha256(exporter.read_bytes(self.source)).hexdigest()
        self.app = FakeApplication(self.source)
        self.source_header = dict(major=20, RunOnOpen=False)
        self.output_header = dict(major=12, RunOnOpen=False)
        self.header_patch = mock.patch.object(exporter, "vi_header", self.header)
        self.header_patch.start()
        self.addCleanup(self.header_patch.stop)

    def header(self, raw):
        if raw == b"audited-native20":
            return self.source_header
        return self.output_header

    def export(self, source=None, destination=None, sha=None):
        return exporter.export_native(
            source or self.source, destination or self.destination,
            sha or self.sha, app_factory=lambda: self.app,
        )

    def test_idle_clean_source_export_has_no_execution_or_source_save(self):
        report = self.export()
        self.assertEqual(exporter.read_bytes(self.source), b"audited-native20")
        self.assertEqual(exporter.read_bytes(self.destination), b"native12-output")
        self.assertEqual(self.app.calls, [
            "identity", ("open", str(self.source)), "state",
            ("export", str(self.destination)), "state",
        ])
        self.assertTrue(report["output_version_verified"])
        self.assertFalse(report["output_version_and_dependencies_verified"])
        for key in ("Run", "SaveInstrument", "RSRC_writer"):
            self.assertFalse(report[key])

    def test_existing_destination_is_never_overwritten_or_loaded(self):
        write_bytes(self.destination, b"keep")
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(exporter.read_bytes(self.destination), b"keep")
        self.assertEqual(self.app.calls, [])

    def test_wrong_hash_prevents_application_activation(self):
        with self.assertRaises(ValueError):
            self.export(sha="0" * 64)
        self.assertEqual(self.app.calls, [])

    def test_invalid_hash_prevents_application_activation(self):
        with self.assertRaises(ValueError):
            self.export(sha="bad")
        self.assertEqual(self.app.calls, [])

    def test_relative_path_is_rejected_before_application_activation(self):
        with self.assertRaises(ValueError):
            self.export(source="source.vi")
        self.assertEqual(self.app.calls, [])

    def test_missing_destination_parent_is_rejected(self):
        with self.assertRaises(ValueError):
            self.export(destination=Path(self.temp.name) / "missing" / "out.vi")
        self.assertEqual(self.app.calls, [])

    def test_non_vi_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            self.export(destination=Path(self.temp.name) / "out.bin")
        self.assertEqual(self.app.calls, [])

    def test_run_on_open_is_rejected_before_native_load(self):
        self.source_header["RunOnOpen"] = True
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.app.calls, [])

    def test_wrong_source_version_is_rejected_before_native_load(self):
        self.source_header["major"] = 12
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.app.calls, [])

    def test_wrong_architecture_is_rejected_before_vi_load(self):
        self.app.directory = r"C:\Program Files\National Instruments\LabVIEW 2020"
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.app.calls, ["identity"])

    def test_wrong_application_version_is_rejected_before_vi_load(self):
        self.app.version = "19.0"
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.app.calls, ["identity"])

    def test_running_vi_is_never_exported(self):
        self.app.vi_state["execution"] = 2
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.destination.exists())

    def test_each_unsaved_modification_category_is_rejected(self):
        for key in ("vi_modifications", "fp_modifications", "bd_modifications"):
            self.app.vi_state[key] = 1
            with self.assertRaises(ValueError):
                self.export()
            self.app.vi_state[key] = 0
        self.assertFalse(self.destination.exists())

    def test_wrong_native_vi_resolution_is_rejected(self):
        self.app.vi_state["path"] = str(Path(self.temp.name) / "other.vi")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.destination.exists())

    def test_source_change_during_load_prevents_export(self):
        self.app.on_open = lambda: write_bytes(self.source, b"changed")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.destination.exists())

    def test_destination_appearing_during_load_prevents_overwrite(self):
        self.app.on_open = lambda: write_bytes(self.destination, b"keep")
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(exporter.read_bytes(self.destination), b"keep")

    def test_source_change_during_export_is_reported_and_evidence_retained(self):
        self.app.on_export = lambda: write_bytes(self.source, b"changed")
        with self.assertRaises(ValueError):
            self.export()
        self.assertTrue(self.destination.exists())

    def test_modified_native_state_after_export_is_rejected(self):
        self.app.on_export = lambda: self.app.vi_state.update(bd_modifications=1)
        with self.assertRaises(ValueError):
            self.export()
        self.assertTrue(self.destination.exists())

    def test_wrong_output_version_is_rejected_without_deleting_evidence(self):
        self.output_header["major"] = 20
        with self.assertRaises(ValueError):
            self.export()
        self.assertTrue(self.destination.exists())

    def test_run_on_open_output_is_rejected_without_deleting_evidence(self):
        self.output_header["RunOnOpen"] = True
        with self.assertRaises(ValueError):
            self.export()
        self.assertTrue(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
