import unittest

from supervision_reconstruction.domain.fw102x_errors import (
    FW102X_ERROR_MESSAGE_BLOCKED,
    FW102X_IVI_CONVERSION_BLOCKED,
    ErrorCluster,
    plan_fw102x_error_message,
    plan_fw102x_ivi_error_conversion,
)


class Fw102xErrorMessagePlanTests(unittest.TestCase):
    def test_external_call_plan_records_zero_buffer_size_without_calling_driver(self) -> None:
        incoming = ErrorCluster(False, 0, "")
        plan = plan_fw102x_error_message("ivi-ref-3", -42, 512, incoming)
        self.assertEqual(plan.instrument_handle_identity, "ivi-ref-3")
        self.assertEqual(plan.error_code, -42)
        self.assertEqual(plan.requested_buffer_size_u32, 512)
        self.assertEqual(plan.zero_initialized_buffer_size, 512)
        self.assertIs(plan.incoming_error, incoming)
        self.assertIs(plan.blocked, FW102X_ERROR_MESSAGE_BLOCKED)

    def test_plan_validates_integer_ranges_without_allocating_u32_buffer(self) -> None:
        incoming = ErrorCluster(False, 0, "")
        self.assertEqual(
            plan_fw102x_error_message(object(), 0, 2**31 - 1, incoming).zero_initialized_buffer_size,
            2**31 - 1,
        )
        with self.assertRaises(OverflowError):
            plan_fw102x_error_message(object(), 0, 2**31, incoming)
        with self.assertRaises(TypeError):
            plan_fw102x_error_message(object(), 2**31, 1, incoming)
        with self.assertRaises(TypeError):
            plan_fw102x_error_message(object(), 0, -1, incoming)


class Fw102xIviConverterPlanTests(unittest.TestCase):
    def test_outer_case_truth_table_and_false_frame_passthrough(self) -> None:
        for incoming_status in (False, True):
            for ivi_code in (0, 7):
                incoming = ErrorCluster(incoming_status, 12, "previous")
                result = plan_fw102x_ivi_error_conversion(3, ivi_code, "caller.vi", incoming)
                expected_attempt = not incoming_status and ivi_code != 0
                self.assertEqual(result.conversion_attempted, expected_attempt)
                if expected_attempt:
                    self.assertIsNone(result.error_out)
                    self.assertEqual(result.external_buffer_sizes, (256, 256, 256, 256))
                    self.assertIs(result.blocked, FW102X_IVI_CONVERSION_BLOCKED)
                else:
                    self.assertIs(result.error_out, incoming)
                    self.assertEqual(result.external_buffer_sizes, ())
                    self.assertIsNone(result.blocked)

    def test_converter_rejects_non_i32_and_malformed_error_cluster(self) -> None:
        incoming = ErrorCluster(False, 0, "")
        with self.assertRaises(TypeError):
            plan_fw102x_ivi_error_conversion(True, 1, "caller.vi", incoming)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plan_fw102x_ivi_error_conversion(1, 2**31, "caller.vi", incoming)
        with self.assertRaises(TypeError):
            plan_fw102x_ivi_error_conversion(1, 1, "caller.vi", ErrorCluster(0, 0, ""))  # type: ignore[arg-type]
