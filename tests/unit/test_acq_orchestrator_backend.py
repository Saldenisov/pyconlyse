"""Direct main-orchestrator ownership; actual Python 3.4 private RAM children.

No NI module, XP host, serial endpoint or network is opened. The only native
processes started here are this test's private card services with RAM owners.
"""
import copy
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import control_backend_factory
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.card_process_owner import create_card_process_tasks
from legacy.xp_acq_control.elyse_agent.chroma_focal_command import ChromaFocalCommand
from legacy.xp_acq_control.elyse_agent.isolated_backend import IsolatedCardBackend
from legacy.xp_acq_control.elyse_agent.orchestrator_backend import PerCardOrchestratorBackend
from tests.unit.test_acq_card_process_owner import RamOwner, wait_until
from tests.unit.test_acq_fault_diagnostic import Wake


class ParentRecordingOwner(RamOwner):
    def read_analog_latest(self, name, timeout):
        values = RamOwner.read_analog_latest(self, name, timeout)
        return [float(os.getppid())] * len(values)

    def get_counter_operation_report(self):
        result = RamOwner.get_counter_operation_report(self)
        result["parent_pid"] = os.getppid()
        return result


def parent_recording_fixture(**options):
    return ParentRecordingOwner(options["selected_devices"][0])


def _process_factory(**options):
    options.update(trusted_factory=__name__ + ":parent_recording_fixture",
                   initialize_timeout=20., close_timeout=1., rpc_timeout=2., period=.05)
    return create_card_process_tasks(**options)


class Focal(object):
    resources_verified = False

    def __init__(self):
        self.pending_worker_count = 0

    def ensure_quiescent(self):
        if self.pending_worker_count:
            raise RuntimeError("retained private helper")

    def snapshot(self):
        return dict(pending_worker_count=self.pending_worker_count, hardware_acknowledged=False)


def _backend():
    backend = PerCardOrchestratorBackend(operator_supervised_test=True,
        control_profile="extended_ht_stop", focal_command=Focal())
    with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.create_card_process_tasks",
               side_effect=_process_factory):
        backend.initialize(threading.Event(), startup_confirmed=True)
    wait_until(lambda: backend.owner.input_snapshot()["all_current"])
    return backend


def _runtime(backend):
    runtime = AcquisitionControlRuntime(lambda: backend, remote_enabled=True)
    runtime._backend, runtime._state = _ObservedBackend(backend, runtime), "RUNNING"
    runtime._ht_sequence_owner = runtime._backend
    runtime._ht_sequence_generation = backend.isolation_snapshot()["worker_generation"]
    runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
    return runtime


class OrchestratorBackendTests(unittest.TestCase):
    def test_owner_publication_failure_precedes_any_dispatcher_or_native_spawn(self):
        created = []
        def publish(owner):
            created.append(owner)
            self.assertEqual(owner.dispatchers, {})
            self.assertEqual(owner.resource_count, 0)
            raise RuntimeError("private owner publication failure")
        with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.CardProcessEndpoint.start") as start:
            self.assertRaises(RuntimeError, create_card_process_tasks,
                authorized=True, outputs_commissioned=True, owner_created=publish)
            self.assertFalse(start.called)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].dispatchers, {})

    def test_gui_factory_selects_cold_direct_per_card_and_preserves_chroma_options(self):
        focal = dict(dll_path=r"C:\private-test\Chroma.dll", resources_verified=False,
                     timeout=7., operator_supervised_test=True)
        with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.create_card_process_tasks") as create:
            factory = control_backend_factory(dict(native_isolation_mode="per_card"), focal)
            self.assertFalse(create.called)
            backend = factory()
            self.assertIsInstance(backend, PerCardOrchestratorBackend)
            self.assertNotIsInstance(backend, IsolatedCardBackend)
            self.assertFalse(create.called)
            self.assertEqual(backend.resource_count, 0)
            cold = backend.isolation_snapshot()
            self.assertEqual(cold["worker_state"], "COLD")
            self.assertFalse(cold["ownership_uncertain"])
            self.assertIsNone(cold["active_request_id"])
            self.assertEqual(cold["worker_pid"], os.getpid())
            self.assertEqual(len(cold["worker_generation"]), 32)
            int(cold["worker_generation"], 16)
            self.assertIsInstance(backend.focal_command, ChromaFocalCommand)
            self.assertEqual(backend.focal_command.dll_path, focal["dll_path"])
            self.assertEqual(backend.focal_command.timeout, focal["timeout"])
            self.assertTrue(backend.focal_command.operator_supervised_test)
            self.assertFalse(backend.focal_command.resources_verified)
        legacy = control_backend_factory(dict(native_isolation_mode="single_owner"), focal)()
        self.assertIsInstance(legacy, IsolatedCardBackend)
        self.assertEqual(legacy.resource_count, 0)
        self.assertRaises(ValueError, PerCardOrchestratorBackend, native_isolation_mode="single_owner")

    def test_eleven_native_children_are_directly_owned_by_main_orchestrator(self):
        original_ni = set(name for name in sys.modules if name in ("nidaqmx", "PyDAQmx"))
        backend = PerCardOrchestratorBackend(operator_supervised_test=True,
            control_profile="extended_ht_stop", focal_command=Focal())
        runtime = _runtime(backend)
        runtime._state = "INITIALIZING"
        with patch("legacy.xp_acq_control.elyse_agent.card_process_owner.create_card_process_tasks",
                   side_effect=_process_factory):
            runtime._backend.initialize(threading.Event(), startup_confirmed=True)
        runtime._state = "RUNNING"
        wait_until(lambda: backend.owner.input_snapshot()["all_current"])
        generation = backend.isolation_snapshot()["worker_generation"]
        try:
            # Direct callback identity must satisfy the unchanged runtime
            # fence, including the INITIAL_LITERAL EPS/DPS observation.
            self.assertIsNotNone(runtime._software_state)
            self.assertEqual(runtime._software_error, "")
            self.assertEqual(backend.started_counters, [0, 1, 2, 5, 6, 7])
            self.assertEqual(backend.resource_count, 21)
            before = backend.isolation_snapshot()
            self.assertEqual(before["worker_state"], "IDLE_OWNED")
            self.assertIsNone(before["active_request_id"])
            self.assertFalse(before["commands_in_flight"])
            self.assertFalse(before["ownership_uncertain"])
            self.assertFalse(before["main_process_owns_ni_tasks"])
            self.assertEqual(len(before["component_generations"]), 11)
            children = set()
            for device, dispatcher in backend.owner.dispatchers.items():
                # These Popen instances are retained directly by dispatcher
                # clients in THIS process, rather than serialized grandchild IDs.
                process = dispatcher.client._process
                children.add(process.pid)
                self.assertEqual(process.pid, before["component_states"][str(device)]["worker_pid"])
                self.assertNotEqual(process.pid, os.getpid())
                if device in (1, 2, 11):
                    wait_until(lambda: dispatcher.input_snapshot()["current"])
                    values = next(iter(dispatcher.input_snapshot()["sample"]["banks"].values()))["values"]
                    self.assertEqual(values[0], float(os.getpid()))
                else:
                    with dispatcher.lock:
                        report = copy.deepcopy(dispatcher.last_driver_report)
                    self.assertEqual(report["parent_pid"], os.getpid())
                    self.assertFalse(report["ni_imported"])
            self.assertEqual(len(children), 11)
            sample = backend.read_snapshot(threading.Event())
            self.assertEqual(len(sample["banks"]), 6)
            self.assertTrue(sample["input_health"]["all_current"])
            self.assertEqual(backend.isolation_snapshot()["worker_generation"], generation)
            self.assertEqual(set(name for name in sys.modules if name in ("nidaqmx", "PyDAQmx")), original_ni)

            runtime._latest = sample
            runtime._received_at = time.monotonic() - sample["source_age_seconds"]
            self.assertTrue(runtime._owner_telemetry_current())
            self.assertTrue(runtime.snapshot()["measurement_current"])

            observed, phases = [], []
            def observe(event):
                observed.append(event)
                phases.append(backend.isolation_snapshot())
            backend.set_execution_observer(observe)
            backend.record_procedure_request("modulator.general.start")
            self.assertTrue(observed)
            event = observed[-1]
            self.assertEqual(event["worker_generation"], generation)
            self.assertEqual(event["worker_pid"], os.getpid())
            self.assertGreater(event["active_request_id"], 0)
            self.assertEqual(event["kind"], "SOFTWARE_STATE_NOT_MEASUREMENT")
            self.assertGreaterEqual(event["software_state_age_seconds"], 0.)
            self.assertEqual(phases[-1]["worker_state"], "EXECUTING_OP")
            self.assertTrue(phases[-1]["commands_in_flight"])
            self.assertEqual(phases[-1]["active_request_id"], event["active_request_id"])
            self.assertEqual(backend.isolation_snapshot()["worker_state"], "IDLE_OWNED")

            # Logical controller identity stays stable across an explicitly
            # clean input replacement; component identity rejects old data.
            card10 = copy.deepcopy(before["component_states"]["10"])
            backend.owner.restart_card(1, affected_outputs_off_confirmed=True,
                expected_generation=before["component_states"]["1"]["worker_generation"])
            wait_until(lambda: backend.owner.input_snapshot()["all_current"])
            after = backend.isolation_snapshot()
            self.assertEqual(after["worker_generation"], generation)
            self.assertNotEqual(after["component_generations"], before["component_generations"])
            self.assertEqual(after["component_states"]["10"]["worker_generation"], card10["worker_generation"])
            self.assertEqual(after["component_states"]["10"]["worker_pid"], card10["worker_pid"])
            self.assertFalse(runtime.snapshot()["measurement_current"])
        finally:
            backend.close()
        closed = backend.isolation_snapshot()
        self.assertEqual(closed["worker_state"], "CLOSED_JOINED")
        self.assertTrue(closed["cleanup_confirmed"])
        self.assertEqual(closed["resource_count"], 0)
        self.assertEqual(closed["worker_generation"], generation)

    def test_fault_read_gate_uses_same_logical_generation_and_explicit_read_request(self):
        backend = _backend()
        runtime = _runtime(backend)
        runtime._general_stop_required = True
        runtime._procedure_fault(RuntimeError("private RAM sticky procedure fault"))
        self.assertTrue(runtime._fault_diagnostic_ready())
        entered, release = threading.Event(), threading.Event()
        original_read = backend._read_snapshot
        calls = [0]
        def delayed_read(cancel, deadline):
            calls[0] += 1
            if calls[0] == 2:
                entered.set()
                if not release.wait(5.):
                    raise AssertionError("private diagnostic read was not released")
            return original_read(cancel, deadline)
        runtime._wake = Wake(runtime, 2)
        worker = threading.Thread(target=runtime._run)
        try:
            with patch.object(backend, "_read_snapshot", side_effect=delayed_read):
                worker.start()
                self.assertTrue(entered.wait(3.))
                native = backend.isolation_snapshot()
                self.assertEqual(native["worker_state"], "EXECUTING_READ_SNAPSHOT")
                self.assertGreater(native["active_request_id"], 0)
                self.assertFalse(native["commands_in_flight"])
                self.assertFalse(native["ownership_uncertain"])
                self.assertFalse(runtime._fault_diagnostic_ready())
                state = runtime.try_telemetry_snapshot()
                self.assertEqual(state["state"], "FAULT")
                self.assertFalse(state["measurement_current"])
                self.assertTrue(state["fault_diagnostic_measurement"]["current"])
                self.assertTrue(state["fault_diagnostic_measurement"]["read_in_progress"])
                self.assertEqual(state["fault_diagnostic_measurement"]["worker_generation"], native["worker_generation"])
                self.assertRaises(RuntimeError, backend.general_start, threading.Event(), operator_confirmed=True)
                release.set()
                worker.join(5.)
            self.assertFalse(worker.is_alive())
            self.assertEqual(calls[0], 2)
            self.assertEqual(backend.isolation_snapshot()["worker_state"], "IDLE_OWNED")
            self.assertTrue(all(v["fault_diagnostic_measurement"]["current"] for v in runtime._wake.views))
        finally:
            release.set()
            if worker.ident is not None:
                worker.join(5.)
            backend.close()

    def test_known_input_failure_is_not_ownership_loss_but_unresolved_native_is(self):
        backend = _backend()
        try:
            card = backend.owner.dispatchers[1]
            with card.lock:
                card.input_error = "private ordinary read error"
            self.assertFalse(backend.isolation_snapshot()["ownership_uncertain"])
            with card.lock:
                card.unresolved_request = True
            self.assertTrue(backend.isolation_snapshot()["ownership_uncertain"])
            self.assertGreater(backend.isolation_snapshot()["resource_count"], 0)
            with card.lock:
                card.unresolved_request = False
            native = card.client.isolation_snapshot()
            with patch.object(card.client, "isolation_snapshot", return_value=dict(native, ownership_uncertain=True)):
                self.assertTrue(backend.isolation_snapshot()["ownership_uncertain"])
                runtime = _runtime(backend)
                runtime._procedure_fault(RuntimeError("private uncertain owner"))
                self.assertFalse(runtime._fault_diagnostic_ready())
            backend.focal_command.pending_worker_count = 1
            self.assertTrue(backend.isolation_snapshot()["ownership_uncertain"])
            self.assertEqual(backend.isolation_snapshot()["resource_count"], 22)
            backend.focal_command.pending_worker_count = 0
            self.assertFalse(backend.isolation_snapshot()["ownership_uncertain"])
        finally:
            backend.focal_command.pending_worker_count = 0
            backend.close()


if __name__ == "__main__":
    unittest.main()
