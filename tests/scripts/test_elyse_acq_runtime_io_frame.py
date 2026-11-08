"""Mutation-sensitive proof of frame-0 graph and heap type resolution."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import (
    AI_SIZES,
    DI_SIZES,
    DO_SIZES,
)
from validate_acq_runtime_io_frame import (
    CONVERSIONS,
    checked_trees,
    heap_type,
    unique,
    validate_trees,
)


class RuntimeIoSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd, cls.main = checked_trees(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_graph_and_model_shapes(self):
        self.assertIn("32 nets, 33 operations", validate_trees(self.bd, self.main))
        self.assertEqual(AI_SIZES, tuple(r[5] for r in CONVERSIONS[10:]))
        self.assertEqual(DI_SIZES, tuple(r[5] for r in reversed(CONVERSIONS[7:10])))
        self.assertEqual(DO_SIZES, tuple(r[5] for r in reversed(CONVERSIONS[4:7])))

    def test_every_conversion_type_and_primitive_mutation_rejected(self):
        for row in CONVERSIONS:
            for target, value in (
                ("primResID", "9999"),
                ("termList/*/dco/typeDesc", "TypeID(1)"),
            ):
                bd = deepcopy(self.bd)
                unique(bd, "prim", row[0]).find(target).text = value
                with self.assertRaises(AssertionError):
                    validate_trees(bd, self.main)

    def test_each_cluster_size_mutation_rejected(self):
        for position, row in enumerate(CONVERSIONS):
            main = deepcopy(self.main)
            cluster, _ = heap_type(main, row[4] if position < 7 else row[2])
            cluster.remove(cluster.find("TypeDesc"))
            with self.assertRaisesRegex(AssertionError, "cluster size changed"):
                validate_trees(self.bd, main)

    def test_frame_order_and_sequence_channel_mutations_rejected(self):
        bd = deepcopy(self.bd)
        frames = unique(bd, "sequence", "1244").find("diagramList")
        first = frames[0]
        frames.remove(first)
        frames.insert(1, first)
        with self.assertRaisesRegex(AssertionError, "runtime sequence order"):
            validate_trees(bd, self.main)
        bd = deepcopy(self.bd)
        unique(bd, "sequence", "1244").find("seqLocDCOList").append(
            deepcopy(unique(bd, "gRef", "1828"))
        )
        with self.assertRaisesRegex(AssertionError, "inter-frame connection"):
            validate_trees(bd, self.main)

    def test_heap_slice_and_nested_flat_type_mutations_rejected(self):
        main = deepcopy(self.main)
        main.find("DTHP/Section/TypeDescSlice").set("IndexShift", "1")
        with self.assertRaises(AssertionError):
            validate_trees(self.bd, main)
        main = deepcopy(self.main)
        cluster, flat = heap_type(main, 3048)
        flat[int(cluster.find("TypeDesc").get("TypeID"))].set("Type", "NumFloat64")
        with self.assertRaisesRegex(AssertionError, "cluster element type changed"):
            validate_trees(self.bd, main)

    def test_wire_order_count_sample_and_local_mutations_rejected(self):
        for target, value in (
            ("signalList/*/termList/*", "999999"),
            ("zPlaneList/*", "999999"),
        ):
            bd = deepcopy(self.bd)
            unique(bd, "diag", "7386").find(target).set("uid", value)
            with self.assertRaises(AssertionError):
                validate_trees(bd, self.main)
        for uid, target, value in (
            ("1628", "termList/*/dco/paramIdx", "23"),
            ("2370", "termList/*/dco/objFlags", "1"),
            ("647", "shortCount", "50"),
        ):
            bd = deepcopy(self.bd)
            node = next(
                n
                for n in bd.iter()
                if n.get("uid") == uid and n.get("class") in ("gRef", "iUse")
            )
            if node.find(target) is None:
                import xml.etree.ElementTree as ET

                ET.SubElement(node.find("termList/*/dco"), "objFlags").text = value
            else:
                node.find(target).text = value
            with self.assertRaises(AssertionError):
                validate_trees(bd, self.main)
        bd = deepcopy(self.bd)
        unique(bd, "diag", "7386").find(
            "nodeList/*/termList/*[@uid='8081']/dco/ConstValue"
        ).text = "00000001"
        with self.assertRaisesRegex(AssertionError, "sample count changed"):
            validate_trees(bd, self.main)


if __name__ == "__main__":
    unittest.main()
