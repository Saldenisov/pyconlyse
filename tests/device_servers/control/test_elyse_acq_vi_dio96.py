"""DIO96 fixture, alias/error and DIO-to-AO request-chain golden traces."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNSUPPLIED,
    CallKey,
    DigitalOutputBanks,
    ErrorCluster,
    LogicalAoBanks,
    ScriptedBoundary,
    TaskReference,
    initialize_dio96,
    record_dio96_exchange,
    record_ni6703_writes,
)
from DeviceServers.control.elyse_acq.vi_simulation.rw_dio96 import (
    READ_UIDS,
    SOURCE,
    WRITE_UIDS,
)

TASKS = tuple(TaskReference(f"supplied-DIO-field-{i}") for i in range(6))
OUTPUTS = DigitalOutputBanks(((True, False), (False,), (True, False, True)))
READS = ((False, True, True), (), (True,))
FAULT = ErrorCluster(True, -432, "supplied DIO fault")
WARNING = ErrorCluster(False, 432, "supplied DIO warning")


def fixture_data():
    return {CallKey(SOURCE.name, uid): bits for uid, bits in zip(READ_UIDS, READS)}


class Dio96GoldenTraceTests(unittest.TestCase):
    def test_call_order_read_assignment_write_data_and_task_fields(self):
        boundary = ScriptedBoundary(data=fixture_data())
        result = record_dio96_exchange(
            boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR
        )
        boundary.assert_all_fixtures_used()
        self.assertEqual(result.di_banks, READS)
        self.assertEqual(
            [c.key.node_uid for c in result.calls], list(READ_UIDS + WRITE_UIDS)
        )
        self.assertEqual(tuple(c.task_in for c in result.calls), TASKS)
        self.assertEqual(result.error_out, NO_ERROR)
        for i, call in enumerate(result.calls):
            self.assertEqual(call.diagram_uid, "1684")
            self.assertEqual(call.args["card"], 3 + i % 3)
            self.assertEqual(call.args["timeout_connection"], "unwired")
            if i >= 3:
                self.assertEqual(call.args["auto_start"], True)
                self.assertEqual(call.args["data"], OUTPUTS.values[i - 3])
            else:
                self.assertNotIn("auto_start", call.args)

    def test_missing_read_returns_remain_unknown_not_all_false(self):
        result = record_dio96_exchange(
            ScriptedBoundary(), OUTPUTS, tasks=TASKS, error_in=NO_ERROR
        )
        self.assertEqual(result.di_banks, (UNSUPPLIED,) * 3)
        self.assertEqual(len(result.calls), 6)
        self.assertEqual(
            result.error_out, NO_ERROR
        )  # Default fixture, not valid-data proof.

    def test_every_boundary_fault_propagates_and_does_not_gate_returned_data(self):
        for index, uid in enumerate(READ_UIDS + WRITE_UIDS):
            with self.subTest(uid=uid):
                boundary = ScriptedBoundary(
                    data=fixture_data(), errors={CallKey(SOURCE.name, uid): FAULT}
                )
                result = record_dio96_exchange(
                    boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR
                )
                boundary.assert_all_fixtures_used()
                self.assertEqual(len(result.calls), 6)
                self.assertEqual(result.error_out, FAULT)
                self.assertEqual(result.di_banks, READS)
                self.assertEqual(
                    [c.error_in for c in result.calls],
                    [NO_ERROR] * (index + 1) + [FAULT] * (5 - index),
                )

    def test_true_incoming_error_and_warning_keep_all_sites(self):
        for error in (FAULT, WARNING):
            result = record_dio96_exchange(
                ScriptedBoundary(data=fixture_data()),
                OUTPUTS,
                tasks=TASKS,
                error_in=error,
            )
            self.assertEqual(result.error_out, error)
            self.assertEqual([c.error_in for c in result.calls], [error] * 6)
            self.assertEqual(result.di_banks, READS)

    def test_external_clear_does_not_get_replaced_by_python_error_latch(self):
        result = record_dio96_exchange(
            ScriptedBoundary(
                errors={
                    CallKey(SOURCE.name, READ_UIDS[0]): FAULT,
                    CallKey(SOURCE.name, READ_UIDS[1]): NO_ERROR,
                }
            ),
            OUTPUTS,
            tasks=TASKS,
            error_in=NO_ERROR,
        )
        self.assertEqual(
            [c.error_in for c in result.calls],
            [NO_ERROR, FAULT, NO_ERROR, NO_ERROR, NO_ERROR, NO_ERROR],
        )
        self.assertEqual(result.error_out, NO_ERROR)

    def test_tasks_from_verified_initializer_keep_cluster_order(self):
        boundary = ScriptedBoundary(data=fixture_data())
        initialized = initialize_dio96(boundary, error_in=NO_ERROR)
        exchanged = record_dio96_exchange(
            boundary, OUTPUTS, tasks=initialized.tasks, error_in=initialized.error_out
        )
        self.assertEqual(tuple(c.task_in for c in exchanged.calls), initialized.tasks)
        self.assertEqual(len(initialized.calls), 12)
        self.assertEqual(len(exchanged.calls), 6)

    def test_returned_tasks_are_not_forwarded_into_other_card_or_exposed(self):
        boundary = ScriptedBoundary(
            tasks={
                CallKey(SOURCE.name, uid): TaskReference("ignored-" + uid)
                for uid in READ_UIDS + WRITE_UIDS
            }
        )
        result = record_dio96_exchange(
            boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR
        )
        boundary.assert_all_fixtures_used()
        self.assertEqual(tuple(c.task_in for c in result.calls), TASKS)
        self.assertFalse(hasattr(result, "tasks"))

    def test_all_ten_dio_then_ao_sites_remain_visible_when_dio_fails(self):
        boundary = ScriptedBoundary(
            data=fixture_data(), errors={CallKey(SOURCE.name, READ_UIDS[0]): FAULT}
        )
        dio = record_dio96_exchange(boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR)
        ao = record_ni6703_writes(
            boundary,
            LogicalAoBanks(((0.0,) * 10,) * 4),
            tasks=tuple(TaskReference(f"ao-{i}") for i in range(4)),
            error_in=dio.error_out,
        )
        self.assertEqual(len(boundary.calls), 10)
        self.assertEqual([c.error_in for c in ao.calls], [FAULT] * 4)
        self.assertEqual(ao.error_out, FAULT)
        self.assertEqual(dio.di_banks, READS)

    def test_bool_only_shape_guards_do_not_invent_array_length_policy(self):
        self.assertEqual(
            DigitalOutputBanks(((), (True,) * 100, (False,) * 3)).values[1],
            (True,) * 100,
        )
        for values in ([(), (), ()], ((), ()), ((1,), (), ()), (("false",), (), ())):
            with self.assertRaises(ValueError):
                DigitalOutputBanks(values)

    def test_non_bool_read_fixture_rejected_as_explicit_python_guard(self):
        boundary = ScriptedBoundary(data={CallKey(SOURCE.name, READ_UIDS[0]): (1,)})
        with self.assertRaisesRegex(ValueError, "Python-only guard"):
            record_dio96_exchange(boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR)
        self.assertEqual(len(boundary.calls), 1)

    def test_mutable_executable_fixture_data_rejected(self):
        for values in ([True], (lambda: None,), ((True,),), (object(),)):
            with self.assertRaises(TypeError):
                ScriptedBoundary(data={CallKey(SOURCE.name, READ_UIDS[0]): values})

    def test_unused_data_fixture_reported(self):
        boundary = ScriptedBoundary(data={CallKey(SOURCE.name, "not-called"): (True,)})
        record_dio96_exchange(boundary, OUTPUTS, tasks=TASKS, error_in=NO_ERROR)
        with self.assertRaisesRegex(ValueError, "unused simulation fixtures"):
            boundary.assert_all_fixtures_used()


if __name__ == "__main__":
    unittest.main()
