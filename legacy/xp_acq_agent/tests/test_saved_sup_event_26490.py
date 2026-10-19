import copy
import itertools
import unittest

from elyse_agent.saved_sup_event_26490 import (project_event_26490,
                                             replay_saved_sup_event_26490)
from sup_event_26490_fixtures import full_payload, minimal_payload, sparse_payload


class Unused(object):
    def __iter__(self):
        raise AssertionError('UNUSED_ITERATED')
    def __bool__(self):
        raise AssertionError('UNUSED_BOOL')
    def __getitem__(self, key):
        raise AssertionError('UNUSED_INDEXED')


class SavedSupEvent26490Test(unittest.TestCase):
    def test_direct_three_phases_and_both_explicit_aliases(self):
        for first, last in itertools.product((False, True), repeat=2):
            result = project_event_26490({'20659': first, '21637': last})
            self.assertEqual(result['source_phase_order'], ('20201', '21020', '21238'))
            self.assertEqual([a['value'] for a in result['source_assignments']], [first, last])
            for a in result['source_assignments']:
                self.assertEqual((a['explicit_paramIdx'], a['saved_FP_bank_uid'],
                                  a['control_terminal_uid']), (132, '19944', '19961'))
            self.assertEqual(result['wait_observation']['provided_data_U32_input'], 200)

    def test_unused_opaque_objects_preserve_identity(self):
        wait, event = Unused(), Unused()
        result = project_event_26490({'20659': True, '21637': False}, wait, event)
        self.assertIs(result['wait_observation']['supplied_unused_return'], wait)
        self.assertIs(result['supplied_unused_event_outputs'], event)

    def test_completion_reports_not_execution_trace(self):
        result = project_event_26490({'20659': False, '21637': True},
                                    completed_sinks=('21619', '19732'))
        self.assertEqual(result['completed_sinks'], ('21619', '19732'))
        self.assertIs(result['completion_observations_are_feasible_trace'], False)
        self.assertIs(result['completion_observations_prove_success'], False)

    def test_three_portable_examples(self):
        for factory in (full_payload, minimal_payload, sparse_payload):
            value = factory(); before = copy.deepcopy(value)
            result = replay_saved_sup_event_26490(value)
            self.assertEqual(value, before)
            self.assertEqual(result['frame_uid'], '26490')
            self.assertIs(result['whole_event_equivalence'], False)

    def test_literal_domain_refusal(self):
        for invalid in (None, {}, {'20659': True}, {'20659': True, '21637': 0},
                        {'20659': 1, '21637': False}, {'20659': True, '21637': False, 'x': True}):
            with self.assertRaises(ValueError):
                project_event_26490(invalid)

    def test_completion_domain_refusal(self):
        for invalid in (None, '19732', ['19732', '19732'], ['19749'], [1], ['UNKNOWN']):
            with self.assertRaises(ValueError):
                project_event_26490({'20659': True, '21637': False}, completed_sinks=invalid)

    def test_exact_source_guard(self):
        for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
            value = minimal_payload(); value[key] = 'WRONG'
            with self.assertRaises(ValueError):
                replay_saved_sup_event_26490(value)

    def test_boundaries_false_and_exact(self):
        value = minimal_payload(); value['unqualified_boundaries']['whole_event_equivalence'] = 0
        with self.assertRaises(ValueError):
            replay_saved_sup_event_26490(value)
        value = minimal_payload(); value['unqualified_boundaries']['unknown'] = False
        with self.assertRaises(ValueError):
            replay_saved_sup_event_26490(value)

    def test_transport_domains(self):
        for invalid in (float('nan'), float('inf'), 2**53, 'X'*4097, [0]*65, object()):
            value = minimal_payload(); value['wait_return'] = invalid
            with self.assertRaises(ValueError):
                replay_saved_sup_event_26490(value)


if __name__ == '__main__':
    unittest.main()
