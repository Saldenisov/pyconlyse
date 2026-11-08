"""Global absence claims stay bounded to the checked gRef register population."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_modulator_start_event_guards import unique
from validate_acq_runtime_local_registers import checked_vam, validate_registers


class RuntimeRegisterSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_passes(self):
        self.assertIn(
            "38 root local references", validate_registers(self.root, self.meta)
        )

    def test_action_cannot_become_an_unverified_permission_read(self):
        root = deepcopy(self.root)
        node = unique(root, "gRef", "10440")
        from xml.etree.ElementTree import SubElement

        SubElement(node.find("termList/*/dco"), "objFlags").text = "1"
        with self.assertRaises(AssertionError):
            validate_registers(root, self.meta)

    def test_wcm_counter_writer_cannot_move_to_initialization(self):
        root = deepcopy(self.root)
        writer = unique(root, "gRef", "100549")
        parent = next(n for n in root.iter() if writer in list(n))
        parent.remove(writer)
        unique(root, "diag", "227").find("zPlaneList").append(writer)
        with self.assertRaises(AssertionError):
            validate_registers(root, self.meta)


if __name__ == "__main__":
    unittest.main()
