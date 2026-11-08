import unittest

from supervision_reconstruction.domain.fw102x_errors import ErrorCluster
from supervision_reconstruction.domain.fw102x_operations import (
    FW102X_OPERATIONS_BLOCKED,
    UnresolvedRuntimeValue,
    execute_fw102x_operation_plan,
    plan_fw102x_close,
    plan_fw102x_get_position,
    plan_fw102x_initialize,
    plan_fw102x_set_position,
)


class Fw102xOperationalPlansTests(unittest.TestCase):
    def setUp(self) -> None:
        self.no_error = ErrorCluster(False, 0, "")
        self.prior_error = ErrorCluster(True, -7, "upstream")

    def test_close_records_parallel_driver_close_and_session_delete_even_with_prior_error(self) -> None:
        handle = object()
        result = plan_fw102x_close(handle, self.prior_error)

        self.assertIs(result.instrument_handle_identity, handle)
        self.assertIs(result.error_out, self.prior_error)
        self.assertEqual(
            result.evaluation_layers,
            (("external_close", "ivi_delete_session"), ("ivi_error_converter",)),
        )
        self.assertEqual([call.primitive_name for call in result.calls], [
            "extFunc", "IVI Delete Session", "FW102x IVI Error Converter.vi"
        ])
        self.assertEqual(result.calls[0].inputs[0].index, 6)
        self.assertIs(result.calls[0].inputs[0].value, handle)
        self.assertEqual(result.calls[2].inputs[-1].value, 0)
        self.assertIs(result.blocked, FW102X_OPERATIONS_BLOCKED)
        self.assertTrue(all(not call.execution_allowed for call in result.calls))

    def test_get_position_prior_error_passthrough_has_no_driver_plan_or_position_value(self) -> None:
        handle = object()
        result = plan_fw102x_get_position(handle, self.prior_error)

        self.assertIs(result.vi_out_identity, handle)
        self.assertIs(result.error_out, self.prior_error)
        self.assertIsNone(result.position_output_source)
        self.assertEqual(result.calls, ())
        self.assertEqual(result.evaluation_layers, ())
        self.assertIsNone(result.blocked)

    def test_get_position_no_error_preserves_wired_storage_and_external_result_terminals(self) -> None:
        handle = object()
        result = plan_fw102x_get_position(handle, self.no_error)

        external, converter = result.calls
        self.assertIs(result.vi_out_identity, handle)
        self.assertIsNone(result.error_out)
        self.assertEqual(result.evaluation_layers, (("external_get_position",), ("ivi_error_converter",)))
        self.assertEqual(external.inputs[0].index, 6)
        self.assertIs(external.inputs[0].value, handle)
        self.assertEqual(external.inputs[1].value, "position")
        self.assertEqual(
            [(value.terminal_index, value.nominal_type) for value in external.outputs],
            [(5, "I32"), (7, "U32"), (9, "I32")],
        )
        self.assertEqual(result.position_output_source, external.outputs[-1])
        self.assertEqual(converter.inputs[-1].value, external.outputs[1])
        self.assertIs(result.blocked, FW102X_OPERATIONS_BLOCKED)

    def test_initialize_converts_bools_at_the_visible_u16_and_u32_terminals(self) -> None:
        result = plan_fw102x_initialize(
            "COM1", 9600, True, False, self.no_error
        )

        external, session, converter = result.calls
        self.assertEqual((result.id_query_u16, result.reset_device_u16, result.id_query_u32), (1, 0, 1))
        self.assertEqual(
            [(item.index, item.nominal_type, item.value) for item in external.inputs],
            [(6, "String", "COM1"), (8, "I32", 9600), (10, "U16", 1), (12, "U16", 0), (14, "U32", 1)],
        )
        self.assertEqual(result.evaluation_layers, (("external_initialize",), ("ivi_new_session", "ivi_error_converter")))
        self.assertEqual(session.primitive_name, "IVI New Session")
        self.assertEqual(session.inputs[0].value, external.outputs[2])
        self.assertEqual(session.inputs[1].value, external.outputs[1])
        self.assertTrue(session.inputs[2].value)
        self.assertEqual(result.instrument_handle_out_source, session.outputs[0])
        self.assertEqual(converter.inputs[-1].value, external.outputs[2])
        self.assertIsNone(result.error_out)
        self.assertIs(result.blocked, FW102X_OPERATIONS_BLOCKED)

    def test_initialize_prior_error_skips_effects_and_preserves_error(self) -> None:
        result = plan_fw102x_initialize("COM2", 0, False, True, self.prior_error)

        self.assertEqual((result.id_query_u16, result.reset_device_u16, result.id_query_u32), (0, 1, 0))
        self.assertIs(result.error_out, self.prior_error)
        self.assertIsNone(result.instrument_handle_out_source)
        self.assertEqual(result.calls, ())
        self.assertEqual(result.evaluation_layers, ())
        self.assertIsNone(result.blocked)

    def test_set_position_preserves_passthrough_or_wires_i32_value_by_error_case(self) -> None:
        handle = object()
        skipped = plan_fw102x_set_position(handle, -3, self.prior_error)
        executed = plan_fw102x_set_position(handle, -3, self.no_error)

        self.assertIs(skipped.vi_out_identity, handle)
        self.assertIs(skipped.error_out, self.prior_error)
        self.assertEqual(skipped.calls, ())
        external, converter = executed.calls
        self.assertIs(executed.vi_out_identity, handle)
        self.assertIsNone(executed.error_out)
        self.assertEqual(external.inputs[0].value, handle)
        self.assertEqual(external.inputs[1].value, -3)
        self.assertEqual(external.inputs[1].nominal_type, "I32")
        self.assertEqual(converter.inputs[-2].value, external.outputs[0])
        self.assertIs(executed.blocked, FW102X_OPERATIONS_BLOCKED)

    def test_runtime_types_i32_bounds_and_execution_denial_are_explicit(self) -> None:
        with self.assertRaises(TypeError):
            plan_fw102x_initialize("COM1", True, False, False, self.no_error)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plan_fw102x_initialize("COM1", 1, 1, False, self.no_error)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plan_fw102x_set_position(object(), 2**31, self.no_error)
        with self.assertRaises(TypeError):
            plan_fw102x_get_position(object(), ErrorCluster(0, 0, ""))  # type: ignore[arg-type]
        with self.assertRaises(PermissionError):
            execute_fw102x_operation_plan(object())

    def test_converter_vi_name_is_unresolved_runtime_path_result_not_literal(self) -> None:
        result = plan_fw102x_set_position(object(), 1, self.no_error)
        name_value = result.calls[1].inputs[1].value
        self.assertIsInstance(name_value, UnresolvedRuntimeValue)
        self.assertEqual(name_value.expression, "Current VI's Path -> Strip Path.name")
        self.assertEqual(name_value.copied_vi_name, "FW102x Set Position.vi")
