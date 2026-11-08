"""Original wire proof and mutations that must prevent tail qualification."""

import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from DeviceServers.control.elyse_acq.vi_simulation.beamline_commands import (
    SETPOINT_COPIES,
)  # noqa: E402
from validate_acq_beamline_commands import validate_tail  # noqa: E402
from validate_acq_modulator_start_event_guards import unique  # noqa: E402
from validate_acq_vam_status import checked_vam  # noqa: E402


class BeamlineWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_both_original_maps_match_inert_projection(self):
        self.assertEqual(validate_tail(*self.roots), dict(SETPOINT_COPIES))

    def test_mutated_nodes_fields_directions_selectors_or_error_edges_fail(self):
        def replace(root, klass, uid, path, value):
            node = unique(root, klass, uid)
            field = node.find(path)
            if field is None:
                parent, leaf = path.rsplit("/", 1)
                field = ET.SubElement(node.find(parent), leaf)
            field.text = value

        mutations = (
            lambda r: replace(r, "gRef", "14405", "termList/*/dco/paramIdx", "10"),
            lambda r: replace(r, "gRef", "14436", "termList/*/dco/objFlags", "1"),
            lambda r: replace(
                r, "nMux", "14411", "termList/*[@uid='14417']/dco/i", "9"
            ),
            lambda r: replace(
                r, "nMux", "64798", "termList/*[@uid='64812']/dco/i", "102"
            ),
            lambda r: replace(r, "prim", "14212", "primResID", "1105"),
            lambda r: replace(
                r, "select", "14339", "SelectRangeArray32/*/diagramIdx", "1"
            ),
            lambda r: (
                unique(r, "sequence", "19041")
                .find("seqLocDCOList/*/termList/*")
                .set("uid", "wrong")
            ),
            lambda r: (
                unique(r, "diag", "14348")
                .find("zPlaneList")
                .append(copy.deepcopy(unique(r, "gRef", "14405")))
            ),
            lambda r: (
                unique(r, "diag", "14553")
                .find("signalList/*/termList/*")
                .set("uid", "14795")
            ),
            lambda r: (
                unique(r, "diag", "64942")
                .find("signalList/*/termList")
                .append(
                    copy.deepcopy(
                        unique(r, "sharedVariableDynamicWrite", "65227").find(
                            "termList/*"
                        )
                    )
                )
            ),
            lambda r: replace(
                r,
                "sharedVariableDynamicWrite",
                "14838",
                "termList/*/dco/terminal_ID",
                "00",
            ),
            lambda r: replace(
                r, "iUse", "65143", "termList/*[@uid='65173']/dco/paramIdx", "8"
            ),
            lambda r: (
                unique(r, "diag", "15917")
                .find("nodeList/*/termList/*[@uid='15319']/dco/ConstValue")
                .__setattr__("text", "00000065")
            ),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                root = copy.deepcopy(self.roots[0])
                mutate(root)
                with self.assertRaises(AssertionError):
                    validate_tail(root, self.roots[1])

    def test_unexpected_operation_inside_true_arm_is_not_silently_ignored(self):
        root = copy.deepcopy(self.roots[0])
        unique(root, "diag", "64786").find("zPlaneList").append(
            copy.deepcopy(unique(root, "prim", "14705"))
        )
        with self.assertRaises(AssertionError):
            validate_tail(root, self.roots[1])


if __name__ == "__main__":
    unittest.main()
