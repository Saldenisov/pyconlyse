"""Original ACQ loop/property identities and non-actuating converter tests."""

from __future__ import annotations

import ast
import copy
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_lvkit import ARCHIVE, DEFAULT_CHECKOUT, verify_checkout  # noqa: E402

verify_checkout(DEFAULT_CHECKOUT)

from lvkit.codegen.context import CodeGenContext  # noqa: E402
from lvkit.codegen.nodes import property_node  # noqa: E402
from lvkit.codegen.nodes.base import CodeGenError  # noqa: E402
from lvkit.graph import InMemoryVIGraph  # noqa: E402
from lvkit.graph.models import PrimitiveNode  # noqa: E402
from lvkit.models import (  # noqa: E402
    ClusterField,
    LVType,
    LVTypeKind,
    PropertyDef,
    Terminal,
)
from qualify_acq_counter_components import (  # noqa: E402
    audit_fragment,
    fragments,
    qualify,
    run_fragment,
    validate_conversion_types,
)
from validate_acq_ni6602_writer import MEMBER, checked_roots  # noqa: E402


def property_fixture():
    """Synthetic mixed access: row order intentionally differs from ports."""
    ref = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="Refnum")
    error = LVType(
        kind=LVTypeKind.CLUSTER,
        fields=[ClusterField(name=n) for n in ("status", "code", "source")],
    )
    definitions = [
        ("ref_in", "input", ref),
        ("ref_out", "output", ref),
        ("error_in", "input", error),
        ("error_out", "output", error),
        ("read_value", "output", ref),
        ("write_value", "input", None),
    ]
    terms = [
        Terminal(id=u, index=i, direction=d, lv_type=t)
        for i, (u, d, t) in enumerate(definitions)
    ]
    node = PrimitiveNode(
        id="property",
        vi_path="fixture.vi",
        node_type="propNode",
        terminals=terms,
        properties=[PropertyDef(name="setpoint"), PropertyDef(name="child")],
        property_value_terminal_ids=["write_value", "read_value"],
    )
    graph = InMemoryVIGraph()
    graph._graph.add_node(node.id, node=node)
    for term in terms:
        graph._term_to_node[term.id] = node.id
    ctx = CodeGenContext(graph=graph)
    ctx.bind("ref_in", "task")
    ctx.bind("error_in", "error")
    ctx.bind("write_value", "value")
    # This fixture tests the emitter, not graph connectivity reconstruction.
    ctx.is_wired = lambda terminal: True
    return node, ctx


class AcqCounterQualificationTests(unittest.TestCase):
    def test_original_acquisition_inventory_has_all_17_pinned_members(self):
        from inventory_control_lvkit import acquisition_inventory

        rows = acquisition_inventory()
        self.assertEqual(len(rows), 17)
        self.assertEqual({r["corpus"] for r in rows}, {"acquisition"})
        self.assertTrue(any(r["source"].endswith("0_ACQ_ELYSE.vi") for r in rows))

    def test_23_poll_traces_and_four_timing_vectors(self):
        receipt = qualify()["receipt"]
        self.assertEqual(len(receipt["poll_traces"]), 23)
        self.assertEqual(receipt["poll_traces"][-1]["iterations"], 22)
        self.assertEqual(receipt["timing_cases"], 4)
        self.assertFalse(receipt["deployable"])
        self.assertFalse(receipt["full_writer_qualified"])

    def test_property_value_ids_are_not_reference_error_ports(self):
        _, _, receipt = fragments()
        self.assertEqual(
            receipt["property_value_uids"],
            {"3202": ["3216"], "3083": ["3097", "3103", "3109"]},
        )
        self.assertEqual(
            receipt["timing_bindings"], {"3088": "task", "3094": "supplied_error"}
        )

    def test_index_saturates_without_two_billion_iterations(self):
        sources, attrs, _ = fragments()
        tree = audit_fragment(sources["poll"], attrs, polling=True)
        loop = next(n for n in tree.body if isinstance(n, ast.While))
        tail = loop.body[-1]
        name = tail.test.left.id
        module = ast.fix_missing_locations(
            ast.Module(body=[copy.deepcopy(tail)], type_ignores=[])
        )
        for initial, expected in ((2147483646, 2147483647), (2147483647, 2147483647)):
            ns = {"__builtins__": {}, name: initial}
            exec(compile(module, "<audited-index-tail>", "exec"), ns)
            self.assertEqual(ns[name], expected)

    def test_done_on_index_20_is_21_polls_not_limit_exit(self):
        sources, attrs, _ = fragments()
        task, waits, _ = run_fragment(sources["poll"], attrs, polling=True, done_at=20)
        self.assertEqual(len(waits), 21)
        self.assertTrue(task.reads[-1])

    def test_u32_target_is_not_proof_of_u32_conversion_node(self):
        _, _, receipt = fragments()
        self.assertEqual(
            receipt["conversion_output_types"], {"157": "NumInt32", "183": "NumInt32"}
        )
        self.assertEqual(
            receipt["archived_numeric_type_proof"]["201"]["type"], "NumInt32"
        )
        self.assertEqual(
            receipt["archived_numeric_type_proof"]["3097"]["type"], "NumUInt32"
        )

    def test_archived_conversion_type_mutation_rejected(self):
        roots = checked_roots(ARCHIVE)
        with ZipFile(ARCHIVE) as archive:
            metadata = archive.read(MEMBER + "/vi.xml").decode("utf-8")
        roots["vi.xml"].findall("VCTP/Section/TypeDesc")[19].set("Type", "NumUInt32")
        with self.assertRaisesRegex(AssertionError, "numeric representation"):
            validate_conversion_types(roots, metadata)

    def test_mixed_rows_follow_dco_list_and_refnum_property_is_value(self):
        node, ctx = property_fixture()
        fragment = property_node.generate(node, ctx)
        self.assertEqual(fragment.bindings["ref_out"], "task")
        self.assertEqual(fragment.bindings["error_out"], "error")
        self.assertNotEqual(fragment.bindings["read_value"], "task")
        statements = fragment.statements
        self.assertEqual(statements[0].targets[0].attr, "setpoint")
        self.assertEqual(statements[1].value.attr, "child")

    def test_missing_row_map_rejected(self):
        node, ctx = property_fixture()
        node.property_value_terminal_ids = []
        with self.assertRaisesRegex(CodeGenError, "identities are unresolved"):
            property_node.generate(node, ctx)

    def test_duplicate_row_map_rejected(self):
        node, ctx = property_fixture()
        node.property_value_terminal_ids = ["read_value", "read_value"]
        with self.assertRaisesRegex(CodeGenError, "duplicated"):
            property_node.generate(node, ctx)

    def test_colliding_property_names_rejected(self):
        node, ctx = property_fixture()
        node.properties = [PropertyDef(name="Level"), PropertyDef(name="level")]
        with self.assertRaisesRegex(CodeGenError, "normalized property names"):
            property_node.generate(node, ctx)

    def test_repeated_access_to_same_property_keeps_row_order(self):
        node, ctx = property_fixture()
        node.properties = [PropertyDef(name="Value"), PropertyDef(name="Value")]
        fragment = property_node.generate(node, ctx)
        self.assertEqual(fragment.statements[0].targets[0].attr, "value")
        self.assertEqual(fragment.statements[1].value.attr, "value")

    def test_missing_value_terminal_rejected(self):
        node, ctx = property_fixture()
        node.property_value_terminal_ids[1] = "absent"
        with self.assertRaisesRegex(CodeGenError, "terminal is missing"):
            property_node.generate(node, ctx)

    def test_unwired_write_not_dropped(self):
        node, ctx = property_fixture()
        ctx.is_wired = lambda terminal: terminal != "write_value"
        with self.assertRaisesRegex(CodeGenError, "unwired property write"):
            property_node.generate(node, ctx)

    def test_implicit_control_binding_rejected(self):
        node, ctx = property_fixture()
        node.bound_control_uid = "unknown_control"
        with self.assertRaisesRegex(CodeGenError, "implicit property"):
            property_node.generate(node, ctx)

    def test_unresolved_error_never_becomes_task_reference(self):
        node, ctx = property_fixture()
        ctx.bind("error_in", None)
        with self.assertRaisesRegex(CodeGenError, "error input is unresolved"):
            property_node.generate(node, ctx)

    def test_ast_gate_rejects_hardware_import_and_method_and_dunder(self):
        _, attrs, _ = fragments()
        for source in (
            "import nidaqmx",
            "task.start()",
            "open('x')",
            "x = task.__class__",
            "while True:\n    pass",
        ):
            with self.subTest(source=source):
                with self.assertRaises(AssertionError):
                    audit_fragment(source, attrs, polling=False)

    def test_fake_task_stops_runaway_poll(self):
        sources, attrs, _ = fragments()
        source = sources["poll"].replace(" > 20", " > 40")
        with self.assertRaisesRegex(AssertionError, "exceeded"):
            run_fragment(source, attrs, polling=True)


if __name__ == "__main__":
    unittest.main()
