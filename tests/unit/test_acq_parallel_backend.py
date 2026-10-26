"""Parallel startup integration; injected task owners only, never NI calls."""
import threading
import time
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import initialization_card_text, BUTTON_LABELS
from legacy.xp_acq_control.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities
from legacy.xp_acq_control.elyse_agent.hardware_plan import digital_startup_image
from legacy.xp_acq_control.elyse_agent.hardware_tasks import PartialTaskCreationError


class PreparedOwner(object):
    def __init__(self):
        self.tasks = {"fixture": object()}
        self.calls = []

    def start_legacy_counters(self):
        self.calls.append("start")
        return []

    def write_initial_images(self):
        self.calls.append("write")
        return dict(digital=digital_startup_image())

    def close(self):
        self.calls.append("close")
        self.tasks.clear()


class FailedRuntimeBackend(object):
    def __init__(self):
        self.resource_count = 2
        self.startup_complete = False
        self.initialization_cards = dict(all_required_ready=False,
            pending_cards=[10], cards={10: dict(state="TIMED_OUT_UNKNOWN")})
        self.close_calls = 0
        self.control_profile = "general_only_test"

    def initialize(self, cancel, startup_confirmed=False):
        raise RuntimeError("fixture pending C10; other card prepared")

    def close(self):
        self.close_calls += 1
        self.resource_count = 0


class ParallelBackendTests(unittest.TestCase):
    def test_all_prepared_then_counters_then_outputs_then_ready(self):
        owner = PreparedOwner()
        backend = CardBackend()
        with mock.patch("legacy.xp_acq_control.elyse_agent.parallel_initialization.prepare_parallel_cards", return_value=owner) as prepare:
            backend.initialize(threading.Event(), startup_confirmed=True)
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(owner.calls, ["start", "write"])
        self.assertTrue(backend.startup_complete)
        backend.close()
        self.assertFalse(backend.startup_complete)

    def test_parallel_error_retains_owner_without_counter_or_output_calls(self):
        owner = PreparedOwner()
        backend = CardBackend()
        with mock.patch("legacy.xp_acq_control.elyse_agent.parallel_initialization.prepare_parallel_cards",
                        side_effect=PartialTaskCreationError(RuntimeError("C10 pending"), owner)):
            with self.assertRaises(PartialTaskCreationError):
                backend.initialize(threading.Event(), startup_confirmed=True)
        self.assertIs(backend.owner, owner)
        self.assertFalse(backend.startup_complete)
        self.assertEqual(owner.calls, [])
        with self.assertRaises(RuntimeError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.calls, [])

    def test_every_remote_command_including_stop_rejected_before_startup_complete(self):
        state = dict(state="FAULT", resource_count=20, remote_setpoints_enabled=True,
                     startup_complete=False, recovery=dict(required=False, protection_active=True))
        capabilities = command_capabilities(state)
        self.assertTrue(capabilities)
        self.assertTrue(all(value == dict(enabled=False, reason="ALL_REQUIRED_CARDS_AND_STARTUP_NOT_READY")
                            for value in capabilities.values()))

    def test_runtime_retains_partial_startup_and_rejects_stops_without_admission_effects(self):
        backend = FailedRuntimeBackend()
        runtime = AcquisitionRuntime(lambda: backend, period=.02)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            deadline = time.monotonic() + 2
            while runtime.snapshot()["state"] != "FAULT" and time.monotonic() < deadline:
                threading.Event().wait(.01)
            self.assertEqual(runtime.snapshot()["state"], "FAULT")
            self.assertEqual(backend.close_calls, 0)
            for call in (lambda: runtime.general_stop(operator_confirmed=True),
                         lambda: runtime.outer_controlled_stop(operator_confirmed=True),
                         lambda: runtime.stage_request("chauffage.stop", operator_confirmed=True)):
                with self.assertRaises(RuntimeError):
                    call()
                self.assertEqual(runtime.snapshot()["state"], "FAULT")
        finally:
            runtime.request_shutdown()
            self.assertTrue(runtime.join(2))
        self.assertEqual(backend.close_calls, 1)

    def test_gui_exposes_every_card_and_last_native_function_without_extra_buttons(self):
        text = initialization_card_text(dict(initialization_cards=dict(cards={
            10: dict(state="TIMED_OUT_UNKNOWN", current_call="DAQmxCreateCOPulseChanTicks", elapsed_seconds=30.0),
            1: dict(state="READY", current_call="AI configure", elapsed_seconds=.5)})))
        self.assertLess(text.index("C01"), text.index("C10"))
        self.assertIn("DAQmxCreateCOPulseChanTicks", text)
        self.assertIn("TIMED_OUT_UNKNOWN", text)
        self.assertEqual(BUTTON_LABELS, ("Initialize", "Deinitialize", "Stop server"))
