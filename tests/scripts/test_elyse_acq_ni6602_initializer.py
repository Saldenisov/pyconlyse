"""Hash-pinned NI6602 initializer and rejecting dataflow mutation tests."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_ni6602_initializer import (
    checked_roots, validate_trees, FRAMES, LITERALS, unique,
)


class NI6602InitializerEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_roots(REPOSITORY /
            "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip")

    def setUp(self):
        self.roots = deepcopy(self.original)

    def change_literal(self, roots, frame_index, argument, value):
        frame = unique(roots["vi_BDHb.xml"], "diag", FRAMES[frame_index][0])
        frame.find(f"nodeList/*/termList/*[@uid='{LITERALS[frame_index][argument]}']/dco/ConstValue").text = value

    def test_original_passes(self):
        lines = validate_trees(self.roots)
        self.assertIn("continuous public error-in", lines[2])

    def test_every_high_tick_change_rejected(self):
        for i in range(8):
            with self.subTest(frame=i):
                roots = deepcopy(self.original)
                self.change_literal(roots, i, 9, "00000001")
                with self.assertRaisesRegex(AssertionError, f"frame {i} literal argument 9"):
                    validate_trees(roots)

    def test_every_low_tick_change_rejected(self):
        for i in range(8):
            with self.subTest(frame=i):
                roots = deepcopy(self.original)
                self.change_literal(roots, i, 10, "00000001")
                with self.assertRaisesRegex(AssertionError, f"frame {i} literal argument 10"):
                    validate_trees(roots)

    def test_every_frame_error_chain_break_rejected(self):
        for i, row in enumerate(FRAMES):
            with self.subTest(frame=i):
                roots = deepcopy(self.original)
                frame = unique(roots["vi_BDHb.xml"], "diag", row[0])
                frame.find(f"signalList/*/termList/*[@uid='{row[8]}']").set("uid", "1234567")
                with self.assertRaisesRegex(AssertionError, f"frame {i} wire set"):
                    validate_trees(roots)

    def test_every_retriggerable_false_rejected(self):
        for i in range(8):
            with self.subTest(frame=i):
                roots = deepcopy(self.original)
                self.change_literal(roots, i, 4, "00")
                with self.assertRaisesRegex(AssertionError, f"frame {i} literal argument 4"):
                    validate_trees(roots)

    def test_counter_seven_rising_trigger_rejected(self):
        self.change_literal(self.roots, 7, 6, "00002828")
        with self.assertRaisesRegex(AssertionError, "frame 7 literal argument 6"):
            validate_trees(self.roots)

    def test_initial_delay_change_rejected(self):
        self.change_literal(self.roots, 3, 8, "0000000001")
        with self.assertRaisesRegex(AssertionError, "frame 3 literal argument 8"):
            validate_trees(self.roots)

    def test_timebase_source_change_rejected(self):
        self.change_literal(self.roots, 1, 3, "000000092F31302F5046493130")
        with self.assertRaisesRegex(AssertionError, "string"):
            validate_trees(self.roots)

    def test_finite_mode_change_rejected(self):
        self.change_literal(self.roots, 5, 12, "000027C3")
        with self.assertRaisesRegex(AssertionError, "literal argument 12"):
            validate_trees(self.roots)

    def test_sample_count_change_rejected(self):
        self.change_literal(self.roots, 0, 13, "00000002")
        with self.assertRaisesRegex(AssertionError, "literal argument 13"):
            validate_trees(self.roots)

    def test_idle_state_change_rejected(self):
        self.change_literal(self.roots, 2, 11, "000027D0")
        with self.assertRaisesRegex(AssertionError, "literal argument 11"):
            validate_trees(self.roots)

    def test_property_read_mode_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "propNode", "7408").find("termList/*/dco/propList/*/objFlags").text = "0"
        with self.assertRaisesRegex(AssertionError, "code/write mode"):
            validate_trees(self.roots)

    def test_property_identity_change_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "propNode", "9723").find("termList/*/dco/propList/*/PropItemCode").text = "4465"
        with self.assertRaisesRegex(AssertionError, "code/write mode"):
            validate_trees(self.roots)

    def test_property_error_direction_change_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "propNode", "8388").find("termList/*/dco/objFlags").text = "131072"
        with self.assertRaisesRegex(AssertionError, "task/error direction"):
            validate_trees(self.roots)

    def test_counter_three_extra_start_rejected(self):
        frame = unique(self.roots["vi_BDHb.xml"], "diag", "9448")
        ET.SubElement(frame.find("zPlaneList"), "extra", {"class": "iUse", "uid": "1234567"})
        with self.assertRaisesRegex(AssertionError, "frame 3 operation census"):
            validate_trees(self.roots)

    def test_counter_zero_start_removed_rejected(self):
        frame = unique(self.roots["vi_BDHb.xml"], "diag", "9978")
        frame.find("zPlaneList").remove(unique(self.roots["vi_BDHb.xml"], "iUse", "9106"))
        with self.assertRaises(AssertionError):
            validate_trees(self.roots)

    def test_cross_frame_error_local_change_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "sLoc", "12933").find("diagDefined").text = "03"
        with self.assertRaisesRegex(AssertionError, "cross-frame error local"):
            validate_trees(self.roots)

    def test_sequence_task_tunnel_swap_rejected(self):
        sequence = unique(self.roots["vi_BDHb.xml"], "sequence", "3868")
        sequence.find("termList/*[@uid='12777']/dco/termList/*[@uid='12756']").set("uid", "11191")
        with self.assertRaisesRegex(AssertionError, "task/error tunnel"):
            validate_trees(self.roots)

    def test_output_task_field_swap_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "nMux", "965").find("termList/*[@uid='13189']/dco/i").text = "4"
        with self.assertRaisesRegex(AssertionError, "output task field"):
            validate_trees(self.roots)

    def test_public_error_alias_change_rejected(self):
        self.roots["vi.xml"].find("CPMp/Section/TypeDesc[1]").set("Flags", "0x0100")
        with self.assertRaisesRegex(AssertionError, "public-to-local"):
            validate_trees(self.roots)

    def test_hidden_error_local_rejected(self):
        ET.SubElement(self.roots["vi_BDHb.xml"].find("root/zPlaneList"), "extra", {"class": "gRef", "uid": "1234567"})
        with self.assertRaisesRegex(AssertionError, "hidden error alias"):
            validate_trees(self.roots)

    def test_implicit_timing_selector_change_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "polyIUse", "10365").find("instanceSelector/menuInstanceUsed").text = "02"
        with self.assertRaisesRegex(AssertionError, "polymorphic"):
            validate_trees(self.roots)


if __name__ == "__main__":
    unittest.main()
