"""Synthetic local handover proof tests; never enumerate live processes or NI."""
import copy
import os
import tempfile
import threading
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_recovery import (
    MARKER_KIND, OwnershipMarker, RecoveryRequired,
)
from legacy.xp_acq_control.elyse_agent.handover_recovery import (
    CONFIRMATION_TTL_SECONDS, HANDOVER_CONFIRMATION, INVENTORY_MAX_AGE_SECONDS,
    LocalHandoverVerifier,
)


class HandoverRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.marker = dict(kind=MARKER_KIND, session_id="a" * 32, build_id="b" * 64,
                           owner_pid=88, nonce="c" * 32)
        self.snapshot = dict(pid=99, observed_monotonic=self.now, processes=[
            dict(pid=0, parent=0, name="[System Process]"),
            dict(pid=4, parent=0, name="System"),
            dict(pid=99, parent=66, name="pythonw.exe"),
            dict(pid=100, parent=66, name="LabVIEW.exe"),
            dict(pid=101, parent=4, name="csrss.exe"),
        ])
        self.calls = 0
        def inventory():
            self.calls += 1
            return copy.deepcopy(self.snapshot)
        self.verifier = LocalHandoverVerifier(99, inventory, lambda: self.now)

    def check(self):
        with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "local operator"):
            return self.verifier(self.marker)

    def test_same_thread_confirmation_qualified_labview_may_remain_open(self):
        proof = self.check()
        self.assertTrue(proof["verified"])
        self.assertTrue(proof["owner_process_absent"])
        self.assertTrue(proof["native_children_absent"])
        self.assertTrue(proof["ni_competitors_absent"])
        self.assertEqual(proof["process_inventory"]["labview_processes_left_open"], [100])
        self.assertTrue(proof["operator_attestation"]["external_ni_tasks_released"])
        self.assertFalse(proof["ni_task_release_independently_verified"])
        self.assertFalse(proof["electrical_off_independently_verified"])
        self.assertFalse(proof["universal_ni_exclusion_established"])
        self.assertFalse(proof["hardware_commands_sent"])
        self.assertIn("point-in-time", proof["method"])
        self.assertEqual(self.calls, 1)

    def test_without_current_confirmation_no_inventory_is_collected(self):
        with self.assertRaises(RecoveryRequired):
            self.verifier(self.marker)
        self.check()
        with self.assertRaises(RecoveryRequired):
            self.verifier(self.marker)
        self.assertEqual(self.calls, 1)

    def test_exact_confirmation_and_identified_operator_required(self):
        for confirmation, operator in ((True, "operator"), ("OFF", "operator"),
                                       (HANDOVER_CONFIRMATION, ""),
                                       (HANDOVER_CONFIRMATION, "   "),
                                       (HANDOVER_CONFIRMATION, "a\nb"),
                                       (HANDOVER_CONFIRMATION, "a" * 161),
                                       (HANDOVER_CONFIRMATION, None)):
            with self.assertRaises(ValueError):
                with self.verifier.local_confirmation(confirmation, operator):
                    self.fail("Invalid local confirmation accepted")
        self.assertEqual(self.calls, 0)

    def test_wrong_thread_cannot_consume_acknowledgement(self):
        errors = []
        def attempted():
            try:
                self.verifier(self.marker)
            except RecoveryRequired as error:
                errors.append(str(error))
        with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
            worker = threading.Thread(target=attempted)
            worker.start()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertEqual(self.calls, 0)
            self.assertTrue(self.verifier(self.marker)["verified"])

    def test_confirmation_expires_or_clock_reverses(self):
        for delta in (CONFIRMATION_TTL_SECONDS + 0.01, -0.01):
            self.now = 1000.0
            with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                self.now += delta
                with self.assertRaises(RecoveryRequired):
                    self.verifier(self.marker)
        self.assertEqual(self.calls, 0)

    def test_confirmation_also_rechecked_after_slow_inventory(self):
        def slow_inventory():
            self.now += CONFIRMATION_TTL_SECONDS + 1
            return self.snapshot
        verifier = LocalHandoverVerifier(99, slow_inventory, lambda: self.now)
        with verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
            with self.assertRaises(RecoveryRequired):
                verifier(self.marker)

    def test_nested_confirmation_refused_without_destroying_outer_scope(self):
        with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "outer"):
            with self.assertRaises(RecoveryRequired):
                with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "inner"):
                    pass
            self.assertEqual(self.verifier(self.marker)["operator_attestation"]["operator"], "outer")

    def test_context_exception_invalidates_confirmation(self):
        with self.assertRaises(RuntimeError):
            with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                raise RuntimeError("Synthetic UI error")
        with self.assertRaises(RecoveryRequired):
            self.verifier(self.marker)

    def test_active_old_parent_or_reused_owner_pid_blocks(self):
        for name in ("pythonw.exe", "unrelated.exe"):
            self.snapshot["processes"].append(dict(pid=88, parent=4, name=name))
            with self.assertRaises(RecoveryRequired):
                self.check()
            self.snapshot["processes"].pop()

    def test_all_other_python_and_known_daq_clients_block(self):
        for name in ("python.exe", "pythonw.exe", "PYTHON3.EXE", "python-service.exe",
                     "py.exe", "pyw.exe", "nimax.exe", "max.exe", "nimaxexeserver.exe",
                     "nidaqmx.exe", "nidaq32.exe", "NiTestPanels.exe", "testpanels.exe",
                     "daqmx-client.exe"):
            self.snapshot["processes"].append(dict(pid=102, parent=4, name=name))
            with self.assertRaises(RecoveryRequired):
                self.check()
            self.snapshot["processes"].pop()

    def test_inventory_exception_access_denied_or_empty_fails_closed(self):
        def denied():
            raise OSError("Access denied")
        verifier = LocalHandoverVerifier(99, denied, lambda: self.now)
        with verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
            with self.assertRaises(RecoveryRequired):
                verifier(self.marker)
        for snapshot in (None, [], {}, dict(self.snapshot, processes=[]),
                         dict(self.snapshot, processes=tuple(self.snapshot["processes"])),
                         dict(self.snapshot, pid=98), dict(self.snapshot, error="partial")):
            old, self.snapshot = self.snapshot, snapshot
            with self.assertRaises(RecoveryRequired):
                self.check()
            self.snapshot = old

    def test_inventory_stale_future_or_nonfinite_fails_closed(self):
        for value in (1000.0 - INVENTORY_MAX_AGE_SECONDS - 0.01, 1000.01,
                      float("nan"), float("inf"), True, "1000"):
            self.snapshot["observed_monotonic"] = value
            with self.assertRaises(RecoveryRequired):
                self.check()

    def test_missing_own_row_duplicate_pid_or_malformed_rows_fail_closed(self):
        original = copy.deepcopy(self.snapshot["processes"])
        variants = ([row for row in original if row["pid"] != 99],
                    original + [dict(original[-1])])
        bad_rows = (None, {}, dict(pid=True, parent=4, name="idle.exe"),
                    dict(pid=-1, parent=4, name="idle.exe"),
                    dict(pid=2 ** 32, parent=4, name="idle.exe"),
                    dict(pid=102, parent=False, name="idle.exe"),
                    dict(pid=102, parent=4, name=""),
                    dict(pid=102, parent=4, name="C:\\python.exe"),
                    dict(pid=102, parent=4, name="bad\x00.exe"),
                    dict(pid=102, parent=4, name="bad\n.exe"),
                    dict(pid=102, parent=4, name=" name.exe"),
                    dict(pid=102, parent=4, name="safe.exe", error="partial"))
        for rows in list(variants) + [original + [bad] for bad in bad_rows]:
            self.snapshot["processes"] = rows
            with self.assertRaises(RecoveryRequired):
                self.check()
        self.snapshot["processes"] = original

    def test_malformed_prior_marker_and_current_owner_pid_fail_closed(self):
        for marker in (None, {}, dict(owner_pid=88), dict(self.marker, owner_pid=True),
                       dict(self.marker, owner_pid=99), dict(self.marker, extra=True)):
            with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                with self.assertRaises(RecoveryRequired):
                    self.verifier(marker)
        self.assertEqual(self.calls, 0)

    def test_invalid_constructor_or_clock_fails_closed(self):
        for pid in (0, -1, True, "99"):
            with self.assertRaises(ValueError):
                LocalHandoverVerifier(pid)
        for options in (dict(inventory=[]), dict(clock=2)):
            with self.assertRaises(ValueError):
                LocalHandoverVerifier(99, **options)
        for now in (-1, float("inf"), float("nan"), "1000", True):
            self.now = now
            with self.assertRaises(RecoveryRequired):
                with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                    pass

    def test_ownership_marker_integration_only_removes_after_explicit_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "control.ownership")
            prior = OwnershipMarker(path, "a" * 32, "b" * 64, process_id=88)
            prior.acquire()
            guard = OwnershipMarker(path, "d" * 32, "e" * 64, process_id=99,
                                    quiescence_checker=self.verifier)
            with open(path, "rb") as source:
                before = source.read()
            with self.assertRaises(RecoveryRequired):
                guard.recover(electrical_off_confirmed=True)
            with open(path, "rb") as source:
                self.assertEqual(source.read(), before)
            with self.verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                result = guard.recover(electrical_off_confirmed=True)
            self.assertFalse(result["required"])
            self.assertFalse(os.path.exists(path))
            self.assertIn("STILL_UNINITIALIZED", result["reason"])

    def test_default_is_cold_no_live_inventory_until_explicit_verification(self):
        with mock.patch("legacy.xp_acq_control.elyse_agent.handover_recovery.windows_process_inventory",
                        side_effect=AssertionError("Live process enumeration prohibited")) as reader:
            verifier = LocalHandoverVerifier(99)
            with verifier.local_confirmation(HANDOVER_CONFIRMATION, "operator"):
                pass
            with self.assertRaises(RecoveryRequired):
                verifier(self.marker)
            self.assertFalse(reader.called)


if __name__ == "__main__":
    unittest.main()
