import unittest

from supervision_reconstruction.domain.dialog_error import (
    DIALOG_ERROR_EFFECTS_BLOCKED,
    DialogType,
    ThreeButtonChoice,
    classify_general_error,
    plan_general_error_handler_core,
    plan_not_found_dialog,
    plan_three_button_dialog_core,
    remap_general_error_handler_dialog_type,
)
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster


class DialogErrorTests(unittest.TestCase):
    def test_wrapper_remaps_exact_five_localized_ring_frames(self) -> None:
        self.assertEqual(
            [remap_general_error_handler_dialog_type(value) for value in range(5)],
            [
                DialogType.NO_DIALOG,
                DialogType.OK_MESSAGE,
                DialogType.CONTINUE_OR_STOP_MESSAGE,
                DialogType.OK_MESSAGE_WITH_WARNINGS,
                DialogType.CONTINUE_STOP_WITH_WARNINGS,
            ],
        )
        for value in (-1, 5, True):
            with self.assertRaises(ValueError):
                remap_general_error_handler_dialog_type(value)

    def test_incoming_status_wins_then_local_code_substitutes_only_without_status(self) -> None:
        incoming = ErrorCluster(True, -7, "incoming")
        selected = classify_general_error(
            local_error_code=99, local_error_source="local", error_in=incoming,
            exception_action=0, exception_code=0, exception_source="",
        )
        self.assertEqual(selected.error_out, incoming)
        self.assertFalse(selected.local_error_substituted)

        local = classify_general_error(
            local_error_code=99, local_error_source="local", error_in=ErrorCluster(False, 4, "old"),
            exception_action=0, exception_code=0, exception_source="",
        )
        self.assertEqual(local.error_out, ErrorCluster(True, 99, "local"))
        self.assertTrue(local.local_error_substituted)

    def test_exception_action_one_clears_code_with_empty_or_matching_source_only(self) -> None:
        common = dict(local_error_code=9, local_error_source="chosen", error_in=ErrorCluster(False, 0, ""), exception_code=9)
        for source in ("", "chosen"):
            result = classify_general_error(exception_action=1, exception_source=source, **common)
            self.assertEqual(result.error_out, ErrorCluster(False, 0, ""))
            self.assertTrue(result.exception_suppressed)
        mismatch = classify_general_error(exception_action=1, exception_source="other", **common)
        self.assertEqual(mismatch.error_out, ErrorCluster(True, 9, "chosen"))
        default_frame = classify_general_error(exception_action=2, exception_source="", **common)
        self.assertEqual(default_frame.error_out, ErrorCluster(True, 9, "chosen"))

    def test_error_question_is_status_or_nonzero_code_after_gates(self) -> None:
        result = classify_general_error(
            local_error_code=0, local_error_source="", error_in=ErrorCluster(False, 5, "odd"),
            exception_action=0, exception_code=0, exception_source="",
        )
        self.assertTrue(result.error_question)

    def test_core_returns_no_error_text_only_for_false_error_question(self) -> None:
        no_error = plan_general_error_handler_core(
            dialog_type=0, no_error_message="No Error", local_error_code=0, local_error_source="",
            error_in=ErrorCluster(False, 0, ""), exception_action=0, exception_code=0, exception_source="",
        )
        self.assertEqual(no_error.no_error_message, "No Error")
        self.assertFalse(no_error.stop_event_propagated)
        self.assertIs(no_error.blocked, DIALOG_ERROR_EFFECTS_BLOCKED)
        error = plan_general_error_handler_core(
            dialog_type=1, no_error_message="No Error", local_error_code=5, local_error_source="here",
            error_in=ErrorCluster(False, 0, ""), exception_action=0, exception_code=0, exception_source="",
        )
        self.assertIsNone(error.no_error_message)
        self.assertIs(error.blocked, DIALOG_ERROR_EFFECTS_BLOCKED)

    def test_not_found_dialog_exact_group_and_choice_routing(self) -> None:
        no_dialog = plan_not_found_dialog(dialog_type=DialogType.NO_DIALOG)
        self.assertEqual((no_dialog.modal_kind, no_dialog.help_requested, no_dialog.stop_event_propagated), ("none", False, False))

        two_button = plan_not_found_dialog(dialog_type=DialogType.OK_MESSAGE, two_button_t_pressed=False)
        self.assertTrue(two_button.help_requested)
        self.assertFalse(two_button.stop_event_propagated)
        self.assertIn("Control Online Help", two_button.ordered_effects[-1])

        center = plan_not_found_dialog(dialog_type=DialogType.CONTINUE_OR_STOP_MESSAGE, three_button_choice=1)
        self.assertEqual((center.help_requested, center.stop_event_propagated, center.stop_primitive_requested), (False, True, True))
        auto_center = plan_not_found_dialog(dialog_type=DialogType.AUTO_ERROR_HANDLING_DIALOG, three_button_choice=ThreeButtonChoice.CENTER_BUTTON)
        self.assertEqual((auto_center.stop_event_propagated, auto_center.stop_primitive_requested), (True, False))
        help_choice = plan_not_found_dialog(dialog_type=DialogType.CONTINUE_STOP_WITH_WARNINGS, three_button_choice=2)
        self.assertEqual((help_choice.help_requested, help_choice.stop_event_propagated), (True, False))
        close = plan_not_found_dialog(dialog_type=2, three_button_choice=ThreeButtonChoice.WINDOW_CLOSE)
        self.assertEqual((close.help_requested, close.stop_event_propagated), (False, False))

    def test_not_found_dialog_preserves_two_button_boolean_as_unmapped_gate(self) -> None:
        unresolved = plan_not_found_dialog(dialog_type=4)
        self.assertIsNone(unresolved.help_requested)
        self.assertIs(unresolved.blocked, DIALOG_ERROR_EFFECTS_BLOCKED)
        with self.assertRaises(ValueError):
            plan_not_found_dialog(dialog_type=0, two_button_t_pressed=True)
        with self.assertRaises(ValueError):
            plan_not_found_dialog(dialog_type=1, three_button_choice=0)

    def test_three_button_core_is_initialization_plan_and_blocks_event_mapping(self) -> None:
        plan = plan_three_button_dialog_core(
            message="M", left_button_text="Yes", center_button_text="No", right_button_text="Cancel",
            window_title="T", keyboard_shortcuts=("Enter", "", ""), justification="Left",
            allow_user_to_close_window=True,
        )
        self.assertTrue(plan.allow_user_to_close_window)
        self.assertEqual(plan.effective_center_button_text, "No")
        self.assertIn("FP.Closeable", plan.ordered_effects[1])
        self.assertIn("event loop", plan.ordered_effects[-1])
        self.assertIs(plan.blocked, DIALOG_ERROR_EFFECTS_BLOCKED)

        all_empty = plan_three_button_dialog_core(
            message="M", left_button_text="", center_button_text="", right_button_text="",
            window_title="", keyboard_shortcuts=("", "", ""), justification="Left",
            allow_user_to_close_window=False,
        )
        self.assertEqual(all_empty.effective_center_button_text, "OK")


if __name__ == "__main__":
    unittest.main()
