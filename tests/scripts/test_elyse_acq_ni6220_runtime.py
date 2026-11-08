"""Pinned graphs reject mutations of cases, fields, locals and caller arguments."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_ni6220_runtime import NETS, checked_vam, unique, validate_runtime


class Ni6220RuntimeSourceTests(unittest.TestCase):
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
            validate_runtime(root, self.meta)

    def test_original_source_passes(self):
        self.assertIn(
            "14 diagrams / 61 direct nets", validate_runtime(self.root, self.meta)
        )

    def test_every_nonempty_frame_wire_mutation_rejected(self):
        for uid, nets in NETS.items():
            if nets:
                with self.subTest(uid=uid):
                    self.rejected(
                        lambda r, uid=uid: unique(r, "diag", uid)
                        .find("signalList/*/termList/*")
                        .set("uid", "999999")
                    )

    def test_every_empty_frame_operation_insertion_rejected(self):
        import xml.etree.ElementTree as ET

        for uid, nets in NETS.items():
            if not nets:
                self.rejected(
                    lambda r, uid=uid: unique(r, "diag", uid)
                    .find("zPlaneList")
                    .append(ET.Element("SL__arrayElement", uid="999999"))
                )

    def test_counter_case_range_and_explicit_default_sensitive(self):
        self.rejected(
            lambda r: unique(r, "select", "100523")
            .find("SelectDefaultCase")
            .__setattr__("text", "00")
        )
        self.rejected(
            lambda r: unique(r, "select", "81854")
            .find("SelectRangeArray32/*/start")
            .__setattr__("text", "1")
        )

    def test_missing_default_not_inferred_from_displayed_case(self):
        import xml.etree.ElementTree as ET

        self.rejected(
            lambda r: unique(r, "select", "81854").append(
                ET.Element("SelectDefaultCase")
            )
        )

    def test_bank67_is_prior_array_not_new_array(self):
        self.rejected(
            lambda r: unique(r, "diag", "206856")
            .find("signalList/*/termList/*[@uid='62724']")
            .set("uid", "208159")
        )

    def test_bank66_capture_destination_not_bank67(self):
        self.rejected(
            lambda r: unique(r, "gRef", "202970")
            .find("termList/*/dco/paramIdx")
            .__setattr__("text", "67")
        )

    def test_special_local_flags_are_not_normalized(self):
        self.rejected(
            lambda r: unique(r, "gRef", "48168")
            .find("termList/*/dco/objFlags")
            .__setattr__("text", "1")
        )

    def test_sequence_tunnel_and_call_slots_sensitive(self):
        self.rejected(
            lambda r: unique(r, "sequence", "15804")
            .find("termList/*/dco/termList/*")
            .set("uid", "999999")
        )
        self.rejected(
            lambda r: unique(r, "iUse", "48830")
            .find("termList/*[@uid='48837']/dco/paramIdx")
            .__setattr__("text", "2")
        )


if __name__ == "__main__":
    unittest.main()
