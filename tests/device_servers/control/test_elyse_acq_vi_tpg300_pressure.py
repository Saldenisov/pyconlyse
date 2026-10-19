"""Golden string/wiring projections; numeric returns remain supplied fixtures."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    ErrorCluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_pressure import (
    ROOT_READS,
    PressureReturn,
    pressure_command,
    pressure_parse_inputs,
    pressure_publication_fault,
    root_pressure_assignment,
    separator_step,
)


class PressureProjectionTests(unittest.TestCase):
    def test_four_commands(self):
        self.assertEqual(
            [pressure_command(i) for i in range(4)], ["PA1", "PA2", "PB1", "PB2"]
        )

    def test_all_periods_replaced_before_first_comma_split(self):
        value = pressure_parse_inputs("0,1.23E-5")
        self.assertEqual(
            (value.normalized_response, value.status_string, value.pressure_string),
            ("0,1,23E-5", "0", "1,23E-5"),
        )
        self.assertTrue(value.use_system_decimal_point)
        self.assertEqual(pressure_parse_inputs("0,1.2.3").pressure_string, "1,2,3")

    def test_separator_feedback_and_final_no_match(self):
        first = separator_step(".x.", 0)
        self.assertEqual(
            (first.text, first.offset, first.keep_running), (",x.", 1, True)
        )
        second = separator_step(first.text, first.offset)
        self.assertEqual(
            (second.text, second.offset, second.keep_running), (",x,", 3, True)
        )
        last = separator_step(second.text, second.offset)
        self.assertEqual(
            (last.text, last.offset, last.keep_running), (",x,", -1, False)
        )

    def test_empty_and_missing_separator_do_not_invent_numeric_values(self):
        for response in ("", "timeout", "123"):
            value = pressure_parse_inputs(response)
            self.assertEqual(value.status_string, response)
            self.assertEqual(value.pressure_string, "")

    def test_error_and_nonzero_sensor_status_do_not_gate_assignment(self):
        for status in (0, 5, -1):
            for error in (NO_ERROR, ErrorCluster(True, -1, "fixture")):
                for _, uid, _, _, bank in ROOT_READS:
                    assigned = root_pressure_assignment(
                        uid, PressureReturn(status, 0.0, error)
                    )
                    self.assertEqual((assigned.bank, assigned.pressure), (bank, 0.0))
                    self.assertIs(assigned.error_handler_input, error)

    def test_independent_calls_share_session_without_forcing_order(self):
        self.assertEqual(
            ROOT_READS,
            (
                ("48320", "46178", 52, 0, 53),
                ("48320", "53865", 51, 0, 54),
                ("52460", "52475", 51, 3, 60),
            ),
        )

    def test_python_only_fixture_domain_guards(self):
        for sensor in (-1, 4, True):
            with self.assertRaises(ValueError):
                pressure_command(sensor)
        with self.assertRaises(ValueError):
            pressure_parse_inputs("é")
        with self.assertRaises(ValueError):
            separator_step("x", -1)
        with self.assertRaises(ValueError):
            PressureReturn(2**31, 0.0, NO_ERROR)
        with self.assertRaises(TypeError):
            root_pressure_assignment("46178", None)
        with self.assertRaises(ValueError):
            root_pressure_assignment("unknown", PressureReturn(0, 0.0, NO_ERROR))

    def test_publication_fault_sets_both_stops_without_success_reset(self):
        self.assertEqual(
            pressure_publication_fault(ErrorCluster(True, -1)), ((30, True), (45, True))
        )
        self.assertEqual(pressure_publication_fault(NO_ERROR), ())
        self.assertEqual(pressure_publication_fault(ErrorCluster(False, 1)), ())


if __name__ == "__main__":
    unittest.main()
