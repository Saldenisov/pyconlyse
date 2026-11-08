"""VAM frame operation, field, iteration and array-shape mutations."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_vam_status import NETS, checked_vam, unique, validate_vam


class VamSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_source_passes(self):
        self.assertIn("39 direct nets", validate_vam(self.root, self.meta))

    def test_every_new_direct_frame_net_mutation_rejected(self):
        for uid in NETS:
            root = deepcopy(self.root)
            unique(root, "diag", uid).find("signalList/*/termList/*").set(
                "uid", "999999"
            )
            with self.assertRaises(AssertionError):
                validate_vam(root, self.meta)

    def test_iteration_tunnel_and_field_order_sensitive(self):
        root = deepcopy(self.root)
        unique(root, "sequence", "45836").find(
            "termList/*[@uid='45904']/dco/termList/*"
        ).set("uid", "999999")
        with self.assertRaises(AssertionError):
            validate_vam(root, self.meta)
        root = deepcopy(self.root)
        unique(root, "nMux", "46933").find("termList/*[@uid='46942']/dco/i").text = "33"
        with self.assertRaises(AssertionError):
            validate_vam(root, self.meta)


if __name__ == "__main__":
    unittest.main()
