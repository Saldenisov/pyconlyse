"""Compiler regression gates. Run with the private fork on PYTHONPATH."""

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

from lvkit.codegen.nodes.base import CodeGenError
from lvkit.codegen.nodes.index_array_node import generate as generate_index
from lvkit.codegen.nodes.primitive import generate as generate_primitive
from lvkit.codegen.nodes.reviewed_math import mean_real64_fragment
from lvkit.graph.models import PrimitiveNode, VINode
from lvkit.models import LVType, LVTypeKind, Terminal
from lvkit.pipeline import _generate_polymorphic_module
from lvkit.runtime import lv


def number(name="NumFloat64"):
    return LVType(kind=LVTypeKind.PRIMITIVE, underlying_type=name)


def array(rank, element=None):
    return LVType(kind=LVTypeKind.ARRAY, dimensions=rank, element_type=element or number())


def terminal(index, direction, kind, prefix="t"):
    return Terminal(id=f"{prefix}{index}", index=index, direction=direction, lv_type=kind)


class Context:
    def __init__(self, values, wired):
        self.values, self.wired = values, wired
        self.array_vars, self.imports = set(), set()
        self.graph = SimpleNamespace(
            terminal_is_wired=lambda term: term in self.wired,
            outgoing_edges=lambda term: [SimpleNamespace()],
        )

    def resolve(self, term):
        return self.values.get(term)

    def is_wired(self, term):
        return term in self.wired

    def make_output_var(self, name, node_id, terminal_id=None):
        return "result_" + (terminal_id or node_id)


def evaluate(fragment, bindings):
    tree = ast.fix_missing_locations(ast.Module(body=fragment.statements, type_ignores=[]))
    namespace = {"_lv": lv, **bindings}
    exec(compile(tree, "<generated-regression>", "exec"), namespace)
    return {term: eval(expr, namespace) for term, expr in fragment.bindings.items()}


class ConverterRegressionTests(unittest.TestCase):
    def test_index_separate_six_channel_shot_axes(self):
        terms = [terminal(0, "input", array(3, number("NumInt32")))]
        values, wired = {"t0": "data"}, {"t0"}
        for channel in range(6):
            output = 1 + 4 * channel
            terms.extend([terminal(output, "output", array(1, number("NumInt32"))),
                          terminal(output + 1, "input", number("NumInt32")),
                          terminal(output + 2, "input", number("NumInt32")),
                          terminal(output + 3, "input", number("NumInt32"))])
            wired.update({f"t{output}", f"t{output + 1}", f"t{output + 2}"})
            values[f"t{output + 1}"], values[f"t{output + 2}"] = str(channel), "shot"
        node = PrimitiveNode(id="index", vi_path="fixture.vi", node_type="aIndx", terminals=terms)
        data = [[[100 * c + 10 * s + w for w in range(3)] for s in range(2)] for c in range(6)]
        result = evaluate(generate_index(node, Context(values, wired)), {"data": data, "shot": 1})
        self.assertEqual(list(result.values()), [[100 * c + 10 + w for w in range(3)] for c in range(6)])

    def test_index_disabled_leading_axis(self):
        node = PrimitiveNode(id="index", vi_path="fixture.vi", node_type="aIndx", terminals=[
            terminal(0, "input", array(2)), terminal(1, "output", array(1)),
            terminal(2, "input", number("NumInt32")), terminal(3, "input", number("NumInt32"))])
        result = evaluate(generate_index(node, Context({"t0": "data", "t3": "1"}, {"t0", "t1", "t3"})),
                          {"data": [[1, 2, 3], [4, 5, 6]]})
        self.assertEqual(result["t1"], [2, 5])
        self.assertEqual(lv.index_array_nd([[1, 2], [3, 4]], [None, 5], []), [])
        self.assertEqual(lv.index_array_nd([[1, 2], [3, 4]], [None, -1], []), [])

    def test_index_implicit_1d_outputs_increment_and_default(self):
        node = PrimitiveNode(id="index", vi_path="fixture.vi", node_type="aIndx", terminals=[
            terminal(0, "input", array(1)), terminal(1, "output", number()),
            terminal(2, "input", number("NumInt32")), terminal(3, "output", number()),
            terminal(4, "input", number("NumInt32")), terminal(5, "output", number()),
            terminal(6, "input", number("NumInt32"))])
        result = evaluate(generate_index(node, Context({"t0": "data"}, {"t0", "t1", "t3", "t5"})),
                          {"data": [7, 9]})
        self.assertEqual(list(result.values()), [7, 9, 0.0])

    def test_index_unknown_implicit_dimension_rejected(self):
        node = PrimitiveNode(id="index", vi_path="fixture.vi", node_type="aIndx", terminals=[
            terminal(0, "input", array(3)), terminal(1, "output", number()),
            terminal(2, "input", number("NumInt32")), terminal(3, "input", number("NumInt32")),
            terminal(4, "input", number("NumInt32"))])
        with self.assertRaises(CodeGenError):
            generate_index(node, Context({"t0": "data", "t2": "0"}, {"t0", "t1", "t2"}))

    def test_i32_array_divide_produces_dbl_ieee_values(self):
        node = PrimitiveNode(id="divide", vi_path="fixture.vi", node_type="prim", prim_id=1053, terminals=[
            terminal(0, "output", array(1)), terminal(1, "input", array(1, number("NumInt32"))),
            terminal(2, "input", array(1, number("NumInt32")))])
        result = evaluate(generate_primitive(node, Context({"t1": "den", "t2": "num"}, {"t0", "t1", "t2"})),
                          {"num": [2, 0, -3], "den": [1, 0, 0]})["t0"]
        self.assertEqual(result[0], 2.0)
        self.assertTrue(result[1] != result[1])
        self.assertEqual(result[2], -float("inf"))

    def test_single_consumer_array_multiply_does_not_inline_scalar_operator(self):
        node = PrimitiveNode(id="multiply", vi_path="fixture.vi", node_type="prim", prim_id=1052, terminals=[
            terminal(0, "output", array(1)), terminal(1, "input", array(1)), terminal(2, "input", number())])
        result = evaluate(generate_primitive(node, Context({"t1": "row", "t2": "factor"}, {"t0", "t1", "t2"})),
                          {"row": [1, -3], "factor": 2.5})
        self.assertEqual(result["t0"], [2.5, -7.5])

    def mean_node(self):
        return VINode(id="mean", vi_path="fixture.vi", name="Mean.vi",
                      qualified_path="<vilib>/analysis/baseanly.llb/Mean (DBL).vi", terminals=[
                          terminal(0, "input", array(1)), terminal(1, "output", number()),
                          terminal(2, "output", number("NumInt32"))])

    def test_mean_numeric_contract_and_empty(self):
        node, ctx = self.mean_node(), Context({"t0": "values"}, {"t0", "t1"})
        self.assertEqual(evaluate(mean_real64_fragment(node, ctx), {"values": [2, 6]})["t1"], 4.0)
        value = evaluate(mean_real64_fragment(node, ctx), {"values": []})["t1"]
        self.assertTrue(value != value)

    def test_mean_error_and_type_are_not_silently_mapped(self):
        node = self.mean_node()
        with self.assertRaises(CodeGenError):
            mean_real64_fragment(node, Context({"t0": "values"}, {"t0", "t1", "t2"}))
        node.terminals[0].lv_type = array(1, number("NumFloat32"))
        with self.assertRaises(CodeGenError):
            mean_real64_fragment(node, Context({"t0": "values"}, {"t0", "t1"}))

    def test_local_same_named_mean_is_not_ni_mean(self):
        node = self.mean_node()
        node.qualified_path = "C:/dev/user/Mean (DBL).vi"
        self.assertIsNone(mean_real64_fragment(node, Context({}, set())))

    def test_windows_wrapper_escaping_and_missing_variant(self):
        graph = SimpleNamespace(get_vi_context=lambda name: SimpleNamespace(inputs=[], outputs=[]))
        code = _generate_polymorphic_module(
            r"C:\National Instruments\Utility\wrapper.vi", ["Missing.vi"], graph,
            None, "fixture", Path("unused"), {})
        namespace = {}
        exec(compile(code, "<windows-wrapper>", "exec"), namespace)
        with self.assertRaises(NotImplementedError):
            namespace["wrapper"]([1])
        with self.assertRaises(NotImplementedError):
            namespace["missing"]([1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
