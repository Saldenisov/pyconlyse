"""Shared body arithmetic, lazy error bypass and explicit Python domain policy."""

import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from elyse_agent.saved_xnode import ErrorValue, evaluate_saved_xnode, replay_saved_xnode


class Poison(object):
    def __iter__(self):
        raise AssertionError("upstream-error branch accessed formula inputs")

    def __float__(self):
        raise AssertionError("upstream-error branch converted formula inputs")


class SavedXNodeTests(unittest.TestCase):
    def test_unequal_four_inputs_detect_axis_and_input_order(self):
        error = ErrorValue(False, -17, "warning is not an error status")
        values = (2.0, 5.0, 11.0, 17.0)
        for uid, numerator in (("37034", 240), ("36467", 120), ("47576", 120)):
            result = evaluate_saved_xnode(uid, values, error)
            self.assertAlmostEqual(
                result.result, float(Fraction(numerator, 35)), places=14
            )
            self.assertIs(result.error_out, error)

    def test_exponentials_use_exp_minus_11_not_power_of_ten(self):
        with localcontext() as context:
            context.prec = 60
            for uid, scale, slope in (
                ("50983", "2.45", "0.85"),
                ("58520", "1.333", "1.2"),
            ):
                for x1 in (-4.0, 0.0, 8.0):
                    oracle = (
                        Decimal(scale)
                        * Decimal(-11).exp()
                        * (Decimal(slope) * Decimal(x1)).exp()
                    )
                    value = evaluate_saved_xnode(
                        uid, (x1,), ErrorValue(False, 8201, "source")
                    )
                    self.assertLess(abs(value.result / float(oracle) - 1), 2e-14)

    def test_true_status_bypasses_even_invalid_or_poisoned_inputs(self):
        for uid in ("50983", "58520", "37034", "36467", "47576"):
            for code in (0, -17, 8201):
                error = ErrorValue(True, code, "upstream disconnect")
                result = evaluate_saved_xnode(uid, Poison(), error)
                self.assertEqual(result.result, 0.0)
                self.assertIs(result.error_out, error)

    def test_nonboolean_status_never_coerced(self):
        for status in (0, 1, None, "False"):
            with self.assertRaises(TypeError):
                evaluate_saved_xnode("36467", (1.0,) * 4, ErrorValue(status, 0, ""))

    def test_bad_error_fields_are_python_refusals(self):
        for code in (True, 0.0, 2**31, -(2**31) - 1):
            with self.assertRaises(ValueError):
                evaluate_saved_xnode("36467", (1.0,) * 4, ErrorValue(False, code, ""))
        with self.assertRaises(TypeError):
            evaluate_saved_xnode("36467", (1.0,) * 4, ErrorValue(False, 0, None))

    def test_unknown_source_or_uid_never_falls_back_to_other_formula(self):
        for uid in ("APP-17::36467", "45051", 36467, None):
            with self.assertRaises(ValueError):
                evaluate_saved_xnode(uid, Poison(), ErrorValue(True, 0, ""))
        with self.assertRaises(ValueError):
            replay_saved_xnode(
                dict(
                    source_id="APP-00",
                    uid="36467",
                    inputs=[1] * 4,
                    error_in=dict(status=False, code=0, source=""),
                )
            )

    def test_unqualified_domains_are_not_zero_defaults(self):
        error = ErrorValue(False, 0, "")
        for values in (
            (1.0, -1.0, 1.0, -1.0),
            (float("inf"),) * 4,
            (float("nan"),) * 4,
            (20.0,) * 4,
            (True,) * 4,
            (0.0, 1e-323, -1.0, 1.0),
        ):
            with self.assertRaises(ValueError):
                evaluate_saved_xnode("36467", values, error)
        for values in ((), (1.0,), [1.0] * 4, None):
            with self.assertRaises(TypeError):
                evaluate_saved_xnode("36467", values, error)
        for value in (-4.0001, 8.0001):
            with self.assertRaises(ValueError):
                evaluate_saved_xnode("50983", (value,), error)

    def test_json_adapter_normalization_does_not_assert_telemetry(self):
        payload = dict(
            source_id="APP-17",
            uid="36467",
            inputs=[2, 5, 11, 17],
            error_in=dict(status=False, code=44, source="source"),
        )
        result = replay_saved_xnode(payload)
        self.assertEqual(result["error_out"], payload["error_in"])
        self.assertFalse(result["acquired_data_bound"])
        self.assertFalse(result["native_runtime_equivalence_qualified"])
        self.assertFalse(result["inactive_saved_body"])
        self.assertEqual(payload["inputs"], [2, 5, 11, 17])
        payload.update(uid="50983", inputs=[0])
        self.assertTrue(replay_saved_xnode(payload)["inactive_saved_body"])
        payload.update(inputs=Poison(), error_in=dict(status=True, code=0, source=""))
        self.assertEqual(replay_saved_xnode(payload)["result"], 0.0)

    def test_json_adapter_rejects_boolean_numbers_extra_keys_and_huge_int(self):
        payload = dict(
            source_id="APP-17",
            uid="50983",
            inputs=[False],
            error_in=dict(status=False, code=0, source=""),
        )
        with self.assertRaises(TypeError):
            replay_saved_xnode(payload)
        payload.update(inputs=[10**1000])
        with self.assertRaises(ValueError):
            replay_saved_xnode(payload)
        payload.update(inputs=[0], hardware=True)
        with self.assertRaises(ValueError):
            replay_saved_xnode(payload)


if __name__ == "__main__":
    unittest.main()
