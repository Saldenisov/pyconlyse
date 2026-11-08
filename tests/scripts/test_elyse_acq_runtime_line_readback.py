"""Original line field-copy proof and mutation rejection for each frame."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.line_readback import FRAMES
from validate_acq_runtime_line_readback import ROWS, checked_root, unique, validate_tree


class LineReadbackSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_root(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_passes_and_all_python_pairs_correspond(self):
        self.assertIn("BOTH use C1[34]", validate_tree(self.original))
        for frame, row in zip(FRAMES, ROWS):
            self.assertEqual((frame.frame_index, frame.diagram_uid), row[:2])
            self.assertEqual(frame.pairs, tuple(zip(row[7], row[8])))
            self.assertEqual(
                (frame.source_local_index, frame.target_local_index), row[10:12]
            )

    def test_each_source_and_destination_field_mutation_rejected(self):
        for row in ROWS:
            for uid in (row[2], row[4]):
                root = deepcopy(self.original)
                fields = unique(root, "nMux", uid).findall("termList/*")
                fields[-1].find("dco/i").text = "0"
                with self.assertRaisesRegex(AssertionError, "field identity/order"):
                    validate_tree(root)

    def test_each_frame_broken_wire_is_rejected(self):
        for row in ROWS:
            root = deepcopy(self.original)
            unique(root, "diag", row[1]).find("signalList/*/termList/*").set(
                "uid", "999999"
            )
            with self.assertRaisesRegex(AssertionError, "wire set"):
                validate_tree(root)

    def test_local_read_write_direction_and_target_identity_checked(self):
        for row in ROWS:
            root = deepcopy(self.original)
            unique(root, "gRef", row[6]).find("termList/*/dco/paramIdx").text = "18"
            with self.assertRaisesRegex(AssertionError, "local identity/direction"):
                validate_tree(root)

    def test_duplicate_source_field_cannot_be_silently_corrected(self):
        root = deepcopy(self.original)
        unique(root, "nMux", "24699").find("termList/*[@uid='24762']/dco/i").text = "35"
        with self.assertRaisesRegex(AssertionError, "field identity/order"):
            validate_tree(root)


if __name__ == "__main__":
    unittest.main()
