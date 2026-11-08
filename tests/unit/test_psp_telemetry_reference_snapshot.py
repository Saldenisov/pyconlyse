"""Safety boundaries of offline PSP evidence capture; no lvkit dependency."""

import tempfile
from pathlib import Path
import unittest

from tools.snapshot_psp_telemetry_reference import capture_reference, sha256


class ReferenceSnapshotBoundaryTests(unittest.TestCase):
    def test_requires_reader_before_loading_any_vi(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            (source / "unrelated.vi").write_bytes(b"not a VI")
            with self.assertRaisesRegex(ValueError, "psp_supervision.vi"):
                capture_reference(source, root / "evidence")
            self.assertFalse((root / "evidence").exists())

    def test_never_writes_into_source_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            reader = source / "psp_supervision.vi"
            reader.write_bytes(b"not a VI")
            before = sha256(reader)
            for output in (source, source / "output"):
                with self.assertRaisesRegex(ValueError, "outside"):
                    capture_reference(source, output)
            self.assertEqual(sha256(reader), before)
            self.assertFalse((source / "output").exists())

    def test_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "source", root / "evidence"
            source.mkdir()
            output.mkdir()
            marker = output / "manifest.json"
            marker.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "empty"):
                capture_reference(source, output)
            self.assertEqual(marker.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
