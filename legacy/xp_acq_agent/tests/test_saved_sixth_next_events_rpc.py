"""G67 signed software replay: actual new fields and explicit open boundaries."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from sixth_next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Pure replay accessed live runtime: ' + name)


class SavedSixthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G67-software-only-stateless-test-key'
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

    def test_acq_new_literal_values_and_separate_publication_reads(self):
        payload = acq_payload()
        payload['snapshots']['43757'][29] = True
        payload['snapshots']['44002'][29] = True
        payload['snapshots']['43866'][14] = True
        payload['snapshots']['43956'][14] = True
        payload['snapshots']['43842'][42] = False
        payload['snapshots']['43979'][42] = False
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-43634', payload)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertFalse(writes['43738'][29])
        self.assertTrue(writes['43763'])
        self.assertEqual((writes['43821'][42], writes['43821'][39]), (True, False))
        self.assertFalse(writes['43848'][14])
        self.assertTrue(calls['43962']['43976'][14])
        self.assertFalse(calls['43985']['43999'][42])
        self.assertTrue(calls['44008']['44022'][29])
        self.assertEqual(calls['44107']['44112'], 100)
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['native_callee_equivalence'])
        self.assertFalse(result['snapshot_equality_qualified'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_acq_error_chain_keeps_returned_error_even_after_true_status(self):
        payload = acq_payload()
        result = self.dispatch('/v1/replay/acquisition-event-43634', payload)
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        for consumer, port, producer, returned in (
            ('43985', '43993', '43962', '43973'),
            ('44008', '44016', '43985', '43996'),
            ('44025', '44055', '44008', '44019')):
            self.assertEqual(calls[consumer][port], payload['leaf_returns'][producer][returned])
        self.assertEqual(calls['43962']['43970'], payload['unwired_inputs']['43970'])

    def test_acq_false_and_pending_leaf_have_no_invented_completion(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-43634', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        stop = next(i + 1 for i, token in enumerate(payload['schedule'])
                    if token == dict(kind='leaf_call', uid='43962'))
        payload['schedule'] = payload['schedule'][:stop]
        result = self.dispatch('/v1/replay/acquisition-event-43634', payload)
        self.assertEqual(result['pending_leaf_uids'], ['43962'])
        self.assertFalse(result['selected_body_completed'])

    def test_sup_newval_arithmetic_and_independent_carrier(self):
        payload = sup_payload()
        payload['local_reads']['52907'][4] = 900.0
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertEqual(result['request_mask'], 4)
        self.assertEqual(result['arithmetic_by_uid']['51397']['value'], 11.0)
        coerce = result['range_by_uid']['52918']
        self.assertEqual(coerce['value'], 11.0)
        self.assertFalse(coerce['unused_boolean_output_evaluated'])
        self.assertEqual(coerce['qualification_domain'], 'strict_finite_lower<x<upper')
        page = result['local_assignments']['53024']['data']
        c8 = result['local_assignments']['52850']['data']
        self.assertEqual(page[5], 11.0)
        self.assertEqual(c8[4], 11.0)
        self.assertEqual(c8[:4], payload['local_reads']['52907'][:4])
        self.assertEqual(c8[5:], payload['local_reads']['52907'][5:])
        self.assertEqual(page[12], payload['event_returns']['53735']['53762'][12])
        self.assertEqual(result['writer_call']['data'], c8)
        self.assertEqual(set(result['local_reads']), {'53769', '52907'})
        self.assertEqual(result['wait_call']['milliseconds'], 250)
        self.assertEqual(result['returned_error'], payload['native_returns']['52858']['52870'])
        self.assertTrue(result['error_text_hex'].endswith('00FF'))
        self.assertFalse(result['native_literal_storage_decode_qualified'])
        self.assertFalse(result['native_primitive_semantics_qualified'])
        self.assertFalse(result['writer_success_gates_local_assignment'])
        self.assertEqual(payload, before)

    def test_sup_all_eight_saved_single_request_paths(self):
        # Values/operators/UIDs are source-bound assertions, not imported core tables.
        for mask, request, arith, coerce, page_write, field, expected in (
            (1, 2, '56367', '56435', '58321', 5, 5.0),
            (2, 4, '74075', '74102', '74207', 5, 9.0),
            (4, 3, '51397', '52918', '53024', 5, 11.0),
            (8, 1, '68795', '68568', '68787', 5, 11.0),
            (16, 14, '26839', '58641', '58742', 17, -10.0),
            (32, 16, '59269', '59005', '59254', 17, -1.0),
            (64, 15, '58370', '63106', '63225', 17, 1.0),
            (128, 13, '71649', '71544', '71641', 17, 10.0)):
            payload = sup_payload()
            values = payload['event_returns']['53735']['53762']
            for i in (2, 4, 3, 1, 14, 16, 15, 13):
                values[i] = i == request
            payload['completed_sinks'] = None
            result = self.dispatch('/v1/replay/supervision-event-53716', payload)
            self.assertEqual(result['request_mask'], mask)
            self.assertEqual(result['arithmetic_by_uid'][arith]['value'], expected)
            self.assertEqual(result['range_by_uid'][coerce]['value'], expected)
            self.assertEqual(result['local_assignments'][page_write]['data'][field], expected)

    def test_sup_stored_lower_bound_is_explicit_hypothesis_and_endpoints_refuse(self):
        payload = sup_payload()
        payload['literal_inputs']['58402'] = 2.0
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertEqual(result['range_by_uid']['52918']['input_slots']['2'], 2.0)
        self.assertEqual(result['supplied_literal_observations'], {'58402': 2.0})
        self.assertIn('hypothetical', result['supplied_literal_semantics'])
        for x in (-1.0, 19.0, 20.0):
            payload = sup_payload()
            payload['event_returns']['53735']['53762'][5] = x
            self.dispatch('/v1/replay/supervision-event-53716', payload, 400)
        payload = sup_payload()
        payload['literal_inputs']['58402'] = 12.0
        self.dispatch('/v1/replay/supervision-event-53716', payload, 400)

    def test_sup_dps_paths_have_no_wait_and_supplied_bytes_do_not_decode_empty(self):
        payload = sup_payload()
        values = payload['event_returns']['53735']['53762']
        for i in (2, 4, 3, 1, 14, 16, 15, 13):
            values[i] = False
        values[7], values[6] = True, False
        payload['completed_sinks'] = None
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertEqual(result['request_mask'], 0)
        self.assertEqual(result['writer_call']['node_uid'], '55466')
        self.assertIsNone(result['wait_call'])
        self.assertEqual(result['local_assignments']['55371']['data'][13:15], [True, False])
        payload['local_reads']['53769'][22] = True
        payload['literal_inputs']['55804'] = 'E9B0'
        payload['literal_inputs']['55821'] = dict(status=False, code=-37, source_hex='00FF')
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertIsNone(result['writer_call'])
        self.assertEqual(result['error_text_hex'], 'E9B000FF')
        self.assertEqual(result['returned_error'], payload['literal_inputs']['55821'])
        self.assertEqual(result['supplied_literal_observations']['55804'], {'bytes_hex': 'E9B0'})
        self.assertIn('55821', result['supplied_literal_observations'])
        self.assertFalse(result['native_literal_storage_decode_qualified'])

    def test_sup_error_selector_and_completions_are_hypothetical(self):
        payload = sup_payload()
        payload['native_returns']['52858']['52870'] = dict(status=False, code=-77, source_hex='00E9B0FF')
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertFalse(result['returned_error']['status'])
        self.assertTrue(result['error_case_selector'])
        self.assertTrue(result['error_text_hex'].endswith('00E9B0FF'))
        self.assertFalse(result['native_error_selector_projection_qualified'])
        self.assertIn('not_feasible_trace_or_prefix', result['completion_observation_semantics'])
        payload['error_case_selector'] = False
        result = self.dispatch('/v1/replay/supervision-event-53716', payload)
        self.assertNotIn('58262', result['local_assignments'])
        self.assertIsNone(result['error_text_hex'])

    def test_signed_authentication_nonce_method_and_source_version(self):
        for path, fixture in (('/v1/replay/acquisition-event-43634', acq_payload),
                              ('/v1/replay/supervision-event-53716', sup_payload)):
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
                else: payload['frame_uid'] = '34191'
                self.dispatch(path, payload, 400)

    def test_unresolved_defaults_and_json_policy_fail_closed(self):
        payload = sup_payload()
        payload['event_returns']['53735']['53762'][2] = True
        self.dispatch('/v1/replay/supervision-event-53716', payload, 400)
        for mutation in ('selector', 'completion', 'lower_type', 'page_shape'):
            payload = sup_payload()
            if mutation == 'selector': payload['error_case_selector'] = 1
            elif mutation == 'completion': payload['completed_sinks'] = ['53024', '53024']
            elif mutation == 'lower_type': payload['literal_inputs']['58402'] = 0
            else: payload['event_returns']['53735']['53762'].pop()
            self.dispatch('/v1/replay/supervision-event-53716', payload, 400)
        payload = acq_payload()
        payload['snapshots']['43757'].pop()
        self.dispatch('/v1/replay/acquisition-event-43634', payload, 400)


if __name__ == '__main__':
    unittest.main()
