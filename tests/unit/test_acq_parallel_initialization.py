"""Parallel preparation with injected owners only; no NI, XP or card APIs."""
import ast
import os
import sys
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent import hardware_plan
from legacy.xp_acq_control.elyse_agent.hardware_tasks import (
    LegacyCardTasks, PartialTaskCreationError, TaskCleanupError,
)
from legacy.xp_acq_control.elyse_agent.parallel_initialization import (
    BOUNDARY_KIND, STATUS_KIND, ParallelCardPreparationError, prepare_parallel_cards,
)


class FakeTask(object):
    def __init__(self, name, calls):
        self.name, self.calls = name, calls
        self.close_count = 0
        self.fail_close_once = False

    def start(self):
        self.calls.append((self.name, "start"))

    def write(self, *args, **kwargs):
        self.calls.append((self.name, "write"))

    def read(self, *args, **kwargs):
        raise AssertionError("Preparation cannot measure")

    def close(self):
        self.close_count += 1
        if self.fail_close_once:
            self.fail_close_once = False
            raise RuntimeError("fixture close failure")
        self.calls.append((self.name, "close"))


def fake_owner(card, calls):
    names = [entry[0] for entry in hardware_plan.AI_BANKS if entry[1] == card]
    names += [entry[0] for entry in hardware_plan.DI_BANKS + hardware_plan.DO_BANKS
              if entry[1] == card]
    names += [entry[0] + "_AO" for entry in hardware_plan.AO_BANKS if entry[1] == card]
    if card == 10:
        names += ["C10_NI6602_CO_{0}".format(number) for number in range(8)]
    plan = hardware_plan.card_initialization_plan()
    plan["device_numbers"] = (card,)
    if card != 10:
        plan["counter_output"] = []
    return LegacyCardTasks(None, plan, dict((name, FakeTask(name, calls)) for name in names),
                           dict((number, object()) for number in range(8)) if card == 10 else {})


def join_workers(owner):
    for thread in owner.threads.values():
        thread.join(2)
        if thread.is_alive():
            raise AssertionError("Fixture initialization worker did not settle")


class ParallelInitializationTests(unittest.TestCase):
    def test_all_eleven_enter_concurrently_and_merge_without_start_write_or_read(self):
        barrier, calls, events, entered, handles = threading.Barrier(11), [], [], [], []
        coordinator = threading.current_thread().ident
        observer_threads = []

        def observer(event):
            observer_threads.append(threading.current_thread().ident)
            events.append(event)

        def create(**options):
            self.assertIs(options["authorized"], True)
            self.assertIs(options["outputs_commissioned"], True)
            card, = options["selected_devices"]
            entered.append(card)
            options["observer"](dict(phase="ENTER", call="fixture configuration",
                                     utc="fixture worker timestamp"))
            barrier.wait(2)
            owner = fake_owner(card, calls)
            handles.extend(owner.tasks.values())
            options["observer"](dict(phase="RETURNED", call="fixture configuration"))
            return owner

        merged = prepare_parallel_cards(create, threading.Event(), observer, timeout=3)
        self.assertIs(type(merged), LegacyCardTasks)
        self.assertEqual(sorted(entered), list(range(1, 12)))
        self.assertEqual(merged.plan, hardware_plan.card_initialization_plan())
        self.assertEqual(len(merged.tasks), 21)
        self.assertEqual(set(merged.counter_channels), set(range(8)))
        self.assertEqual(calls, [])
        wrapper = merged.parallel_initialization
        self.assertIs(wrapper.tasks, merged.tasks)
        self.assertTrue(all(thread.daemon for thread in wrapper.threads.values()))
        self.assertEqual(set(observer_threads), {coordinator})
        self.assertTrue(all(not owner.tasks for owner in wrapper.owners.values()))
        self.assertEqual([wrapper.snapshot()["cards"][card]["task_count"] for card in range(1, 12)],
                         [1, 1, 2, 2, 2, 1, 1, 1, 1, 8, 1])
        statuses = [event["initialization_cards"] for event in events if event["kind"] == STATUS_KIND]
        self.assertTrue(statuses[-1]["all_required_ready"])
        boundaries = [event for event in events if event["kind"] == BOUNDARY_KIND]
        self.assertEqual(set(event["card"] for event in boundaries), set(range(1, 12)))
        self.assertTrue(all(event["utc"] for event in boundaries))
        self.assertEqual(len([event for event in boundaries if event["utc"] == "fixture worker timestamp"]), 11)

        # The caller still explicitly starts counters before writing startup images.
        self.assertEqual(merged.start_legacy_counters(), [0, 1, 2, 5, 6, 7])
        merged.write_initial_images()
        self.assertEqual([method for _name, method in calls], ["start"] * 6 + ["write"] * 7)
        join_workers(wrapper)
        wrapper.close()
        wrapper.close()
        self.assertEqual(wrapper.resource_count, 0)
        self.assertTrue(all(task.close_count == 1 for task in handles))

    def test_normal_and_partial_failures_do_not_skip_other_cards_or_release_owners(self):
        barrier, calls, entered, handles = threading.Barrier(3), [], [], []

        class DriverError(RuntimeError):
            error_code = -200220

        def create(**options):
            card, = options["selected_devices"]
            entered.append(card)
            barrier.wait(2)
            if card == 2:
                raise DriverError("fixture absent card")
            owner = fake_owner(card, calls)
            handles.extend(owner.tasks.values())
            if card == 3:
                raise PartialTaskCreationError("fixture retained partial card", owner)
            return owner

        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(create, threading.Event(), timeout=3, devices=(1, 2, 3))
        self.assertIsInstance(raised.exception, PartialTaskCreationError)
        owner = raised.exception.owner
        join_workers(owner)
        self.assertEqual(sorted(entered), [1, 2, 3])
        self.assertEqual(set(owner.owners), {1, 3})
        self.assertEqual(owner.resource_count, 3)
        self.assertEqual(len(owner.tasks), 3)
        self.assertEqual(calls, [])
        cards = owner.snapshot()["cards"]
        self.assertEqual([cards[card]["state"] for card in (1, 2, 3)], ["READY", "FAILED", "FAILED"])
        self.assertEqual(cards[2]["error_code"], -200220)
        self.assertEqual(cards[2]["error"]["message"], "fixture absent card")
        self.assertFalse(owner.snapshot()["all_required_ready"])
        owner.close()
        self.assertTrue(all(task.close_count == 1 for task in handles))

    def test_one_total_timeout_retains_all_workers_and_late_returned_handles(self):
        release, barrier = threading.Event(), threading.Barrier(11)
        calls, handles = [], []

        def create(**options):
            card, = options["selected_devices"]
            owner = fake_owner(card, calls)
            handles.extend(owner.tasks.values())
            options["observer"](dict(phase="ENTER", call="fixture blocked native call"))
            barrier.wait(2)
            release.wait(3)
            return owner

        started = time.monotonic()
        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(create, threading.Event(), timeout=0.15)
        elapsed = time.monotonic() - started
        owner = raised.exception.owner
        try:
            self.assertLess(elapsed, 0.8)
            self.assertEqual(len(owner.snapshot()["pending_cards"]), 11)
            self.assertTrue(all(card["state"] == "TIMED_OUT_UNKNOWN"
                                for card in owner.snapshot()["cards"].values()))
            self.assertEqual(owner.resource_count, 11)  # Unknown-ownership sentinels.
            self.assertEqual(owner.tasks, {})
            self.assertTrue(all(thread.is_alive() for thread in owner.threads.values()))
            with self.assertRaisesRegex(RuntimeError, "ownership retained"):
                owner.close()
            self.assertEqual(calls, [])
            self.assertTrue(all(task.close_count == 0 for task in handles))
        finally:
            release.set()
            join_workers(owner)
        self.assertEqual(owner.resource_count, 21)
        self.assertEqual(len(owner.tasks), 21)
        self.assertTrue(all(card["state"] == "READY" and card["timed_out"]
                            for card in owner.snapshot()["cards"].values()))
        self.assertFalse(owner.snapshot()["all_required_ready"])
        owner.close()
        self.assertEqual(owner.resource_count, 0)
        self.assertTrue(all(task.close_count == 1 for task in handles))

    def test_cancellation_retains_pending_calls_and_never_accepts_late_success(self):
        cancel, release, barrier = threading.Event(), threading.Event(), threading.Barrier(3)
        calls = []

        def create(**options):
            card, = options["selected_devices"]
            barrier.wait(2)
            cancel.set()
            release.wait(3)
            return fake_owner(card, calls)

        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(create, cancel, timeout=3, devices=(1, 2, 3))
        owner = raised.exception.owner
        try:
            self.assertTrue(owner.snapshot()["cancelled"])
            self.assertEqual([card["state"] for card in owner.snapshot()["cards"].values()],
                             ["CANCELLED_UNKNOWN"] * 3)
            with self.assertRaises(RuntimeError):
                owner.close()
            self.assertEqual(calls, [])
        finally:
            release.set()
            join_workers(owner)
        self.assertFalse(owner.snapshot()["all_required_ready"])
        owner.close()

    def test_preexisting_cancellation_does_not_enter_any_card(self):
        cancel, entered = threading.Event(), []
        cancel.set()
        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(lambda **options: entered.append(options), cancel)
        owner = raised.exception.owner
        join_workers(owner)
        self.assertEqual(entered, [])
        self.assertEqual(owner.resource_count, 0)
        self.assertTrue(all(card["state"] == "CANCELLED_NOT_ENTERED"
                            for card in owner.snapshot()["cards"].values()))
        owner.close()

    def test_duplicate_task_or_counter_names_fail_without_losing_either_owner(self):
        for duplicate_counter in (False, True):
            with self.subTest(duplicate_counter=duplicate_counter):
                calls, handles = [], []

                def create(**options):
                    card, = options["selected_devices"]
                    name = "card{0}".format(card) if duplicate_counter else "duplicate"
                    task = FakeTask(name, calls)
                    handles.append(task)
                    return LegacyCardTasks(None, {}, {name: task}, {0: object()} if duplicate_counter else {})

                with self.assertRaises(ParallelCardPreparationError) as raised:
                    prepare_parallel_cards(create, threading.Event(), devices=(1, 2))
                owner = raised.exception.owner
                join_workers(owner)
                self.assertIn("Duplicate", str(raised.exception))
                self.assertEqual(len(owner.tasks), 2)
                self.assertEqual(owner.resource_count, 2)
                self.assertEqual(calls, [])
                owner.close()
                self.assertTrue(all(task.close_count == 1 for task in handles))

    def test_cleanup_failure_does_not_skip_other_retained_owners_and_can_be_retried(self):
        calls, handles = [], []

        def create(**options):
            card, = options["selected_devices"]
            if card == 3:
                raise ValueError("fixture failure")
            owner = fake_owner(card, calls)
            handles.extend(owner.tasks.values())
            if card == 1:
                next(iter(owner.tasks.values())).fail_close_once = True
            return owner

        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(create, threading.Event(), devices=(1, 2, 3))
        owner = raised.exception.owner
        join_workers(owner)
        with self.assertRaises(TaskCleanupError):
            owner.close()
        self.assertEqual(owner.resource_count, 1)
        self.assertEqual(sorted(task.close_count for task in handles), [1, 1])
        owner.close()
        self.assertEqual(owner.resource_count, 0)
        self.assertEqual(sorted(task.close_count for task in handles), [1, 2])

    def test_diagnostic_observer_failure_does_not_interrupt_preparation(self):
        def broken(event):
            raise OSError("fixture diagnostic failure")
        merged = prepare_parallel_cards(lambda **options: fake_owner(options["selected_devices"][0], []),
                                        threading.Event(), broken, devices=(1,))
        join_workers(merged.parallel_initialization)
        merged.close()

    def test_missing_owner_is_a_card_failure_and_does_not_skip_another_card(self):
        entered, calls = [], []

        def create(**options):
            card, = options["selected_devices"]
            entered.append(card)
            return None if card == 1 else fake_owner(card, calls)

        with self.assertRaises(ParallelCardPreparationError) as raised:
            prepare_parallel_cards(create, threading.Event(), devices=(1, 2))
        owner = raised.exception.owner
        join_workers(owner)
        self.assertEqual(sorted(entered), [1, 2])
        self.assertEqual(owner.snapshot()["cards"][1]["state"], "FAILED")
        self.assertEqual(owner.snapshot()["cards"][1]["error"]["error_type"], "TypeError")
        self.assertEqual(owner.resource_count, 1)
        self.assertEqual(calls, [])
        owner.close()

    def test_production_module_parses_with_python34_grammar(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "legacy", "xp_acq_control",
                            "elyse_agent", "parallel_initialization.py")
        with open(path, "r") as source:
            text = source.read()
        if sys.version_info >= (3, 8):
            ast.parse(text, feature_version=(3, 4))
        else:
            ast.parse(text)  # Actual deployed grammar on the Python 3.4 lane.


if __name__ == "__main__":
    unittest.main()
