"""Mutation tests for offline saved-LabVIEW sequence-tunnel evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_cooling_start_completion import checked_root, unique
from validate_acq_controlled_stop_wait_tunnels import validate_tree


class StopWaitTunnelEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_root(
            REPOSITORY / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.root = deepcopy(self.original)

    def assert_rejected(self, reason):
        with self.assertRaisesRegex(AssertionError, reason):
            validate_tree(self.root)

    def test_saved_source_passes(self):
        self.assertEqual(len(validate_tree(self.root)), 3)

    def test_phase4_constant_change_is_rejected(self):
        unique(self.root, "sRN", "7985").find("termList/*/dco/ConstValue").text = "00000095"
        self.assert_rejected("literal 150")

    def test_phase5_constant_change_is_rejected(self):
        unique(self.root, "sRN", "52163").find("termList/*/dco/ConstValue").text = "00000097"
        self.assert_rejected("literal 150")

    def test_parent_constant_to_tunnel_wire_change_is_rejected(self):
        unique(self.root, "signal", "47286").find("termList/*").set("uid", "wrong")
        self.assert_rejected("47276->42403")

    def test_swapped_tunnel_frame_ports_are_rejected(self):
        terms = unique(self.root, "sequence", "42397").findall("termList/*/dco/termList/*")
        terms[0].set("uid", "42407")
        terms[1].set("uid", "42406")
        self.assert_rejected("frame-port list")

    def test_wrong_frame_port_dco_reference_is_rejected(self):
        frame = unique(self.root, "sequence", "42397").find("diagramList")[3]
        frame.find("nodeList/*/termList/*[@uid='42409']/dco").set("uid", "54282")
        self.assert_rejected("port 42409 no longer references")

    def test_wrong_wait_duration_terminal_is_rejected(self):
        unique(self.root, "prim", "54568").find("termList/*[@uid='54573']/dco/parmIndex").text = "0"
        self.assert_rejected("54568 duration input")

    def test_missing_tunnel_to_wait_wire_is_rejected(self):
        frame = unique(self.root, "sequence", "54275").find("diagramList")[4]
        signal = next(s for s in frame.findall("signalList/*")
                      if "54573" in {t.get("uid") for t in s.findall("termList/*")})
        signal.find("termList/*[@uid='54573']").set("uid", "wrong")
        self.assert_rejected("54288->54573")

    def test_extra_connected_restore_frame_is_rejected(self):
        frame = unique(self.root, "sequence", "42397").find("diagramList")[1]
        frame.find("signalList/*/termList/*").set("uid", "42407")
        self.assert_rejected("connected tunnel frames")

    def test_constant_relocation_is_rejected(self):
        phases = unique(self.root, "sequence", "51954").find("diagramList")
        source = unique(self.root, "sRN", "7985")
        phases[4].find("nodeList").remove(source)
        phases[5].find("nodeList").append(source)
        self.assert_rejected("constant source moved")


if __name__ == "__main__":
    unittest.main()
