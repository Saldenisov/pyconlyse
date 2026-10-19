"""False entry is empty for every procedure event, including magnet-zero25."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.event_envelope import procedure_entry


class EventEnvelopeProjectionTests(unittest.TestCase):
    def test_all_23_true_and_false_entries(self):
        for event in range(3, 26):
            for new in (False, True):
                result = procedure_entry(event, new_value=new)
                self.assertIs(result.enters_sequence, new)
                self.assertEqual(
                    result.duration_argument,
                    (1000 if event == 3 else 150) if new else None,
                )

    def test_magnet_zero_keeps_newval_gate_and_special_registration_flags(self):
        self.assertFalse(procedure_entry(25, new_value=False).enters_sequence)
        self.assertEqual(
            procedure_entry(25, new_value=True).registration_flags, -2147483647
        )

    def test_no_timeout_line_event_or_integer_bool_coercion_invented(self):
        with self.assertRaises(ValueError):
            procedure_entry(0, new_value=True)
        with self.assertRaises(TypeError):
            procedure_entry(20, new_value=1)


if __name__ == "__main__":
    unittest.main()
