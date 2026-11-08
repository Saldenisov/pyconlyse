"""Non-actuating checks for the saved Supervision Page HT event selector."""

import unittest

from DeviceServers.control.elyse_acq.supervision_requests import (
    FLUIDES_DPS_COMMAND_FIELDS,
    FLUIDES_TEMPERATURE_BUTTON_FIELDS,
    HT_ADJUSTMENT_FIELD_INDEXES,
    HT_DPS_COMMAND_FIELDS,
    MODULATOR_DPS_COMMAND_FIELDS,
    MAGNET_DPS_COMMAND_FIELDS,
    HF_ADJUSTMENT_FIELD_INDEXES,
    HF_DPS_COMMAND_FIELDS,
    page_ht_event_selects_dps_branch,
    project_page_fluides_dps_write,
    project_page_ht_dps_write,
    project_page_modulator_dps_write,
    project_page_alimentations_dps_write,
    project_page_hf_dps_write,
)
from DeviceServers.control.elyse_acq.dps_bridge import first_asserted_dps_request


class PageHtRequestGateTests(unittest.TestCase):
    def test_only_idle_request_and_adjustment_banks_select_dps_branch(self):
        self.assertEqual(
            HT_ADJUSTMENT_FIELD_INDEXES, (15, 13, 14, 16, 21, 19, 20, 22)
        )
        self.assertTrue(page_ht_event_selects_dps_branch([False] * 29, [False] * 8))
        for index in range(29):
            bank = [False] * 29
            bank[index] = True
            with self.subTest(pending_dps=index):
                self.assertFalse(page_ht_event_selects_dps_branch(bank, [False] * 8))
        for index in range(8):
            buttons = [False] * 8
            buttons[index] = True
            with self.subTest(ht_adjustment=index):
                self.assertFalse(page_ht_event_selects_dps_branch([False] * 29, buttons))

    def test_rejects_wrong_bank_shapes_and_non_boolean_values(self):
        bad_dps = ([False] * 28, [False] * 30, [False] * 28 + [1])
        bad_buttons = ([False] * 7, [False] * 9, [False] * 7 + [1])
        for bank in bad_dps:
            with self.subTest(dps=bank):
                with self.assertRaises(ValueError):
                    page_ht_event_selects_dps_branch(bank, [False] * 8)
        for buttons in bad_buttons:
            with self.subTest(buttons=buttons):
                with self.assertRaises(ValueError):
                    page_ht_event_selects_dps_branch([False] * 29, buttons)

    def test_five_button_fields_project_to_dps_and_acq_case_20(self):
        self.assertEqual(
            HT_DPS_COMMAND_FIELDS,
            ((10, 15), (11, 17), (9, 16), (25, 18), (24, 19)),
        )
        for position, (_, dps_index) in enumerate(HT_DPS_COMMAND_FIELDS):
            buttons = [False] * 5
            buttons[position] = True
            snapshot = project_page_ht_dps_write(
                [False] * 29, [False] * 8, buttons
            )
            with self.subTest(dps_index=dps_index):
                self.assertEqual(
                    snapshot,
                    tuple(index == dps_index for index in range(29)),
                )
        start = project_page_ht_dps_write(
            [False] * 29, [False] * 8, [True, False, False, False, False]
        )
        self.assertEqual(first_asserted_dps_request(start[:24]).legacy_event_case, 20)

    def test_busy_gate_has_no_dps_write_and_invalid_buttons_fail(self):
        pending = [False] * 29
        pending[0] = True
        self.assertIsNone(
            project_page_ht_dps_write(pending, [False] * 8, [True] * 5)
        )
        arrows = [False] * 8
        arrows[0] = True
        self.assertIsNone(
            project_page_ht_dps_write([False] * 29, arrows, [True] * 5)
        )
        for buttons in ([False] * 4, [False] * 6, [False] * 4 + [1]):
            with self.subTest(buttons=buttons):
                with self.assertRaises(ValueError):
                    project_page_ht_dps_write([False] * 29, [False] * 8, buttons)

    def test_idle_event_writes_false_fields_without_mutating_input(self):
        pending = [False] * 29
        result = project_page_ht_dps_write(
            pending, [False] * 8, [False] * 5
        )
        self.assertEqual(result, tuple([False] * 29))
        self.assertEqual(pending, [False] * 29)

    def test_modulator_buttons_project_all_eleven_dps_fields(self):
        self.assertEqual(
            MODULATOR_DPS_COMMAND_FIELDS,
            ((22, 2), (23, 3), (46, 4), (47, 5), (48, 6), (49, 7),
             (50, 8), (51, 9), (52, 10), (53, 11), (21, 12)),
        )
        for position, (_, dps_index) in enumerate(MODULATOR_DPS_COMMAND_FIELDS):
            buttons = [False] * 11
            buttons[position] = True
            result = project_page_modulator_dps_write([False] * 29, buttons)
            with self.subTest(dps_index=dps_index):
                self.assertEqual(
                    result, tuple(index == dps_index for index in range(29))
                )
        general_start = project_page_modulator_dps_write(
            [False] * 29, [True] + [False] * 10
        )
        self.assertEqual(
            first_asserted_dps_request(general_start[:24]).legacy_event_case, 5
        )

    def test_modulator_busy_gate_and_invalid_inputs(self):
        self.assertEqual(
            project_page_modulator_dps_write([False] * 29, [False] * 11),
            tuple([False] * 29),
        )
        for index in range(29):
            pending = [False] * 29
            pending[index] = True
            with self.subTest(pending=index):
                self.assertIsNone(
                    project_page_modulator_dps_write(pending, [True] * 11)
                )
        for pending, buttons in (
            ([False] * 28, [False] * 11),
            ([False] * 28 + [1], [False] * 11),
            ([False] * 29, [False] * 10),
            ([False] * 29, [False] * 10 + [1]),
        ):
            with self.subTest(pending=pending, buttons=buttons):
                with self.assertRaises(ValueError):
                    project_page_modulator_dps_write(pending, buttons)

    def test_five_modulator_start_buttons_map_to_distinct_acq_cases(self):
        for position, expected_case in ((0, 5), (2, 12), (4, 13), (6, 14), (8, 15)):
            buttons = [False] * 11
            buttons[position] = True
            snapshot = project_page_modulator_dps_write(
                [False] * 29, buttons
            )
            with self.subTest(position=position):
                self.assertEqual(
                    first_asserted_dps_request(snapshot[:24]).legacy_event_case,
                    expected_case,
                )

    def test_simultaneous_general_start_and_stop_select_start_first(self):
        buttons = [True, True] + [False] * 9
        snapshot = project_page_modulator_dps_write([False] * 29, buttons)
        self.assertTrue(snapshot[2])
        self.assertTrue(snapshot[3])
        self.assertEqual(
            first_asserted_dps_request(snapshot[:24]).legacy_event_case, 5
        )


class PageFluidesRequestGateTests(unittest.TestCase):
    def test_idle_branch_maps_start_and_stop_to_acq_cases(self):
        self.assertEqual(FLUIDES_TEMPERATURE_BUTTON_FIELDS, (7, 6, 20, 19))
        self.assertEqual(FLUIDES_DPS_COMMAND_FIELDS, ((9, 0), (8, 1)))
        for buttons, expected_field, expected_case in (
            ((True, False), 0, 3),
            ((False, True), 1, 4),
        ):
            with self.subTest(buttons=buttons):
                result = project_page_fluides_dps_write(
                    [False] * 29, [False] * 4, buttons
                )
                self.assertEqual(result, tuple(i == expected_field for i in range(29)))
                self.assertEqual(
                    first_asserted_dps_request(result[:24]).legacy_event_case,
                    expected_case,
                )

    def test_any_pending_request_or_temperature_button_skips_cooling_write(self):
        for index in range(29):
            pending = [False] * 29
            pending[index] = True
            with self.subTest(pending=index):
                self.assertIsNone(
                    project_page_fluides_dps_write(
                        pending, [False] * 4, [True, False]
                    )
                )
        for index in range(4):
            adjustments = [False] * 4
            adjustments[index] = True
            with self.subTest(adjustment=index):
                self.assertIsNone(
                    project_page_fluides_dps_write(
                        [False] * 29, adjustments, [True, False]
                    )
                )

    def test_idle_all_false_still_projects_write_and_preserves_input(self):
        pending = [False] * 29
        self.assertEqual(
            project_page_fluides_dps_write(pending, [False] * 4, [False] * 2),
            tuple([False] * 29),
        )
        self.assertEqual(pending, [False] * 29)

    def test_simultaneous_start_stop_selects_acq_start_first(self):
        result = project_page_fluides_dps_write(
            [False] * 29, [False] * 4, [True, True]
        )
        self.assertEqual(result[:2], (True, True))
        self.assertEqual(first_asserted_dps_request(result[:24]).legacy_event_case, 3)

    def test_rejects_invalid_shapes_and_non_boolean_values(self):
        for pending, adjustments, buttons in (
            ([False] * 28, [False] * 4, [False] * 2),
            ([False] * 28 + [1], [False] * 4, [False] * 2),
            ([False] * 29, [False] * 3, [False] * 2),
            ([False] * 29, [False] * 3 + [1], [False] * 2),
            ([False] * 29, [False] * 4, [False]),
            ([False] * 29, [False] * 4, [False, 1]),
        ):
            with self.subTest(pending=pending, adjustments=adjustments, buttons=buttons):
                with self.assertRaises(ValueError):
                    project_page_fluides_dps_write(pending, adjustments, buttons)


class PageAlimentationsRequestGateTests(unittest.TestCase):
    def test_three_buttons_match_saved_dps_fields_and_acq_cases(self):
        self.assertEqual(MAGNET_DPS_COMMAND_FIELDS, (20, 23, 21))
        for button_index, expected_field, expected_case in (
            (0, 20, 16), (1, 23, 17), (2, 21, 25)
        ):
            buttons = [False] * 3
            buttons[button_index] = True
            result = project_page_alimentations_dps_write([False] * 29, buttons)
            with self.subTest(button_index=button_index):
                self.assertEqual(result, tuple(i == expected_field for i in range(29)))
                self.assertEqual(
                    first_asserted_dps_request(result[:24]).legacy_event_case,
                    expected_case,
                )

    def test_pending_request_skips_magnet_write_including_orphaned_pt(self):
        for index in range(29):
            pending = [False] * 29
            pending[index] = True
            with self.subTest(pending=index):
                self.assertIsNone(
                    project_page_alimentations_dps_write(pending, [True, False, False])
                )

    def test_idle_false_write_and_simultaneous_button_priority(self):
        pending = [False] * 29
        self.assertEqual(
            project_page_alimentations_dps_write(pending, [False] * 3),
            tuple([False] * 29),
        )
        self.assertEqual(pending, [False] * 29)
        result = project_page_alimentations_dps_write(
            [False] * 29, [True, True, True]
        )
        self.assertEqual((result[20], result[21], result[23]), (True, True, True))
        self.assertEqual(first_asserted_dps_request(result[:24]).legacy_event_case, 16)

    def test_rejects_invalid_dps_or_button_vector(self):
        for pending, buttons in (
            ([False] * 28, [False] * 3),
            ([False] * 28 + [1], [False] * 3),
            ([False] * 29, [False] * 2),
            ([False] * 29, [False] * 2 + [1]),
        ):
            with self.subTest(pending=pending, buttons=buttons):
                with self.assertRaises(ValueError):
                    project_page_alimentations_dps_write(pending, buttons)


class PageHfRequestGateTests(unittest.TestCase):
    def test_two_hf_commands_map_to_acq_cases(self):
        self.assertEqual(HF_ADJUSTMENT_FIELD_INDEXES, (2, 4, 3, 1, 14, 16, 15, 13))
        self.assertEqual(HF_DPS_COMMAND_FIELDS, ((7, 13), (6, 14)))
        for buttons, expected_field, expected_case in (
            ((True, False), 13, 18),
            ((False, True), 14, 19),
        ):
            result = project_page_hf_dps_write(
                [False] * 29, [False] * 8, buttons
            )
            with self.subTest(buttons=buttons):
                self.assertEqual(result, tuple(i == expected_field for i in range(29)))
                self.assertEqual(
                    first_asserted_dps_request(result[:24]).legacy_event_case,
                    expected_case,
                )

    def test_any_pending_request_or_hf_arrow_skips_dps_write(self):
        for index in range(29):
            pending = [False] * 29
            pending[index] = True
            with self.subTest(pending=index):
                self.assertIsNone(
                    project_page_hf_dps_write(pending, [False] * 8, [True, False])
                )
        for index in range(8):
            arrows = [False] * 8
            arrows[index] = True
            with self.subTest(arrow=index):
                self.assertIsNone(
                    project_page_hf_dps_write([False] * 29, arrows, [True, False])
                )

    def test_idle_false_write_and_simultaneous_button_priority(self):
        pending = [False] * 29
        self.assertEqual(
            project_page_hf_dps_write(pending, [False] * 8, [False] * 2),
            tuple([False] * 29),
        )
        self.assertEqual(pending, [False] * 29)
        result = project_page_hf_dps_write(
            [False] * 29, [False] * 8, [True, True]
        )
        self.assertEqual((result[13], result[14]), (True, True))
        self.assertEqual(first_asserted_dps_request(result[:24]).legacy_event_case, 18)

    def test_rejects_invalid_shapes_and_non_boolean_values(self):
        for pending, arrows, buttons in (
            ([False] * 28, [False] * 8, [False] * 2),
            ([False] * 28 + [1], [False] * 8, [False] * 2),
            ([False] * 29, [False] * 7, [False] * 2),
            ([False] * 29, [False] * 7 + [1], [False] * 2),
            ([False] * 29, [False] * 8, [False]),
            ([False] * 29, [False] * 8, [False, 1]),
        ):
            with self.subTest(pending=pending, arrows=arrows, buttons=buttons):
                with self.assertRaises(ValueError):
                    project_page_hf_dps_write(pending, arrows, buttons)


if __name__ == "__main__":
    unittest.main()
