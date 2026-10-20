"""Original outer-stop callback execution; fake memory only, Python 3.4."""
import unittest
from unittest.mock import patch

from legacy.xp_acq_agent.elyse_agent.acquisition_outer_stop import (
    BANK_SHAPES, CONTROLLED_STOP, OuterStopExecutionCancelled,
    OuterStopExecutionError, SOURCE_ARCHIVE_SHA256, SOURCE_VI_SHA256,
    execute_outer_stop,
)


class Fixture(object):
    def __init__(self, ht=0.0):
        self.banks = {}
        for bank, (size, kind) in BANK_SHAPES.items():
            self.banks[bank] = tuple(float(i + bank) if kind is float else True
                                     for i in range(size))
        self.banks[12] = (ht,) + self.banks[12][1:]
        self.banks.update({35: False, 46: False, 47: True, 48: 0.0, 50: 0.0})
        self.events, self.frames, self.reads = [], [], []
        self.done = {3: False, 4: False}
        self.cancel = False

    def read(self, bank):
        self.reads.append(bank)
        return self.banks[bank]

    def write(self, bank, changes):
        self.events.append(("write", bank, changes))
        if bank in BANK_SHAPES:
            values = list(self.banks[bank])
            for field, value in changes:
                values[field] = value
            self.banks[bank] = tuple(values)
        else:
            self.banks[bank] = changes[0][1]

    def pulse_done(self, number):
        self.events.append(("poll", number))
        return self.done[number]

    def stop(self, number):
        self.events.append(("stop", number))

    def wait(self, seconds):
        self.events.append(("wait", seconds))

    def observer(self, index, uid):
        self.frames.append((index, uid))

    def execute(self, **kwargs):
        return execute_outer_stop(self.read, self.write, self.pulse_done,
                                  self.stop, self.wait, lambda: self.cancel,
                                  self.observer, **kwargs)


def all_frames(sequence=CONTROLLED_STOP):
    result = []
    for uid, effects in sequence:
        result.append((uid, effects))
        for effect in effects:
            if effect[0] == "subsequence":
                result.extend(all_frames(effect[1]))
    return result


class OuterStopTests(unittest.TestCase):
    def test_seven_phases_40_frames_and_explicit_source_identity(self):
        self.assertEqual([uid for uid, effects in CONTROLLED_STOP],
                         ["60323", "51962", "43360", "129793", "1722", "52159", "64826"])
        fixture = Fixture()
        result = fixture.execute()
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["source_vi_sha256"], SOURCE_VI_SHA256)
        self.assertEqual(result["source_archive_sha256"], SOURCE_ARCHIVE_SHA256)
        self.assertEqual(len(result["started_frames"]), 40)
        self.assertEqual(result["started_frames"], [uid for uid, e in all_frames()])
        self.assertEqual(fixture.frames, list(enumerate(result["started_frames"])))
        self.assertEqual(result["completed_frames"][-1], "64826")
        self.assertEqual(result["pending_output_restorations"], [])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertFalse(result["source_error_semantics_reproduced"])

    def test_all_literal_writes_and_waits_preserve_selected_frame_schedule(self):
        fixture = Fixture()
        fixture.done = {3: True, 4: True}
        fixture.execute()
        expected = []

        def walk(sequence):
            for uid, effects in sequence:
                for kind in ("write", "ht_ramp", "counter_poll_stop_clear", "subsequence", "wait"):
                    for effect in effects:
                        if effect[0] != kind:
                            continue
                        if kind == "write":
                            expected.append(effect)
                        elif kind == "ht_ramp":
                            expected.extend([("write", 50, ((-1, 6.0),)),
                                             ("write", 48, ((-1, 0.0),))])
                        elif kind == "counter_poll_stop_clear":
                            expected.extend([("poll", effect[2]), ("wait", 0.001),
                                             ("stop", effect[2])])
                        elif kind == "subsequence":
                            walk(effect[1])
                        else:
                            expected.append(("wait", effect[1] / 1000.0))
        walk(CONTROLLED_STOP)
        self.assertEqual(fixture.events, expected)

    def test_fixed_waits_are_12850ms_not_wall_clock_guarantee(self):
        waits = [e[1] for uid, effects in all_frames() for e in effects if e[0] == "wait"]
        self.assertEqual(sum(waits), 12850)
        fixture = Fixture()
        fixture.execute()
        total = sum(e[1] for e in fixture.events if e[0] == "wait")
        self.assertAlmostEqual(total, 12.850 + 0.084)

    def test_counter_done_or_i_greater_40_means_42_polls_and_42_waits(self):
        fixture = Fixture()
        result = fixture.execute()
        self.assertEqual(result["counter_poll_counts"], {3: 42, 4: 42})
        self.assertEqual(result["counter_stop_attempts"], [3, 4])
        self.assertEqual(result["counter_stop_completed"], [3, 4])
        self.assertEqual(result["conceptual_error_clears"], [3, 4])
        self.assertEqual(len([e for e in fixture.events if e == ("wait", 0.001)]), 84)

    def test_done_true_first_call_still_waits_and_stops_each_task_once(self):
        fixture = Fixture()
        fixture.done = {3: True, 4: True}
        result = fixture.execute()
        self.assertEqual(result["counter_poll_counts"], {3: 1, 4: 1})
        polls = [e for e in fixture.events if e[0] in ("poll", "stop")]
        self.assertEqual(polls, [("poll", 3), ("stop", 3), ("poll", 4), ("stop", 4)])

    def test_pulse_done_is_strict_bool_no_truthy_substitution(self):
        for invalid in (0, 1, None, "False"):
            fixture = Fixture()
            fixture.done[3] = invalid
            with self.assertRaises(OuterStopExecutionError) as error:
                fixture.execute()
            result = error.exception.report
            self.assertEqual(result["counter_stop_attempts"], [3, 4])
            self.assertTrue(result["ht_supply_stop_complete"])
            self.assertNotIn("52159", result["started_frames"])

    def test_strict_threshold_6_6_zero_and_negative_are_not_clamped(self):
        for value in (-10.0, 0.0, 6.599999999999999):
            fixture = Fixture(value)
            result = fixture.execute()
            self.assertEqual(result["ramp_decrements"], 0)
            self.assertEqual(fixture.banks[12][0], value)
            self.assertEqual(fixture.banks[48], value)
        fixture = Fixture(6.6)
        result = fixture.execute()
        self.assertEqual(result["ramp_decrements"], 1)
        self.assertEqual(fixture.banks[12][0], 6.6 - 0.1)

    def test_12_7_is_62_decrements_then_retains_below_threshold_command(self):
        fixture = Fixture(12.7)
        result = fixture.execute()
        self.assertEqual(result["ramp_decrements"], 62)
        self.assertEqual(result["ramp_iterations"], 63)
        self.assertAlmostEqual(fixture.banks[12][0], 6.5)
        self.assertEqual(len([e for e in fixture.events if e == ("wait", 0.5)]), 62)

    def test_ramp_separate_check_and_bundle_reads_preserve_fresh_other_fields(self):
        fixture = Fixture(6.6)
        original = fixture.read
        reads = [0]

        def read(bank):
            if bank == 12:
                reads[0] += 1
                if reads[0] == 3:  # preflight, check, then fresh bundle read
                    fixture.banks[12] = (99.0,) + (33.0,) * 9
            return original(bank)
        fixture.read = read
        fixture.execute()
        self.assertEqual(fixture.banks[12], (6.6 - 0.1,) + (33.0,) * 9)
        self.assertEqual(reads[0], 4)  # preflight + check + RMW + final check

    def test_large_finite_fixed_point_aborts_at_python_bound_and_stops_ht(self):
        fixture = Fixture(1e200)
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute(max_ramp_steps=3)
        result = error.exception.report
        self.assertEqual(result["ramp_decrements"], 3)
        self.assertEqual(result["counter_stop_attempts"], [3, 4])
        self.assertTrue(result["ht_supply_stop_complete"])
        self.assertEqual(result["started_frames"], ["60323"])
        self.assertFalse(fixture.banks[46])
        self.assertTrue(fixture.banks[47])
        self.assertEqual(fixture.banks[50], 6.0)

    def test_zeroing_preserves_c6_8_c7_2_and_unassigned_digital_fields(self):
        fixture = Fixture()
        before = dict(fixture.banks)
        fixture.execute()
        self.assertEqual(fixture.banks[9], (0.0,) * 8 + (before[9][8], 0.0))
        self.assertEqual(fixture.banks[10], (0.0, 0.0, before[10][2]) + (0.0,) * 7)
        self.assertEqual(fixture.banks[12], before[12])
        assigned = set(i for uid, effects in all_frames() for e in effects
                       if e[0] == "write" and e[1] == 17 for i, v in e[2])
        for index in set(range(40)) - assigned:
            self.assertEqual(fixture.banks[17][index], before[17][index])

    def test_phase51962_does_not_invent_event24_eps_writes(self):
        fixture = Fixture()
        phases = []
        current = [None]
        original = fixture.write
        fixture.observer = lambda index, uid: current.__setitem__(0, uid)

        def write(bank, changes):
            if current[0] in ("51962", "47671", "47989", "48537"):
                phases.append((bank, changes))
            original(bank, changes)
        fixture.write = write
        fixture.execute()
        self.assertEqual(phases, [(35, ((-1, True),)), (50, ((-1, 5.0),))])

    def test_duplicate_dps_eps_assignments_not_deduplicated(self):
        fixture = Fixture()
        fixture.execute()
        writes = [e for e in fixture.events if e[0] == "write" and e[1] in (36, 44)]
        self.assertEqual(len(writes), 4)
        self.assertEqual(writes[:2], writes[2:])
        self.assertEqual(fixture.banks[50], 0.0)
        self.assertTrue(fixture.banks[46])
        self.assertFalse(fixture.banks[47])

    def test_invalid_callback_and_bound_fail_before_any_callbacks(self):
        fixture = Fixture()
        for value in (0, -1, True, 1.0, 100001):
            with self.assertRaises(ValueError):
                fixture.execute(max_ramp_steps=value)
        with self.assertRaises(TypeError):
            execute_outer_stop(None, fixture.write, fixture.pulse_done,
                               fixture.stop, fixture.wait, lambda: False)
        self.assertEqual(fixture.events, [])
        self.assertEqual(fixture.reads, [])

    def test_invalid_snapshots_abort_no_cooling_or_final_flags(self):
        for invalid in ([0.0] * 10, (0.0,) * 9, (0,) * 10,
                        (float("inf"),) * 10, (float("nan"),) * 10, (True,) * 10):
            fixture = Fixture()
            fixture.banks[12] = invalid
            with self.assertRaises(OuterStopExecutionError) as error:
                fixture.execute()
            result = error.exception.report
            self.assertEqual(result["started_frames"], [])
            self.assertEqual(result["counter_stop_attempts"], [3, 4])
            self.assertTrue(result["ht_supply_stop_complete"])
            self.assertFalse(fixture.banks[46])

    def test_each_bank_requires_complete_immutable_exact_element_types(self):
        for bank, (size, kind) in BANK_SHAPES.items():
            valid = Fixture().banks[bank]
            wrong_type = (0,) * size
            for invalid in (list(valid), valid[:-1], wrong_type):
                fixture = Fixture()
                fixture.banks[bank] = invalid
                with self.assertRaises(OuterStopExecutionError) as error:
                    fixture.execute()
                report = error.exception.report
                self.assertEqual(report["started_frames"], [])
                self.assertFalse(fixture.banks[46])
                self.assertNotIn("52159", report["started_frames"])

    def test_cleanup_failures_are_aggregated_without_fabricated_ht_completion(self):
        fixture = Fixture()
        fixture.banks[12] = (float("nan"),) * 10
        fixture.banks[15] = (False,) * 31

        def stop(number):
            fixture.events.append(("stop", number))
            raise RuntimeError("counter stop failed")
        fixture.stop = stop
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        report = error.exception.report
        self.assertEqual(report["counter_stop_attempts"], [3, 4])
        self.assertEqual(report["counter_stop_completed"], [])
        self.assertFalse(report["ht_supply_stop_complete"])
        self.assertEqual(len(report["failures"]), 4)
        self.assertEqual([e for e in fixture.events if e[0] == "write"], [])

    def test_failed_cleanup_dwell_releases_assertion_but_reports_incomplete(self):
        fixture = Fixture()

        def wait(seconds):
            fixture.events.append(("wait", seconds))
            raise RuntimeError("clock/wait unavailable")
        fixture.wait = wait
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        report = error.exception.report
        self.assertTrue(report["ht_supply_assert_completed"])
        self.assertFalse(report["ht_supply_dwell_completed"])
        self.assertTrue(report["ht_supply_release_completed"])
        self.assertFalse(report["ht_supply_stop_complete"])
        self.assertEqual(report["pending_output_restorations"], [])
        self.assertNotIn("52159", report["started_frames"])

    def test_counter_stop_failure_not_retried_and_other_counter_and_ht_attempted(self):
        fixture = Fixture()
        original = fixture.stop

        def stop(number):
            original(number)
            if number == 3:
                raise RuntimeError("StopTask unknown")
        fixture.stop = stop
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertEqual(result["counter_stop_attempts"], [3, 4])
        self.assertEqual(result["counter_stop_completed"], [4])
        self.assertEqual([e for e in fixture.events if e == ("stop", 3)], [("stop", 3)])
        self.assertTrue(result["ht_supply_stop_complete"])
        self.assertNotIn("52159", result["started_frames"])

    def test_observer_failure_aborts_and_runs_only_bounded_cleanup(self):
        fixture = Fixture()

        def observer(index, uid):
            raise RuntimeError("observer failed")
        fixture.observer = observer
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertEqual(result["started_frames"], ["60323"])
        self.assertEqual(result["counter_stop_attempts"], [3, 4])
        self.assertTrue(result["ht_supply_stop_complete"])

    def test_cancellation_before_entry_stops_counters_and_ht_without_normal_effects(self):
        fixture = Fixture()
        fixture.cancel = True
        with self.assertRaises(OuterStopExecutionCancelled) as error:
            fixture.execute()
        result = error.exception.report
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["started_frames"], [])
        self.assertEqual(result["counter_stop_attempts"], [3, 4])
        self.assertTrue(result["ht_supply_stop_complete"])
        self.assertFalse(fixture.banks[46])

    def test_cancel_during_nonht_pulse_restores_baseline_without_cooling(self):
        fixture = Fixture()
        original = fixture.wait

        def wait(seconds):
            original(seconds)
            if fixture.banks[15][8] is False:
                fixture.cancel = True
        fixture.wait = wait
        with self.assertRaises(OuterStopExecutionCancelled) as error:
            fixture.execute()
        result = error.exception.report
        self.assertIn((15, 8), result["restored_fields"])
        self.assertTrue(fixture.banks[15][8])
        self.assertNotIn("52159", result["started_frames"])
        self.assertEqual(result["pending_output_restorations"], [])

    def test_partial_apply_then_raise_tracks_uncertain_pulse_and_restoration(self):
        fixture = Fixture()
        original = fixture.write
        raised = [False]

        def write(bank, changes):
            original(bank, changes)
            if bank == 15 and changes == ((8, False),) and not raised[0]:
                raised[0] = True
                raise RuntimeError("partial output write")
        fixture.write = write
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertIn((15, 8), result["restored_fields"])
        self.assertTrue(fixture.banks[15][8])
        self.assertNotIn("52159", result["started_frames"])

    def test_failed_restoration_retains_exact_owner_recovery_triples(self):
        fixture = Fixture()
        original = fixture.write

        def write(bank, changes):
            if bank == 15 and changes in (((8, False),), ((8, True),)):
                raise RuntimeError("output driver lost")
            original(bank, changes)
        fixture.write = write
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertEqual(result["pending_output_restorations"], [(15, 8, True)])
        self.assertEqual(len(result["restoration_failures"]), 1)
        self.assertTrue(result["ht_supply_stop_complete"])

    def test_failed_ht_assert_attempts_release_not_second_assert(self):
        fixture = Fixture()
        original = fixture.write

        def write(bank, changes):
            original(bank, changes)
            if bank == 15 and changes == ((19, False),):
                raise RuntimeError("uncertain HT assertion")
        fixture.write = write
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertEqual(fixture.events.count(("write", 15, ((19, False),))), 1)
        self.assertEqual(fixture.events.count(("write", 15, ((19, True),))), 1)
        self.assertFalse(result["ht_supply_stop_complete"])
        self.assertFalse(result["ht_supply_assert_completed"])
        self.assertTrue(result["ht_supply_release_completed"])
        self.assertEqual(result["pending_output_restorations"], [])
        self.assertNotIn("52159", result["started_frames"])

    def test_failed_release_not_replayed_as_pulse_baseline_restore_is_explicit(self):
        fixture = Fixture()
        original = fixture.write
        release_attempts = [0]

        def write(bank, changes):
            if bank == 15 and changes == ((19, True),):
                release_attempts[0] += 1
                raise RuntimeError("release uncertain")
            original(bank, changes)
        fixture.write = write
        with self.assertRaises(OuterStopExecutionError) as error:
            fixture.execute()
        result = error.exception.report
        self.assertFalse(result["ht_supply_stop_complete"])
        # Second identical data patch is explicitly baseline recovery, not a
        # replayed HT assertion/dwell/release sequence. It also fails visibly.
        self.assertEqual(release_attempts[0], 2)
        self.assertEqual(result["pending_output_restorations"], [(15, 19, True)])

    def test_invalid_cancel_type_is_fault_not_truthy_cancel(self):
        fixture = Fixture()
        with self.assertRaises(OuterStopExecutionError) as error:
            execute_outer_stop(fixture.read, fixture.write, fixture.pulse_done,
                               fixture.stop, fixture.wait, lambda: 1)
        self.assertFalse(error.exception.report["cancelled"])
        self.assertEqual(error.exception.report["status"], "PARTIAL_FAILURE")

    def test_every_normal_callback_failure_aborts_without_counter_replay(self):
        """Each callback site fails once, including after a partial effect."""
        callback_names = ("read", "write", "pulse_done", "stop", "wait", "observer")
        counts = dict((name, 0) for name in callback_names)
        normal = Fixture(6.6)
        for name in callback_names:
            original = getattr(normal, name)

            def count(*args, **kwargs):
                key, callback = kwargs["key"], kwargs["callback"]
                counts[key] += 1
                return callback(*args)
            setattr(normal, name,
                    lambda *args, _name=name, _original=original:
                    count(*args, key=_name, callback=_original))
        normal.execute()
        # Python 3.4 supports keyword-only defaults; all adapters stay fake.
        self.assertGreater(sum(counts.values()), 250)
        for name in callback_names:
            for failed_site in range(1, counts[name] + 1):
                fixture = Fixture(6.6)
                original = getattr(fixture, name)
                calls = [0]

                def fail(*args):
                    calls[0] += 1
                    value = original(*args)
                    if calls[0] == failed_site:
                        raise RuntimeError("injected callback partial failure")
                    return value
                setattr(fixture, name, fail)
                with self.assertRaises(OuterStopExecutionError) as error:
                    fixture.execute()
                report = error.exception.report
                self.assertEqual(report["status"], "PARTIAL_FAILURE")
                self.assertTrue(report["failures"])
                self.assertFalse(report["hardware_acknowledged"])
                for number in (3, 4):
                    self.assertEqual(fixture.events.count(("stop", number)), 1)
                if report["failures"][0]["phase_uid"] in (
                        None, "60323", "51962", "43360", "129793", "1722"):
                    self.assertNotIn("52159", report["started_frames"])

    def test_cancel_after_each_effect_has_no_normal_continuation(self):
        """Boundary cancellation does not become an implicit shutdown ACK."""
        normal = Fixture(6.6)
        normal.execute()
        # Cancel after each source write, poll, stop and wait in turn. Cleanup
        # ignores cancellation only for its explicitly bounded stop/restores.
        source_effect_count = len(normal.events)
        for cancelled_site in range(1, source_effect_count + 1):
            fixture = Fixture(6.6)
            for name in ("write", "pulse_done", "stop", "wait"):
                original = getattr(fixture, name)

                def cancel_after(*args, **kwargs):
                    value = kwargs["callback"](*args)
                    if len(fixture.events) == cancelled_site:
                        fixture.cancel = True
                    return value
                setattr(fixture, name, lambda *args, _callback=original:
                        cancel_after(*args, callback=_callback))
            with self.assertRaises(OuterStopExecutionCancelled) as error:
                fixture.execute()
            report = error.exception.report
            self.assertEqual(report["status"], "CANCELLED")
            self.assertFalse(report["hardware_acknowledged"])
            self.assertEqual(report["pending_output_restorations"], [])
            for number in (3, 4):
                self.assertEqual(fixture.events.count(("stop", number)), 1)

    def test_no_real_network_sleep_or_driver_import(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network")), \
                patch("time.sleep", side_effect=AssertionError("sleep")):
            self.assertEqual(Fixture().execute()["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
