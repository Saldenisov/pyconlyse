"""Typed source-default evidence and no-I/O generated-fragment grammar."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from qualify_acq_ni6220_index_defaults import audit_fragment
from validate_acq_ni6220_index_defaults import (
    INDEX_NODES,
    ROOT_ARCHIVE,
    checked_vam,
    heap_type,
    unique,
    validate_indices,
)


class Ni6220IndexSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.metadata = checked_vam(ROOT_ARCHIVE)

    def rejected_text(self, element, value, *, metadata=None):
        before = element.text
        element.text = value
        try:
            with self.assertRaises(AssertionError):
                validate_indices(
                    self.root, self.metadata if metadata is None else metadata
                )
        finally:
            element.text = before

    def test_original_three_nodes_all25_typed_terminals_pass(self):
        proof = validate_indices(self.root, self.metadata)
        self.assertEqual(proof["scalar_outputs"], 11)
        self.assertEqual(proof["typed_terminals"], 25)
        self.assertEqual(proof["out_of_bounds_default"], 0.0)
        self.assertFalse(proof["driver_failure_return_proven"])
        self.assertFalse(proof["array_to_cluster_padding_proven"])

    def test_all25_terminal_type_ids_and_flags_are_checked(self):
        for uid in INDEX_NODES:
            for term in unique(self.root, "aIndx", uid).findall("termList/*"):
                with self.subTest(uid=uid, port=term.get("uid")):
                    self.rejected_text(term.find("dco/typeDesc"), "TypeID(1)")
                    self.rejected_text(term.find("objFlags"), "0")
                    self.rejected_text(term.find("dco/objFlags"), "0")

    def test_output_representation_not_just_type_id_is_checked(self):
        descriptor, _ = heap_type(self.metadata, 2688)
        before = descriptor.get("Type")
        descriptor.set("Type", "NumFloat32")
        try:
            with self.assertRaises(AssertionError):
                validate_indices(self.root, self.metadata)
        finally:
            descriptor.set("Type", before)

    def test_array_element_representation_and_rank_are_checked(self):
        descriptor, flat = heap_type(self.metadata, 2687)
        element = flat[58]
        before = element.get("Type")
        element.set("Type", "NumInt32")
        try:
            with self.assertRaises(AssertionError):
                validate_indices(self.root, self.metadata)
        finally:
            element.set("Type", before)
        dimension = descriptor.find("Dimension")
        descriptor.remove(dimension)
        try:
            with self.assertRaises(AssertionError):
                validate_indices(self.root, self.metadata)
        finally:
            descriptor.insert(0, dimension)

    def test_coerced_display_index_and_expansion_are_not_normalized(self):
        self.rejected_text(
            unique(self.root, "aIndx", "48810").find(
                "termList/*[@uid='48818']/dco/dsw"
            ),
            "4096",
        )
        for uid in INDEX_NODES:
            self.rejected_text(unique(self.root, "aIndx", uid).find("shortCount"), "0")


class IndexFragmentGrammarTests(unittest.TestCase):
    def test_guarded_scalar_and_tuple_index_fragments_accepted(self):
        audit_fragment(
            "v = _lv.index_array(values, selected, 0.0)\nresult = v",
            ("values", "selected"),
        )
        audit_fragment(
            "a = _lv.index_array(values, 4, 0.0)\nresult = (a,)", ("values",)
        )

    def test_io_import_raw_index_defaults_and_input_overwrites_rejected(self):
        for source in (
            "import os\nresult = 0.0",
            "result = open('file')",
            "result = values[0]",
            "a, b = _lv.index_array(values, 4, 0.0)\nresult = (a, b)",
            "result = _lv.index_array(values, 4, 0)",
            "result = _lv.index_array(values, 4, None)",
            "result = _lv.index_array(values, 4, 1.0)",
            "result = _lv.other(values, 4, 0.0)",
            "values = ()\nresult = values",
            "result = _lv.__dict__",
            "while True: pass\nresult = 0.0",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source, ("values",))


if __name__ == "__main__":
    unittest.main()
