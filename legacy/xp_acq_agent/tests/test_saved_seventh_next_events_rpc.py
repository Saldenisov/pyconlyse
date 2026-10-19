"""G68 signed inert replay: exact pulse wires and repeated loop boundary UIDs."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from seventh_next_event_fixtures import acq_payload, sup_payload
from sup_event_18780_fixtures import full_payload as complete_sup_payload
from elyse_agent.saved_sup_event_18780 import replay_saved_sup_event_18780


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Pure replay accessed live runtime: ' + name)


class SavedSeventhNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G68-software-only-stateless-test-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        body = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=timestamp,
            nonce=nonce, signature=request_mac(self.key, 'RPC/' + method, path, timestamp, nonce, body))

    def dispatch(self, path, payload, status=200):
        request = self.request(path, payload)
        response = self.endpoint.dispatch(request)
        self.assertEqual(response['status'], status)
        self.assertFalse(response['body']['execution_allowed'])
        self.assertFalse(response['body']['hardware_writes'])
        self.assertEqual(response['body']['physical_status'], 'NOT_EXECUTED')
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST', path,
            request['nonce'], status, json_bytes(response['body'])))
        return response['body'].get('result')

    def test_acq_independent_pulse_snapshots_and_actual_two_wait_inputs(self):
        p = acq_payload()
        p['snapshots']['33106'][3] = True
        p['snapshots']['33201'][3] = False
        p['snapshots']['33499'][16] = True
        p['snapshots']['33594'][20] = True
        before = copy.deepcopy(p)
        r = self.dispatch('/v1/replay/acquisition-event-31552', p)
        writes = {x['node_uid']: x['value'] for x in r['writes']}
        calls = {x['node_uid']: x['input_ports'] for x in r['leaf_calls']}
        self.assertEqual((writes['33041'][20], writes['33185'][20]), (True, False))
        self.assertEqual((writes['33041'][3], writes['33185'][3]), (True, False))
        self.assertTrue(writes['33124'])
        self.assertFalse(writes['33392'][16])
        self.assertTrue(calls['33509']['33568'][16])
        self.assertTrue(calls['33600']['33614'][20])
        self.assertEqual((calls['33144']['33149'], calls['33985']['34152']), (150, 100))
        self.assertEqual(r['completed_stages'], ['32931','33169','33217','33438','33886'])
        self.assertTrue(r['selected_body_completed'])
        for flag in ('whole_event_equivalence', 'snapshot_equality_qualified',
                     'wait_units_or_pulse_duration_qualified', 'native_tunnel_forwarding_qualified'):
            # Native tunnel forwarding is flagged on each transfer, not invented globally.
            if flag in r: self.assertFalse(r[flag])
        self.assertEqual(p, before)

    def test_acq_returned_errors_route_without_success_gate(self):
        p = acq_payload()
        r = self.dispatch('/v1/replay/acquisition-event-31552', p)
        calls = {x['node_uid']: x['input_ports'] for x in r['leaf_calls']}
        for consumer, face, producer, output in (
            ('33577','33585','33509','33564'), ('33600','33608','33577','33588'),
            ('33617','33845','33600','33611')):
            self.assertEqual(calls[consumer][face], p['leaf_returns'][producer][output])
            self.assertTrue(calls[consumer][face]['status'])
        self.assertEqual(calls['33509']['33561'], p['unwired_inputs']['33561'])

    def test_acq_first_wait_pending_prevents_next_stage(self):
        p = acq_payload()
        end = p['schedule'].index(dict(kind='leaf_call', uid='33144')) + 1
        p['schedule'] = p['schedule'][:end]
        r = self.dispatch('/v1/replay/acquisition-event-31552', p)
        self.assertEqual(r['pending_leaf_uids'], ['33144'])
        self.assertEqual(r['active_stage'], '32931')
        self.assertEqual(r['completed_stages'], [])
        self.assertFalse(r['selected_body_completed'])
        p['schedule'].append(dict(kind='stage_complete', uid='32931'))
        self.dispatch('/v1/replay/acquisition-event-31552', p, 400)

    def test_acq_false_arm_never_reads_boundaries(self):
        p = acq_payload(False)
        for name in ('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):
            p[name] = None
        r = self.dispatch('/v1/replay/acquisition-event-31552', p)
        self.assertEqual((r['writes'],r['leaf_calls']), ([],[]))

    def test_sup_actual_33_differences_and_independent_page_snapshots(self):
        p = sup_payload()
        before = copy.deepcopy(p)
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        self.assertEqual(r['iteration_count'], 33)
        self.assertEqual([x['index'] for x in r['iterations'] if x['changed']], [0,7,32])
        self.assertEqual([r['iterations'][i]['increment'] for i in (0,7,32)], [1,8,33])
        self.assertEqual([r['differences'][i] for i in (0,7,32)], [0.5]*3)
        writes = [x for x in r['local_assignments'] if x['node_uid']=='35923']
        for row in writes:
            i = row['loop_iteration']
            self.assertEqual(row['data'][:32], p['local_reads']['19774'][i][:32])
            self.assertEqual(row['data'][32], float(i+1))
        co = [x for x in r['local_assignments'] if x['node_uid']=='21948']
        self.assertEqual([x['data'] for x in co], [0,7,32])
        self.assertEqual(p, before)

    def test_sup_loop_output_and_final_read_remain_independent(self):
        p = sup_payload()
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        self.assertNotEqual(r['loop_error_candidate'], r['supplied_loop_error_output'])
        self.assertFalse(r['loop_error_candidate_is_native_projection'])
        leaves = {(x['node_uid'],x['loop_iteration']):x for x in r['leaf_observations']}
        self.assertEqual(leaves[('40236',None)]['inputs']['40252'], p['intrinsic_outputs']['29296'])
        self.assertEqual(next(x for x in r['index_projections'] if x['node_uid']=='40313')['index'], 4)
        self.assertEqual([x['loop_iteration'] for x in r['local_reads'] if x['node_uid']=='19774'], [0,7,32])

    def test_sup_native_properties_variant_and_format_are_supplied_leaves(self):
        p = sup_payload()
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        leaves = {(x['node_uid'],x['loop_iteration']):x for x in r['leaf_observations']}
        self.assertEqual(leaves[('41806',7)]['inputs']['41817'], {'control':7})
        self.assertEqual(leaves[('62591',None)]['inputs']['62630'], {'opaque_variant':1})
        self.assertEqual(leaves[('62591',None)]['inputs']['62638'], 2.0)
        self.assertEqual(r['formatted_string_hex'], '5300FF')
        self.assertEqual(r['returned_error'], p['final_returns']['22086']['53679'])
        self.assertTrue(r['message_hex'].endswith('FF0041'))
        for flag in ('native_formatting_qualified','native_variant_conversion_qualified',
                     'native_literal_storage_decode_qualified','native_loop_output_policy_qualified',
                     'native_error_selector_projection_qualified','control_reference_constants_are_local_bank_reads'):
            self.assertFalse(r[flag])

    def test_sup_comparison_literal_and_error_selector_are_explicit_hypotheses(self):
        p = complete_sup_payload()
        p['literal_inputs']['49984'] = 0.5
        p['completed_sinks'] = None
        p['intrinsic_outputs']['20154'] = False
        r = replay_saved_sup_event_18780(p)
        self.assertEqual(sum(x['changed'] for x in r['iterations']), 30)
        self.assertFalse(r['error_case_selector'])
        # This accepted pure trace exceeds the existing signed response cap.
        request = self.request('/v1/replay/supervision-event-18780', p)
        response = self.endpoint.dispatch(request)
        self.assertEqual(response['status'], 400)
        self.assertEqual(response['body']['error'], 'Supervision response exceeds 65536 bytes')
        self.assertFalse(response['body']['execution_allowed'])
        self.assertFalse(response['body']['hardware_writes'])
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST',
            request['path'], request['nonce'], 400, json_bytes(response['body'])))
        # A bounded three-iteration envelope admits the hypothetical selector.
        p = sup_payload()
        p['intrinsic_outputs']['20154'] = False
        p['completed_sinks'] = None
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        self.assertTrue(r['returned_error']['status'])
        self.assertFalse(r['error_case_selector'])
        self.assertEqual(next(x['data'] for x in r['local_assignments'] if x['node_uid']=='22126'), {'bytes_hex':'5300FF'})
        self.assertFalse(r['native_false_case_default_qualified'])

    def test_sup_busy_arm_never_decodes_unselected_loop_native_values(self):
        p = sup_payload()
        p['local_reads']['19687'][28] = True
        p['completed_sinks'] = None
        for name in ('loop_returns','final_returns','wait_return'):
            p[name] = None
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        self.assertTrue(r['dps_any'])
        self.assertEqual((r['iteration_count'],r['local_assignments'],r['leaf_observations']), (0,[],[]))

    def test_sup_pair_observations_are_not_native_feasible_schedules(self):
        p = sup_payload()
        p['completed_sinks'] = [['20132',32],['20132',0]]
        r = self.dispatch('/v1/replay/supervision-event-18780', p)
        self.assertEqual(r['completed_sinks'], p['completed_sinks'])
        self.assertIn('not_source_feasible_schedule_or_prefix', r['completion_observation_semantics'])
        p['completed_sinks'] = [['20132',1]]
        self.dispatch('/v1/replay/supervision-event-18780', p, 400)

    def test_sup_unqualified_domains_refuse(self):
        for mutation in ('shape','integer','overflow','reference_index','missing_intrinsic','missing_literal','selector'):
            p = sup_payload()
            if mutation=='shape': p['event_returns']['19499']['19675'].pop()
            elif mutation=='integer': p['event_returns']['19499']['19675'][0]=0
            elif mutation=='overflow': p['event_returns']['19499']['19675'][0]=float(2**41)
            elif mutation=='reference_index': p['final_returns']['40236']['40279']=[]
            elif mutation=='missing_intrinsic': p['intrinsic_outputs'].pop('29296')
            elif mutation=='missing_literal': p['literal_inputs'].pop('49984')
            else: p['intrinsic_outputs']['20154']=1
            self.dispatch('/v1/replay/supervision-event-18780', p, 400)

    def test_authentication_nonce_method_and_exact_version(self):
        for path, fixture in (('/v1/replay/acquisition-event-31552',acq_payload),
                              ('/v1/replay/supervision-event-18780',sup_payload)):
            request = self.request(path,fixture()); request['signature']='0'*64
            self.assertEqual(self.endpoint.dispatch(request)['status'],401)
            request = self.request(path,fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'],200)
            self.assertEqual(self.endpoint.dispatch(request)['status'],401)
            self.assertEqual(self.endpoint.dispatch(self.request(path,None,'GET'))['status'],404)
            for key,value in (('source_version','0'*64),('frame_uid','31552' if fixture is sup_payload else '18780')):
                p=fixture();p[key]=value;self.dispatch(path,p,400)


if __name__=='__main__':
    unittest.main()
