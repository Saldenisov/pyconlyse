"""Independent complete frame0 wire proof and negative mutation checks."""

import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from DeviceServers.control.elyse_acq.vi_simulation.beamline_adjustment import (  # noqa: E402
    adjustment_parameters,
)
from validate_acq_beamline_adjustment import validate_adjustment  # noqa: E402
from validate_acq_modulator_start_event_guards import unique  # noqa: E402
from validate_acq_vam_status import checked_vam  # noqa: E402


class BeamlineAdjustmentWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_all_original_frame0_diagrams_and_80_device_button_rules(self):
        proof = validate_adjustment(*self.roots)
        self.assertEqual(
            (len(proof["diagram_uids"]), proof["direct_nets"], len(proof["rules"])),
            (52, 424, 80),
        )
        self.assertFalse(proof["outer_default_independently_verified"])
        for key, params in proof["rules"].items():
            self.assertEqual(adjustment_parameters(*key), params)

    def test_corrupted_arithmetic_cases_masks_properties_and_wire_fanouts_fail(self):
        mutations = (
            ("prim", "11912", "primResID", "1050"),
            ("prim", "11244", "objFlags", "0"),
            ("select", "11808", "SelectDefaultCase", "00"),
            ("select", "63290", "SelectRangeArray32/*/end", "4"),
            ("forLoop", "11263", "termList/*[@uid='11269']/dco/TunnelType", "00"),
            ("propNode", "11429", "termList/*[@uid='11443']/dco/objFlags", "1"),
            (
                "propNode",
                "62933",
                "termList/*[@uid='62947']/dco/propList/*/PropItemCode",
                "104013838",
            ),
            ("nMux", "11490", "termList/*[@uid='11513']/dco/i", "6"),
            (
                "diag",
                "11283",
                "nodeList/*/termList/*[@uid='11292']/dco/ConstValue",
                "00000781",
            ),
            (
                "diag",
                "14167",
                "nodeList/*/termList/*[@uid='14173']/dco/ConstValue",
                "00000047",
            ),
        )
        for klass, uid, path, value in mutations:
            with self.subTest(uid=uid):
                root = copy.deepcopy(self.roots[0])
                node = unique(root, klass, uid)
                field = node.find(path)
                if field is None:
                    parent, tag = path.rsplit("/", 1)
                    field = ET.SubElement(node.find(parent), tag)
                field.text = value
                with self.assertRaises(AssertionError):
                    validate_adjustment(root, self.roots[1])
        root = copy.deepcopy(self.roots[0])
        unique(root, "diag", "11844").find("signalList/*/termList/*").set(
            "uid", "wrong"
        )
        with self.assertRaises(AssertionError):
            validate_adjustment(root, self.roots[1])


if __name__ == "__main__":
    unittest.main()
