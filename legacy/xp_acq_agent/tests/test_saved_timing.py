"""Python 3.4 strict replay types and pure adapter behavior."""
import unittest

from elyse_agent.saved_timing import (Timing, evaluate_saved_timing, replay_saved_timing,
                                     timing_from_json, timing_to_json)
from elyse_agent.saved_xnode import ErrorValue


class SavedTimingTests(unittest.TestCase):
    def config(self):
        return timing_to_json(evaluate_saved_timing("19070"))

    def test_config_saved_body_ignores_input_values(self):
        self.assertEqual(evaluate_saved_timing("19070", object()).period, 1000)
        result = replay_saved_timing(dict(source_id="APP-17", uid="19070",
                                        inputs=dict(source_name=["unused"], period=None)))
        self.assertEqual(result["outputs"]["timing"], self.config())
        self.assertFalse(result["scheduler_execution_qualified"])
        self.assertFalse(result["runtime_defaults_qualified"])

    def test_right_constant_and_nested_error_are_immutable(self):
        value = evaluate_saved_timing("32991")
        self.assertEqual((value.period, value.timeout, value.mode, value.assigned_cpu), (-1, 0, 0, -1))
        with self.assertRaises(AttributeError):
            value.error.status = True
        self.assertEqual(value.error, ErrorValue(False, 0, ""))

    def test_late_projection_does_not_inspect_other_fields(self):
        timing = Timing(*([object()] * 29))._replace(finished_late_i_1=True)
        self.assertIs(evaluate_saved_timing("32954", timing), True)
        timing = timing._replace(finished_late_i_1=False, error=ErrorValue(True, -17, "fault"))
        self.assertIs(evaluate_saved_timing("32954", timing), False)
        self.assertEqual(timing.error, ErrorValue(True, -17, "fault"))

    def test_all_fields_roundtrip_including_ones_after_nested_error(self):
        raw = self.config()
        raw.update(source_type="selected direct field21", secondary_source_type="field22",
                   global_end_time=2**64 - 1, period=-(2**63), priority=2**31 - 1,
                   assigned_cpu=-(2**31), mode=2**32 - 1, error=dict(status=True, code=-17, source="fault"))
        self.assertEqual(timing_to_json(timing_from_json(raw)), raw)

    def test_exact_schema_and_unqualified_uid_refuse(self):
        for uid in ("19142", "17671", "62172", 19070):
            with self.assertRaises(ValueError):
                evaluate_saved_timing(uid)
        for change in (dict(unexpected=1), dict(source_id="APP-16")):
            payload = dict(source_id="APP-17", uid="32991", inputs={})
            payload.update(change)
            with self.assertRaises(ValueError):
                replay_saved_timing(payload)
        with self.assertRaises(ValueError):
            replay_saved_timing(dict(source_id="APP-17", uid="32991", inputs=dict(period=1)))

    def test_required_full_timing_and_strict_selected_boolean(self):
        raw = self.config()
        raw.pop("source_type")
        with self.assertRaises(ValueError):
            timing_from_json(raw)
        for value in (0, 1, None, "True"):
            raw = self.config()
            raw["finished_late_i_1"] = value
            with self.assertRaises(TypeError):
                timing_from_json(raw)
        with self.assertRaises(TypeError):
            evaluate_saved_timing("32954", tuple(evaluate_saved_timing("19070")))

    def test_integer_storage_ranges_and_boolean_rejection(self):
        for name, values in (("global_end_time", (-1, 2**64, True)),
                             ("period", (-(2**63)-1, 2**63, 1.0)),
                             ("priority", (-(2**31)-1, 2**31, False)),
                             ("mode", (-1, 2**32, "2"))):
            for value in values:
                raw = self.config()
                raw[name] = value
                with self.assertRaises(ValueError):
                    timing_from_json(raw)

    def test_error_storage_types_and_shape_refuse(self):
        for error in (None, dict(status=1, code=0, source=""),
                      dict(status=False, code=True, source=""),
                      dict(status=False, code=2**31, source=""),
                      dict(status=False, code=0, source=None)):
            raw = self.config()
            raw["error"] = error
            with self.assertRaises((ValueError, TypeError)):
                timing_from_json(raw)


if __name__ == "__main__":
    unittest.main()
