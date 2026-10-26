"""Real private child processes with RAM hardware fixtures; Python 3.4.

No NI module, network, running XP process or live device is opened. One test
deliberately crashes ONLY the child it just created from crash_fixture.
"""
import os
import sys
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.card_process_owner import (
    CardProcessTasks, CardProcessEndpoint, CardRequestTimeout, create_card_process_tasks,
)
from legacy.xp_acq_control.elyse_agent.hardware_plan import AI_BANKS, DI_BANKS, DO_BANKS, AO_BANKS
from legacy.xp_acq_control.elyse_agent.hardware_tasks import PartialTaskCreationError, TaskCleanupError
from legacy.xp_acq_control.elyse_agent.card_service import CardService


class RamTask(object):
    def __init__(self, owner, name, count=0):
        self.owner, self.name, self.count = owner, name, count

    def start(self):
        self.owner.events.append(("start", self.name))

    def stop(self):
        self.owner.events.append(("stop", self.name))

    def read(self, timeout):
        self.owner.read_count += 1
        return [False] * self.count


class RamOwner(object):
    def __init__(self, device, mode="normal"):
        self.device, self.mode = device, mode
        self.tasks, self.events = {}, []
        self.read_count = self.write_count = self.legacy_start_count = 0
        self.running = []
        for name, number, count in AI_BANKS:
            if number == device:
                self.tasks[name] = RamTask(self, name, count)
        for name, number, first, last, count in DI_BANKS + DO_BANKS:
            if number == device:
                self.tasks[name] = RamTask(self, name, count)
        for name, number in AO_BANKS:
            if number == device:
                self.tasks[name + "_AO"] = RamTask(self, name + "_AO", 10)
        if device == 10:
            for number in range(8):
                name = "C10_NI6602_CO_{0}".format(number)
                self.tasks[name] = RamTask(self, name)

    def read_analog_latest(self, name, timeout):
        self.read_count += 1
        if self.mode == "read_failure" and self.read_count > 1:
            raise IOError("fixture input failure")
        return [float(self.read_count)] * self.tasks[name].count

    def write_digital_bank(self, name, values):
        if name not in self.tasks:
            raise ValueError("foreign fixture bank")
        if len(values) != self.tasks[name].count or any(type(v) is not bool for v in values):
            raise ValueError("fixture Boolean bank shape")
        if self.mode == "crash" and values[0]:
            os._exit(23)  # Private RAM child created by this test ONLY.
        if self.mode == "slow" and values[0]:
            time.sleep(.3)
        self.write_count += 1
        return len(values)

    def write_analog_logical_bank(self, name, values):
        if name + "_AO" not in self.tasks or len(values) != 10:
            raise ValueError("foreign fixture AO bank")
        self.write_count += 1
        return tuple(values)

    def start_legacy_counters(self):
        self.legacy_start_count += 1
        if self.mode == "partial_start":
            self.running = [0, 1]
            raise IOError("fixture partially started counters")
        self.running = [0, 1, 2, 5, 6, 7]
        return list(self.running)

    def start_counter(self, number):
        self.running.append(number)
        return dict(pid=os.getpid(), counter=number)

    def stop_counter(self, number):
        if number in self.running:
            self.running.remove(number)

    def read_counter_pulse_done(self, number):
        return True

    def write_counter_ticks(self, number, initial, low, high):
        return dict(pid=os.getpid(), running=list(self.running),
                    legacy_start_count=self.legacy_start_count)

    def get_counter_operation_report(self):
        return dict(pid=os.getpid(), write_count=self.write_count,
                    legacy_start_count=self.legacy_start_count, running=list(self.running),
                    ni_imported=any(n in sys.modules for n in ("nidaqmx", "PyDAQmx")))

    def close(self):
        self.tasks.clear()


def _make(selected_devices, mode="normal", **unused):
    return RamOwner(selected_devices[0], mode)


def normal_fixture(**options):
    return _make(**options)


def crash_fixture(**options):
    return _make(mode="crash", **options)


def slow_fixture(**options):
    return _make(mode="slow", **options)


def read_failure_fixture(**options):
    return _make(mode="read_failure", **options)


def partial_start_fixture(**options):
    return _make(mode="partial_start", **options)


def initialization_failure_fixture(**options):
    if options["selected_devices"] == (3,):
        raise IOError("fixture failed card preparation")
    return _make(**options)


def fixture_name(name):
    return __name__ + ":" + name


def wait_until(predicate, timeout=5.):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Bounded RAM fixture wait expired")


def make_owner(devices, name="normal_fixture", **options):
    options.setdefault("rpc_timeout", 1.)
    options.setdefault("initialize_timeout", 10.)
    options.setdefault("close_timeout", 1.)
    options.setdefault("period", .05)
    return create_card_process_tasks(authorized=True, outputs_commissioned=True,
        devices=devices, trusted_factory=fixture_name(name), **options)


class CardProcessOwnerTests(unittest.TestCase):
    def test_service_rejects_foreign_banks_and_input_lifecycle_before_effects(self):
        service = CardService(3, trusted_factory=fixture_name("normal_fixture"))
        service.initialize(threading.Event(), startup_confirmed=True)
        try:
            for action, arguments in (("task.start", ("C3_DIO96_DI",)),
                    ("task.stop", ("C3_DIO96_DO",)),
                    ("write_digital_bank", ("C4_DIO96_DO", tuple([False] * 32))),
                    ("write_analog_logical_bank", ("C6NI6703", tuple([0.] * 10))),
                    ("start_counter", (0,)), ("start_legacy_counters", ())):
                self.assertRaises(ValueError, service.card_call,
                    dict(action=action, arguments=arguments), threading.Event())
            self.assertEqual(service.owner.write_count, 0)
            self.assertEqual(service.owner.events, [])
        finally:
            service.close()

    def test_cold_construction_and_explicit_admission(self):
        endpoint = CardProcessEndpoint(10)
        self.assertIsNone(endpoint.status()["native"]["worker_pid"])
        endpoint.close()
        self.assertTrue(endpoint.status()["native"]["cleanup_confirmed"])
        self.assertRaises(ValueError, create_card_process_tasks)

    def test_one_process_per_card_and_counter_start_commit_once(self):
        owner = make_owner((1, 3, 10))
        try:
            wait_until(lambda: owner.input_snapshot()["all_current"])
            cards = owner.snapshot()["cards"]
            self.assertEqual(len(set(v["native"]["worker_pid"] for v in cards.values())), 3)
            self.assertEqual(cards["10"]["started_counters"], [])
            self.assertEqual(owner.start_legacy_counters(), [0, 1, 2, 5, 6, 7])
            self.assertEqual(owner.start_legacy_counters(), [0, 1, 2, 5, 6, 7])
            report = owner.write_counter_ticks(0, 0, 31, 20)
            self.assertEqual(report["legacy_start_count"], 1)
            self.assertFalse(owner.get_counter_operation_report()["ni_imported"])
            self.assertNotIn(3, report["running"])
            self.assertNotIn(4, report["running"])
            self.assertRaises(RuntimeError, owner.tasks["C1_NI6071E_AI"].start)
            self.assertRaises(RuntimeError, owner.tasks["C3_DIO96_DI"].stop)
            self.assertTrue(owner.read_counter_pulse_done(0))
            self.assertEqual(owner.start_counter(3)["pid"], cards["10"]["native"]["worker_pid"])
        finally:
            owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_full_topology_retains_21_tasks_and_source_startup_images(self):
        owner = make_owner(tuple(range(1, 12)), initialize_timeout=20.)
        try:
            self.assertEqual(owner.resource_count, 21)
            self.assertEqual(len(owner.tasks), 21)
            self.assertEqual(len(set(v["native"]["worker_pid"]
                                     for v in owner.snapshot()["cards"].values())), 11)
            self.assertEqual(owner.start_legacy_counters(), [0, 1, 2, 5, 6, 7])
            images = owner.write_initial_images()
            self.assertEqual(set(images["digital"]), {"C3_DIO96_DO", "C4_DIO96_DO", "C5_DIO96_DO"})
            self.assertEqual(set(images["analog_volts"]), {"C6NI6703", "C7NI6703", "C8NI6703", "C9NI6703"})
            wait_until(lambda: owner.input_snapshot()["all_current"])
            self.assertEqual(len(owner.input_snapshot()["banks"]), 6)
        finally:
            owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_foreground_read_does_not_return_idle_cache(self):
        owner = make_owner((1,), period=.5)
        try:
            wait_until(lambda: owner.input_snapshot()["all_current"])
            before = owner.input_snapshot()["banks"]["C1_NI6071E_AI"]["values"][0]
            fresh = owner.fresh_input(1)
            self.assertGreater(fresh["sample"]["banks"]["C1_NI6071E_AI"]["values"][0], before)
            self.assertLess(fresh["age_seconds"], 2.)
            self.assertEqual(fresh["card_generation"], owner.snapshot()["cards"]["1"]["native"]["worker_generation"])
        finally:
            owner.close()

    def test_read_failure_does_not_freshen_old_measurements(self):
        owner = make_owner((1,), "read_failure_fixture")
        try:
            wait_until(lambda: bool(owner.snapshot()["cards"]["1"]["input_error"]))
            state = owner.snapshot()["cards"]["1"]
            self.assertEqual(state["state"], "READY")
            self.assertIsNotNone(state["sample"])
            self.assertFalse(state["input_current"])
            self.assertEqual(owner.input_snapshot()["banks"], {})
            self.assertFalse(owner.input_snapshot()["all_current"])
        finally:
            owner.close()

    def test_unrelated_restart_preserves_synchronization_process_and_generation(self):
        owner = make_owner((3, 10))
        try:
            owner.start_legacy_counters()
            before = owner.snapshot()
            generation = before["cards"]["3"]["native"]["worker_generation"]
            self.assertRaises(ValueError, owner.restart_card, 3)
            result = owner.restart_card(3, True, generation)
            after = owner.snapshot()
            self.assertNotEqual(result["old_generation"], result["new_generation"])
            self.assertFalse(result["synchronization_interrupted"])
            self.assertEqual(before["cards"]["10"]["native"]["worker_generation"],
                             after["cards"]["10"]["native"]["worker_generation"])
            self.assertEqual(before["cards"]["10"]["native"]["worker_pid"],
                             after["cards"]["10"]["native"]["worker_pid"])
            self.assertEqual(owner.write_counter_ticks(0, 0, 31, 20)["legacy_start_count"], 1)
            self.assertRaises(RuntimeError, owner.restart_card, 3, True, generation)
        finally:
            owner.close()

    def test_crashed_card_retains_uncertainty_while_other_card_samples_continue(self):
        owner = make_owner((1, 3, 10), "crash_fixture", rpc_timeout=.5)
        owner.start_legacy_counters()
        wait_until(lambda: owner.input_snapshot()["all_current"])
        before = owner.snapshot()
        try:
            self.assertRaises(Exception, owner.write_digital_bank, "C3_DIO96_DO", [True] + [False] * 39)
            wait_until(lambda: owner.snapshot()["cards"]["1"]["sample_sequence"] >
                       before["cards"]["1"]["sample_sequence"])
            after = owner.snapshot()
            self.assertTrue(after["cards"]["3"]["native"]["ownership_uncertain"])
            self.assertIn("C1_NI6071E_AI", owner.input_snapshot()["banks"])
            self.assertNotIn("C3_DIO96_DI", owner.input_snapshot()["banks"])
            self.assertFalse(owner.input_snapshot()["all_current"])
            self.assertEqual(before["cards"]["10"]["native"]["worker_generation"],
                             after["cards"]["10"]["native"]["worker_generation"])
            self.assertRaises(RuntimeError, owner.restart_card, 3, True,
                              after["cards"]["3"]["native"]["worker_generation"])
        finally:
            self.assertRaises(TaskCleanupError, owner.close)
        self.assertEqual(owner.snapshot()["cards"]["1"]["state"], "CLOSED_JOINED")
        self.assertEqual(owner.snapshot()["cards"]["10"]["state"], "CLOSED_JOINED")
        self.assertGreater(owner.resource_count, 0)

    def test_expired_queued_write_is_never_dispatched_later(self):
        owner = make_owner((3,), "slow_fixture")
        errors = []
        def first_write():
            try:
                owner.write_digital_bank("C3_DIO96_DO", [True] + [False] * 39)
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=first_write)
        try:
            thread.start()
            wait_until(lambda: owner.snapshot()["cards"]["3"]["native"].get("worker_state") == "EXECUTING_CARD_CALL")
            self.assertRaises(CardRequestTimeout, owner._call, 3, "write_digital_bank",
                ("C3_DIO96_DO", tuple([False] * 40)), .05)
            thread.join(3.)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            wait_until(lambda: owner.snapshot()["cards"]["3"]["queue_depth"] == 0)
            self.assertEqual(owner.dispatchers[3].last_driver_report["write_count"], 1)
        finally:
            owner.close()

    def test_partial_initialization_preserves_each_owner_without_counter_start(self):
        with self.assertRaises(PartialTaskCreationError) as failure:
            make_owner((3, 10), "initialization_failure_fixture")
        owner = failure.exception.owner
        try:
            self.assertEqual(owner.snapshot()["cards"]["10"]["started_counters"], [])
            self.assertFalse(owner.snapshot()["all_required_ready"])
            self.assertRaises(RuntimeError, owner.start_legacy_counters)
        finally:
            owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_partial_counter_start_is_not_replayed(self):
        owner = make_owner((10,), "partial_start_fixture")
        try:
            self.assertRaises(Exception, owner.start_legacy_counters)
            self.assertRaises(RuntimeError, owner.start_legacy_counters)
            report = owner.write_counter_ticks(0, 0, 31, 20)
            self.assertEqual(report["legacy_start_count"], 1)
            self.assertEqual(report["running"], [0, 1])
        finally:
            owner.close()

    def test_old_counter_task_proxy_cannot_address_replaced_generation(self):
        owner = make_owner((10,))
        try:
            owner.start_legacy_counters()
            stale_task = owner.tasks["C10_NI6602_CO_0"]
            state = owner.snapshot()["cards"]["10"]
            result = owner.restart_card(10, True, state["native"]["worker_generation"])
            self.assertTrue(result["synchronization_interrupted"])
            self.assertRaises(RuntimeError, stale_task.start)
            self.assertIsNone(owner.tasks["C10_NI6602_CO_0"].stop())
        finally:
            owner.close()


if __name__ == "__main__":
    unittest.main()
