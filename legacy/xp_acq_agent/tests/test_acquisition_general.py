"""Python 3.4 fake-callback tests. General Marche never reaches real hardware."""
import threading
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import (
    execute_general_start, ProcedureCancelled, GENERAL_START_FRAMES,
)
from legacy.xp_acq_agent.tests.test_acquisition_runtime import FakeBackend, wait_state
from legacy.xp_acq_agent.tests import test_acquisition_runtime as runtime_tests
from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime


class GeneralProcedureTests(unittest.TestCase):
    def test_exact_ten_frames_six_writes_and_status_after_last_reset(self):
        log = []
        execute_general_start(lambda i, value: log.append(("write", i, value)),
                              lambda eps, dps: log.append(("status", eps, dps)),
                              lambda seconds: log.append(("wait", seconds)), lambda: False,
                              lambda index, uid: log.append(("frame", index, uid)), True)
        self.assertEqual([row[1] for row in log if row[0] == "frame"], list(range(10)))
        self.assertEqual([row[1:] for row in log if row[0] == "write"],
                         [(0, True), (0, False), (2, True), (2, False), (2, True), (2, False)])
        self.assertEqual([row[1] for row in log if row[0] == "wait"], [.15, 1, .15, 1, .15, .1])
        self.assertAlmostEqual(sum(row[1] for row in log if row[0] == "wait"), 2.55)
        status = [row for row in log if row[0] == "status"]
        self.assertEqual(status, [("status", ((11, False), (8, True), (6, False)), ((2, False),))])
        self.assertEqual(tuple(row[2] for row in log if row[0] == "frame"),
                         tuple(row[1] for row in GENERAL_START_FRAMES))

    def test_missing_confirmation_performs_no_callback(self):
        callback = Mock()
        with self.assertRaises(ValueError):
            execute_general_start(callback, callback, callback, callback)
        callback.assert_not_called()

    def test_cancel_during_assertion_restores_pulse_before_return(self):
        log, cancelled = [], threading.Event()
        status = Mock()
        with self.assertRaises(ProcedureCancelled):
            execute_general_start(lambda *row: log.append(row), status,
                                  lambda _seconds: cancelled.set(), cancelled.is_set,
                                  operator_confirmed=True)
        self.assertEqual(log, [(0, True), (0, False)])
        status.assert_not_called()

    def test_failed_assertion_attempts_restore_and_does_not_mark_ok(self):
        writes, status = [], Mock()
        def commit(index, value):
            writes.append((index, value))
            if value:
                raise RuntimeError("synthetic driver write failure")
        with self.assertRaises(RuntimeError):
            execute_general_start(commit, status, Mock(), lambda: False, operator_confirmed=True)
        self.assertEqual(writes, [(0, True), (0, False)])
        status.assert_not_called()

    def test_backend_preserves_all_unrelated_c4_bits_and_fixed_startup_image(self):
        owner = runtime_tests.BackendTests().fake_owner()
        backend = CardBackend(Mock(return_value=owner), focal_off=lambda: None)
        backend.initialize(threading.Event(), startup_confirmed=True)
        startup = tuple(backend.initial_images["digital"]["C4_DIO96_DO"])
        cancel = Mock()
        cancel.is_set.return_value = False
        backend.general_start(cancel, operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 6)
        for call in owner.write_digital_bank.call_args_list:
            name, bank = call[0]
            self.assertEqual(name, "C4_DIO96_DO")
            self.assertEqual(len(bank), 32)
            self.assertTrue(all(bank[i] == startup[i] for i in range(32) if i not in (0, 2)))
        self.assertEqual(backend.initial_images["digital"]["C4_DIO96_DO"], startup)
        self.assertEqual(backend.software_status_assignments, {"EPS": {11: False, 8: True, 6: False}, "DPS": {2: False}})
        self.assertFalse(backend.commanded_digital["C4_DIO96_DO"][0])
        self.assertFalse(backend.commanded_digital["C4_DIO96_DO"][2])


class GeneralRuntimeTests(unittest.TestCase):
    def test_only_card_owner_runs_procedure_and_unverified_deinit_cannot_drop_owner(self):
        backend = FakeBackend()
        entered = threading.Event()
        def procedure(cancel, operator_confirmed=False):
            self.assertTrue(operator_confirmed)
            self.assertEqual(threading.current_thread().name, "ACQ-card-owner")
            entered.set()
            cancel.wait(2)
            self.assertEqual(backend.close_calls, 0)
            raise ProcedureCancelled()
        backend.general_start = procedure
        runtime = AcquisitionRuntime(lambda: backend, period=.02)
        runtime.start()
        try:
            with self.assertRaises(ValueError):
                runtime.general_start()
            with self.assertRaises(RuntimeError):
                runtime.general_start(operator_confirmed=True)
            runtime.initialize(startup_confirmed=True)
            wait_state(runtime, "RUNNING")
            runtime.general_start(operator_confirmed=True)
            self.assertTrue(entered.wait(1))
            self.assertEqual(runtime.snapshot()["state"], "EXECUTING")
            with self.assertRaises(RuntimeError):
                runtime.general_start(operator_confirmed=True)
            with self.assertRaises(RuntimeError):
                runtime.deinitialize()
            self.assertEqual(backend.close_calls, 0)
            runtime.deinitialize(electrical_off_confirmed=True)
            wait_state(runtime, "IDLE")
            self.assertEqual(backend.close_calls, 1)
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(3))


if __name__ == "__main__":
    unittest.main()
