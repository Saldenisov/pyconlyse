"""Source EPS/DPS memory and same-owner deadline sampling, Python 3.4.

Only RAM owners and local pinned catalog/calibration files. No NI driver,
instrument, XP host, network receiver, live process or HDF5 file is accessed.
Original root XML archive SHA256: 6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527.
"""
import json
import sys
import threading
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent import acquisition_backend as module
from legacy.xp_acq_control.elyse_agent.acquisition_backend import (
    CardBackend, AcquisitionCancelled, PROCEDURE_DPS_REQUESTS,
)
from legacy.xp_acq_control.elyse_agent.acquisition_stage_execution import StageExecutionCancelled
from legacy.xp_acq_control.elyse_agent.acquisition_stage_model import load_model, CATALOG_SHA256
from legacy.xp_acq_control.elyse_agent.hardware_plan import AI_BANKS, DI_BANKS, digital_startup_image


SOURCE_STATUS = {
    'cooling.start': ('24540', {0: False, 1: False, 2: True, 5: False, 8: True}, 0),
    'cooling.stop': ('22878', {1: False, 2: False, 3: False, 5: True}, 1),
    'chauffage.start': ('38483', {12: False, 14: True, 17: False}, 4),
    'chauffage.stop': ('24497', {14: False, 15: False, 17: True}, 5),
    'prema.start': ('29025', {18: False, 20: True, 23: False}, 6),
    'prema.stop': ('26962', {20: False, 21: False, 23: True}, 7),
    'relays_ht.start': ('36334', {24: False, 26: True, 29: False}, 8),
    'relays_ht.stop': ('31360', {26: False, 27: False, 29: True}, 9),
    'modulator.reset': ('33828', {36: False}, 12),
    'alimentation_ht.start': ('54126', {45: True, 49: False}, 15),
    'alimentation_ht.stop': ('32123', {45: False, 49: True}, 17),
    'alimentation_ht.reset': ('33217', {}, 16),
    'focales.start': ('40463', {30: False, 32: True, 35: False}, 10),
    'focales.stop': ('23880', {32: False, 33: False, 35: True}, 11),
}


class Clock(object):
    def __init__(self):
        self.value = 0.
        self.cancelled = False

    def now(self):
        return self.value

    def is_set(self):
        return self.cancelled

    def wait(self, seconds):
        self.value += seconds
        return self.cancelled


class Focal(object):
    resources_verified = True

    def ensure_ready(self):
        pass

    def ensure_quiescent(self):
        pass

    def snapshot(self):
        return dict(pending_worker_count=0, hardware_acknowledged=False)

    def execute(self, enabled, cancelled):
        if cancelled():
            raise RuntimeError('offline focal cancelled')
        return dict(injected_ram_fixture=True, hardware_acknowledged=False)


class Task(object):
    def __init__(self, owner, name, count, kind):
        self.owner, self.name, self.count, self.kind = owner, name, count, kind

    def start(self):
        self.owner.trace.append(('ai_start', self.name))
        self.owner.clock.value += self.owner.start_duration

    def stop(self):
        self.owner.trace.append(('ai_stop', self.name))

    def read(self, timeout):
        self.owner.trace.append(('di_read', self.name, timeout, self.owner.clock.value))
        self.owner.clock.value += self.owner.read_duration
        if self.name == self.owner.late_read:
            self.owner.clock.value += 1.
        return [False] * self.count


class Owner(object):
    def __init__(self, clock):
        self.clock, self.trace = clock, []
        self.fail_write = False
        self.fail_analog = False
        self.start_duration = 0.
        self.read_duration = .01
        self.late_read = None
        self.cancel_initial_images = False
        self.tasks = {}
        for name, device, count in AI_BANKS:
            self.tasks[name] = Task(self, name, count, float)
        for name, device, first, last, count in DI_BANKS:
            self.tasks[name] = Task(self, name, count, bool)

    def start_legacy_counters(self):
        self.trace.append(('startup_counters',))
        return []

    def write_initial_images(self):
        self.trace.append(('startup_images',))
        if self.cancel_initial_images:
            self.clock.cancelled = True
        return dict(digital=digital_startup_image())

    def write_digital_bank(self, name, values):
        self.trace.append(('do', name, tuple(values)))
        if self.fail_write:
            self.fail_write = False
            raise IOError('offline partial DO write')

    def read_analog_latest(self, name, timeout_seconds):
        self.trace.append(('ai_read', name, timeout_seconds, self.clock.value))
        self.clock.value += self.read_duration
        if self.fail_analog:
            raise IOError('offline AI error')
        return [1.] * self.tasks[name].count

    def start_counter(self, number):
        self.trace.append(('counter_start', number))

    def stop_counter(self, number):
        self.trace.append(('counter_stop', number))

    def read_counter_pulse_done(self, number):
        self.trace.append(('counter_done', number))
        return True

    def close(self):
        self.trace.append(('close',))
        self.tasks = {}


def fixture(observer=True, initialize=True, cancel_initial=False):
    clock, events = Clock(), []
    owner = Owner(clock)
    owner.cancel_initial_images = cancel_initial
    calls = []
    def factory(**kwargs):
        calls.append(kwargs)
        return owner
    backend = CardBackend(factory=factory, stop_wait=clock.wait, focal_command=Focal(),
                          stage_controls_verified=True, cooling_trip_verified=True,
                          ht_controls_verified=True, focal_controls_verified=True,
                          counter_controls_verified=True)
    if observer:
        backend.set_execution_observer(events.append)
        backend._execution_scheduler.clock = clock.now
    if initialize:
        backend.initialize(clock, startup_confirmed=True)
    return backend, owner, clock, events, calls


def status_events(events):
    return [event for event in events if event.get('kind') == 'SOFTWARE_STATE_NOT_MEASUREMENT']


class SoftwareStatusTests(unittest.TestCase):
    def test_cold_construct_has_no_driver_and_no_valid_zero_status(self):
        before = set(sys.modules)
        backend, owner, clock, events, calls = fixture(initialize=False)
        self.assertEqual(calls, [])
        self.assertEqual(owner.trace, [])
        self.assertEqual(events, [])
        self.assertFalse(backend._software_state_valid)
        with self.assertRaises(RuntimeError):
            backend.get_software_state()
        self.assertNotIn('nidaqmx', set(sys.modules) - before)

    def test_initial_literals_only_after_success_and_close_invalidates(self):
        backend, owner, clock, events, calls = fixture()
        initial = status_events(events)
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0]['source_effect'], 'INITIAL_LITERAL')
        self.assertEqual(initial[0]['source_uid'], '33052')
        self.assertEqual(initial[0]['software_state']['EPS'], (False,) * 77)
        self.assertEqual(initial[0]['software_state']['DPS'], (False,) * 29)
        self.assertTrue(backend._stage_snapshot()['software_status_valid'])
        backend.close()
        self.assertEqual(len(status_events(events)), 1)
        with self.assertRaises(RuntimeError):
            backend.get_software_state()

    def test_cancelled_initialization_does_not_publish_valid_literals(self):
        backend, owner, clock, events, calls = fixture(initialize=False, cancel_initial=True)
        with self.assertRaises(AcquisitionCancelled):
            backend.initialize(clock, startup_confirmed=True)
        self.assertEqual(status_events(events), [])
        with self.assertRaises(RuntimeError):
            backend.get_software_state()

    def test_full_vectors_detached_bounded_and_independent_of_measurement(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        before = backend.get_software_state()
        backend._stage_write_local(44, ((8, True),))
        event = status_events(events)[-1]
        self.assertFalse(event['safe_to_sample'])
        self.assertFalse(event['hardware_acknowledged'])
        self.assertNotIn('sample', event)
        self.assertNotIn('age_seconds', event['software_state'])
        self.assertEqual(owner.trace, [])
        self.assertLess(len(json.dumps(event)), 4096)
        self.assertEqual(len(event['software_state']['EPS']), 77)
        self.assertEqual(len(event['software_state']['DPS']), 29)
        self.assertTrue(all(type(value) is bool for key in ('EPS', 'DPS')
                            for value in event['software_state'][key]))
        self.assertGreater(event['software_state']['revision'], before['revision'])
        self.assertFalse(before['EPS'][8])
        event['software_state']['EPS'] = (False,) * 77
        self.assertTrue(backend.get_software_state()['EPS'][8])

    def test_software_observation_anchor_precedes_getter_copy_delay(self):
        backend, owner, clock, events, calls = fixture()
        original_getter = backend.get_software_state
        def slow_getter():
            clock.value += .25
            return original_getter()
        backend.get_software_state = slow_getter
        owner.trace[:] = []
        with patch.object(module.time, 'monotonic', clock.now):
            backend._stage_write_local(44, ((8, True),))
        event = status_events(events)[-1]
        self.assertEqual(event['software_state_observed_monotonic'], 0.)
        self.assertEqual(clock.value, .25)
        self.assertTrue(event['software_state']['EPS'][8])
        self.assertEqual(owner.trace, [])

    def test_all_source_stage_status_literals_preserve_sibling_bits_and_requests(self):
        for operation, (uid, assignments, request_field) in SOURCE_STATUS.items():
            backend, owner, clock, events, calls = fixture()
            eps = tuple(index % 2 == 0 for index in range(77))
            dps = tuple(index % 2 == 1 for index in range(29))
            backend._stage_write_local(44, tuple(enumerate(eps)))
            backend._stage_write_local(36, tuple(enumerate(dps)))
            events[:] = []
            backend.execute_stage(operation, clock, operator_confirmed=True)
            admitted = [e for e in status_events(events) if e.get('request_intent_only')]
            self.assertEqual(len(admitted), 1, operation)
            self.assertTrue(admitted[0]['software_state']['DPS'][request_field])
            state = backend.get_software_state()
            expected_eps, expected_dps = list(eps), list(dps)
            for field, value in assignments.items():
                expected_eps[field] = value
            expected_dps[request_field] = False
            self.assertEqual(state['EPS'], tuple(expected_eps), operation)
            self.assertEqual(state['DPS'], tuple(expected_dps), operation)
            self.assertTrue(any(e.get('source_uid') == uid and e['source_effect'] == 'LOCAL_ASSIGNMENT'
                                for e in status_events(events)), operation)
            self.assertFalse(any(row[0] in ('ai_read', 'di_read') for row in owner.trace))

    def test_request_metadata_uses_requested_operation_not_previous_procedure(self):
        backend, owner, clock, events, calls = fixture()
        backend.procedure = dict(name='old.procedure', frame=88, source_uid='old')
        backend._stage_write_local(36, ((28, True),))
        backend.record_procedure_request('prema.start')
        event = status_events(events)[-1]
        self.assertEqual(event['operation'], 'prema.start')
        self.assertIsNone(event['frame'])
        self.assertIsNone(event['source_uid'])
        self.assertTrue(event['request_intent_only'])
        self.assertTrue(event['software_state']['DPS'][6])
        self.assertTrue(event['software_state']['DPS'][28])
        self.assertFalse(backend.record_procedure_request('alimentation_ht.voltage'))

    def test_rejected_preflight_and_false_event_never_record_request(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        backend.stage_controls_verified = False
        with self.assertRaises(RuntimeError):
            backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
        backend.stage_controls_verified = True
        backend.execute_stage('chauffage.start', clock, operator_confirmed=True, new_value=False)
        with self.assertRaises(ValueError):
            backend.general_start(clock, operator_confirmed=False)
        with self.assertRaises(ValueError):
            backend.general_stop(operator_confirmed=False)
        backend.counter_controls_verified = False
        with self.assertRaises(RuntimeError):
            backend.execute_impulsion('modulator_impulse.start', clock, operator_confirmed=True)
        self.assertEqual(backend.get_software_state()['DPS'], (False,) * 29)
        self.assertFalse(any(e.get('request_intent_only') for e in status_events(events)))
        self.assertEqual(owner.trace, [])

    def test_publication_retains_frame_entry_snapshot_without_overwriting_live_vector(self):
        backend, owner, clock, events, calls = fixture()
        entry = backend.get_software_state()['EPS']
        backend._stage_write_local(44, ((7, True),))
        backend._stage_publish('EPS', 44, entry)
        event = status_events(events)[-1]
        self.assertEqual(event['source_effect'], 'SOURCE_PUBLICATION')
        self.assertTrue(event['software_state']['EPS'][7])
        self.assertFalse(event['publication']['values'][7])
        self.assertEqual(event['publication']['name'], 'EPS')
        self.assertFalse(backend.stage_publications['EPS']['psp_delivered'])

    def test_general_start_stop_assignments_and_separate_dps_publications(self):
        backend, owner, clock, events, calls = fixture()
        backend.general_start(clock, operator_confirmed=True)
        state = backend.get_software_state()
        self.assertTrue(state['EPS'][8])
        self.assertFalse(state['DPS'][2])
        published = [e for e in status_events(events) if e['source_effect'] == 'SOURCE_PUBLICATION']
        self.assertEqual(published[-1]['source_uid'], '35570')
        self.assertFalse(published[-1]['publication']['values'][2])
        backend.general_stop(operator_confirmed=True)
        state = backend.get_software_state()
        self.assertTrue(all(state['EPS'][index] is False for index in (8, 14, 20, 26, 32, 9)))
        self.assertTrue(all(state['EPS'][index] is True for index in (11, 17, 23, 29, 35)))
        self.assertFalse(state['DPS'][3])
        published = [e for e in status_events(events) if e['source_effect'] == 'SOURCE_PUBLICATION']
        self.assertEqual(published[-1]['source_uid'], '35146')

    def test_fault_before_source_tail_retains_request_not_fake_reset(self):
        backend, owner, clock, events, calls = fixture()
        owner.fail_write = True
        with self.assertRaises(IOError):
            backend.general_start(clock, operator_confirmed=True)
        self.assertTrue(backend.get_software_state()['DPS'][2])
        self.assertFalse(backend.get_software_state()['EPS'][8])
        self.assertFalse(any(e['source_effect'] == 'SOURCE_PUBLICATION' for e in status_events(events)))

    def test_cancellation_before_stage_tail_retains_pending_request(self):
        backend, owner, clock, events, calls = fixture()
        clock.cancelled = True
        with self.assertRaises(StageExecutionCancelled):
            backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
        self.assertTrue(backend.get_software_state()['DPS'][4])
        self.assertFalse(backend.get_software_state()['EPS'][14])

    def test_cancellation_after_source_tail_does_not_rollback_reached_literals(self):
        backend, owner, clock, events, calls = fixture()
        def observe(event):
            if (event.get('kind') == 'SOFTWARE_STATE_NOT_MEASUREMENT'
                    and event['software_state']['EPS'][14]):
                clock.cancelled = True
        backend.set_execution_observer(observe)
        backend._execution_scheduler.clock = clock.now
        with self.assertRaises(StageExecutionCancelled):
            backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
        state = backend.get_software_state()
        # The model's actual schedule writes DPS before EPS in this source
        # frame. Cancellation after EPS must not invent rollback or reassert
        # a request that the reached source tail already cleared.
        self.assertTrue(state['EPS'][14])
        self.assertFalse(state['DPS'][4])

    def test_general_stop_does_not_clear_an_unreached_failed_start_request(self):
        backend, owner, clock, events, calls = fixture()
        owner.fail_write = True
        with self.assertRaises(IOError):
            backend.general_start(clock, operator_confirmed=True)
        backend.general_stop(operator_confirmed=True)
        state = backend.get_software_state()
        self.assertTrue(state['DPS'][2])
        self.assertFalse(state['DPS'][3])

    def test_impulsion_stop_preserves_source_eps42_eps55_asymmetry(self):
        backend, owner, clock, events, calls = fixture()
        backend._stage_write_local(44, ((55, True),))
        backend.execute_impulsion('modulator_impulse.start', clock, operator_confirmed=True)
        self.assertTrue(backend.get_software_state()['EPS'][52])
        self.assertFalse(backend.get_software_state()['EPS'][55])
        backend._stage_write_local(44, ((55, True),))
        backend.execute_impulsion('modulator_impulse.stop', clock, operator_confirmed=True)
        state = backend.get_software_state()
        self.assertTrue(state['EPS'][42])
        self.assertTrue(state['EPS'][55])
        self.assertFalse(state['EPS'][52])
        self.assertFalse(state['DPS'][19])

    def test_status_observer_errors_do_not_change_hardware_order_or_nominal_waits(self):
        def run(observe):
            backend, owner, clock, events, calls = fixture(observer=False)
            if observe:
                def fail(event):
                    raise IOError('offline publication subscriber failed')
                backend.set_execution_observer(fail)
                backend._execution_scheduler.clock = clock.now
            backend.execute_stage('chauffage.start', clock, operator_confirmed=True)
            if observe:
                self.assertGreater(backend._software_state_observer_error_count, 0)
            return owner.trace, clock.value, backend.get_software_state()
        original, observed = run(False), run(True)
        self.assertEqual(original[0], observed[0])
        self.assertAlmostEqual(original[1], observed[1])
        self.assertEqual(original[2], observed[2])

    def test_status_observer_cannot_reenter_request_or_procedure(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        owner_ident = threading.current_thread().ident
        called = []
        def observe(event):
            if event.get('kind') == 'SOFTWARE_STATE_NOT_MEASUREMENT':
                called.append(threading.current_thread().ident)
                backend.record_procedure_request('prema.start')
        backend.set_execution_observer(observe)
        backend._stage_write_local(44, ((8, True),))
        self.assertEqual(called, [owner_ident])
        self.assertEqual(owner.trace, [])
        self.assertFalse(backend.get_software_state()['DPS'][6])
        self.assertEqual(backend._software_state_observer_error_count, 1)

    def test_ram_status_observer_cannot_trigger_ni_input_reads(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        def observe(event):
            if event.get('kind') == 'SOFTWARE_STATE_NOT_MEASUREMENT':
                backend.read_snapshot(clock)
        backend.set_execution_observer(observe)
        backend._stage_write_local(44, ((8, True),))
        self.assertEqual(owner.trace, [])
        self.assertEqual(backend._software_state_observer_error_count, 1)
        self.assertIn('cannot read NI', backend._software_state_observer_error)

    def test_pinned_catalog_agrees_with_source_status_fields(self):
        model = load_model()
        for operation, (uid, assignments, request_field) in SOURCE_STATUS.items():
            effects = [effect for frame_uid, entries in model.plan(operation)
                       for effect in entries if frame_uid == uid and effect[0] == 'write']
            actual = {effect[1]: dict(effect[2]) for effect in effects}
            self.assertEqual(actual.get(44, {}), assignments, operation)
            self.assertEqual(actual[36], {request_field: False}, operation)
            self.assertEqual(PROCEDURE_DPS_REQUESTS[operation], request_field)
        self.assertEqual(CATALOG_SHA256, 'a9d821e7519ea50f6b35593e58c78129ec7d8a7bfedcc06098e247bef011a0b0')


class ExecutionReadDeadlineTests(unittest.TestCase):
    def test_budget_is_aggregate_and_regular_reads_keep_original_timeout(self):
        backend, owner, clock, events, calls = fixture()
        self.assertAlmostEqual(backend.execution_sample_budget_seconds(), 3.05)
        owner.trace[:] = []
        with patch.object(module.time, 'monotonic', clock.now):
            sample = backend.read_snapshot(clock)
        reads = [row for row in owner.trace if row[0] in ('ai_read', 'di_read')]
        self.assertEqual(len(reads), 6)
        self.assertTrue(all(row[2] == .5 for row in reads))
        self.assertEqual(len(sample['banks']), 6)

    def test_execution_reads_share_one_deadline_and_keep_same_owner(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        with patch.object(module.time, 'monotonic', clock.now):
            sample = backend.read_snapshot_for_execution(clock, .3)
        self.assertEqual(len(sample['banks']), 6)
        reads = [row for row in owner.trace if row[0] in ('ai_read', 'di_read')]
        self.assertEqual(len(reads), 6)
        for index, row in enumerate(reads):
            self.assertLessEqual(row[2], (.3 - row[3]) / (6 - index) + 1e-12)
        self.assertAlmostEqual(reads[0][2], .05)
        self.assertFalse(any(row[0] in ('do', 'counter_start', 'counter_stop') for row in owner.trace))

    def test_expired_deadline_does_not_start_another_card(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        with patch.object(module.time, 'monotonic', clock.now):
            with self.assertRaises(TimeoutError):
                backend.read_snapshot_for_execution(clock, 0.)
        self.assertEqual(owner.trace, [])

    def test_start_overrun_discards_sample_and_still_stops_started_ai(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        owner.start_duration = .4
        with patch.object(module.time, 'monotonic', clock.now):
            with self.assertRaises(TimeoutError):
                backend.read_snapshot_for_execution(clock, .3)
        self.assertEqual([row[0] for row in owner.trace], ['ai_start', 'ai_stop'])

    def test_last_read_overrun_is_not_published_as_success(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        owner.late_read = DI_BANKS[-1][0]
        with patch.object(module.time, 'monotonic', clock.now):
            with self.assertRaises(TimeoutError):
                backend.read_snapshot_for_execution(clock, .3)
        self.assertEqual(len([row for row in owner.trace if row[0] in ('ai_read', 'di_read')]), 6)

    def test_native_read_error_never_skips_ai_stop(self):
        backend, owner, clock, events, calls = fixture()
        owner.trace[:] = []
        owner.fail_analog = True
        with patch.object(module.time, 'monotonic', clock.now):
            with self.assertRaises(IOError):
                backend.read_snapshot_for_execution(clock, .3)
        self.assertEqual([row[0] for row in owner.trace], ['ai_start', 'ai_read', 'ai_stop'])


if __name__ == '__main__':
    unittest.main()
