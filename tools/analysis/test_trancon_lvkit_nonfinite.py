"""Regression gates for executable scalar NaN/Inf constants in lvkit."""

import math
import unittest

from lvkit.codegen.context import _decode_numeric_constant, _format_constant
from lvkit.graph.models import Constant
from lvkit.models import LVType, LVTypeKind


class NonfiniteConstantTests(unittest.TestCase):
    def assert_number(self, expression, expected):
        actual = eval(expression, {})
        if math.isnan(expected):
            self.assertTrue(math.isnan(actual))
        else:
            self.assertEqual(actual, expected)
            self.assertEqual(math.copysign(1, actual), math.copysign(1, expected))

    def test_scalar_decimal_and_hex_nonfinite_constants(self):
        for value, expected in (("nan", float("nan")), ("inf", float("inf")),
                                ("-inf", -float("inf")), ("-0.0", -0.0),
                                ("7FF8000000000000", float("nan")),
                                ("7FF0000000000000", float("inf")),
                                ("FFF0000000000000", -float("inf"))):
            with self.subTest(value=value):
                self.assert_number(_decode_numeric_constant(value, "NumFloat64"), expected)

    def test_already_decoded_floats_are_executable(self):
        kind = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="NumFloat64")
        for value in (float("nan"), float("inf"), -float("inf"), -0.0, 2.5):
            self.assert_number(_format_constant(Constant(id="scalar", value=value, lv_type=kind)), value)

    def test_text_nan_remains_text(self):
        kind = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="String")
        self.assertEqual(eval(_format_constant(Constant(id="text", value="nan", lv_type=kind))), "nan")


if __name__ == "__main__":
    unittest.main(verbosity=2)
