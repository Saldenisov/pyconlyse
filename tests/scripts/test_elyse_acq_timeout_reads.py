"""All command-read frame nets, call shapes and final stop resets are pinned."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_timeout_reads import NETS, SITES, checked_vam, unique, validate_reads


class TimeoutReadsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def rejected(self, mutate):
        root = deepcopy(self.root)
        mutate(root)
        with self.assertRaises(AssertionError):
            validate_reads(root, self.meta)

    def test_original_source_passes(self):
        self.assertIn(
            "6 diagrams / 53 direct nets", validate_reads(self.root, self.meta)
        )

    def test_all_nonempty_frame_net_mutations_rejected(self):
        for uid, nets in NETS.items():
            if nets:
                self.rejected(
                    lambda r, uid=uid: unique(r, "diag", uid)
                    .find("signalList/*/termList/*")
                    .set("uid", "999999")
                )

    def test_default_and_write_local_not_confused_at_each_reader(self):
        def set_read_flag(root, write):
            dco = unique(root, "gRef", write).find("termList/*/dco")
            flags = dco.find("objFlags")
            if flags is None:
                flags = ET.SubElement(dco, "objFlags")
            flags.text = "1"

        for site in SITES:
            write = site[5]
            self.rejected(lambda r, write=write: set_read_flag(r, write))

    def test_all_uri_literals_sensitive(self):
        for site in SITES:
            literal = site[1]
            self.rejected(
                lambda r, literal=literal: unique(r, "diag", "10115")
                .find(f"nodeList/*/termList/*[@uid='{literal}']/dco/ConstValue")
                .__setattr__("text", "00000000")
            )

    def test_read_error_false_literal_not_replaced_with_safe_policy_true(self):
        self.rejected(
            lambda r: unique(r, "diag", "40224")
            .find("nodeList/*/termList/*[@uid='44039']/dco/ConstValue")
            .__setattr__("text", "01")
        )

    def test_stop_and_tcp_banks_and_event_wait_sensitive(self):
        self.rejected(
            lambda r: unique(r, "gRef", "85095")
            .find("termList/*/dco/paramIdx")
            .__setattr__("text", "45")
        )
        self.rejected(
            lambda r: unique(r, "diag", "110")
            .find("nodeList/*/termList/*[@uid='290']/dco/ConstValue")
            .__setattr__("text", "00000015")
        )

    def test_final_error_case_polarity_sensitive(self):
        self.rejected(
            lambda r: unique(r, "select", "40205")
            .find("SelectRangeArray32/*/start")
            .__setattr__("text", "1")
        )


if __name__ == "__main__":
    unittest.main()
