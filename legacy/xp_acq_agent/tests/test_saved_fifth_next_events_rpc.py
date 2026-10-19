"""G66 original body facets through signed stateless software replay."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from fifth_next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Pure replay accessed live runtime: ' + name)


class SavedFifthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G66-software-only-stateless-test-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        body = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=timestamp,
            nonce=nonce, signature=request_mac(self.key, 'RPC/' + method, path,
                timestamp, nonce, body))

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

    def test_acq_three_distinct_publication_reads_and_error_chain(self):
        payload = acq_payload()
        payload['snapshots']['35802'][13] = True
        payload['snapshots']['35878'][13] = True
        payload['snapshots']['35778'][39] = False
        payload['snapshots']['49466'][39] = False
        payload['snapshots']['34377'][29] = False
        payload['snapshots']['52019'][29] = False
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-34191', payload)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertTrue(writes['34333'][29])
        self.assertTrue(writes['34383'])
        self.assertEqual((writes['35744'][42], writes['35744'][39]), (False, True))
        self.assertFalse(writes['35784'][13])
        self.assertTrue(calls['35884']['35898'][13])
        self.assertFalse(calls['49501']['49515'][39])
        self.assertFalse(calls['52054']['52068'][29])
        for consumer, port, producer, returned in (
            ('49501', '49509', '35884', '35895'),
            ('52054', '52062', '49501', '49512'),
            ('52071', '52101', '52054', '52065')):
            self.assertEqual(calls[consumer][port], payload['leaf_returns'][producer][returned])
        self.assertEqual(calls['35870']['35875'], 100)
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['native_callee_equivalence'])
        self.assertFalse(result['snapshot_equality_qualified'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_arm_and_pending_leaf_do_not_invent_native_completion(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-34191', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        stop = next(i + 1 for i, token in enumerate(payload['schedule'])
                    if token == dict(kind='leaf_call', uid='35884'))
        payload['schedule'] = payload['schedule'][:stop]
        result = self.dispatch('/v1/replay/acquisition-event-34191', payload)
        self.assertEqual(result['pending_leaf_uids'], ['35884'])
        self.assertFalse(result['selected_body_completed'])

    def test_sup_duplicate_raw_index_and_independent_newval_carrier(self):
        payload = sup_payload()
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/supervision-event-38030', payload)
        self.assertEqual(result['request_mask'], 4)
        self.assertAlmostEqual(result['arithmetic_by_uid']['10570']['value'], 30.9, places=12)
        page = result['local_assignments']['45062']['data']
        self.assertEqual(page[21], result['arithmetic_by_uid']['10570']['value'])
        self.assertFalse(page[6])
        self.assertTrue(page[7])
        self.assertEqual(page[3], payload['local_reads']['45088'][3])
        raw = [row['raw_flattened_field_index'] for row in result['field_updates']
               if row['node_uid'] == '45095']
        self.assertEqual(raw, [28, 13, 13, 26, 27])
        self.assertEqual(result['writer_call']['data'][2], page[21])
        self.assertEqual(result['wait_call']['milliseconds'], 123)
        self.assertEqual(result['returned_error'], payload['native_returns']['44982']['45013'])
        self.assertEqual(result['error_text_hex'], result['error_prefix_hex'] + '00505350FF')
        self.assertEqual(result['local_assignments']['38326']['data']['bytes_hex'], result['error_text_hex'])
        self.assertEqual(result['completed_sinks'], ['44959', '38326'])
        self.assertFalse(result['native_error_selector_projection_qualified'])
        self.assertFalse(result['multi_request_mask_default_qualified'])
        self.assertFalse(result['writer_success_gates_local_assignment'])
        self.assertEqual(payload, before)

    def test_sup_four_saved_request_paths_and_composite_masks_refused(self):
        for index, primitive, page_write, c8_write, field, sign in (
            (7, '39304', '10163', '26383', 4, -1),
            (6, '13520', '43029', '42984', 4, 1),
            (20, '10570', '45062', '44959', 21, -1),
            (19, '19403', '48863', '48829', 21, 1)):
            payload = sup_payload()
            values = payload['event_returns']['38049']['38074']
            for request in (7, 6, 20, 19):
                values[request] = request == index
            payload['completed_sinks'] = None
            result = self.dispatch('/v1/replay/supervision-event-38030', payload)
            value = values[field] + sign * .1
            self.assertAlmostEqual(result['arithmetic_by_uid'][primitive]['value'], value, places=12)
            self.assertEqual(result['local_assignments'][page_write]['data'][field], value)
            self.assertEqual(result['writer_call']['data'], result['local_assignments'][c8_write]['data'])
        payload = sup_payload()
        payload['event_returns']['38049']['38074'][7] = True
        self.dispatch('/v1/replay/supervision-event-38030', payload, 400)

    def test_sup_error_selector_is_supplied_boundary_and_bytes_remain_exact(self):
        payload = sup_payload()
        payload['native_returns']['44982']['45013'] = dict(status=False, code=-77, source_hex='00E9B0FF')
        payload['completed_sinks'] = None
        result = self.dispatch('/v1/replay/supervision-event-38030', payload)
        self.assertFalse(result['returned_error']['status'])
        self.assertTrue(result['error_case_selector'])
        self.assertTrue(result['error_text_hex'].endswith('00E9B0FF'))
        self.assertIn('not_feasible_trace_or_prefix', result['completion_observation_semantics'])
        self.assertIn('do_not_prove_source_realizability', result['selector_boundary_semantics'])
        payload['error_case_selector'] = False
        result = self.dispatch('/v1/replay/supervision-event-38030', payload)
        self.assertIsNone(result['error_text_hex'])
        self.assertNotIn('38326', result['local_assignments'])

    def test_sup_no_request_dps_carrier_and_absent_saved_field_index(self):
        payload = sup_payload()
        newval = payload['event_returns']['38049']['38074']
        for index in (7, 6, 20, 19):
            newval[index] = False
        newval[9], newval[8] = True, False
        payload['completed_sinks'] = None
        payload['error_case_selector'] = False
        result = self.dispatch('/v1/replay/supervision-event-38030', payload)
        self.assertEqual(result['request_mask'], 0)
        self.assertFalse(result['dps_any'])
        dps = result['local_assignments']['38203']['data']
        self.assertEqual(dps[:2], [True, False])
        self.assertEqual(dps[2:], payload['local_reads']['38095'][2:])
        first = result['field_updates'][0]
        self.assertIsNone(first['raw_flattened_field_index'])
        self.assertEqual(first['typed_position_path'], [0])
        self.assertEqual(result['writer_call']['node_uid'], '38229')
        payload['local_reads']['38095'][2] = True
        result = self.dispatch('/v1/replay/supervision-event-38030', payload)
        self.assertTrue(result['dps_any'])
        self.assertEqual(result['local_assignments'], {})
        self.assertIsNone(result['writer_call'])
        self.assertIsNone(result['wait_call'])
        self.assertEqual(result['returned_error'], dict(status=False, code=0, source_hex=''))

    def test_signed_authentication_nonce_method_and_exact_source_version(self):
        for path, fixture in (('/v1/replay/acquisition-event-34191', acq_payload),
                              ('/v1/replay/supervision-event-38030', sup_payload)):
            request = self.request(path, fixture())
            request['signature'] = '0' * 64
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            request = self.request(path, fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)
            for mutation in ('wrong_version', 'missing_version', 'wrong_frame'):
                payload = fixture()
                if mutation == 'wrong_version': payload['source_version'] = '0' * 64
                elif mutation == 'missing_version': payload.pop('source_version')
                else: payload['frame_uid'] = '45123'
                self.dispatch(path, payload, 400)

    def test_replay_storage_shapes_and_hypothetical_boundary_types_required(self):
        payload = acq_payload()
        payload['snapshots']['34377'].pop()
        self.dispatch('/v1/replay/acquisition-event-34191', payload, 400)
        for mutation in ('page_length', 'graph_length', 'nonbool_selector', 'lower_hex', 'duplicate_completion'):
            payload = sup_payload()
            if mutation == 'page_length': payload['local_reads']['45088'].pop()
            elif mutation == 'graph_length': payload['local_reads']['45088'][3].pop()
            elif mutation == 'nonbool_selector': payload['error_case_selector'] = 1
            elif mutation == 'lower_hex': payload['native_returns']['44982']['45013']['source_hex'] = 'ff'
            else: payload['completed_sinks'] = ['44959', '44959']
            self.dispatch('/v1/replay/supervision-event-38030', payload, 400)


if __name__ == '__main__':
    unittest.main()
