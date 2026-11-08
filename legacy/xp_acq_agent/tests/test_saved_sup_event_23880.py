"""Fresh bounded source-port/supplied-data tests; no original/native execution."""
import copy
import unittest
from elyse_agent import saved_sup_event_23880 as kernel
from sup_event_23880_fixtures import full_payload, minimal_payload, sparse_payload, pure_arguments


class Tripwire(object):
    def __iter__(self):
        raise AssertionError('Unused source boundary read')

    def __getitem__(self, key):
        raise AssertionError('Unused source boundary read')

    def __bool__(self):
        raise AssertionError('Unused source boundary read')


class SavedSupEvent23880Tests(unittest.TestCase):
    def test_three_portable_examples_same_identity(self):
        for factory in (full_payload, minimal_payload, sparse_payload):
            payload = factory()
            before = copy.deepcopy(payload)
            result = kernel.replay_saved_sup_event_23880(payload)
            self.assertEqual(payload, before)
            self.assertEqual((result['source_id'], result['source_version'], result['event_uid'], result['frame_uid']),
                             ('APP-17', kernel.SOURCE_VERSION, '5909', '23880'))
            self.assertFalse(result['whole_event_equivalence'])

    def test_direct_true_case_error_and_reference_chain_identity(self):
        arguments = pure_arguments(kernel, full_payload())
        result = kernel.project_event_23880(**arguments)
        calls = {row['node_uid']: row['inputs'] for row in result['leaf_observations']}
        native = arguments['native_boundaries']
        for uid, face, producer, output in (
            ('17485', '17519', '17431', '17440'), ('17485', '17528', '17431', '17453'),
            ('17531', '17558', '17485', '17491'), ('17531', '17571', '17485', '17500'),
            ('17574', '17614', '17531', '17534'), ('17574', '17624', '17531', '17543'),
            ('17627', '17654', '17574', '17577'), ('17627', '17663', '17574', '17587'),
            ('28756', '28794', '17627', '17630')):
            self.assertIs(calls[uid][face], native[producer]['outputs'][output])
        self.assertEqual(calls['17431']['17475'], 9600)
        self.assertEqual(calls['17666'], {'17677': 50})
        self.assertEqual(calls['17485']['17525'], arguments['local_reads']['31193'])
        writes = {row['node_uid']: row['value'] for row in result['local_assignments']}
        self.assertIs(writes['30337'], native['17574']['outputs']['17584'])
        self.assertEqual(writes['34747'], native['17531']['outputs']['17540'])
        self.assertTrue(native['17627']['outputs']['17630'].status)
        self.assertEqual(result['selected_case_frame'], '25142')
        self.assertFalse(result['completion_observations_prove_success'])

    def test_false_arm_nonaccess_and_unused_leaf_outputs(self):
        opaque = Tripwire()
        result = kernel.project_event_23880({'25668': False, '17326': opaque, '17367': opaque},
                                            opaque, opaque, opaque, opaque)
        self.assertEqual(result['selected_case_frame'], '25108')
        self.assertEqual(result['leaf_observations'], [])
        self.assertEqual(result['local_assignments'], [])
        self.assertIs(result['supplied_unused_event_outputs'], opaque)
        arguments = pure_arguments(kernel, full_payload())
        arguments['native_boundaries']['28756']['outputs'] = opaque
        arguments['native_boundaries']['17666']['outputs'] = opaque
        arguments['event_outputs'] = opaque
        result = kernel.project_event_23880(**arguments)
        for row in result['leaf_observations']:
            if row['node_uid'] in ('28756', '17666'):
                self.assertIs(row['supplied_outputs'], opaque)

    def test_integer_widening_and_local_return_bounds(self):
        for position in (0, 1, 65535):
            for returned in (-(2 ** 31), 0, 2 ** 31 - 1):
                payload = full_payload()
                payload['local_reads']['31193'] = position
                payload['native_boundaries']['17531']['outputs']['17540'] = returned
                result = kernel.replay_saved_sup_event_23880(payload)
                calls = {row['node_uid']: row['inputs'] for row in result['leaf_observations']}
                self.assertEqual(calls['17485']['17525'], position)
                self.assertEqual(result['local_assignments'][0]['value'], returned)
                self.assertFalse(result['native_coercion_qualified'])
        for bad in (-1, 65536, True, 1.0):
            payload = full_payload()
            payload['local_reads']['31193'] = bad
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)

    def test_explicit_boolean_and_exact_stored_byte_candidate(self):
        for flag in (False, True):
            payload = full_payload()
            payload['literal_inputs']['17326'] = flag
            result = kernel.replay_saved_sup_event_23880(payload)
            self.assertIs(result['leaf_observations'][0]['inputs']['17465'], flag)
        for uid, value in (('25668', 0), ('17326', 0), ('17367', {'bytes_hex': '00'})):
            payload = full_payload()
            payload['literal_inputs'][uid] = value
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)
        payload = full_payload()
        del payload['unwired_inputs']['17471']
        with self.assertRaises(ValueError):
            kernel.replay_saved_sup_event_23880(payload)

    def test_completion_subsets_are_caller_reports(self):
        payload = full_payload()
        payload['completed_sinks'] = ['28756', '17431', '30337']
        result = kernel.replay_saved_sup_event_23880(payload)
        self.assertEqual(result['completed_sinks'], payload['completed_sinks'])
        self.assertFalse(result['completion_observations_are_feasible_trace'])
        for reports in (['17431', '17431'], ['25142'], ['17525']):
            payload = full_payload()
            payload['completed_sinks'] = reports
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)
        payload = minimal_payload()
        payload['completed_sinks'] = ['17431']
        with self.assertRaises(ValueError):
            kernel.replay_saved_sup_event_23880(payload)

    def test_byte_domains_error_fields_and_json_guards(self):
        for raw in ('', '00FF', 'AB' * 4096):
            payload = full_payload()
            payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex': raw}
            result = kernel.replay_saved_sup_event_23880(payload)
            self.assertEqual(result['local_assignments'][1]['value'], {'bytes_hex': raw})
        for raw in ('0', 'ff', 'GG', 'AB' * 4097):
            payload = full_payload()
            payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex': raw}
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)
        payload = full_payload()
        payload['native_boundaries']['17431']['outputs']['17440']['status'] = 0
        with self.assertRaises(ValueError):
            kernel.replay_saved_sup_event_23880(payload)
        payload = full_payload()
        payload['event_outputs'] = float('nan')
        with self.assertRaises(ValueError):
            kernel.replay_saved_sup_event_23880(payload)

    def test_source_and_unqualified_boundary_refusals(self):
        for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
            payload = full_payload()
            payload[key] = 'wrong'
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)
        for key in kernel.UNQUALIFIED_FLAGS:
            payload = full_payload()
            payload['unqualified_boundaries'][key] = True
            with self.assertRaises(ValueError):
                kernel.replay_saved_sup_event_23880(payload)


if __name__ == '__main__':
    unittest.main()
