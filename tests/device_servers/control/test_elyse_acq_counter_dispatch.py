import unittest

from DeviceServers.control.elyse_acq.counter_dispatch import (
    changed_timing_commands,
    decode_counter_request,
    decode_supervision_counter_request,
)


class CounterDispatchTests(unittest.TestCase):
    def setUp(self):
        self.fields = list(range(32))

    def test_all_integer_commands_map_to_eight_c10_pairs(self):
        for number in range(1, 17):
            with self.subTest(number=number):
                result = decode_counter_request(number, self.fields)
                index = (number - 1) // 2
                self.assertEqual(result.owner, "acquisition")
                self.assertEqual(result.counter_index, index)
                self.assertEqual(result.task_name, f"C10_NI6602.ctr{index}")
                self.assertEqual(result.delay_field_index, 2 * index)
                self.assertEqual(result.width_field_index, 2 * index + 1)
                self.assertEqual(result.delay_microseconds, float(2 * index))
                self.assertEqual(result.width_microseconds, float(2 * index + 1))

    def test_c11_half_has_no_effect_on_saved_vi_request(self):
        original = decode_counter_request(16, self.fields)
        changed_c11 = self.fields[:16] + [999.0] * 16
        self.assertEqual(original, decode_counter_request(16, changed_c11))

    def test_supervision_commands_map_to_eight_local_c11_pairs(self):
        for number in range(17, 33):
            with self.subTest(number=number):
                result = decode_supervision_counter_request(number, self.fields)
                index = (number - 17) // 2
                self.assertEqual(result.owner, "supervision")
                self.assertEqual(result.counter_index, index)
                self.assertEqual(result.task_name, f"SUPERVISION.Dev1/ctr{index}")
                self.assertEqual(result.delay_field_index, 16 + 2 * index)
                self.assertEqual(result.width_field_index, 17 + 2 * index)
                self.assertEqual(result.delay_microseconds, float(16 + 2 * index))
                self.assertEqual(result.width_microseconds, float(17 + 2 * index))

    def test_c10_half_has_no_effect_on_saved_supervision_request(self):
        original = decode_supervision_counter_request(17, self.fields)
        changed_c10 = [999.0] * 16 + self.fields[16:]
        self.assertEqual(original, decode_supervision_counter_request(17, changed_c10))

    def test_reject_unverified_or_out_of_range_numbers(self):
        for number in (0, 17, 1.5, True, "1"):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    decode_counter_request(number, self.fields)

    def test_reject_short_bank(self):
        with self.assertRaises(ValueError):
            decode_counter_request(1, self.fields[:15])
        with self.assertRaises(ValueError):
            decode_supervision_counter_request(17, self.fields[:31])

    def test_reject_unverified_supervision_numbers(self):
        for number in (16, 33, 17.5, True, "17"):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    decode_supervision_counter_request(number, self.fields)

    def test_supervision_delta_loop_emits_one_based_changed_indices_in_order(self):
        before = [0.0] * 33
        after = list(before)
        for index in (0, 15, 16, 31):
            after[index] = float(index + 1)
        self.assertEqual(changed_timing_commands(before, after), (1, 16, 17, 32))
        self.assertEqual(changed_timing_commands(after, after), ())

    def test_selector_field_change_would_emit_unmapped_command_33(self):
        before = [0.0] * 33
        after = list(before)
        after[32] = 1.0
        self.assertEqual(changed_timing_commands(before, after), (33,))
        with self.assertRaises(ValueError):
            decode_supervision_counter_request(33, after)

    def test_delta_loop_rejects_wrong_size(self):
        with self.assertRaises(ValueError):
            changed_timing_commands([0.0] * 32, [0.0] * 32)


if __name__ == "__main__":
    unittest.main()
