import copy
import unittest
from elyse_agent import saved_sup_event_23770 as k
from sup_event_23770_fixtures import full_payload, minimal_payload, sparse_payload, pure_arguments


class Tripwire(object):
    def __getitem__(self, key): raise AssertionError('UNUSED_ACCESSED')
    def __iter__(self): raise AssertionError('UNUSED_ACCESSED')
    def __bool__(self): raise AssertionError('UNUSED_ACCESSED')


class SavedSUP23770Tests(unittest.TestCase):
    def test_three_portable_examples(self):
        for factory in (full_payload, minimal_payload, sparse_payload):
            p = factory(); before = copy.deepcopy(p)
            self.assertEqual(k.replay_saved_sup_event_23770(p), k._encode(k.project_event_23770(**pure_arguments(k, p))))
            self.assertEqual(p, before)

    def test_independent_carriers_and_exact_field(self):
        a = pure_arguments(k, full_payload()); r = k.project_event_23770(**a)
        calls = {row['node_uid']: row for row in r['leaf_observations']}
        for index, read, writer, face in ((0, '78286', '78302', '78395'), (1, '78515', '78531', '78545')):
            value = r['local_assignments'][index]['value']
            self.assertIs(value, calls[writer]['inputs'][face])
            self.assertEqual(value[24], a['literal_inputs']['78270' if index == 0 else '78499'])
            for i in range(40):
                if i != 24: self.assertIs(value[i], a['local_reads'][read][i])
        self.assertNotEqual(r['local_assignments'][0]['value'], r['local_assignments'][1]['value'])
        self.assertEqual([u['raw_flattened_field_index'] for u in r['field_updates']], [24, 24])

    def test_faulted_writers_do_not_gate_given_projection(self):
        a = pure_arguments(k, full_payload()); r = k.project_event_23770(**a)
        calls = {row['node_uid']: row for row in r['leaf_observations']}
        self.assertIs(calls['78398']['inputs']['78428'], a['native_boundaries']['78302']['outputs']['78392'])
        self.assertIs(calls['78548']['inputs']['78600'], a['native_boundaries']['78531']['outputs']['78542'])
        self.assertEqual(len(r['local_assignments']), 5)
        self.assertEqual(calls['78464']['inputs'], {'78469': 500})

    def test_three_distinct_reset_targets(self):
        a = pure_arguments(k, sparse_payload()); r = k.project_event_23770(**a)
        self.assertEqual([(x['node_uid'], x['explicit_paramIdx'], x['value']) for x in r['local_assignments'][2:]],
                         [('82122', 156, True), ('15517', 10, True), ('82078', 7, True)])

    def test_false_nonaccess_and_unused_outputs(self):
        trap = Tripwire()
        r = k.project_event_23770(False, trap, trap, trap, trap, trap, event_outputs=trap)
        self.assertEqual(r['leaf_observations'], [])
        self.assertIs(r['supplied_unused_event_outputs'], trap)
        a = pure_arguments(k, full_payload())
        for uid in ('78398', '78464', '78548'): a['native_boundaries'][uid]['outputs'] = trap
        r = k.project_event_23770(**a)
        for row in r['leaf_observations']:
            if row['node_uid'] in ('78398', '78464', '78548'): self.assertIs(row['supplied_outputs'], trap)

    def test_explicit_defaults_are_required(self):
        for uid in k.UNWIRED:
            p = full_payload(); del p['unwired_inputs'][uid]
            self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)

    def test_strict_domain_and_identity(self):
        for value in (None, 0, 1, 'true'):
            p = full_payload(); p['new_value'] = value
            self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)
        for read in ('78286', '78515'):
            for value in ([True] * 39, [False] * 41, [0] * 40):
                p = full_payload(); p['local_reads'][read] = value
                self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)
        p = full_payload(); p['source_version'] = k.ORIGINAL_SHA256
        self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)

    def test_stored_uri_and_reference_identity(self):
        a = pure_arguments(k, full_payload()); r = k.project_event_23770(**a)
        calls = {row['node_uid']: row for row in r['leaf_observations']}
        self.assertIs(calls['78302']['inputs']['78304'], a['reference_bindings']['78252']['native_reference'])
        self.assertIs(calls['78531']['inputs']['78533'], a['reference_bindings']['78481']['native_reference'])
        p = full_payload(); p['reference_bindings']['78252']['stored_URI_bytes']['bytes_hex'] += '00'
        self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)

    def test_completion_reports_are_not_source_traces(self):
        p = full_payload(); p['completed_sinks'] = ['78548']
        r = k.replay_saved_sup_event_23770(p)
        self.assertEqual(r['completed_sinks'], ['78548'])
        self.assertIs(r['completion_observations_are_feasible_trace'], False)
        for report in (['78302', '78302'], ['78646']):
            p['completed_sinks'] = report
            self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)

    def test_raw_byte_and_transport_boundaries(self):
        p = full_payload(); p['unwired_inputs']['78413'] = {'bytes_hex': '00FF' * 2048}
        self.assertEqual(k.replay_saved_sup_event_23770(p)['leaf_observations'][1]['inputs']['78413'], {'bytes_hex': '00FF' * 2048})
        p['unwired_inputs']['78413']['bytes_hex'] += '00'
        self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)
        p = full_payload(); p['event_outputs'] = float('nan')
        self.assertRaises(ValueError, k.replay_saved_sup_event_23770, p)


if __name__ == '__main__': unittest.main()
