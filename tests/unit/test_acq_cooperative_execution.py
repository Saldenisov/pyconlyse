"""Offline deterministic cooperative waits; runnable on real Python 3.4.

No NI, XP, instrument, live TCP receiver or live HDF5 file is accessed.
"""
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.cooperative_execution import CooperativeExecution
from legacy.xp_acq_control.elyse_agent.acquisition_procedures import (
    execute_general_start, execute_general_stop, execute_general_only_stop,
    ProcedureCancelled, GeneralStopError,
)
from legacy.xp_acq_control.elyse_agent.acquisition_stage_execution import (
    execute_stage, SUPPORTED_OPERATIONS, StageExecutionError, StageExecutionCancelled,
)
from legacy.xp_acq_control.elyse_agent.acquisition_backend import DemoBackend
from legacy.xp_acq_control.elyse_agent.acquisition_outer_stop import (
    execute_outer_stop, BANK_SHAPES, PULSE_FIELDS, OuterStopExecutionError,
)
from legacy.xp_acq_control.elyse_agent.acquisition_cooling_trip import (
    execute_cooling_trip, CoolingTripCancelled,
)
from legacy.xp_acq_control.elyse_agent.acquisition_impulsion import execute_impulsion


class Clock(object):
    def __init__(self):
        self.value = 0.
        self.waits = []
        self.cancelled = False

    def now(self):
        return self.value

    def wait(self, seconds):
        self.waits.append(seconds)
        if not self.cancelled:
            self.value += seconds
        return self.cancelled

    def is_set(self):
        return self.cancelled


def execute_stage_fixture(operation, clock, observer=None, fail_write=None):
    banks = {15: (False,) * 32, 17: (False,) * 40,
             36: (False,) * 29, 44: (False,) * 77, 35: False}
    trace = []
    def write(bank, changes):
        trace.append(('write', bank, changes))
        if fail_write is not None:
            fail_write(bank, changes)
        if bank == 35:
            banks[bank] = True
        else:
            value = list(banks[bank])
            for index, item in changes:
                value[index] = item
            banks[bank] = tuple(value)
    scheduler = CooperativeExecution(observer, .2, clock.now)
    report = execute_stage(operation, lambda bank: banks[bank], write,
        lambda *args: trace.append(('publish', args)), clock.wait, clock.is_set,
        lambda *args: trace.append(('frame', args)), operator_confirmed=True,
        focal_helper=lambda name: trace.append(('helper', name)),
        execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, clock.wait, safe, phase))
    return trace, report, scheduler


class CooperativeWaitTests(unittest.TestCase):
    def test_disabled_preserves_original_single_wait(self):
        clock = Clock()
        scheduler = CooperativeExecution(None, clock=clock.now)
        scheduler.wait(1., clock.wait, True)
        self.assertEqual(clock.waits, [1.])

    def test_critical_span_never_calls_observer_or_slices_wait(self):
        clock, events = Clock(), []
        scheduler = CooperativeExecution(events.append, clock=clock.now)
        scheduler.wait(.15, clock.wait, False)
        self.assertEqual(clock.waits, [.15])
        self.assertEqual(events, [])

    def test_observer_time_consumes_original_deadline(self):
        clock, events = Clock(), []
        def observe(event):
            events.append(event)
            self.assertAlmostEqual(event['minimum_next_action_deadline'], 1.)
            clock.value += .03
        scheduler = CooperativeExecution(observe, .2, clock.now)
        scheduler.wait(1., clock.wait, True, dict(operation='fixture', phase='wait'))
        self.assertAlmostEqual(clock.value, 1.)
        self.assertGreater(len(events), 1)
        self.assertTrue(all(e['safe_to_sample'] for e in events))
        self.assertTrue(all(e['hardware_acknowledged'] is False for e in events))
        self.assertLess(sum(clock.waits), 1.)

    def test_slow_native_observer_overrun_is_not_followed_by_extra_dwell(self):
        clock = Clock()
        def observe(event):
            clock.value += 2.
        scheduler = CooperativeExecution(observe, clock=clock.now)
        scheduler.wait(1., clock.wait, True)
        self.assertEqual(clock.value, 2.)
        self.assertEqual(clock.waits, [])
        self.assertEqual(scheduler.snapshot()['last_wait_overrun_seconds'], 1.)
        self.assertEqual(scheduler.snapshot()['maximum_wait_overrun_seconds'], 1.)

    def test_observer_errors_are_diagnostic_not_stop_failures(self):
        clock = Clock()
        def observe(event):
            raise IOError('offline sampler unavailable')
        scheduler = CooperativeExecution(observe, clock=clock.now)
        scheduler.wait(.5, clock.wait, True)
        self.assertAlmostEqual(clock.value, .5)
        self.assertGreater(scheduler.observer_error_count, 0)
        self.assertIn('offline sampler unavailable', scheduler.snapshot()['last_observer_error'])

    def test_event_wait_cancellation_returns_without_nominal_remaining_wait(self):
        clock = Clock()
        def observe(event):
            clock.cancelled = True
        scheduler = CooperativeExecution(observe, clock=clock.now)
        self.assertIs(scheduler.wait(10., clock.wait, True), True)
        self.assertEqual(clock.value, 0.)
        self.assertEqual(scheduler.checkpoint_count, 1)

    def test_callback_always_runs_on_owner_and_other_owner_is_rejected(self):
        clock, calls = Clock(), []
        scheduler = CooperativeExecution(lambda event: calls.append(threading.current_thread().ident),
                                         clock=clock.now)
        scheduler.wait(.1, clock.wait, True)
        self.assertEqual(calls, [threading.current_thread().ident])
        errors = []
        def other_owner():
            try:
                scheduler.wait(.1, clock.wait, True)
            except RuntimeError as error:
                errors.append(str(error))
        worker = threading.Thread(target=other_owner)
        worker.start()
        worker.join(2.)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(calls), 1)

    def test_reentrant_execution_is_rejected_and_outer_dwell_completes(self):
        clock = Clock()
        scheduler = CooperativeExecution(clock=clock.now)
        scheduler.observer = lambda event: scheduler.wait(.1, clock.wait, True)
        scheduler.wait(.3, clock.wait, True)
        self.assertAlmostEqual(clock.value, .3)
        self.assertIn('Reentrant', scheduler.last_observer_error)


class ProcedureCheckpointTests(unittest.TestCase):
    def test_general_start_preserves_effect_order_and_no_sample_during_pulse(self):
        def run(cooperative):
            clock, trace, active, events = Clock(), [], set(), []
            def write(line, value):
                trace.append(('write', line, value))
                (active.add if value else active.discard)(line)
            def observe(event):
                self.assertFalse(active)
                events.append(event)
                clock.value += .01
            scheduler = CooperativeExecution(observe, clock=clock.now)
            execute_general_start(write, lambda *args: trace.append(('status', args)),
                clock.wait, clock.is_set,
                lambda *args: trace.append(('frame', args)), operator_confirmed=True,
                execution_wait=(lambda seconds, safe, phase: scheduler.wait(
                    seconds, clock.wait, safe, phase)) if cooperative else None)
            return clock.value, trace, events
        original, cooperative = run(False), run(True)
        self.assertEqual(original[1], cooperative[1])
        self.assertAlmostEqual(original[0], cooperative[0])
        self.assertTrue(cooperative[2])
        self.assertTrue(all(e['frame'] in (2, 5, 9) for e in cooperative[2]))

    def test_general_start_cancel_in_safe_checkpoint_does_not_assert_next_pulse(self):
        clock, writes = Clock(), []
        scheduler = CooperativeExecution(lambda event: setattr(clock, 'cancelled', True), clock=clock.now)
        with self.assertRaises(ProcedureCancelled):
            execute_general_start(lambda *args: writes.append(args), lambda *args: None,
                clock.wait, clock.is_set, operator_confirmed=True,
                execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, clock.wait, safe, phase))
        self.assertEqual(writes, [(0, True), (0, False)])

    def test_general_start_cancel_in_critical_wait_restores_asserted_output(self):
        clock, writes, events = Clock(), [], []
        def wait(seconds):
            clock.cancelled = True
            return True
        scheduler = CooperativeExecution(events.append, clock=clock.now)
        with self.assertRaises(ProcedureCancelled):
            execute_general_start(lambda *args: writes.append(args), lambda *args: None,
                wait, clock.is_set, operator_confirmed=True,
                execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, wait, safe, phase))
        self.assertEqual(writes, [(0, True), (0, False)])
        self.assertEqual(events, [])

    def test_general_stop_retains_best_effort_after_focal_failure(self):
        clock, writes, events = Clock(), [], []
        def focal():
            raise IOError('offline focal failure')
        scheduler = CooperativeExecution(events.append, clock=clock.now)
        with self.assertRaises(GeneralStopError) as raised:
            execute_general_stop(lambda *args: writes.append(args), focal,
                lambda *args: None, clock.wait, operator_confirmed=True, clock=clock.now,
                execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, clock.wait, safe, phase))
        self.assertEqual(writes[-2:], [(1, False), (1, True)])
        self.assertTrue(any('offline focal failure' in failure for failure in raised.exception.failures))
        self.assertFalse(any(e['frame'] in (0, 1, 4, 7, 10, 13) for e in events))

    def test_uncertain_stop_pulse_disables_later_checkpoints_until_restoration(self):
        clock, events, writes = Clock(), [], []
        def write(line, value):
            writes.append((line, value))
            if line == 8 and value:
                raise IOError('offline release failure')
        scheduler = CooperativeExecution(events.append, clock=clock.now)
        with self.assertRaises(GeneralStopError):
            execute_general_stop(write, lambda: None, lambda *args: None,
                clock.wait, operator_confirmed=True, clock=clock.now,
                execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, clock.wait, safe, phase))
        self.assertTrue(events)
        self.assertTrue(all(e['frame'] == 0 for e in events))
        self.assertEqual(writes[-1], (8, True))

    def test_general_only_stop_does_not_observe_asserted_pulse(self):
        clock, events = Clock(), []
        scheduler = CooperativeExecution(events.append, clock=clock.now)
        execute_general_only_stop(lambda *args: None, lambda *args: None,
            clock.wait, operator_confirmed=True,
            execution_wait=lambda seconds, safe, phase: scheduler.wait(seconds, clock.wait, safe, phase))
        self.assertEqual([e['frame'] for e in events], [16])
        self.assertAlmostEqual(clock.value, .25)

    def test_all_source_stages_keep_effect_order_and_total_nominal_dwell(self):
        for operation in SUPPORTED_OPERATIONS:
            original_clock, clock = Clock(), Clock()
            original, report, unused = execute_stage_fixture(operation, original_clock)
            events = []
            def observe(event):
                events.append(event)
                clock.value += .01
            cooperative, cooperative_report, unused = execute_stage_fixture(operation, clock, observe)
            self.assertEqual(original, cooperative, operation)
            self.assertEqual(report, cooperative_report, operation)
            self.assertAlmostEqual(original_clock.value, clock.value, places=7, msg=operation)
            self.assertTrue(all(e['operation'] == operation for e in events))

    def test_stage_cancellation_at_safe_wait_is_not_completion(self):
        clock = Clock()
        def observe(event):
            clock.cancelled = True
        with self.assertRaises(StageExecutionCancelled) as raised:
            execute_stage_fixture('chauffage.start', clock, observe)
        self.assertEqual(raised.exception.report['status'], 'CANCELLED')
        self.assertFalse(raised.exception.report['hardware_acknowledged'])
        self.assertEqual(raised.exception.report['pending_output_restorations'], [])

    def test_backend_hook_supplies_safe_sample_on_same_owner_without_native_io(self):
        clock, events, samples = Clock(), [], []
        backend = DemoBackend(stage_controls_verified=True)
        backend.initialize(clock)
        backend.set_execution_observer(lambda event: (
            events.append(event), samples.append(backend.read_snapshot(clock))))
        backend._execution_scheduler.clock = clock.now
        report = backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
        self.assertEqual(report['status'], 'COMPLETED')
        self.assertTrue(samples)
        self.assertTrue(all(sample['simulated'] for sample in samples))
        self.assertTrue(all(e['safe_to_sample'] for e in events))
        self.assertEqual(backend._execution_scheduler.owner_ident, threading.current_thread().ident)
        self.assertGreater(backend.procedure['execution_checkpoints']['checkpoint_count'], 0)

    def test_backend_observer_cannot_start_nested_procedure_or_close_owner(self):
        for action in ('stage', 'close', 'initialize'):
            clock = Clock()
            backend = DemoBackend(stage_controls_verified=True)
            backend.initialize(clock)
            def observe(event):
                if action == 'stage':
                    backend.execute_stage('prema.start', clock, operator_confirmed=True)
                elif action == 'close':
                    backend.close()
                else:
                    backend.initialize(clock)
            backend.set_execution_observer(observe)
            backend._execution_scheduler.clock = clock.now
            report = backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
            self.assertEqual(report['status'], 'COMPLETED')
            self.assertEqual(backend.procedure['name'], 'chauffage.start')
            self.assertTrue(backend.active)
            self.assertGreater(backend._execution_scheduler.observer_error_count, 0)
            self.assertIn('not reenter', backend._execution_scheduler.last_observer_error)

    def test_backend_observer_cannot_reenter_true_cooling_guard_or_change_outer_effects(self):
        def run(reenter):
            clock, trace, attempts = Clock(), [], []
            backend = DemoBackend(stage_controls_verified=True, cooling_trip_verified=True)
            backend.initialize(clock)
            read, write, publish = (backend._stage_read_local, backend._stage_write_local,
                                    backend._stage_publish)
            def trace_read(bank):
                trace.append(('read', bank))
                return read(bank)
            def trace_write(bank, changes):
                trace.append(('write', bank, changes))
                return write(bank, changes)
            def trace_publish(*args):
                trace.append(('publish', args))
                return publish(*args)
            backend._stage_read_local = trace_read
            backend._stage_write_local = trace_write
            backend._stage_publish = trace_publish
            c4, c3 = [False] * 64, [True] * 56
            c4[19], c3[0] = True, False
            snapshot = dict(simulated=True, banks={
                'C4_DIO96_DI': dict(values=c4), 'C3_DIO96_DI': dict(values=c3)})
            from legacy.xp_acq_control.elyse_agent.acquisition_cooling_trip import cooling_trip_predicate
            self.assertTrue(cooling_trip_predicate(tuple(c4), tuple(c3)))
            def observe(event):
                attempts.append(event)
                before = list(trace)
                try:
                    backend.execute_cooling_guard(snapshot, clock)
                finally:
                    # Reject before reads, writes, publication or procedure
                    # replacement, not only after reaching a nested wait.
                    self.assertEqual(trace, before)
            if reenter:
                backend.set_execution_observer(observe)
                backend._execution_scheduler.clock = clock.now
            report = backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
            self.assertEqual(backend.procedure['name'], 'chauffage.start')
            self.assertIsNone(backend.last_cooling_guard)
            self.assertFalse(any(row[0] == 'write' and row[1] == 17 for row in trace))
            if reenter:
                self.assertTrue(attempts)
                self.assertEqual(backend._execution_scheduler.observer_error_count, len(attempts))
                self.assertIn('not reenter', backend._execution_scheduler.last_observer_error)
            return trace, clock.value, report
        original, reentered = run(False), run(True)
        self.assertEqual(original[0], reentered[0])
        self.assertAlmostEqual(original[1], reentered[1])
        self.assertEqual(original[2], reentered[2])


class AdditionalSourceCheckpointTests(unittest.TestCase):
    def run_outer(self, cooperative, fail_release=False):
        clock, events, trace = Clock(), [], []
        banks = {bank: (True,) * size if kind is bool else
                 (6.8 if bank == 12 else 1.,) + (1.,) * (size - 1)
                 for bank, (size, kind) in BANK_SHAPES.items()}
        def read(bank):
            trace.append(('read', bank))
            return banks[bank]
        def write(bank, changes):
            trace.append(('write', bank, changes))
            if fail_release and bank == 15 and changes == ((19, True),):
                raise IOError('offline HT release failed')
            if bank in BANK_SHAPES:
                values = list(banks[bank])
                for index, value in changes:
                    values[index] = value
                banks[bank] = tuple(values)
        def observe(event):
            for bank, fields in PULSE_FIELDS.items():
                self.assertTrue(all(banks[bank][field] for field in fields), event)
            events.append(event)
            clock.value += .01
        scheduler = CooperativeExecution(observe, clock=clock.now)
        report = execute_outer_stop(read, write,
            lambda number: trace.append(('done', number)) or True,
            lambda number: trace.append(('stop', number)), clock.wait, clock.is_set,
            observer=lambda *args: trace.append(('frame', args)),
            execution_wait=(lambda seconds, safe, phase: scheduler.wait(
                seconds, clock.wait, safe, phase)) if cooperative else None)
        return clock.value, trace, report, events

    def test_outer_stop_preserves_exact_source_effects_and_safe_ramp_waits(self):
        original, cooperative = self.run_outer(False), self.run_outer(True)
        self.assertEqual(original[1], cooperative[1])
        self.assertEqual(original[2], cooperative[2])
        self.assertAlmostEqual(original[0], cooperative[0])
        self.assertTrue(any(e['phase'] == 'ht_ramp_wait' for e in cooperative[3]))
        self.assertFalse(any(e['source_uid'] in ('49114', '42424', '42763',
            '43197', '43345', '43520', '54293', '54470') for e in cooperative[3]))

    def test_outer_stop_failed_release_still_reports_uncertain_pulse(self):
        with self.assertRaises(OuterStopExecutionError) as raised:
            self.run_outer(True, True)
        self.assertTrue(raised.exception.report['pending_output_restorations'])
        self.assertFalse(raised.exception.report['hardware_acknowledged'])

    def run_cooling(self, cooperative, cancel_safe=False):
        clock, events, trace = Clock(), [], []
        banks = {17: (True,) * 40, 36: (False,) * 29, 44: (False,) * 77}
        c4, c3 = [False] * 64, [True] * 56
        c4[19], c3[0] = True, False
        def read(bank):
            trace.append(('read', bank))
            return banks[bank]
        def write(bank, changes):
            trace.append(('write', bank, changes))
            if bank == 35:
                return
            values = list(banks[bank])
            for index, value in changes:
                values[index] = value
            banks[bank] = tuple(values)
        def observe(event):
            self.assertTrue(banks[17][1])
            self.assertTrue(banks[17][4])
            events.append(event)
            if cancel_safe:
                clock.cancelled = True
            else:
                clock.value += .01
        scheduler = CooperativeExecution(observe, clock=clock.now)
        result = execute_cooling_trip(tuple(c4), tuple(c3), read, write,
            lambda *args: trace.append(('publish', args)), clock.wait, clock.is_set,
            frame_observer=lambda *args: trace.append(('frame', args)), enabled_arm=True,
            execution_wait=(lambda seconds, safe, phase: scheduler.wait(
                seconds, clock.wait, safe, phase)) if cooperative else None)
        return clock.value, trace, result, events

    def test_cooling_trip_preserves_exact_trace_and_observes_released_waits_only(self):
        original, cooperative = self.run_cooling(False), self.run_cooling(True)
        self.assertEqual(original[1], cooperative[1])
        self.assertEqual(original[2], cooperative[2])
        self.assertAlmostEqual(original[0], cooperative[0])
        self.assertTrue(cooperative[3])
        self.assertTrue(all(e['frame'] in (2, 6) for e in cooperative[3]))

    def test_cooling_trip_cancellation_at_safe_wait_never_claims_completion(self):
        with self.assertRaises(CoolingTripCancelled) as raised:
            self.run_cooling(True, True)
        self.assertEqual(raised.exception.result['status'], 'cancelled')
        self.assertFalse(raised.exception.result['completed'])
        self.assertEqual(raised.exception.result['pending_output_restorations'], [])

    def test_impulsion_poll_stop_chain_stays_indivisible_and_final_wait_can_yield(self):
        for operation in ('modulator_impulse.start', 'modulator_impulse.stop'):
            def run(cooperative):
                clock, trace, events = Clock(), [], []
                banks = {36: (False,) * 29, 44: (False,) * 77}
                def write(bank, changes):
                    trace.append(('write', bank, changes))
                    if bank == 35:
                        return
                    values = list(banks[bank])
                    for index, value in changes:
                        values[index] = value
                    banks[bank] = tuple(values)
                def observe(event):
                    events.append(event)
                    clock.value += .01
                scheduler = CooperativeExecution(observe, clock=clock.now)
                result = execute_impulsion(operation,
                    lambda number: trace.append(('start', number)),
                    lambda number: trace.append(('done', number)) or True,
                    lambda number: trace.append(('stop', number)),
                    lambda bank: banks[bank], write,
                    lambda *args: trace.append(('publish', args)), clock.wait, clock.is_set,
                    execution_wait=(lambda seconds, safe, phase: scheduler.wait(
                        seconds, clock.wait, safe, phase)) if cooperative else None)
                return clock.value, trace, result, events
            original, cooperative = run(False), run(True)
            self.assertEqual(original[1], cooperative[1])
            self.assertEqual(original[2], cooperative[2])
            self.assertAlmostEqual(original[0], cooperative[0])
            self.assertTrue(cooperative[3])
            self.assertTrue(all(e['phase'] == 'final_status_wait' for e in cooperative[3]))


if __name__ == '__main__':
    unittest.main()
