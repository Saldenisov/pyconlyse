"""Python 3.4 offline scope tests; injected NI owner, never real NI/Chroma."""
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from legacy.xp_acq_agent.elyse_agent import acquisition_backend as module
from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_gui import load_configuration, AcquisitionWindow
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import (
    execute_general_start, execute_general_only_stop, GENERAL_ONLY_STOP_FRAMES,
    GENERAL_ONLY_STOP_EPS, GENERAL_ONLY_STOP_DPS, GeneralStopError,
)
from legacy.xp_acq_agent.tests import test_acquisition_runtime as runtime_tests


wait_state = runtime_tests.wait_state


class GeneralOnlyTests(unittest.TestCase):
    def backend(self):
        owner = runtime_tests.BackendTests().fake_owner()
        forbidden_focal = Mock(side_effect=AssertionError("Chroma must not be called"))
        forbidden_focal.ensure_ready.side_effect = AssertionError("No Chroma preflight in this profile")
        backend = CardBackend(Mock(return_value=owner), focal_off=forbidden_focal,
                              stop_wait=lambda _seconds: None, control_profile="general_only_test")
        backend.initialize(threading.Event(), startup_confirmed=True)
        return owner, backend, forbidden_focal

    def test_stop_subset_pulses_only_general_and_waits_250_ms(self):
        writes, waits, status, frames = [], [], [], []
        execute_general_only_stop(lambda *row: writes.append(row), lambda *row: status.append(row),
                                  waits.append, lambda *row: frames.append(row), operator_confirmed=True)
        self.assertEqual(writes, [(1, False), (1, True)])
        self.assertEqual(waits, [.15, .1])
        self.assertEqual(frames, [(row[0], row[1]) for row in GENERAL_ONLY_STOP_FRAMES])
        self.assertEqual([row[0] for row in frames], [13, 14, 15, 16])
        self.assertEqual(status, [(GENERAL_ONLY_STOP_EPS, GENERAL_ONLY_STOP_DPS)])
        self.assertEqual(set(i for i, _value in GENERAL_ONLY_STOP_EPS), set((8, 9, 11)))

    def test_confirmation_required_before_any_callback(self):
        callback = Mock()
        with self.assertRaises(ValueError):
            execute_general_only_stop(callback, callback, callback, callback)
        callback.assert_not_called()

    def test_failed_assertion_still_releases_and_does_not_mark_ok(self):
        writes, status = [], Mock()
        def commit(index, value):
            writes.append((index, value))
            if not value:
                raise RuntimeError("partial assertion")
        with self.assertRaises(GeneralStopError):
            execute_general_only_stop(commit, status, Mock(), operator_confirmed=True)
        self.assertEqual(writes, [(1, False), (1, True)])
        status.assert_not_called()

    def test_failed_release_is_retried_and_error_retained(self):
        writes, status = [], Mock()
        def commit(index, value):
            writes.append((index, value))
            if len(writes) == 2:
                raise RuntimeError("release failed")
        with self.assertRaises(GeneralStopError) as caught:
            execute_general_only_stop(commit, status, Mock(), operator_confirmed=True)
        self.assertEqual(writes, [(1, False), (1, True), (1, True)])
        self.assertIn("release failed", str(caught.exception))
        status.assert_not_called()

    def test_failed_wait_still_releases_and_does_not_claim_success(self):
        writes, status = [], Mock()
        with self.assertRaises(GeneralStopError):
            execute_general_only_stop(lambda *row: writes.append(row), status,
                                      Mock(side_effect=RuntimeError("wait failed")), operator_confirmed=True)
        self.assertEqual(writes, [(1, False), (1, True)])
        status.assert_not_called()

    def test_failed_status_is_reported_without_other_stage_commands(self):
        writes = []
        with self.assertRaises(GeneralStopError):
            execute_general_only_stop(lambda *row: writes.append(row),
                                      Mock(side_effect=RuntimeError("status failed")), Mock(), operator_confirmed=True)
        self.assertEqual(writes, [(1, False), (1, True)])

    def test_constructor_does_not_construct_chroma_in_test_profile(self):
        with patch.object(module, "ChromaFocalStop") as adapter:
            backend = CardBackend(control_profile="general_only_test")
        adapter.assert_not_called()
        self.assertIsNone(backend.focal_off)
        self.assertEqual(backend.resource_count, 0)

    def test_start_and_stop_never_call_chroma_or_change_other_bits(self):
        owner, backend, focal = self.backend()
        startup = tuple(backend.commanded_digital["C4_DIO96_DO"])
        cancel = Mock()
        cancel.is_set.return_value = False
        backend.general_start(cancel, operator_confirmed=True)
        backend.software_status_assignments["EPS"][14] = True
        backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 8)
        for index, call in enumerate(owner.write_digital_bank.call_args_list):
            name, bank = call[0]
            self.assertEqual(name, "C4_DIO96_DO")
            allowed = (0, 2) if index < 6 else (1,)
            self.assertTrue(all(value == startup[i] for i, value in enumerate(bank) if i not in allowed))
        self.assertEqual(tuple(backend.commanded_digital["C4_DIO96_DO"]), startup)
        self.assertTrue(backend.software_status_assignments["EPS"][14])
        self.assertEqual(backend.procedure["control_profile"], "general_only_test")
        self.assertFalse(backend.procedure["full_event_6_executed"])
        self.assertFalse(backend.procedure["other_stages_stopped"])
        self.assertFalse(backend.procedure["hardware_off_confirmed"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()
        focal.assert_not_called()
        focal.ensure_ready.assert_not_called()

    def test_changed_non_general_image_refuses_start_before_any_write(self):
        for name, index in (("C3_DIO96_DO", 0), ("C4_DIO96_DO", 3), ("C5_DIO96_DO", 0)):
            owner, backend, _focal = self.backend()
            image = list(backend.commanded_digital[name])
            image[index] = not image[index]
            backend.commanded_digital[name] = image
            with self.assertRaises(RuntimeError):
                backend.general_start(threading.Event(), operator_confirmed=True)
            owner.write_digital_bank.assert_not_called()

    def test_malformed_image_refuses_start_before_any_write(self):
        owner, backend, _focal = self.backend()
        backend.commanded_digital["C4_DIO96_DO"] = (False,)
        with self.assertRaises(RuntimeError):
            backend.general_start(threading.Event(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()

    def test_asserted_start_reset_or_stop_pulse_refuses_another_start(self):
        for index in (0, 1, 2):
            owner, backend, _focal = self.backend()
            image = list(backend.commanded_digital["C4_DIO96_DO"])
            image[index] = not image[index]
            backend.commanded_digital["C4_DIO96_DO"] = image
            with self.assertRaises(RuntimeError):
                backend.general_start(threading.Event(), operator_confirmed=True)
            owner.write_digital_bank.assert_not_called()

    def test_stop_restores_interrupted_start_pulses_before_stop(self):
        owner, backend, focal = self.backend()
        image = list(backend.commanded_digital["C4_DIO96_DO"])
        image[0] = image[2] = True
        backend.commanded_digital["C4_DIO96_DO"] = image
        backend.general_stop(operator_confirmed=True)
        writes = [call[0][1] for call in owner.write_digital_bank.call_args_list]
        self.assertEqual(len(writes), 4)
        self.assertEqual([(row[0], row[2], row[1]) for row in writes],
                         [(False, True, True), (False, False, True),
                          (False, False, False), (False, False, True)])
        focal.assert_not_called()

    def test_failed_start_restore_still_attempts_stop_and_reports_partial_failure(self):
        owner, backend, _focal = self.backend()
        image = list(backend.commanded_digital["C4_DIO96_DO"])
        image[0] = True
        backend.commanded_digital["C4_DIO96_DO"] = image
        owner.write_digital_bank.side_effect = [RuntimeError("restore failed"), None, None]
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 3)
        self.assertEqual([call[0][1][1] for call in owner.write_digital_bank.call_args_list],
                         [True, False, True])
        self.assertEqual([call[0][1][0] for call in owner.write_digital_bank.call_args_list],
                         [False, False, False])
        self.assertEqual(backend.software_status_assignments, {"EPS": {}, "DPS": {}})
        self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
        owner.close.assert_not_called()

    def test_stop_failure_retains_owner_for_retry(self):
        owner, backend, focal = self.backend()
        owner.write_digital_bank.side_effect = RuntimeError("NI write failed")
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()
        focal.assert_not_called()

    def test_unknown_profile_is_cold_error(self):
        factory = Mock()
        with self.assertRaises(ValueError):
            CardBackend(factory, control_profile="skip_checks")
        factory.assert_not_called()

    def test_fake_owner_runtime_roundtrip_keeps_owner_and_reads_after_stop(self):
        owner, backend, focal = self.backend()
        # The runtime performs its own initialization on the same fake owner.
        backend.owner = None
        thread_names = []
        owner.write_digital_bank.side_effect = lambda *_args: thread_names.append(threading.current_thread().name)
        runtime = AcquisitionRuntime(lambda: backend, period=.02)
        def fast_start(commit, assign, _wait, cancelled, observer=None, operator_confirmed=False):
            return execute_general_start(commit, assign, lambda _seconds: None, cancelled,
                                         observer, operator_confirmed=operator_confirmed)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            wait_state(runtime, "RUNNING")
            with patch.object(module, "execute_general_start", side_effect=fast_start):
                runtime.general_start(operator_confirmed=True)
                wait_state(runtime, "RUNNING")
            self.assertTrue(runtime.snapshot()["general_stop_required"])
            runtime.general_stop(operator_confirmed=True)
            wait_state(runtime, "RUNNING")
            self.assertFalse(runtime.snapshot()["general_stop_required"])
            self.assertEqual(runtime.snapshot()["control_profile"], "general_only_test")
            self.assertEqual(set(thread_names), set(("ACQ-card-owner",)))
            self.assertEqual(len(thread_names), 8)
            owner.close.assert_not_called()
            focal.assert_not_called()
            runtime.deinitialize()
            wait_state(runtime, "IDLE")
            self.assertEqual(runtime.snapshot()["resource_count"], 0)
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(3))


class GeneralOnlyConfigurationTests(unittest.TestCase):
    def configuration(self, folder, profile=None):
        key_path = os.path.join(folder, "test.key")
        with open(key_path, "wb") as stream:
            stream.write(b"synthetic-offline-key-0000000000000000000000000000")
        config = dict(bind_host="127.0.0.1", port=8771, key_file=key_path,
                      period_seconds=.2, read_timeout_seconds=.5)
        if profile is not None:
            config["control_profile"] = profile
        path = os.path.join(folder, "config.json")
        with open(path, "w") as stream:
            json.dump(config, stream)
        return path

    def test_profile_is_explicit_and_omission_preserves_legacy_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.configuration(folder)
            config, _key = load_configuration(path)
            self.assertEqual(config.get("control_profile", "legacy_full"), "legacy_full")
            path = self.configuration(folder, "general_only_test")
            config, _key = load_configuration(path)
            self.assertEqual(config["control_profile"], "general_only_test")

    def test_unknown_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.configuration(folder, "skip_checks")
            with self.assertRaises(ValueError):
                load_configuration(path)

    def window(self, answer=True, general_only=True):
        window = AcquisitionWindow.__new__(AcquisitionWindow)
        window.demo, window.general_only = False, general_only
        window.root, window.runtime, window.messagebox = Mock(), Mock(), Mock()
        window.messagebox.askyesno.return_value = answer
        return window

    def test_gui_requires_off_stages_confirmation_before_test_start(self):
        window = self.window(answer=False)
        window.general_start()
        window.runtime.general_start.assert_not_called()
        message = window.messagebox.askyesno.call_args[0][1]
        self.assertIn("physically OFF", message)
        self.assertIn("Arret will stop only low-level General", message)
        window.messagebox.askyesno.return_value = True
        window.general_start()
        window.runtime.general_start.assert_called_once_with(operator_confirmed=True)

    def test_gui_stop_names_limited_scope_not_legacy_full_shutdown(self):
        window = self.window()
        window.general_stop()
        window.runtime.general_stop.assert_called_once_with(operator_confirmed=True)
        message = window.messagebox.askyesno.call_args[0][1]
        self.assertIn("No Chroma", message)
        self.assertIn("not a full installation shutdown", message)

    def test_gui_profile_cannot_become_windows_startup(self):
        window = self.window()
        with patch("legacy.xp_acq_agent.elyse_agent.acquisition_gui.install_startup") as install:
            window.enable_startup()
        install.assert_not_called()
        window.messagebox.showerror.assert_called_once()


if __name__ == "__main__":
    unittest.main()
