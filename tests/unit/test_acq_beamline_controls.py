"""Offline command-source traces and owner failure fences; Python 3.4.

No NI imports, network, native process, XP, VI or HDF5 access. Constants below
pin the reviewed original typed literals/wires, not the captions or inferred
physical meaning. The adapter's full-bank traces prove bounded software intent
only; physical wiring, feedback and native timing still require qualification.
"""
import copy
import json
import subprocess
import sys
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_control.elyse_agent.acquisition_beamline import (
    BEAMLINE_OPERATIONS, SOURCE_VI_SHA256, SOURCE_BDHB_SHA256, SOURCE_PATHS,
    SOURCE_PSP_URI, ACQUISITION_WRITER_PATH, BeamlineExecutionError,
    BeamlineExecutionCancelled, execute_beamline_pulse,
)
from tests.unit.test_acq_stage_status_telemetry import Clock, Owner, Focal


EXPECTED = {
    'faraday_1.en_pulse': (23, 28, .5, '53772', '54575', ('54581', '54873', '54970'),
                         '54669', '54943', '54903', '55252'),
    'faraday_3.en_pulse': (25, 30, .5, '56943', '62574', ('62578', '62813', '62872'),
                         '62647', '62840', '62820', '62956'),
    'laser_mirror.en_pulse': (22, 26, 1., '53656', '77973', ('77981', '81258', '85997'),
                            '53908', '81888', '83199', '86028'),
    'laser_mirror.hors_pulse': (26, 22, 1., '53656', '56518', ('56523', '56742', '56785'),
                              '56584', '56768', '56748', '56849'),
}


class BeamlineOwner(Owner):
    def __init__(self, clock):
        Owner.__init__(self, clock)
        self.c5_calls = 0
        self.fail_c5_calls = set()
        self.writer_threads = []

    def write_digital_bank(self, name, values):
        Owner.write_digital_bank(self, name, values)
        self.writer_threads.append(threading.current_thread().ident)
        if name == 'C5_DIO96_DO':
            self.c5_calls += 1
            if self.c5_calls in self.fail_c5_calls:
                raise IOError('offline C5 callback may have applied')

    def write_analog_logical_bank(self, name, values):
        self.trace.append(('ao', name, tuple(values)))
        if self.fail_analog:
            raise IOError('offline ambiguous C9 command')


def fixture(commissioned=True, initialize=True, profile='legacy_full'):
    clock = Clock()
    owner = BeamlineOwner(clock)
    backend = CardBackend(factory=lambda **kwargs: owner, focal_command=Focal(),
        stop_wait=clock.wait, control_profile=profile, stage_controls_verified=True,
        beamline_controls_verified=commissioned, ht_controls_verified=True,
        counter_controls_verified=True, ht_voltage_controls_verified=True,
        outer_stop_verified=True)
    if initialize:
        backend.initialize(clock, startup_confirmed=True)
    owner.trace[:] = []
    return backend, owner, clock


def c5_trace(owner):
    return [row for row in owner.trace if row[:2] == ('do', 'C5_DIO96_DO')]


def retained_release():
    backend, owner, clock = fixture()
    owner.fail_c5_calls.add(2)
    with unittest.TestCase().assertRaises(BeamlineExecutionError):
        backend.execute_stage('faraday_1.en_pulse', clock, operator_confirmed=True)
    owner.trace[:] = []
    return backend, owner, clock


class SourcePulseTests(unittest.TestCase):
    def test_original_hashes_and_typed_wire_traceback(self):
        self.assertEqual(SOURCE_VI_SHA256,
            'B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B')
        self.assertEqual(SOURCE_BDHB_SHA256,
            'F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7')
        self.assertEqual(SOURCE_PSP_URI, 'ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96')
        self.assertEqual(set(BEAMLINE_OPERATIONS), set(EXPECTED))
        for operation, values in EXPECTED.items():
            source = SOURCE_PATHS[operation]
            keys = ('field', 'opposite_exclusion_field', 'nominal_wait_seconds', 'diagram_uid',
                'sequence_uid', 'frame_uids', 'assertion_writer_uid', 'wait_uid',
                'wait_literal_uid', 'release_writer_uid')
            self.assertEqual(tuple(source[key] for key in keys), values)
        self.assertEqual(ACQUISITION_WRITER_PATH, dict(timeout_reader_uid='25449', timeout_uri_uid='25268',
            local_bank=13, local_writer_uid='25484', runtime_frame_uid='7386',
            runtime_local_reader_uid='2378', cluster_to_array_uid='8127', dio96_call_uid='686',
            helper='1_ACQ_RW_DIO96.vi', helper_c5_write_uid='742'))

    def test_each_source_pulse_full_bank_order_dwell_and_no_status_claim(self):
        for operation, expected in EXPECTED.items():
            backend, owner, clock = fixture()
            before = list(backend.commanded_digital['C5_DIO96_DO'])
            before[7] = not before[7]
            backend.commanded_digital['C5_DIO96_DO'] = tuple(before)
            state = copy.deepcopy(backend.get_software_state())
            publications = backend.stage_publication_count
            frames = []
            def wait(seconds):
                frames.append((backend.procedure['frame'], backend.procedure['source_uid'], seconds))
                owner.trace.append(('wait', seconds))
                return Clock.wait(clock, seconds)
            clock.wait = wait
            report = backend.execute_stage(operation, clock, operator_confirmed=True)
            asserted = list(before)
            asserted[expected[0]] = True
            self.assertEqual(owner.trace, [('do', 'C5_DIO96_DO', tuple(asserted)),
                ('wait', expected[2]), ('do', 'C5_DIO96_DO', tuple(before))])
            self.assertEqual(frames, [(1, expected[5][1], expected[2])])
            self.assertEqual(clock.value, expected[2])
            self.assertEqual(backend.get_software_state(), state)
            self.assertEqual(backend.stage_publication_count, publications)
            self.assertEqual(owner.writer_threads, [threading.current_thread().ident] * 2)
            self.assertIs(report['completed'], True)
            for key in ('hardware_acknowledged', 'position_feedback_qualified',
                        'psp_delivery_acknowledged', 'source_native_timing_equivalence'):
                self.assertIs(report[key], False)
            self.assertEqual(report['physical_position'], 'UNKNOWN')
            self.assertEqual(report['source_path']['field'], expected[0])
            self.assertEqual(backend._stage_snapshot()['last_beamline_command'], report)

    def test_no_unqualified_faraday_direction_or_index_is_admitted(self):
        backend, owner, clock = fixture()
        for operation in ('faraday_1.hors_pulse', 'faraday_2.en_pulse', 'faraday_3.hors_pulse',
                          'faraday_1.open', 'laser_mirror.move', 'laser_mirror.en'):
            self.assertRaises(ValueError, backend.execute_stage, operation, clock, operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_separate_default_disabled_gate_and_exact_flags(self):
        for cls in (CardBackend, DemoBackend):
            self.assertIs(cls().beamline_controls_verified, False)
            for value in (0, 1, None, 'true'):
                self.assertRaises(ValueError, cls, beamline_controls_verified=value)
        backend, owner, clock = fixture(commissioned=False)
        self.assertRaises(RuntimeError, backend.execute_stage, BEAMLINE_OPERATIONS[0], clock,
                          operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_confirmation_initialized_profile_and_stage_gate(self):
        for options in (dict(initialize=False), dict(profile='general_only_test')):
            backend, owner, clock = fixture(**options)
            self.assertRaises(RuntimeError, backend.execute_stage, BEAMLINE_OPERATIONS[0], clock,
                              operator_confirmed=True)
            self.assertEqual(owner.trace, [])
        backend, owner, clock = fixture()
        self.assertRaises(ValueError, backend.execute_stage, BEAMLINE_OPERATIONS[0], clock)
        backend.stage_controls_verified = False
        self.assertRaises(RuntimeError, backend.execute_stage, BEAMLINE_OPERATIONS[0], clock,
                          operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_selected_or_opposite_command_true_is_fail_closed_no_write(self):
        for operation, expected in EXPECTED.items():
            for field in expected[:2]:
                backend, owner, clock = fixture()
                changed = list(backend.commanded_digital['C5_DIO96_DO'])
                changed[field] = True
                backend.commanded_digital['C5_DIO96_DO'] = tuple(changed)
                self.assertRaises(BeamlineExecutionError, backend.execute_stage, operation,
                                  clock, operator_confirmed=True)
                self.assertEqual(owner.trace, [])
                self.assertIsNone(backend._pending_beamline_release)

    def test_false_newvalue_callback_free_and_does_not_drain_retained_release(self):
        backend, owner, clock = retained_release()
        before = copy.deepcopy(backend._pending_beamline_release)
        report = backend.execute_stage(BEAMLINE_OPERATIONS[0], clock,
                                       operator_confirmed=True, new_value=False)
        self.assertEqual(report['status'], 'NOOP')
        self.assertEqual(owner.trace, [])
        self.assertEqual(backend._pending_beamline_release, before)

    def test_partial_assertion_attempts_false_release_without_wait_or_success(self):
        backend, owner, clock = fixture()
        before = backend.commanded_digital['C5_DIO96_DO']
        owner.fail_c5_calls.add(1)
        with self.assertRaises(BeamlineExecutionError) as error:
            backend.execute_stage(BEAMLINE_OPERATIONS[0], clock, operator_confirmed=True)
        self.assertEqual([row[2][23] for row in c5_trace(owner)], [True, False])
        self.assertEqual(clock.value, 0.)
        self.assertEqual(backend.commanded_digital['C5_DIO96_DO'], before)
        self.assertIsNone(backend._pending_beamline_release)
        self.assertIs(error.exception.report['assertion_callback_completed'], False)
        self.assertIs(error.exception.report['release_callback_completed'], True)
        self.assertIs(error.exception.report['completed'], False)

    def test_cancellation_during_wait_always_releases(self):
        backend, owner, clock = fixture()
        def cancel_wait(seconds):
            clock.value += .1
            clock.cancelled = True
        clock.wait = cancel_wait
        with self.assertRaises(BeamlineExecutionCancelled) as error:
            backend.execute_stage(BEAMLINE_OPERATIONS[0], clock, operator_confirmed=True)
        self.assertEqual([row[2][23] for row in c5_trace(owner)], [True, False])
        self.assertIs(error.exception.report['completed'], False)
        self.assertIsNone(backend._pending_beamline_release)

    def test_cancel_before_assert_is_write_free(self):
        backend, owner, clock = fixture()
        clock.cancelled = True
        self.assertRaises(BeamlineExecutionCancelled, backend.execute_stage, BEAMLINE_OPERATIONS[0],
                          clock, operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_wait_failure_always_attempts_release_without_reassertion(self):
        backend, owner, clock = fixture()
        def failed_wait(seconds):
            raise RuntimeError('offline waiter failed')
        clock.wait = failed_wait
        self.assertRaises(BeamlineExecutionError, backend.execute_stage, BEAMLINE_OPERATIONS[0],
                          clock, operator_confirmed=True)
        self.assertEqual([row[2][23] for row in c5_trace(owner)], [True, False])
        self.assertIsNone(backend._pending_beamline_release)

    def test_failed_assert_and_release_latch_even_when_last_successful_image_false(self):
        backend, owner, clock = fixture()
        owner.fail_c5_calls.update((1, 2))
        self.assertRaises(BeamlineExecutionError, backend.execute_stage, BEAMLINE_OPERATIONS[0],
                          clock, operator_confirmed=True)
        self.assertIs(backend.commanded_digital['C5_DIO96_DO'][23], False)
        self.assertEqual(backend._pending_beamline_release['field'], 23)
        self.assertEqual(owner.c5_calls, 2)

    def test_unresolved_release_blocks_starts_motion_and_cleanup_without_replay(self):
        backend, owner, clock = retained_release()
        actions = (
            lambda: backend.execute_stage(BEAMLINE_OPERATIONS[2], clock, operator_confirmed=True),
            lambda: backend.general_start(clock, operator_confirmed=True),
            lambda: backend.execute_stage('chauffage.start', clock, operator_confirmed=True),
            lambda: backend.execute_impulsion('modulator_impulse.start', clock, operator_confirmed=True),
            lambda: backend.set_ht_voltage(7., clock, operator_confirmed=True),
            backend.close,
        )
        for action in actions:
            self.assertRaises(RuntimeError, action)
        self.assertEqual(owner.trace, [])
        self.assertIs(backend.owner, owner)
        self.assertEqual(backend._pending_beamline_release['field'], 23)

    def test_pending_c5_does_not_block_reviewed_independent_energy_reducing_stops(self):
        operations = (
            lambda b, c: b.general_stop(operator_confirmed=True),
            lambda b, c: b.execute_stage('alimentation_ht.stop', c, operator_confirmed=True),
            lambda b, c: b.execute_impulsion('modulator_impulse.stop', c, operator_confirmed=True),
            lambda b, c: b.set_ht_voltage(6., c, operator_confirmed=True),
            lambda b, c: b.outer_controlled_stop(operator_confirmed=True),
        )
        for operation in operations:
            backend, owner, clock = retained_release()
            pending = copy.deepcopy(backend._pending_beamline_release)
            operation(backend, clock)
            self.assertTrue(owner.trace)
            self.assertEqual(c5_trace(owner), [])
            self.assertEqual(backend._pending_beamline_release, pending)
            self.assertRaises(RuntimeError, backend.close)
            self.assertNotIn(('close',), owner.trace)

    def test_protective_stop_scope_cannot_write_c5_or_skip_serial_quiescence(self):
        backend, owner, clock = retained_release()
        with backend._energy_reducing_scope('modulator.general.stop'):
            self.assertRaises(RuntimeError, backend._stage_write_digital,
                              'C5_DIO96_DO', [False] * 40)
        self.assertEqual(owner.trace, [])
        def uncertain_serial_worker():
            raise RuntimeError('offline retained serial worker is not quiescent')
        backend.focal_command.ensure_quiescent = uncertain_serial_worker
        self.assertRaises(RuntimeError, backend.general_stop, operator_confirmed=True)
        self.assertEqual(owner.trace, [])
        self.assertIsNotNone(backend._pending_beamline_release)

    def test_no_reentrant_read_other_stage_or_close_during_asserted_pulse(self):
        backend, owner, clock = fixture()
        seen = []
        def wait(seconds):
            for action in (lambda: backend.read_snapshot(clock), backend.close,
                lambda: backend.execute_stage('chauffage.start', clock, operator_confirmed=True),
                lambda: backend.general_stop(operator_confirmed=True)):
                self.assertRaises(RuntimeError, action)
                seen.append(True)
            clock.value += seconds
        clock.wait = wait
        backend.execute_stage(BEAMLINE_OPERATIONS[0], clock, operator_confirmed=True)
        self.assertEqual(len(seen), 4)
        self.assertEqual(len(owner.trace), 2)

    def test_different_thread_cannot_use_pulse_or_retained_protective_stop_scope(self):
        backend, owner, clock = fixture()
        failures = []
        def other():
            try:
                backend.execute_stage(BEAMLINE_OPERATIONS[0], clock, operator_confirmed=True)
            except RuntimeError as error:
                failures.append(str(error))
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        self.assertEqual(len(failures), 1)
        self.assertEqual(owner.trace, [])
        backend, owner, clock = retained_release()
        def stop_other():
            try:
                backend.general_stop(operator_confirmed=True)
            except RuntimeError as error:
                failures.append(str(error))
        thread = threading.Thread(target=stop_other)
        thread.start()
        thread.join()
        self.assertEqual(len(failures), 2)
        self.assertEqual(owner.trace, [])

    def test_execution_observer_is_never_called_as_a_safe_pulse_sampler(self):
        backend, owner, clock = fixture()
        events = []
        backend.set_execution_observer(events.append)
        backend.execute_stage(BEAMLINE_OPERATIONS[0], clock, operator_confirmed=True)
        self.assertEqual(events, [])
        self.assertFalse(any(row[0].startswith('ai_') or row[0] == 'di_read' for row in owner.trace))

    def test_demo_uses_same_command_only_adapter_without_ni_owner(self):
        backend = DemoBackend(stage_controls_verified=True, beamline_controls_verified=True)
        clock = Clock()
        backend.initialize(clock)
        report = backend.execute_stage('laser_mirror.hors_pulse', clock, operator_confirmed=True)
        self.assertEqual(clock.value, 1.)
        self.assertEqual(backend.resource_count, 0)
        self.assertIs(report['hardware_acknowledged'], False)
        self.assertIs(report['simulated'], True)
        self.assertIs(backend._stage_snapshot()['beamline_position_feedback_qualified'], False)

    def test_observer_failure_cannot_suppress_selected_false_release(self):
        state, writes = [tuple([False] * 40)], []
        def commit(index, value):
            changed = list(state[0])
            changed[index] = value
            state[0] = tuple(changed)
            writes.append((index, value))
        def observe(frame, uid):
            if frame == 2:
                raise RuntimeError('offline observer fault at release')
        self.assertRaises(BeamlineExecutionError, execute_beamline_pulse, BEAMLINE_OPERATIONS[0],
            lambda: state[0], commit, lambda seconds: None, lambda: False, observe)
        self.assertEqual(writes, [(23, True), (23, False)])

    def test_cold_import_has_no_native_driver_import(self):
        script = ('import sys; from legacy.xp_acq_control.elyse_agent import acquisition_beamline; '
                  'from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend; '
                  'b=CardBackend(); assert b.resource_count == 0; '
                  'assert "nidaqmx" not in sys.modules; print("COLD_NO_NI_IMPORT")')
        output = subprocess.check_output([sys.executable, '-c', script])
        self.assertIn(b'COLD_NO_NI_IMPORT', output)


class HTSoftwareSequenceTests(unittest.TestCase):
    def test_cold_partial_and_ambiguous_commands_are_unknown_without_io(self):
        backend, owner, clock = fixture(initialize=False)
        self.assertIs(backend.ht_sequence_state['command_known'], False)
        self.assertEqual(owner.trace, [])
        backend.initialize(clock, startup_confirmed=True)
        owner.trace[:] = []
        self.assertIs(backend.ht_sequence_state['command_known'], True)
        backend.ht_command_uncertain = True
        self.assertIs(backend.ht_sequence_state['command_known'], False)
        self.assertEqual(owner.trace, [])

    def test_eps_alone_does_not_fake_successful_supply_or_counter_callback(self):
        backend, owner, clock = fixture()
        backend._stage_write_local(44, ((45, True), (52, True)))
        sequence = backend.ht_sequence_state
        self.assertIs(sequence['supply_sequence_completed'], False)
        self.assertIs(sequence['pulses_sequence_completed'], False)
        self.assertRaises(RuntimeError, backend.set_ht_voltage, 7., clock, operator_confirmed=True)
        self.assertEqual(owner.trace, [])

    def test_supply_then_pulses_qualify_increase_only_as_software_order(self):
        backend, owner, clock = fixture()
        self.assertRaises(RuntimeError, backend.set_ht_voltage, 7., clock, operator_confirmed=True)
        backend.execute_stage('alimentation_ht.start', clock, operator_confirmed=True)
        self.assertIs(backend.ht_sequence_state['supply_sequence_completed'], True)
        self.assertRaises(RuntimeError, backend.set_ht_voltage, 7., clock, operator_confirmed=True)
        backend.execute_impulsion('modulator_impulse.start', clock, operator_confirmed=True)
        self.assertIs(backend.ht_sequence_state['pulses_sequence_completed'], True)
        owner.trace[:] = []
        report = backend.set_ht_voltage(7., clock, operator_confirmed=True)
        self.assertIs(report['hardware_acknowledged'], False)
        self.assertEqual([row[:2] for row in owner.trace], [('ao', 'C9NI6703')])
        self.assertEqual(backend.ht_sequence_state['current_command_kv'], 7.)
        backend.execute_impulsion('modulator_impulse.stop', clock, operator_confirmed=True)
        self.assertIs(backend.ht_sequence_state['pulses_sequence_completed'], False)
        self.assertRaises(RuntimeError, backend.set_ht_voltage, 8., clock, operator_confirmed=True)

    def test_nonincreasing_ht_remains_available_without_start_flags(self):
        backend, owner, clock = fixture()
        self.assertIs(backend.ht_sequence_state['supply_sequence_completed'], False)
        backend.set_ht_voltage(6., clock, operator_confirmed=True)
        backend.set_ht_voltage(6., clock, operator_confirmed=True)
        self.assertEqual(len(owner.trace), 2)
        self.assertEqual(backend.commanded_analog['C9NI6703'][0], 6.)

    def test_failed_source_callback_invalidates_retained_order_without_repairing_eps(self):
        backend, owner, clock = fixture()
        backend.execute_stage('alimentation_ht.start', clock, operator_confirmed=True)
        backend.execute_impulsion('modulator_impulse.start', clock, operator_confirmed=True)
        owner.fail_write = True
        self.assertRaises(Exception, backend.execute_stage, 'relays_ht.start', clock, operator_confirmed=True)
        self.assertIs(backend.get_software_state()['EPS'][45], True)
        self.assertIs(backend.ht_sequence_state['supply_sequence_completed'], False)
        self.assertIs(backend.ht_sequence_state['pulses_sequence_completed'], False)


if __name__ == '__main__':
    unittest.main()
