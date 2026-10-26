"""Optional local takeover timing: RAM NI fixture, actual Python3.4 compatible."""
import copy
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.supervision_cards import (
    SupervisionCounterCard, SupervisionCardError, validate_initial_sync_values_us)
from legacy.xp_acq_control.elyse_agent.supervision_service import SupervisionSyncService
from legacy.xp_acq_control.elyse_agent.supervision_gui import (
    BUTTON_LABELS, default_supervision_configuration, validate_supervision_configuration)
from legacy.xp_acq_control.elyse_agent.synchronization_profiles import (
    supervision_counter_profile, source_timing_pairs)
from tests.unit.test_supervision_card_adapters import FakeDriver


# An explicitly supplied RAM test profile, not an assertion about current
# physical timing or which live VI/application context owns these values.
REVIEWED_TEST_PROFILE = (.35, .35, 4691.200000000001, 100., 2000.4999999999995, 10.,
    2175., 10., 2175., 100., 1250., 500., .3, 10., 2175., 100.)
EXPECTED_TICKS = ((7, 7), (93824, 2000), (40010, 200), (43500, 200),
    (43500, 2000), (25000, 10000), (6, 200), (43500, 2000))


class SupervisionInitialSyncProfileTests(unittest.TestCase):
    def test_reviewed_local_profile_configures_all_eight_before_first_start(self):
        driver = FakeDriver()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        before = supervision_counter_profile()
        state = owner.initialize(True, True, initial_sync_values_us=REVIEWED_TEST_PROFILE)
        starts = [i for i, event in enumerate(driver.trace) if event[0] == "start"]
        configurations = [i for i, event in enumerate(driver.trace) if event[0] == "timing"]
        self.assertEqual(len(starts), 8)
        self.assertLess(max(configurations), min(starts))
        self.assertEqual([driver.trace[i][1] for i in starts], list(range(8)))
        for i, pair in enumerate(EXPECTED_TICKS):
            channel = next(event for event in driver.trace if event[:2] == ("channel", i))
            self.assertEqual(channel[2:4], ("Dev1/ctr" + str(i), "/Dev1/PFI11"))
            self.assertEqual(channel[4], dict(idle_state="LOW", initial_delay=0,
                                            low_ticks=pair[0], high_ticks=pair[1]))
            self.assertIn(("trigger", i, "/Dev1/PFI10", {"trigger_edge": "RISING"}), driver.trace)
            self.assertIsNone(state["synchronization"]["counter_ticks"][i]["physical_timebase_hz"])
        self.assertIn("not_physical_readback", state["synchronization"]["initial_timing_provenance"])
        self.assertEqual(supervision_counter_profile(), before)
        owner.close()

    def test_entire_profile_is_validated_before_driver_load_or_any_task(self):
        invalid = [[], list(REVIEWED_TEST_PROFILE[:-1]), True]
        for bad in (True, float("nan"), float("inf"), 0., -1., .001, 2147483648. / 20., 10 ** 500):
            row = list(REVIEWED_TEST_PROFILE)
            row[-1] = bad
            invalid.append(row)
        for values in invalid:
            calls, driver = [], FakeDriver()
            owner = SupervisionCounterCard(driver_factory=lambda: calls.append("native import") or driver)
            self.assertRaises(ValueError, owner.initialize, True, True, None, values)
            self.assertEqual(calls, [])
            self.assertEqual(driver.trace, [])
            self.assertEqual(owner.resource_count, 0)

    def test_partial_override_configuration_never_starts_any_counter(self):
        class LastConfigurationFails(FakeDriver):
            def Task(self, new_task_name):
                task = FakeDriver.Task(self, new_task_name)
                if task.number == 7:
                    def fail(**values):
                        self.trace.append(("timing_failure", 7))
                        raise IOError("injected eighth counter configuration failure")
                    task.timing.cfg_implicit_timing = fail
                return task
        driver = LastConfigurationFails()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        self.assertRaises(SupervisionCardError, owner.initialize, True, True, None, REVIEWED_TEST_PROFILE)
        self.assertFalse(any(event[0] == "start" for event in driver.trace))
        self.assertEqual(owner.resource_count, 8)
        owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_source_factor_and_nearest_even_tick_encoding(self):
        driver = FakeDriver()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        values = list(REVIEWED_TEST_PROFILE)
        values[:2] = [.125, .175]  # 2.5 ->2, 3.5 ->4 at source factor20.
        owner.initialize(True, True, initial_sync_values_us=values)
        first = next(event for event in driver.trace if event[:2] == ("channel", 0))
        self.assertEqual((first[4]["low_ticks"], first[4]["high_ticks"]), (2, 4))
        self.assertEqual(first[4]["initial_delay"], 0)
        owner.close()

    def test_service_validates_cold_profile_and_passes_it_to_retained_adapter(self):
        self.assertRaises(ValueError, SupervisionSyncService, initial_sync_values_us=[1.] * 15)
        service = SupervisionSyncService(initial_sync_values_us=REVIEWED_TEST_PROFILE)
        self.assertIsNone(service.adapter)
        driver = FakeDriver()
        service.adapter = SupervisionCounterCard(driver_factory=lambda: driver)
        self.assertEqual(driver.trace, [])
        result = service.initialize(threading.Event(), startup_confirmed=True)
        self.assertEqual(result["started_counters"], list(range(8)))
        memory = service.read_snapshot(threading.Event())["counter_memory"]
        self.assertEqual(memory["timing_pairs_us"][2:6], (4691.2, 100., 2000.5, 10.))
        self.assertFalse(memory["physical_readback"])
        service.close()

    def test_local_configuration_optional_profile_and_default_source_are_distinct(self):
        config = default_supervision_configuration()
        self.assertNotIn("initial_sync_values_us", config)
        self.assertEqual(source_timing_pairs(supervision_counter_profile())[2:6], (2176., 100., 2008.3, 10.))
        config["initial_sync_values_us"] = list(REVIEWED_TEST_PROFILE)
        self.assertIs(validate_supervision_configuration(config), config)
        for values in (None, [1.] * 15, [float("nan")] * 16):
            bad = copy.deepcopy(config)
            bad["initial_sync_values_us"] = values
            self.assertRaises(ValueError, validate_supervision_configuration, bad)
        self.assertEqual(BUTTON_LABELS, ("Initialize", "Deinitialize", "Stop server"))


if __name__ == "__main__":
    unittest.main()
